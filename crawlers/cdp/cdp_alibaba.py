import json
import time
import os
from typing import Any, Dict, List
from playwright.sync_api import sync_playwright

def run_alibaba_cdp():
    print("Connecting to Chrome via CDP on port 9222 for Alibaba...")
    payloads = []
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception as e:
            print(f"Failed to connect to CDP: {e}")
            return
            
        context = browser.contexts[0]
        ali_page = None
        for page in context.pages:
            if "talent.alibaba.com" in page.url:
                ali_page = page
                break
                
        if not ali_page:
            print("Alibaba page not found. Please open talent.alibaba.com in the CDP browser.")
            return

        print("Found Alibaba page. Injecting XHR interceptor and reloading...")
        ali_page.bring_to_front()
        
        interceptor_js = """
        if (!window.__interceptedAliData) {
            window.__interceptedAliData = [];
            const originalSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.send = function() {
                this.addEventListener('load', function() {
                    try {
                        if (this.responseURL && this.responseURL.indexOf('position/search') !== -1) {
                            const data = JSON.parse(this.responseText);
                            if (data.content && data.content.data) {
                                window.__interceptedAliData.push(data);
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
                if (url.indexOf('position/search') !== -1) {
                    clone.json().then(data => {
                        if (data.content && data.content.data) {
                            window.__interceptedAliData.push(data);
                        }
                    }).catch(e => {});
                }
                return response;
            };
        }
        """
        
        context.add_init_script(interceptor_js)
        ali_page.reload()
        ali_page.wait_for_load_state("networkidle")
        time.sleep(3)
        
        consecutive_fails = 0
        last_len = 0
        same_len_count = 0
        
        # Bypass XHR completely by extracting data directly from the DOM using Playwright
        # Alibaba seems to block any script using fetch() with a 403.
        # We will instead paginate by clicking, and parse the HTML to get job info directly.
        all_data = []
        
        try:
            total_pages = 46
            print(f"Paginating and extracting DOM data directly for {total_pages} pages...")
            
            for page_num in range(1, total_pages + 1):
                # Extract currently visible job cards
                page_data = ali_page.evaluate("""() => {
                    const cards = Array.from(document.querySelectorAll('.PositionListCard--pcPositionListCard--cdsEg95, div[class*="PositionListCard"]'));
                    const jobs = [];
                    for (const card of cards) {
                        const linkEl = card.querySelector('a');
                        if (!linkEl) continue;
                        
                        const titleEl = card.querySelector('div[class*="mame"]');
                        const detailEls = Array.from(card.querySelectorAll('span[class*="text"]')).map(e => e.innerText).filter(t => t);
                        
                        jobs.push({
                            title: titleEl ? titleEl.innerText : '',
                            url: linkEl.href,
                            details: detailEls
                        });
                    }
                    return jobs;
                }""")
                
                # A fallback extractor since class names might vary
                if not page_data:
                    page_data = ali_page.evaluate("""() => {
                        const cards = Array.from(document.querySelectorAll('a')).filter(a => a.href && a.href.includes('position/') && !a.href.includes('batchId'));
                        return cards.map(link => {
                            const container = link.closest('div[style], li') || link.parentElement;
                            const texts = container.innerText.split('\\n').filter(t => t.trim().length > 0);
                            return {
                                title: texts.length > 0 ? texts[0] : 'Unknown',
                                url: link.href,
                                details: texts
                            };
                        });
                    }""")
                
                if page_data:
                    all_data.append({"page": page_num, "items": page_data})
                    print(f"Extracted {len(page_data)} jobs from page {page_num}")
                else:
                    print(f"No jobs found on page {page_num}")
                
                # Go to next page
                if page_num < total_pages:
                    ali_page.mouse.wheel(0, 2000)
                    time.sleep(1)
                    
                    clicked = ali_page.evaluate("""() => {
                        const btn = document.querySelector('button.next-next:not([disabled]), button.next-pagination-item-next:not([disabled])');
                        if (btn) {
                            btn.click();
                            return true;
                        }
                        return false;
                    }""")
                    
                    if clicked:
                        time.sleep(2.5) # Wait for page to render
                    else:
                        print("Could not find or click next button. Stopping early.")
                        break
                        
        except Exception as e:
            print(f"Error during DOM extraction: {e}")
            
        payloads.extend(all_data)
        
        print(f"Finished Alibaba data extraction. Total {len(payloads)} chunks.")
        
        if payloads:
            os.makedirs("cdp_data", exist_ok=True)
            with open("cdp_data/alibaba.json", "w", encoding="utf-8") as f:
                json.dump({"alibaba": payloads}, f, ensure_ascii=False, indent=2)
            print("Saved to cdp_data/alibaba.json")

if __name__ == "__main__":
    run_alibaba_cdp()
