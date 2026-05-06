from playwright.sync_api import sync_playwright

def inspect_tencent():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        tc_page = None
        for page in context.pages:
            if "join.qq.com" in page.url:
                tc_page = page
                break
        
        if tc_page:
            print("Found Tencent page.")
            tc_page.bring_to_front()
            
            # Print html elements related to pagination
            pagination_html = tc_page.evaluate("""() => {
                const el = document.querySelector('.pagination') || document.querySelector('.el-pagination') || document.querySelector('[class*="page"]');
                return el ? el.outerHTML : 'No pagination element found';
            }""")
            print("Pagination HTML:")
            print(pagination_html)
            
            # Also try to print the entire body text to see if it's rendered
            body_text = tc_page.evaluate("""() => document.body.innerText.substring(0, 500)""")
            print("Body Text excerpt:")
            print(body_text)

if __name__ == "__main__":
    inspect_tencent()
