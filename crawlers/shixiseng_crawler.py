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
from urllib.parse import urlencode

import pandas as pd
from bs4 import BeautifulSoup

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
    params = {"page": page_num, "city": city}
    if keyword:
        params["keyword"] = keyword
    url = f"{SEARCH_URL}?{urlencode(params)}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        print(f"  [sxs] goto failed: {e}")
        return []
    page.wait_for_timeout(4000)

    # Fast scroll
    for _ in range(4):
        try:
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(300)
        except:
            break

    # Check if cards exist
    try:
        card_count = page.evaluate("document.querySelectorAll('.intern-wrap').length")
    except:
        card_count = 0
    if card_count == 0:
        try:
            url_now = page.url[:80]
        except:
            url_now = "N/A"
        print(f"  [sxs] pg{page_num}: 0 cards, url={url_now}")
        return []

    # Use JS to extract card data in one shot
    rows: List[Dict[str, str]] = []
    cards_data = page.evaluate("""() => {
        const cards = document.querySelectorAll('.intern-wrap');
        const results = [];
        cards.forEach(function(c) {
            var link = c.querySelector('a[href*="/intern/"]');
            var href = link ? link.getAttribute('href') : '';
            var title = link ? link.innerText.trim() : '';
            var companyEl = c.querySelector('.intern-detail__company a[title]');
            var company = companyEl ? companyEl.getAttribute('title') : (
                c.querySelector('.intern-detail__company') ? c.querySelector('.intern-detail__company').innerText.trim() : ''
            );
            var salary = c.querySelector('.day_money') ? c.querySelector('.day_money').innerText.trim() : '';
            var loc = c.querySelector('.city') ? c.querySelector('.city').innerText.trim() : '';
            results.push({href: href, title: title, company: company, salary: salary, loc: loc});
        });
        return results;
    }""")

    if not cards_data:
        return []

    for cd in cards_data:
        detail_url = str(cd.get("href", ""))
        if detail_url and not detail_url.startswith("http"):
            detail_url = f"{BASE_URL}{detail_url}"
        job_id = re.search(r"/intern/([A-Za-z0-9_]+)", detail_url)
        job_id = job_id.group(1) if job_id else ""

        rows.append({
            "external_job_id": job_id,
            "name": apply_font_map(_norm(cd.get("title", "")), font_map),
            "company": apply_font_map(_norm(cd.get("company", "")), font_map) or "未知公司",
            "city": apply_font_map(_norm(cd.get("loc", "")), font_map) or city,
            "salary": apply_font_map(_norm(cd.get("salary", "")), font_map),
            "url": detail_url,
            "source": K,
            "recruit_type": "实习",
            "collect_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "publish_time": "unknown",
            "deadline": "unknown",
            "jd_raw": "",
            "raw_tags": keyword if keyword else "",
        })

    return rows


def _fetch_detail(page, job: Dict[str, str], font_map: Dict[str, str]) -> Dict[str, str]:
    """Visit a detail page and extract full JD text from raw HTML."""
    url = job.get("url", "")
    if not url:
        return {}

    # Try using page's JS context to fetch (bypasses some anti-bot)
    content = ""
    try:
        js = f"""
        (async () => {{
            try {{
                const r = await fetch('{url}', {{credentials: 'include'}});
                return await r.text();
            }} catch(e) {{
                return 'FETCH_ERROR: ' + e.message;
            }}
        }})()
        """
        fetched = page.evaluate(js)
        if not fetched.startswith("FETCH_ERROR") and len(fetched) > 100:
            content = fetched
    except Exception:
        pass

    # If JS fetch failed or returned captcha, try page.goto
    if not content or "code\":100" in content[:200]:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except Exception:
            pass
        page.wait_for_timeout(2000)
        content = page.content()

    result: Dict[str, str] = {}
    try:
        # Use JS-fetched content if available, else page.content()
        html_text = content or page.content()

        soup = BeautifulSoup(html_text, "html.parser")
        content = soup.get_text("\n")
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


def _extract_font_map_from_bytes(font_data: bytes) -> Dict[str, str]:
    """Extract PUA->character mapping from shixiseng's WOFF font file."""
    try:
        from fontTools.ttLib import TTFont
        import io, re
        font = TTFont(io.BytesIO(font_data))
        cmap = font.getBestCmap()
        mapping = {}
        for code, glyph_name in cmap.items():
            if 0xE000 <= code <= 0xF8FF:
                m = re.search(r'uni([0-9A-Fa-f]{2,6})', str(glyph_name))
                if m:
                    actual = int(m.group(1), 16)
                    if 32 <= actual <= 0x10FFFF:
                        mapping[chr(code)] = chr(actual)
        font.close()
        return mapping
    except Exception:
        return {}


def _fetch_shixiseng(
    city: str = "上海",
    keywords: Optional[List[str]] = None,
    max_pages: int = 5,
    max_details: int = 0,
) -> List[Dict[str, str]]:
    font_map = load_font_map()
    all_rows: List[Dict[str, str]] = []
    seen_urls = set()

    if keywords is None:
        keywords = [""]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--proxy-server=direct://"])
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        page = ctx.new_page()
        detail_page = ctx.new_page() if max_details > 0 else None

        # Intercept font file to build font_map live
        live_font_map = {}
        def on_font_response(resp):
            if "iconfonts/file" in resp.url:
                try:
                    data = resp.body()
                    if data and len(data) > 100:
                        fm = _extract_font_map_from_bytes(data)
                        live_font_map.update(fm)
                except Exception:
                    pass
        page.on("response", on_font_response)

        # Merge cached font_map with live-extracted one

        # Merge cached font_map with live-extracted one
        if live_font_map:
            font_map.update(live_font_map)
            print(f"  [shixiseng] font_map live: {len(live_font_map)} chars")

        # Cache the font map for future runs
        if live_font_map:
            try:
                os.makedirs(os.path.dirname(FONT_MAP_PATH), exist_ok=True)
                with open(FONT_MAP_PATH, "w", encoding="utf-8") as f:
                    json.dump(font_map, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        # Now crawl all keywords
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
                    time.sleep(1)

            # Optionally fetch details
            if max_details > 0 and detail_page:
                details_done = 0
                for row in all_rows:
                    if details_done >= max_details:
                        break
                    d = _fetch_detail(detail_page, row, font_map)
                    if d:
                        for k, v in d.items():
                            if v:
                                row[k] = v
                        details_done += 1
                    time.sleep(0.8)
        finally:
            page.close()
            if detail_page:
                detail_page.close()
            ctx.close()
            browser.close()

    # Dedup
    dedup: List[Dict[str, str]] = []
    seen = set()
    for r in all_rows:
        u = r.get("url", "")
        if u and u not in seen:
            seen.add(u)
            dedup.append(r)
    return dedup


def run() -> dict:
    paths = default_paths(K)
    city = os.getenv("SHIXISENG_CITY", "上海")
    max_pages = int(os.getenv("SHIXISENG_MAX_PAGES", "5"))
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
