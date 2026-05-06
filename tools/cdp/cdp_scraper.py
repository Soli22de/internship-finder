import json
import time
import os
from typing import Any, Dict, List
import pandas as pd
import yaml
from playwright.sync_api import sync_playwright

def norm(x: Any) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return str(x).strip()

def load_rules(config_path: str) -> Dict[str, Any]:
    if not os.path.exists(config_path):
        print(f"Warning: config file {config_path} not found.")
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_cdp_scraper():
    rules_path = os.path.join(os.path.dirname(__file__), "cdp_rules.yaml")
    config = load_rules(rules_path)
    rules = config.get("rules", {})
    
    print("Connecting to Chrome via CDP on port 9222...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception as e:
            print(f"Failed to connect to CDP: {e}")
            print("Did you run start_chrome_debug.bat?")
            return
        
        context = browser.contexts[0]
        
        # Inject XHR interceptor to catch API payloads
        for page in context.pages:
            try:
                page.evaluate("""
                    if (!window._interceptedPayloads) {
                        window._interceptedPayloads = [];
                        const origFetch = window.fetch;
                        window.fetch = async function() {
                            const response = await origFetch.apply(this, arguments);
                            const clone = response.clone();
                            clone.json().then(data => {
                                window._interceptedPayloads.push({
                                    url: arguments[0] && typeof arguments[0] === 'string' ? arguments[0] : (arguments[0] && arguments[0].url ? arguments[0].url : ''),
                                    data: data
                                });
                            }).catch(e => {});
                            return response;
                        };
                        
                        const origOpen = XMLHttpRequest.prototype.open;
                        XMLHttpRequest.prototype.open = function() {
                            this._url = arguments[1];
                            return origOpen.apply(this, arguments);
                        };
                        
                        const origSend = XMLHttpRequest.prototype.send;
                        XMLHttpRequest.prototype.send = function() {
                            this.addEventListener('load', function() {
                                try {
                                    window._interceptedPayloads.push({
                                        url: this._url,
                                        data: JSON.parse(this.responseText)
                                    });
                                } catch(e) {}
                            });
                            return origSend.apply(this, arguments);
                        };
                    }
                """)
            except Exception:
                pass

        pages = context.pages
        print(f"Found {len(pages)} open pages in Chrome.")
        
        for page in pages:
            url = page.url
            matched_rule = None
            rule_name = ""
            
            # Find matching rule
            for name, rule in rules.items():
                if rule.get("domain") in url:
                    matched_rule = rule
                    rule_name = name
                    break
                    
            if not matched_rule:
                continue
                
            print(f"Found {rule_name} page. Starting auto-pagination...")
            page.bring_to_front()
            time.sleep(2)
            
            consecutive_fails = 0
            max_retries = matched_rule.get("max_retries", 10)
            scroll_first = matched_rule.get("scroll_first", True)
            scroll_amount = matched_rule.get("scroll_amount", 2000)
            pagination_selector = matched_rule.get("pagination_selector")
            
            while consecutive_fails < max_retries:
                try:
                    if scroll_first:
                        page.mouse.wheel(0, scroll_amount)
                        time.sleep(1)
                        
                    next_btn = page.locator(pagination_selector)
                    if next_btn.is_visible():
                        next_btn.click()
                        time.sleep(3)
                        consecutive_fails = 0
                    else:
                        if not scroll_first:
                            page.mouse.wheel(0, scroll_amount)
                        time.sleep(2)
                        consecutive_fails += 1
                except Exception:
                    consecutive_fails += 1
                    
            print(f"Finished {rule_name} pagination.")

        print("Finished scraping pages.")
        
        # Retrieve all payloads from the browser context
        payloads = {}
        for page in pages:
            try:
                page_payloads = page.evaluate("window._interceptedPayloads || []")
                if page_payloads:
                    payloads[page.url] = page_payloads
            except Exception:
                pass

        output_file = os.path.join(os.path.dirname(__file__), "cdp_intercepted_payloads.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(payloads, f, ensure_ascii=False, indent=2)
            
        print(f"Data saved to {output_file}")

if __name__ == "__main__":
    run_cdp_scraper()
