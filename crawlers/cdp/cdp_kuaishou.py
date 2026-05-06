import json
import time
import os
from typing import Any, Dict, List
from playwright.sync_api import sync_playwright

def run_kuaishou_cdp():
    print("Connecting to Chrome via CDP on port 9222 for Kuaishou...")
    payloads = []
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception as e:
            print(f"Failed to connect to CDP: {e}")
            return
            
        context = browser.contexts[0]
        ks_page = None
        for page in context.pages:
            if "campus.kuaishou.cn" in page.url:
                ks_page = page
                break
                
        if not ks_page:
            print("Kuaishou page not found. Please open campus.kuaishou.cn in the CDP browser.")
            return

        print("Found Kuaishou page. Injecting XHR interceptor and reloading...")
        ks_page.bring_to_front()
        
        interceptor_js = """
        if (!window.__interceptedKuaishouData) {
            window.__interceptedKuaishouData = [];
            const originalSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.send = function() {
                this.addEventListener('load', function() {
                    if (this.responseURL.includes('api/v1/open/positions')) {
                        try {
                            const data = JSON.parse(this.responseText);
                            window.__interceptedKuaishouData.push(data);
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
                if (url.includes('api/v1/open/positions')) {
                    clone.json().then(data => {
                        window.__interceptedKuaishouData.push(data);
                    }).catch(e => {});
                }
                return response;
            };
        }
        """
        
        context.add_init_script(interceptor_js)
        ks_page.reload()
        ks_page.wait_for_load_state("networkidle")
        time.sleep(3)
        
        consecutive_fails = 0
        while consecutive_fails < 10:
            try:
                ks_page.mouse.wheel(0, 2000)
                time.sleep(1)
                next_btn = ks_page.locator("li.ant-pagination-next:not(.ant-pagination-disabled)")
                if next_btn.is_visible() and next_btn.get_attribute("aria-disabled") != "true":
                    next_btn.click()
                    time.sleep(3)
                    consecutive_fails = 0
                    current_len = ks_page.evaluate("window.__interceptedKuaishouData ? window.__interceptedKuaishouData.length : 0")
                    print(f"Clicked Next. Intercepted so far: {current_len}")
                else:
                    consecutive_fails += 1
                    time.sleep(2)
            except Exception:
                consecutive_fails += 1
                
        # Extract the data from the page
        extracted_data = ks_page.evaluate("window.__interceptedKuaishouData")
        if extracted_data:
            payloads.extend(extracted_data)
            
        print(f"Finished Kuaishou pagination. Intercepted {len(payloads)} chunks.")
        
        if payloads:
            os.makedirs("cdp_data", exist_ok=True)
            with open("cdp_data/kuaishou.json", "w", encoding="utf-8") as f:
                json.dump({"kuaishou": payloads}, f, ensure_ascii=False, indent=2)
            print("Saved to cdp_data/kuaishou.json")

if __name__ == "__main__":
    run_kuaishou_cdp()
