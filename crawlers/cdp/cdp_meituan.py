import json
import time
import os
from typing import Any, Dict, List
from playwright.sync_api import sync_playwright

def run_meituan_cdp():
    print("Connecting to Chrome via CDP on port 9222 for Meituan...")
    payloads = []
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception as e:
            print(f"Failed to connect to CDP: {e}")
            return
            
        context = browser.contexts[0]
        meituan_page = None
        for page in context.pages:
            if "zhaopin.meituan.com" in page.url:
                meituan_page = page
                break
                
        if not meituan_page:
            print("Meituan page not found. Please open zhaopin.meituan.com in the CDP browser.")
            return

        print("Found Meituan page. Injecting XHR interceptor and reloading...")
        meituan_page.bring_to_front()
        
        interceptor_js = """
        if (!window.__interceptedMeituanData) {
            window.__interceptedMeituanData = [];
            const originalSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.send = function() {
                this.addEventListener('load', function() {
                    if (this.responseURL && this.responseURL.includes('job/getJobList')) {
                        try {
                            const data = JSON.parse(this.responseText);
                            if (data.data && data.data.list) {
                                window.__interceptedMeituanData.push(data);
                            }
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
                if (url.includes('job/getJobList')) {
                    clone.json().then(data => {
                        if (data.data && data.data.list) {
                            window.__interceptedMeituanData.push(data);
                        }
                    }).catch(e => {});
                }
                return response;
            };
        }
        """
        
        context.add_init_script(interceptor_js)
        meituan_page.reload()
        meituan_page.wait_for_load_state("networkidle")
        time.sleep(3)
        
        consecutive_fails = 0
        while consecutive_fails < 10:
            try:
                # Need to wait for load to ensure next button is correctly evaluated
                meituan_page.mouse.wheel(0, 2000)
                time.sleep(2)
                
                next_btn = meituan_page.locator("li.mtd-pagination-next:not(.mtd-pagination-item-disabled)")
                if next_btn.is_visible():
                    next_btn.click()
                    time.sleep(3)
                    consecutive_fails = 0
                    current_len = meituan_page.evaluate("window.__interceptedMeituanData ? window.__interceptedMeituanData.length : 0")
                    print(f"Clicked Next. Intercepted so far: {current_len}")
                    
                    # Hard stop if we intercept more than 100 pages to avoid infinite loops
                    if current_len > 351:
                        print("Reached maximum page limit. Stopping pagination.")
                        break
                else:
                    consecutive_fails += 1
            except Exception:
                consecutive_fails += 1
                
        # Extract the data from the page
        extracted_data = meituan_page.evaluate("window.__interceptedMeituanData")
        if extracted_data:
            payloads.extend(extracted_data)
            
        print(f"Finished Meituan pagination. Intercepted {len(payloads)} chunks.")
        
        if payloads:
            os.makedirs("cdp_data", exist_ok=True)
            with open("cdp_data/meituan.json", "w", encoding="utf-8") as f:
                json.dump({"meituan": payloads}, f, ensure_ascii=False, indent=2)
            print("Saved to cdp_data/meituan.json")

if __name__ == "__main__":
    run_meituan_cdp()
