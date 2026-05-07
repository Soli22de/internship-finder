"""
Baidu careers crawler — Playwright Firefox + DOM extraction.
Baidu uses SSR (server-side rendering), so job data is embedded in the HTML.
"""
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

K = "baidu"
BASE_URL = "https://talent.baidu.com"


def _norm(x: Any) -> str:
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def _crawl_baidu(max_pages: int = 10) -> List[Dict[str, str]]:
    all_rows: List[Dict[str, str]] = []

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = ctx.new_page()

        for pg in range(1, max_pages + 1):
            url = f"{BASE_URL}/jobs/list?recruitType=2&pageNum={pg}"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000)
            except Exception:
                break

            if "about:blank" in page.url:
                break

            # Extract jobs from DOM
            try:
                jobs = page.evaluate("""(pg) => {
                    const cards = document.querySelectorAll('.post-item, .job-item, [class*=post-card]');
                    const results = [];
                    const getText = (el, s) => {
                        const found = el.querySelector(s);
                        if (found) {
                            const txt = found.innerText.trim();
                            return txt;
                        }
                        return '';
                    };
                    cards.forEach(c => {
                        const title = getText(c, '.post-name, .title, .job-name');
                        if (!title) return;
                        results.push({
                            title: title,
                            company: '百度',
                            city: getText(c, '.city, .location, .addr, .place'),
                            salary: getText(c, '.salary, .money, .pay'),
                            date: getText(c, '.date, .time, .pub-date'),
                            tags: getText(c, '.type, .tag, .label, .recruit-type'),
                        });
                    });
                    return results;
                }""", pg)
            except Exception:
                break

            if not jobs:
                # Fallback: parse text from page body
                body = page.inner_text("body")
                lines = [l.strip() for l in body.split("\n") if l.strip()]
                print(f"  [baidu] pg{pg}: no cards, {len(lines)} text lines")
                # Try regex: find job-like patterns
                for m in re.finditer(r"(.{2,30})\(([A-Z0-9]+)\)", body):
                    title = _norm(m.group(1))
                    if title and len(title) > 3:
                        all_rows.append({
                            "name": title,
                            "company": "百度",
                            "city": "",
                            "salary": "",
                            "url": f"{BASE_URL}/jobs/list?recruitType=2",
                            "external_job_id": "",
                            "jd_raw": "",
                            "publish_time": "",
                            "deadline": "",
                            "recruit_type": "校园招聘",
                            "source": K,
                            "collect_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                        })
                break
            else:
                for j in jobs:
                    all_rows.append({
                        "name": _norm(j.get("title", "")),
                        "company": "百度",
                        "city": _norm(j.get("city", "")),
                        "salary": _norm(j.get("salary", "")),
                        "url": url,
                        "external_job_id": "",
                        "jd_raw": "",
                        "publish_time": _norm(j.get("date", "")),
                        "deadline": "",
                        "recruit_type": _norm(j.get("tags", "")),
                        "source": K,
                        "collect_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    })

                print(f"  [baidu] pg{pg}: {len(jobs)} jobs (total {len(all_rows)})")
                time.sleep(1)

        page.close()
        ctx.close()
        browser.close()

    # Dedup
    seen = set()
    dedup = []
    for r in all_rows:
        u = r.get("name", "") + r.get("company", "")
        if u and u not in seen:
            seen.add(u)
            dedup.append(r)
    return dedup


def run() -> dict:
    paths = default_paths(K)
    max_pages = int(os.getenv("BAIDU_MAX_PAGES", "5"))

    result = run_single_source(
        K, lambda: _crawl_baidu(max_pages=max_pages), paths["raw"]
    )
    pd.DataFrame([result]).to_csv(paths["health"], index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [{"company": "百度", "source": K, "strategy": "firefox+dom", "total": result["rows"], "status": result["status"]}]
    ).to_csv(paths["param_audit"], index=False, encoding="utf-8-sig")
    result["param_audit_path"] = paths["param_audit"]
    return result


if __name__ == "__main__":
    r = run()
    print(f"baidu_rows {r['rows']} {r['status']} {r['raw_path']}")
