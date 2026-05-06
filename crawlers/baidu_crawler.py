import os
import sys

import pandas as pd
from playwright.sync_api import sync_playwright

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from crawlers.base_runner import default_paths, run_single_source
from official_multi_crawler import SOURCES, crawl_one_source


def _fetch_baidu() -> list:
    conf = next((x for x in SOURCES if x.get("source") in {"official_baidu", "baidu"}), None)
    if conf is None:
        return []
    with sync_playwright() as p:
        return crawl_one_source(p, conf, use_cdp=False)


def run() -> dict:
    paths = default_paths("baidu")
    result = run_single_source("baidu", _fetch_baidu, paths["raw"])
    pd.DataFrame([result]).to_csv(paths["health"], index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [{"company": "百度", "source": "official_baidu", "strategy": "default", "total": result["rows"], "status": result["status"]}]
    ).to_csv(paths["param_audit"], index=False, encoding="utf-8-sig")
    result["param_audit_path"] = paths["param_audit"]
    return result


if __name__ == "__main__":
    r = run()
    print("baidu_rows", r["rows"], r["status"], r["raw_path"])
