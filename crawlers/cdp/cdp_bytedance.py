import time
import json
import os
from playwright.sync_api import sync_playwright

def scrape_bytedance():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = None
        for p_idx in context.pages:
            if "jobs.bytedance.com" in p_idx.url:
                page = p_idx
                break
        
        if not page:
            print("Bytedance page not found!")
            return
            
        print("Found Bytedance page.")
        page.bring_to_front()
        
        interceptor_js = """
        if (!window.__interceptedByteData) {
            window.__interceptedByteData = [];
            const originalSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.send = function() {
                this.addEventListener('load', function() {
                    try {
                        if (this.responseURL && this.responseURL.includes('jobs/api/v1/search')) {
                            const data = JSON.parse(this.responseText);
                            if (data.data && data.data.job_post_list) {
                                window.__interceptedByteData.push(data);
                            }
                        }
                    } catch (e) {}
                });
                return originalSend.apply(this, arguments);
            };
            
            const originalFetch = window.fetch;
            window.fetch = async function() {
                const response = await originalFetch.apply(this, arguments);
                const clone = response.clone();
                const url = arguments[0] && typeof arguments[0] === 'string' ? arguments[0] : (arguments[0] && arguments[0].url ? arguments[0].url : '');
                if (url.includes('jobs/api/v1/search') || url.includes('api/v1/search/job/')) {
                    clone.json().then(data => {
                        if (data.data && data.data.job_post_list) {
                            window.__interceptedByteData.push(data);
                        }
                    }).catch(e => {});
                }
                return response;
            };
        }
        """
        
        context.add_init_script(interceptor_js)
        page.reload()
        time.sleep(5)
        
        payloads = []
        
        consecutive_fails = 0
        last_len = 0
        same_len_count = 0
        
        while consecutive_fails < 10 and same_len_count < 5:
            try:
                page.mouse.wheel(0, 2000)
                time.sleep(1)
                
                # Use evaluate to find the next button and click it to bypass visibility issues
                clicked = page.evaluate("""() => {
                    const btn = document.querySelector('li.atsx-pagination-next[aria-disabled="false"], li.atsx-pagination-next:not(.atsx-pagination-disabled)');
                    if (btn && !btn.className.includes('disabled') && btn.getAttribute('aria-disabled') !== 'true') {
                        btn.click();
                        return true;
                    }
                    return false;
                }""")
                
                if clicked:
                    time.sleep(3)
                    consecutive_fails = 0
                    
                    current_len = page.evaluate("window.__interceptedByteData ? window.__interceptedByteData.length : 0")
                    print(f"Clicked Next. Intercepted so far: {current_len}")
                    
                    if current_len == last_len:
                        same_len_count += 1
                    else:
                        same_len_count = 0
                    last_len = current_len
                    
                    if current_len > 200:
                        print("Reached maximum page limit. Stopping pagination.")
                        break
                else:
                    consecutive_fails += 1
                    time.sleep(2)
            except Exception:
                consecutive_fails += 1
                
        # Extract the data from the page
        extracted_data = page.evaluate("window.__interceptedByteData")
        if extracted_data and len(extracted_data) > 0:
            payloads.extend(extracted_data)
            
        print(f"Finished Bytedance pagination. Intercepted {len(payloads)} chunks.")
        
        if payloads:
            os.makedirs("cdp_data", exist_ok=True)
            with open("cdp_data/bytedance.json", "w", encoding="utf-8") as f:
                json.dump({"bytedance": payloads}, f, ensure_ascii=False, indent=2)
            print("Saved bytedance data to cdp_data/bytedance.json")

if __name__ == "__main__":
    scrape_bytedance()
