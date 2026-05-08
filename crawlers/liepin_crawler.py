import os, re, sys, time
from typing import Any, Dict, List
import pandas as pd
from playwright.sync_api import sync_playwright

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from crawlers.base_runner import default_paths, run_single_source

K = "liepin"


def _norm(x: Any) -> str:
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def _crawl_liepin(city: str = "010", keyword: str = "",
                  max_pages: int = 5) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--proxy-server=direct://"])
        ctx = browser.new_context()
        page = ctx.new_page()

        all_job_data = []
        def on_resp(resp):
            if "pc-search-job" in resp.url and "cond-init" not in resp.url:
                try:
                    d = resp.json().get("data", {}).get("data", {})
                    job_list = d.get("jobCardList", [])
                    all_job_data.extend(job_list)
                except Exception:
                    pass

        page.on("response", on_resp)

        for pg in range(1, max_pages + 1):
            url = f"https://www.liepin.com/zhaopin/?city={city}&key={keyword}&curPage={pg}"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000)
            except Exception:
                break

        page.close()
        ctx.close()
        browser.close()

    seen = set()
    for item in all_job_data:
        job = item.get("job", {})
        comp = item.get("comp", {})
        job_id = _norm(job.get("jobId", ""))
        link = _norm(job.get("link", ""))
        if job_id in seen:
            continue
        seen.add(job_id)

        rows.append({
            "name": _norm(job.get("title", "")),
            "company": _norm(comp.get("compName", "")),
            "city": _norm(job.get("dq", "")),
            "salary": _norm(job.get("salary", "")),
            "jd_raw": "",
            "url": link or f"https://www.liepin.com/lptjob/{job_id}",
            "external_job_id": job_id,
            "publish_time": _norm(job.get("refreshTime", "")),
            "deadline": "",
            "recruit_type": _norm(job.get("campusJobKind", "")),
            "raw_tags": " ".join(_norm(t) for t in job.get("labels", [])),
            "source": K,
            "collect_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

    print(f"  [liepin] {len(all_job_data)} raw, {len(rows)} unique")
    return rows


def run() -> dict:
    paths = default_paths(K)
    city = os.getenv("LIEPIN_CITY", "010")
    keyword = os.getenv("LIEPIN_KEYWORD", "实习")
    max_pages = int(os.getenv("LIEPIN_MAX_PAGES", "3"))

    result = run_single_source(
        K, lambda: _crawl_liepin(city=city, keyword=keyword, max_pages=max_pages), paths["raw"]
    )
    pd.DataFrame([result]).to_csv(paths["health"], index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [{"company": "猎聘", "source": K, "strategy": "api", "total": result["rows"], "status": result["status"]}]
    ).to_csv(paths["param_audit"], index=False, encoding="utf-8-sig")
    result["param_audit_path"] = paths["param_audit"]
    return result


if __name__ == "__main__":
    r = run()
    print(f"liepin_rows {r['rows']} {r['status']} {r['raw_path']}")
