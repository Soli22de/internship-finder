import json
import time
import os
from typing import Any, Dict, List
from playwright.sync_api import sync_playwright

def run_jd_cdp():
    print("Connecting to Chrome via CDP on port 9222 for JD...")
    payloads = []
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception as e:
            print(f"Failed to connect to CDP: {e}")
            return
            
        context = browser.contexts[0]
        jd_page = None
        for page in context.pages:
            if "campus.jd.com" in page.url:
                jd_page = page
                break
                
        if not jd_page:
            print("JD page not found. Please open campus.jd.com in the CDP browser.")
            return

        print("Found JD page. Injecting XHR interceptor and reloading...")
        jd_page.bring_to_front()
        
        interceptor_js = """
        if (!window.__interceptedJDData) {
            window.__interceptedJDData = [];
            const originalSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.send = function() {
                this.addEventListener('load', function() {
                    if (this.responseURL.includes('position/page') || this.responseURL.includes('position/list')) {
                        try {
                            const data = JSON.parse(this.responseText);
                            window.__interceptedJDData.push(data);
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
                if (url.includes('position/page') || url.includes('position/list')) {
                    clone.json().then(data => {
                        window.__interceptedJDData.push(data);
                    }).catch(e => {});
                }
                return response;
            };
        }
        """
        
        context.add_init_script(interceptor_js)
        jd_page.reload()
        jd_page.wait_for_load_state("networkidle")
        time.sleep(3)
        
        consecutive_fails = 0
        while consecutive_fails < 10:
            try:
                jd_page.mouse.wheel(0, 2000)
                time.sleep(1)
                next_btn = jd_page.locator("li.ant-pagination-next:not(.ant-pagination-disabled)")
                if next_btn.is_visible() and next_btn.get_attribute("aria-disabled") != "true":
                    next_btn.click()
                    time.sleep(3)
                    consecutive_fails = 0
                    current_len = jd_page.evaluate("window.__interceptedJDData ? window.__interceptedJDData.length : 0")
                    print(f"Clicked Next. Intercepted so far: {current_len}")
                else:
                    consecutive_fails += 1
                    time.sleep(2)
            except Exception:
                consecutive_fails += 1
                
        # Extract the data from the page
        extracted_data = jd_page.evaluate("window.__interceptedJDData")
        if extracted_data:
            payloads.extend(extracted_data)
            
        print(f"Finished JD pagination. Intercepted {len(payloads)} chunks.")
        
        if payloads:
            os.makedirs("cdp_data", exist_ok=True)
            with open("cdp_data/jd.json", "w", encoding="utf-8") as f:
                json.dump({"jd": payloads}, f, ensure_ascii=False, indent=2)
            print("Saved to cdp_data/jd.json")

if __name__ == "__main__":
    run_jd_cdp()
