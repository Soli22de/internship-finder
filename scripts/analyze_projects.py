from playwright.sync_api import sync_playwright
import re
import json
import time

URLS_TO_CHECK = {
    "字节跳动": "https://jobs.bytedance.com/campus/",
    "腾讯": "https://join.qq.com/",
    "快手": "https://campus.kuaishou.cn/recruit/campus/e/#/campus/home",
    "小红书": "https://job.xiaohongshu.com/campus/",
    "美团": "https://zhaopin.meituan.com/web/campus",
    "阿里": "https://talent.alibaba.com/campus/",
    "京东": "https://campus.jd.com/#/",
    "哔哩哔哩": "https://jobs.bilibili.com/campus"
}

def analyze_page(page, company_name):
    try:
        page.bring_to_front()
        time.sleep(2)  # wait for any dynamic content
        text = page.evaluate("document.body.innerText")
        
        # Regex to find project names (2 to 10 characters before 计划/Star/星/生/实习/营/大咖)
        # We allow Chinese characters and English letters
        pattern = r'[A-Za-z0-9\u4e00-\u9fa5]{2,10}(?:计划|Star|star|星|生|实习|营|人才|大咖)'
        words = set(re.findall(pattern, text))
        
        # Filter out common false positives
        stopwords = {"关于我们实习", "日常实习", "暑期实习", "应届生", "毕业生", "实习生"}
        words = {w for w in words if w not in stopwords and not w.endswith("生") and not w.endswith("实习")}
        
        # Extract surrounding context for 2027
        sentences = set(re.findall(r'.{0,20}(?:2026|2027|26届|27届).{0,20}', text))
        
        return {
            "title": page.title(),
            "url": page.url,
            "project_keywords": list(words),
            "year_contexts": list(sentences)
        }
    except Exception as e:
        return {"error": str(e)}

def run():
    print("Connecting to CDP...")
    results = {}
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            
            # 1. Analyze already open tabs
            print(f"Found {len(context.pages)} open tabs. Analyzing...")
            for page in context.pages:
                url = page.url
                for comp, curl in URLS_TO_CHECK.items():
                    # very loose matching
                    if curl.split("://")[1].split("/")[0] in url:
                        print(f"Analyzing open tab for {comp}: {url}")
                        results[f"open_tab_{comp}"] = analyze_page(page, comp)
            
            # 2. If some companies weren't found in open tabs, let's open them in a new tab temporarily
            found_companies = [k.replace("open_tab_", "") for k in results.keys()]
            missing = [c for c in URLS_TO_CHECK.keys() if c not in found_companies]
            
            if missing:
                print(f"Navigating to missing companies: {missing}")
                temp_page = context.new_page()
                for comp in missing:
                    print(f"Visiting {comp}: {URLS_TO_CHECK[comp]}")
                    try:
                        temp_page.goto(URLS_TO_CHECK[comp], timeout=15000, wait_until="domcontentloaded")
                        results[f"navigated_{comp}"] = analyze_page(temp_page, comp)
                    except Exception as e:
                        print(f"Failed to load {comp}: {e}")
                temp_page.close()

            with open("campus_projects_analysis.json", "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print("Analysis saved to campus_projects_analysis.json")
            
        except Exception as e:
            print(f"CDP Connection failed: {e}")

if __name__ == "__main__":
    run()