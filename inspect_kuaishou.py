from playwright.sync_api import sync_playwright

def inspect_kuaishou():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        ks_page = None
        for page in context.pages:
            if "campus.kuaishou.cn" in page.url:
                ks_page = page
                break
        
        if ks_page:
            print("Found Kuaishou page.")
            ks_page.bring_to_front()
            
            body_text = ks_page.evaluate("""() => document.body.innerText.substring(0, 1000)""")
            print("Body Text excerpt:")
            print(body_text)
            
            # Print recently intercepted requests
            requests = ks_page.evaluate("""() => {
                if (window.__interceptedKuaishouData) {
                    return `Intercepted ${window.__interceptedKuaishouData.length} responses`;
                }
                return 'No data intercepted. Checking performance entries... ' + 
                    performance.getEntriesByType('resource')
                    .filter(r => r.name.includes('position') || r.name.includes('job') || r.name.includes('list'))
                    .map(r => r.name).join('\\n');
            }""")
            print("Requests:")
            print(requests)

if __name__ == "__main__":
    inspect_kuaishou()
