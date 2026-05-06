import os
import sys
import json
import time
import argparse
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ImportError:
    pass

def get_compressed_html(page) -> str:
    """Extracts and compresses HTML to save LLM tokens."""
    # Scroll down a few times to trigger lazy loading
    for _ in range(3):
        page.mouse.wheel(0, 1000)
        page.wait_for_timeout(500)
    
    html = page.content()
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove useless tags
    for tag in soup(["script", "style", "svg", "img", "noscript", "iframe"]):
        tag.decompose()
        
    # Compress classes and ids slightly but keep them as they are crucial for selectors
    # We just get the text and structure
    return soup.prettify()

def call_deepseek_api(prompt: str, api_key: str) -> str:
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert Python web scraping engineer. You generate robust crawler code following the 'scrape-with-discipline' pattern."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1
    }
    
    print("Calling DeepSeek API (this might take a minute)...")
    response = requests.post(url, headers=headers, json=data, timeout=120)
    
    if response.status_code != 200:
        print(f"Error calling DeepSeek API: {response.status_code}")
        print(response.text)
        sys.exit(1)
        
    result = response.json()
    return result["choices"][0]["message"]["content"]

def generate_prompt(url: str, html_snippet: str) -> str:
    return f"""
I need to write a Python web scraper for a job board or company career site using a specific `SiteAdapter` pattern.
Here is the URL of the job list page: {url}

Here is a simplified HTML snippet of the list page (focus on finding the job card list, pagination, and fields like job title, company, location, salary, and detail URL):
```html
{html_snippet[:40000]}  # Limiting to ~40k chars to fit context window
```

Your task:
1. Identify the CSS selector for the job list container/cards.
2. Identify the CSS selectors for the individual fields inside the card:
   - company_name
   - job_title
   - salary_range
   - location
   - link to the detail page (url)
3. WARNING: Some sites use anti-bot measures. Look closely at the HTML. If you see custom fonts (like `&#x` entities or missing characters in salary/company fields), mention this in a comment inside the `__post_init__` method so the user knows they must extract a font map!
4. Generate a Python script containing a class that subclasses `SiteAdapter`. 
5. The generated code MUST strictly follow this exact structure:

```python
from bs4 import BeautifulSoup
from template_crawler import SiteAdapter, clean_text

class GeneratedSiteAdapter(SiteAdapter):
    name: str = "generated_site"
    base_url: str = "{url}"
    list_selector: str = "YOUR_CARD_SELECTOR"
    detail_link_selector: str = "YOUR_LINK_SELECTOR"

    def __post_init__(self):
        # Adjust page param if needed
        self.list_query = {{"page": "{{page}}"}}

    def parse_list_card(self, card) -> dict:
        # Example implementation:
        # title_el = card.select_one("YOUR_TITLE_SELECTOR")
        # return {{
        #     "company_name": clean_text(..., self.font_map),
        #     "job_title": clean_text(title_el.get_text() if title_el else "", self.font_map),
        #     "salary_range": clean_text(..., self.font_map),
        #     "location": clean_text(..., self.font_map),
        #     "url": ...
        # }}
        pass

    def parse_detail(self, soup: BeautifulSoup) -> dict:
        # Return empty dict if we just want list page for now
        return {{}}

    def filter_row(self, row: dict) -> bool:
        return True
```

Please output ONLY the valid Python code. Do not include markdown formatting like ```python, just the raw code.
"""

def main():
    parser = argparse.ArgumentParser(description="AI-Assisted Crawler Generator")
    parser.add_argument("url", help="Target URL of the job list page")
    parser.add_argument("--output", default="generated_adapter.py", help="Output python file name")
    args = parser.parse_args()

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY environment variable is not set.")
        print("Please set it: set DEEPSEEK_API_KEY=your_key")
        sys.exit(1)

    print(f"Launching Playwright to fetch DOM for {args.url} ...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)  # Wait for JS to render
            html_snippet = get_compressed_html(page)
            print(f"Extracted HTML, length: {len(html_snippet)} chars.")
        except Exception as e:
            print(f"Failed to fetch page: {e}")
            browser.close()
            sys.exit(1)
        browser.close()

    prompt = generate_prompt(args.url, html_snippet)
    
    code = call_deepseek_api(prompt, api_key)
    
    # Cleanup possible markdown code blocks
    code = code.replace("```python", "").replace("```", "").strip()
    
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(code)
        
    print(f"Success! Generated SiteAdapter saved to {args.output}.")
    print("Please review the generated code, adjust selectors if necessary, and run it with template_crawler.py.")

if __name__ == "__main__":
    main()
