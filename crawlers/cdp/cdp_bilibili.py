import json
import time
import os
from typing import Any, Dict, List
from playwright.sync_api import sync_playwright

def run_bilibili_cdp():
    print("Connecting to Chrome via CDP on port 9222 for Bilibili...")
    payloads = []
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception as e:
            print(f"Failed to connect to CDP: {e}")
            return
            
        context = browser.contexts[0]
        bili_page = None
        for page in context.pages:
            if "jobs.bilibili.com" in page.url:
                bili_page = page
                break
                
        if not bili_page:
            print("Bilibili page not found. Please open jobs.bilibili.com in the CDP browser.")
            return

        print("Found Bilibili page. Injecting XHR interceptor and reloading...")
        bili_page.bring_to_front()
        
        interceptor_js = """
        if (!window.__interceptedBiliData) {
            window.__interceptedBiliData = [];
            const originalSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.send = function() {
                this.addEventListener('load', function() {
                    if (this.responseURL.includes('position/positionList')) {
                        try {
                            const data = JSON.parse(this.responseText);
                            window.__interceptedBiliData.push(data);
                        } catch (e) {}
                    }
                });
                return originalSend.apply(this, arguments);
            };
            
            const originalFetch = window.fetch;
            window.fetch = async function() {
                const response = await originalFetch.apply(this, arguments);
                const clone = response.clone();
                const url = arguments[0] && typeof arguments[0] === 'string' ? arguments[0] : (arguments[0] && arguments[0].url ? arguments[0].url : '');
                if (url.includes('position/positionList')) {
                    clone.json().then(data => {
                        window.__interceptedBiliData.push(data);
                    }).catch(e => {});
                }
                return response;
            };
        }
        """
        
        context.add_init_script(interceptor_js)
        bili_page.reload()
        time.sleep(5) # Use static sleep instead of networkidle which times out on streaming media sites
        
        consecutive_fails = 0
        while consecutive_fails < 10:
            try:
                bili_page.mouse.wheel(0, 2000)
                time.sleep(1)
                next_btn = bili_page.locator("li.ant-pagination-next:not(.ant-pagination-disabled)")
                if next_btn.is_visible() and next_btn.get_attribute("aria-disabled") != "true":
                    next_btn.click()
                    time.sleep(3)
                    consecutive_fails = 0
                    current_len = bili_page.evaluate("window.__interceptedBiliData ? window.__interceptedBiliData.length : 0")
                    print(f"Clicked Next. Intercepted so far: {current_len}")
                else:
                    consecutive_fails += 1
                    time.sleep(2)
            except Exception:
                consecutive_fails += 1
                
        # Extract the data from the page
        extracted_data = bili_page.evaluate("window.__interceptedBiliData")
        if extracted_data:
            payloads.extend(extracted_data)
            
        print(f"Finished Bilibili pagination. Intercepted {len(payloads)} chunks.")
        
        if payloads:
            os.makedirs("cdp_data", exist_ok=True)
            with open("cdp_data/bilibili.json", "w", encoding="utf-8") as f:
                json.dump({"bilibili": payloads}, f, ensure_ascii=False, indent=2)
            print("Saved to cdp_data/bilibili.json")

if __name__ == "__main__":
    run_bilibili_cdp()
