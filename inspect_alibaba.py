import time
from playwright.sync_api import sync_playwright

def inspect_alibaba():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        ali_page = None
        for page in context.pages:
            if "talent.alibaba.com" in page.url:
                ali_page = page
                break
        
        if ali_page:
            print("Found Alibaba page.")
            ali_page.bring_to_front()
            
            body_text = ali_page.evaluate("""() => document.body.innerText.substring(0, 1000)""")
            print("Body Text excerpt:")
            print(body_text)
            
            # Print all button tags and some context
            pagination_html = ali_page.evaluate("""() => {
                const els = document.querySelectorAll('button.next-btn, li.next-pagination-item, .next-pagination-item-next');
                return Array.from(els).map(e => e.outerHTML).join('\\n');
            }""")
            print("Next button HTML:")
            print(pagination_html)
            
            # Print page text again to see if it's rendered properly
            body_text2 = ali_page.evaluate("""() => document.body.innerText.substring(2000, 3000)""")
            print("Body Text excerpt 2:")
            print(body_text2)
            
            # Inspect actual response bodies
            responses = ali_page.evaluate("""async () => {
                const results = [];
                const entries = performance.getEntriesByType('resource').filter(r => r.name.includes('position/search'));
                return entries.map(e => e.name).join('\\n');
            }""")
            print("Position search endpoints:")
            print(responses)
            
            # Let's try to extract one position block by finding text markers
            card_html = ali_page.evaluate("""() => {
                // The actual job lists might be under a specific container
                const titleLinks = Array.from(document.querySelectorAll('a')).filter(a => a.innerText && a.innerText.includes('类'));
                if (titleLinks.length > 0) {
                    const card = titleLinks[0].closest('div[style], li') || titleLinks[0].parentElement.parentElement;
                    return card.outerHTML;
                }
                
                // Another approach
                const divs = Array.from(document.querySelectorAll('div'));
                const jobDiv = divs.find(d => {
                    const txt = d.innerText;
                    return txt.includes('更新于') && txt.includes('类') && txt.length < 500 && txt.length > 20;
                });
                return jobDiv ? jobDiv.outerHTML : 'Still no card found';
            }""")
            print("Targeted Job Card HTML:")
            print(card_html)

if __name__ == "__main__":
    inspect_alibaba()
