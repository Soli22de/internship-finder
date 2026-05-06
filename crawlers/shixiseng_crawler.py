"""
Shixiseng crawler — headless Playwright, no RPC server.
Integrated into the main crawlers/ architecture (same pattern as bytedance_crawler).

Handles font encryption via optional font_map.json.
Without font_map, encrypted fields (salary, company name) will show garbled characters,
but URLs and detail-page JD text are typically unencrypted.
"""
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from playwright.sync_api import sync_playwright

from crawlers.base_runner import default_paths, run_single_source

K = "shixiseng"
BASE_URL = "https://www.shixiseng.com"
SEARCH_URL = f"{BASE_URL}/interns"
FONT_MAP_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "shixiseng_font_map.json")


def _norm(x: Any) -> str:
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def load_font_map(path: str = "") -> Dict[str, str]:
    p = path or FONT_MAP_PATH
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {k: v for k, v in raw.items() if v}
    except Exception:
        return {}


def apply_font_map(text: str, font_map: Dict[str, str]) -> str:
    if not text or not font_map:
        return text or ""
    for garbled, real in font_map.items():
        text = text.replace(garbled, real)
    return text


def _fetch_one_page(page, page_num: int, city: str, keyword: str, font_map: Dict[str, str]) -> List[Dict[str, str]]:
    """Fetch one page of search results, return list of partial job records with URLs."""
    params = {"page": page_num, "city": city}
    if keyword:
        params["keyword"] = keyword
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{SEARCH_URL}?{qs}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception:
        return []
    page.wait_for_timeout(4000)

    # Scroll to trigger lazy loading
    for _ in range(6):
        page.mouse.wheel(0, 1500)
        page.wait_for_timeout(600)

    # Extract job cards
    cards = page.locator(".intern-wrap")
    count = cards.count()
    if count == 0:
        return []

    rows: List[Dict[str, str]] = []
    for i in range(count):
        try:
            card = cards.nth(i)
            # URL — always unencrypted (href attribute)
            link_el = card.locator("a.intern-detail__title").first
            detail_url = ""
            try:
                href = link_el.get_attribute("href") or ""
                detail_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            except Exception:
                pass

            if not detail_url:
                # Try alternative link selectors
                for a in card.locator("a").all():
                    try:
                        h = a.get_attribute("href") or ""
                        if "/intern/" in h:
                            detail_url = h if h.startswith("http") else f"{BASE_URL}{h}"
                            break
                    except Exception:
                        pass

            job_id = re.search(r"/intern/([A-Za-z0-9_]+)", detail_url)
            job_id = job_id.group(1) if job_id else ""

            # Title (may be encrypted)
            title = ""
            try:
                title = apply_font_map(_norm(link_el.inner_text()), font_map)
            except Exception:
                pass

            # Company
            company = ""
            try:
                company_div = card.locator(".intern-detail__company a[title]").first
                company = apply_font_map(_norm(company_div.get_attribute("title") or ""), font_map)
            except Exception:
                try:
                    company_div2 = card.locator(".intern-detail__company").first
                    company = apply_font_map(_norm(company_div2.inner_text()), font_map)
                except Exception:
                    pass

            # Salary
            salary = ""
            try:
                salary_el = card.locator(".day_money").first
                salary = apply_font_map(_norm(salary_el.inner_text()), font_map)
            except Exception:
                pass

            # Location
            location = city
            try:
                loc_el = card.locator(".city").first
                location = apply_font_map(_norm(loc_el.inner_text()), font_map)
            except Exception:
                pass

            rows.append({
                "external_job_id": job_id,
                "name": title,
                "company": company or "未知公司",
                "city": location,
                "salary": salary,
                "url": detail_url,
                "source": K,
                "recruit_type": "实习",
                "collect_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "publish_time": "unknown",
                "deadline": "unknown",
                "jd_raw": "",
                "raw_tags": keyword if keyword else "",
            })
        except Exception:
            continue

    return rows


def _fetch_detail(page, job: Dict[str, str], font_map: Dict[str, str]) -> Dict[str, str]:
    """Visit a detail page and extract full JD text."""
    url = job.get("url", "")
    if not url:
        return {}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception:
        return {}
    page.wait_for_timeout(3000)

    result: Dict[str, str] = {}
    try:
        content = page.inner_text("body")
        content = apply_font_map(content, font_map)

        # Extract JD sections
        resp = ""
        req = ""
        for marker, section in [("岗位职责", "resp"), ("职位描述", "resp"), ("工作职责", "resp"),
                                ("任职要求", "req"), ("职位要求", "req"), ("岗位要求", "req")]:
            idx = content.find(marker)
            if idx >= 0:
                part = content[idx + len(marker):]
                end_markers = ["任职要求", "职位要求", "岗位要求", "工作地址", "截止日期", "福利待遇"]
                end = len(part)
                for em in end_markers:
                    eidx = part.find(em)
                    if 0 < eidx < end:
                        end = eidx
                text = _norm(part[:end])
                if section == "resp":
                    resp = text
                else:
                    req = text

        jd_raw = resp
        if req:
            jd_raw = f"{resp}\n岗位要求：{req}" if resp else req
        if not jd_raw:
            jd_raw = _norm(content[:2000])

        result["jd_raw"] = jd_raw

        # Extract publish time
        pub_match = re.search(r"(20\d{2}[-/]\d{1,2}[-/]\d{1,2})", content)
        if pub_match:
            result["publish_time"] = pub_match.group(1).replace("/", "-")
        elif "天前" in content:
            m = re.search(r"(\d+)天前", content)
            if m:
                import datetime
                d = datetime.date.today() - datetime.timedelta(days=int(m.group(1)))
                result["publish_time"] = d.isoformat()

        # Extract deadline
        dl_match = re.search(r"截止日期[：:]\s*(20\d{2}[-/]\d{1,2}[-/]\d{1,2})", content)
        if dl_match:
            result["deadline"] = dl_match.group(1).replace("/", "-")

        # Try to get better company name
        comp_match = re.search(r"公司[：:]\s*(.{2,30})", content)
        if comp_match and "未知" in job.get("company", ""):
            result["company"] = apply_font_map(_norm(comp_match.group(1)), font_map)

    except Exception:
        pass

    return result


def _fetch_shixiseng(
    city: str = "上海",
    keywords: Optional[List[str]] = None,
    max_pages: int = 20,
    fetch_details: bool = True,
    max_details: int = 200,
) -> List[Dict[str, str]]:
    font_map = load_font_map()
    all_rows: List[Dict[str, str]] = []
    seen_urls = set()

    if keywords is None:
        keywords = ["", "数据分析", "数据", "产品", "运营", "商业分析", "策略", "算法"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        page = ctx.new_page()

        try:
            for keyword in keywords:
                kw = keyword.strip() if keyword else ""
                for page_num in range(1, max_pages + 1):
                    page_rows = _fetch_one_page(page, page_num, city, kw, font_map)
                    if not page_rows:
                        break
                    for row in page_rows:
                        url = row.get("url", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_rows.append(row)
                    print(f"  [shixiseng] kw={kw or '(all)'} page={page_num} cards={len(page_rows)} total={len(all_rows)}")
                    time.sleep(2)
        finally:
            page.close()
            ctx.close()
            browser.close()

    # Dedup by URL
    dedup: List[Dict[str, str]] = []
    seen = set()
    for r in all_rows:
        u = r.get("url", "")
        if u and u not in seen:
            seen.add(u)
            dedup.append(r)

    # Fetch detail pages
    if fetch_details and dedup:
        details_fetched = 0
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
            )
            page = ctx.new_page()
            try:
                for row in dedup:
                    if details_fetched >= max_details:
                        break
                    detail = _fetch_detail(page, row, font_map)
                    if detail:
                        for k, v in detail.items():
                            if v:
                                row[k] = v
                        details_fetched += 1
                    if details_fetched % 10 == 0:
                        print(f"  [shixiseng] details: {details_fetched}/{min(len(dedup), max_details)}")
                    time.sleep(1.5)
            finally:
                page.close()
                ctx.close()
                browser.close()

    return dedup


def run() -> dict:
    paths = default_paths(K)
    city = os.getenv("SHIXISENG_CITY", "上海")
    max_pages = int(os.getenv("SHIXISENG_MAX_PAGES", "3"))
    max_details = int(os.getenv("SHIXISENG_MAX_DETAILS", "50"))

    result = run_single_source(
        K,
        lambda: _fetch_shixiseng(city=city, max_pages=max_pages, max_details=max_details),
        paths["raw"],
    )
    pd.DataFrame([result]).to_csv(paths["health"], index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [{"company": "实习僧", "source": K, "strategy": "playwright_headless", "total": result["rows"], "status": result["status"]}]
    ).to_csv(paths["param_audit"], index=False, encoding="utf-8-sig")
    result["param_audit_path"] = paths["param_audit"]
    return result


if __name__ == "__main__":
    r = run()
    print(f"shixiseng_rows {r['rows']} {r['status']} {r['raw_path']}")
