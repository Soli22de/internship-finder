"""
BOSS直聘 crawler — connects to REAL user Chrome via CDP.
Requires Chrome running on port 9222 with a logged-in BOSS session.
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
CHROME_URL = "http://localhost:9222"


def _norm(x: Any) -> str:
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def _crawl_boss(city: str = "101020100", keyword: str = "数据分析",
                max_pages: int = 20) -> List[Dict[str, str]]:
    """Connect to user's Chrome, scrape BOSS jobs via API interception."""
    all_rows: List[Dict[str, str]] = []

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CHROME_URL)
        context = browser.contexts[0]
        page = context.new_page()

        api_payloads: List[Dict] = []

        def on_response(resp):
            url = resp.url
            ct = resp.headers.get("content-type", "")
            if "json" not in ct:
                return
            if "/api" not in url and "/wapi" not in url:
                return
            if "zhipin.com" not in url:
                return
            try:
                data = resp.json()
                api_payloads.append({"url": url, "data": data})
            except Exception:
                pass

        page.on("response", on_response)

        base_url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city}"
        page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)

        # Scroll to trigger lazy load
        for _ in range(8):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(800)

        # Also try clicking next page
        for pg in range(2, max_pages + 1):
            try:
                next_btn = page.locator(".page-next, .next, [class*=next]").first
                if next_btn.is_visible():
                    next_btn.click()
                    page.wait_for_timeout(3000)
                else:
                    break
            except Exception:
                break

        # Try to extract jobs from API payloads
        for payload in api_payloads:
            rows = _parse_boss_api(payload["data"], payload["url"])
            all_rows.extend(rows)

        # Fallback: parse DOM if API extraction returned nothing
        if not all_rows:
            rows = _parse_boss_dom(page)
            all_rows.extend(rows)

        page.close()
        # Don't close context/browser in CDP mode

    # Dedup
    seen = set()
    dedup = []
    for r in all_rows:
        u = r.get("url", "")
        if u and u not in seen:
            seen.add(u)
            dedup.append(r)
    return dedup


def _parse_boss_api(data: Dict, url: str) -> List[Dict[str, str]]:
    """Extract jobs from BOSS API JSON response."""
    rows = []

    def walk(obj):
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from walk(v)
        elif isinstance(obj, list):
            for x in obj:
                yield from walk(x)

    for d in walk(data):
        if not isinstance(d, dict):
            continue
        job_id = _norm(d.get("jobId") or d.get("encryptJobId") or "")
        name = _norm(d.get("jobName") or d.get("name") or "")
        if not name or not job_id:
            continue
        salary = _norm(d.get("salaryDesc") or d.get("salary") or "")
        city = _norm(d.get("cityName") or d.get("city") or "")
        company = ""
        brand = d.get("brandName") or d.get("brand") or {}
        if isinstance(brand, dict):
            company = _norm(brand.get("brandName") or "")
        else:
            company = _norm(brand)
        if not company:
            company = _norm(d.get("brandName", ""))

        rows.append({
            "name": name,
            "company": company,
            "city": city,
            "salary": salary,
            "jd_raw": _norm(d.get("jobDesc", "")),
            "url": f"https://www.zhipin.com/job_detail/{job_id}.html",
            "external_job_id": job_id,
            "publish_time": _norm(d.get("firstPublishTime", "")),
            "deadline": "",
            "recruit_type": "实习",
            "source": K,
            "collect_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return rows


def _parse_boss_dom(page) -> List[Dict[str, str]]:
    """Fallback: extract from DOM if API interception failed."""
    try:
        cards_data = page.evaluate("""() => {
            const cards = document.querySelectorAll('.job-card-wrapper, .job-card-box, [class*=job-card]');
            return Array.from(cards).slice(0, 50).map(c => {
                const link = c.querySelector('a[href*="/job_detail/"]');
                const href = link ? link.getAttribute('href') : '';
                const title = link ? link.innerText.trim() : '';
                const salary = (c.querySelector('.salary') || c.querySelector('.job-salary') || {}).innerText || '';
                const company = (c.querySelector('.company-name') || c.querySelector('.brand-name') || c.querySelector('[class*=company]') || {}).innerText || '';
                const city = (c.querySelector('.job-area') || c.querySelector('.city') || {}).innerText || '';
                return {href, title, salary, company, city};
            });
        }""")
    except Exception:
        return []

    rows = []
    for cd in cards_data or []:
        href = str(cd.get("href", ""))
        url = href if href.startswith("http") else f"https://www.zhipin.com{href}"
        job_id = re.search(r"/job_detail/(.+?)\.html", url)
        job_id = job_id.group(1) if job_id else url

        if not url:
            continue

        rows.append({
            "name": _norm(cd.get("title", "")),
            "company": _norm(cd.get("company", "")),
            "city": _norm(cd.get("city", "上海")),
            "salary": _norm(cd.get("salary", "")),
            "jd_raw": "",
            "url": url,
            "external_job_id": job_id,
            "publish_time": "",
            "deadline": "",
            "recruit_type": "实习",
            "source": K,
            "collect_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return rows


def run() -> dict:
    paths = default_paths(K)
    city = os.getenv("BOSS_CITY", "101020100")
    keyword = os.getenv("BOSS_KEYWORD", "数据分析")
    max_pages = int(os.getenv("BOSS_MAX_PAGES", "5"))

    result = run_single_source(
        K,
        lambda: _crawl_boss(city=city, keyword=keyword, max_pages=max_pages),
        paths["raw"],
    )
    pd.DataFrame([result]).to_csv(paths["health"], index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [{"company": "BOSS直聘", "source": K, "strategy": "cdp", "total": result["rows"], "status": result["status"]}]
    ).to_csv(paths["param_audit"], index=False, encoding="utf-8-sig")
    result["param_audit_path"] = paths["param_audit"]
    return result


if __name__ == "__main__":
    r = run()
    print(f"boss_rows {r['rows']} {r['status']} {r['raw_path']}")
