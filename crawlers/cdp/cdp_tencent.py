import json
import time
import os
from typing import Any, Dict, List
from playwright.sync_api import sync_playwright

def run_tencent_cdp():
    print("Connecting to Chrome via CDP on port 9222 for Tencent...")
    payloads = []
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception as e:
            print(f"Failed to connect to CDP: {e}")
            return
            
        context = browser.contexts[0]
        tc_page = None
        for page in context.pages:
            if "join.qq.com" in page.url:
                tc_page = page
                break
                
        if not tc_page:
            print("Tencent page not found. Please open join.qq.com in the CDP browser.")
            return

        print("Found Tencent page. Injecting XHR interceptor and reloading...")
        tc_page.bring_to_front()
        
        # Inject an XHR interceptor script that pushes data to a global array
        interceptor_js = """
        if (!window.__interceptedTencentData) {
            window.__interceptedTencentData = [];
            const originalSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.send = function() {
                this.addEventListener('load', function() {
                    if (this.responseURL.includes('api/v1/position/searchPosition')) {
                        try {
                            const data = JSON.parse(this.responseText);
                            window.__interceptedTencentData.push(data);
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
                if (url.includes('api/v1/position/searchPosition')) {
                    clone.json().then(data => {
                        window.__interceptedTencentData.push(data);
                    }).catch(e => {});
                }
                return response;
            };
        }
        """
        
        # We need to reload to capture the first page request
        # First we add an init script that will run before page load
        context.add_init_script(interceptor_js)
        tc_page.reload()
        tc_page.wait_for_load_state("networkidle")
        time.sleep(3)
        
        consecutive_fails = 0
        last_len = 0
        same_len_count = 0
        
        while consecutive_fails < 10 and same_len_count < 5:
            try:
                tc_page.mouse.wheel(0, 2000)
                time.sleep(1)
                next_btn = tc_page.locator("button.btn-next:not([disabled])")
                if next_btn.is_visible() and next_btn.is_enabled():
                    next_btn.click()
                    time.sleep(3)
                    consecutive_fails = 0
                    current_len = tc_page.evaluate("window.__interceptedTencentData.length")
                    print(f"Clicked Next. Intercepted so far: {current_len}")
                    
                    if current_len == last_len:
                        same_len_count += 1
                    else:
                        same_len_count = 0
                    last_len = current_len
                else:
                    consecutive_fails += 1
                    time.sleep(2)
            except Exception:
                consecutive_fails += 1
                
        # To fix the missing JD data, let's also try to extract directly from the DOM for Tencent
        # The list API doesn't seem to have full JDs. We'll extract what we can from the DOM too.
        dom_data = tc_page.evaluate("""() => {
            const jobs = [];
            // We need to collect all items across all pages if we want full JDs from DOM
            // Since we've already paginated, we only see the last page's DOM.
            // This is why we rely on the API for the list. 
            // For Tencent, the JD is typically retrieved by a separate detail API call.
            return [];
        }""")
        
        print(f"Also extracted {len(dom_data)} items from DOM.")
        
        # Extract the data from the page
        extracted_data = tc_page.evaluate("window.__interceptedTencentData")
        if extracted_data:
            payloads.extend(extracted_data)
            
        print(f"Finished Tencent pagination. Intercepted {len(payloads)} chunks.")
        
        if payloads:
            os.makedirs("cdp_data", exist_ok=True)
            with open("cdp_data/tencent.json", "w", encoding="utf-8") as f:
                json.dump({"tencent": payloads}, f, ensure_ascii=False, indent=2)
            print("Saved to cdp_data/tencent.json")

if __name__ == "__main__":
    run_tencent_cdp()
