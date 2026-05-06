from playwright.sync_api import sync_playwright

def inspect_meituan():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        meituan_page = None
        for page in context.pages:
            if "zhaopin.meituan.com" in page.url:
                meituan_page = page
                break
        
        if meituan_page:
            print("Found Meituan page.")
            meituan_page.bring_to_front()
            
            body_text = meituan_page.evaluate("""() => document.body.innerText.substring(0, 1000)""")
            print("Body Text excerpt:")
            print(body_text)
            
            # Print all button tags and some context
            pagination_html = meituan_page.evaluate("""() => {
                const els = document.querySelectorAll('button, li, a');
                return Array.from(els).filter(e => e.innerText.includes('下一页') || e.innerText.includes('页') || e.className.includes('next')).map(e => e.outerHTML).slice(0, 5).join('\\n');
            }""")
            print("Next button HTML:")
            print(pagination_html)
            
            # Print recently intercepted requests
            requests = meituan_page.evaluate("""() => {
                const entries = performance.getEntriesByType('resource');
                return entries
                    .filter(r => r.name.includes('api') || r.name.includes('position') || r.name.includes('job') || r.name.includes('list'))
                    .map(r => r.name).join('\\n');
            }""")
            print("Recent API Requests:")
            print(requests)

if __name__ == "__main__":
    inspect_meituan()
