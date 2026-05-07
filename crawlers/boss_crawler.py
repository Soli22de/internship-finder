"""
BOSS直聘 crawler — uses Playwright Firefox + cookies from user's real Firefox.
No CDP needed. The user logs into BOSS in Firefox once; crawler reuses those cookies.
"""
import json
import os
import re
import sys
import time
from typing import Any, Dict, List

import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from playwright.sync_api import sync_playwright
from crawlers.base_runner import default_paths, run_single_source

K = "boss"
COOKIE_CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "chrome_dev_profile", "boss_cookies.json")


def _norm(x: Any) -> str:
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def _get_cookies() -> List[Dict[str, str]]:
    """Get BOSS cookies directly from Firefox (not cache)."""
    try:
        import browser_cookie3
        cookies = browser_cookie3.firefox(domain_name="zhipin.com")
        ck_list = [{"name": ck.name, "value": ck.value, "domain": ".zhipin.com", "path": "/"}
                   for ck in cookies]
        if ck_list:
            # Cache for backup
            ck_dict = {ck["name"]: ck["value"] for ck in ck_list}
            os.makedirs(os.path.dirname(COOKIE_CACHE), exist_ok=True)
            with open(COOKIE_CACHE, "w", encoding="utf-8") as f:
                json.dump(ck_dict, f, ensure_ascii=False)
            return ck_list
    except Exception as e:
        print(f"  [boss] Firefox cookie error: {e}")

    # Fallback: try cache
    if os.path.exists(COOKIE_CACHE):
        try:
            with open(COOKIE_CACHE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached:
                return [{"name": n, "value": v, "domain": ".zhipin.com", "path": "/"}
                        for n, v in cached.items()]
        except Exception:
            pass
    print("  [boss] No cookies. Log into BOSS in Firefox first.")
    return []


def _crawl_boss(city: str = "101020100", keyword: str = "实习",
                max_pages: int = 5) -> List[Dict[str, str]]:
    """Scrape BOSS jobs using Playwright Firefox + real cookies."""
    cookies = _get_cookies()
    if not cookies:
        print("  [boss] No cookies found. Log into BOSS in Firefox first.")
        return []

    all_rows: List[Dict[str, str]] = []

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        ctx = browser.new_context(
            locale="zh-CN",
            viewport={"width": 1920, "height": 1080},
        )
        # Hide automation traces
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        for pg in range(1, max_pages + 1):
            base_query = f"query={keyword}&city={city}"
            if pg > 1:
                base_query += f"&page={pg}"
            url = f"https://www.zhipin.com/web/geek/job?{base_query}"

            # Navigate twice: first triggers JS security challenge, second passes with token
            for attempt in range(2):
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(5000)
                except Exception as e:
                    print(f"  [boss] nav error: {e}")
                    break
                curr = page.url
                if "security" in curr or "about:blank" in curr:
                    print(f"  [boss] attempt {attempt+1}: security page, waiting...")
                    page.wait_for_timeout(10000)
                else:
                    break

            page.wait_for_timeout(3000)

            if "security" in page.url or "about:blank" in page.url:
                print(f"  [boss] Anti-bot triggered on page {pg}")
                break

            try:
                jobs = page.evaluate("""(pg) => {
                    const cards = document.querySelectorAll('[class*=job-card]');
                    const results = [];
                    const limit = pg > 1 ? 50 : 60;
                    cards.forEach(c => {
                        if (results.length >= limit) return;
                        if (!c.querySelector('[class*=job-name]')) return;
                        const getText = (s) => {
                            const el = c.querySelector(s);
                            return el ? el.innerText.trim() : '';
                        };
                        const link = c.querySelector('a[href*=\"/job_detail/\"]');
                        const href = link ? (link.getAttribute('href') || '') : '';
                        const jobId = href.match(/\\/job_detail\\/([^\\/]+)\\.html/);
                        results.push({
                            name: getText('.job-name, [class*=job-name]'),
                            salary: getText('.job-salary, [class*=job-salary]'),
                            company: getText('.boss-name, [class*=boss-name]'),
                            city: getText('.company-location'),
                            tags: Array.from(c.querySelectorAll('.tag-list li')).map(function(l){return l.innerText.trim();}).join(' | '),
                            url: href.startsWith('http') ? href : 'https://www.zhipin.com' + href,
                            jobId: jobId ? jobId[1] : '',
                        });
                    });
                    return results;
                }""", pg)
            except Exception:
                break

            if not jobs:
                break

            for j in jobs:
                all_rows.append({
                    "name": _norm(j.get("name", "")),
                    "company": _norm(j.get("company", "")),
                    "city": _norm(j.get("city", "")),
                    "salary": _norm(j.get("salary", "")),
                    "url": _norm(j.get("url", "")),
                    "external_job_id": _norm(j.get("jobId", "")),
                    "jd_raw": "",
                    "publish_time": "",
                    "deadline": "",
                    "recruit_type": "实习",
                    "raw_tags": _norm(j.get("tags", "")),
                    "duration": "",
                    "academic": "",
                    "source": K,
                    "collect_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                })

            print(f"  [boss] page {pg}: {len(jobs)} jobs (total {len(all_rows)})")
            time.sleep(2)

        page.close()
        ctx.close()
        browser.close()

    # Enrich with JD from mobile detail pages
    if all_rows:
        enriched = _fetch_boss_details(all_rows)
        for r in enriched:
            for orig in all_rows:
                if orig.get("url") == r.get("url"):
                    orig["jd_raw"] = r.get("jd_raw", orig.get("jd_raw", ""))
                    orig["publish_time"] = r.get("publish_time", orig.get("publish_time", ""))
                    break

    # Dedup
    seen = set()
    dedup = []
    for r in all_rows:
        u = r.get("url", "")
        if u and u not in seen:
            seen.add(u)
            dedup.append(r)
    return dedup


def _fetch_boss_details(jobs: List[Dict[str, str]], max_details: int = 30) -> List[Dict[str, str]]:
    """Visit mobile detail pages to extract JD text."""
    cookies = _get_cookies()
    if not cookies:
        return []
    results = []
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        ctx = browser.new_context(locale="zh-CN", viewport={"width": 400, "height": 800})
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        done = 0
        for job in jobs:
            if done >= max_details:
                break
            job_id = job.get("external_job_id", "")
            if not job_id:
                continue
            url = f"https://m.zhipin.com/job_detail/{job_id}.html"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000)
            except Exception:
                continue
            if "about:blank" in page.url or "security" in page.url:
                continue

            try:
                text = page.inner_text("body")
                results.append({
                    "url": job.get("url", ""),
                    "jd_raw": _norm(text[:5000]),
                    "publish_time": "",
                })
                done += 1
            except Exception:
                continue

        page.close()
        ctx.close()
        browser.close()

    print(f"  [boss] fetched {len(results)} detail pages")
    return results


def run() -> dict:
    paths = default_paths(K)
    city = os.getenv("BOSS_CITY", "101020100")
    keyword = os.getenv("BOSS_KEYWORD", "实习")
    max_pages = int(os.getenv("BOSS_MAX_PAGES", "5"))

    result = run_single_source(
        K,
        lambda: _crawl_boss(city=city, keyword=keyword, max_pages=max_pages),
        paths["raw"],
    )
    pd.DataFrame([result]).to_csv(paths["health"], index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [{"company": "BOSS直聘", "source": K, "strategy": "firefox+dom", "total": result["rows"], "status": result["status"]}]
    ).to_csv(paths["param_audit"], index=False, encoding="utf-8-sig")
    result["param_audit_path"] = paths["param_audit"]
    return result


if __name__ == "__main__":
    r = run()
    print(f"boss_rows {r['rows']} {r['status']} {r['raw_path']}")
