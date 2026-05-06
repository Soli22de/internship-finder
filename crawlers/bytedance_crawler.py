import os
import sys

import pandas as pd
from playwright.sync_api import sync_playwright

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from crawlers.base_runner import default_paths, run_single_source
from official_multi_crawler import SOURCES, crawl_one_source


def _fetch_bytedance() -> list:
    conf = next((x for x in SOURCES if x.get("source") in {"official_bytedance", "bytedance"}), None)
    if conf is None:
        return []
    with sync_playwright() as p:
        return crawl_one_source(p, conf, use_cdp=False)


def run() -> dict:
    paths = default_paths("bytedance")
    result = run_single_source("bytedance", _fetch_bytedance, paths["raw"])
    pd.DataFrame([result]).to_csv(paths["health"], index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [{"company": "字节跳动", "source": "official_bytedance", "strategy": "default", "total": result["rows"], "status": result["status"]}]
    ).to_csv(paths["param_audit"], index=False, encoding="utf-8-sig")
    result["param_audit_path"] = paths["param_audit"]
    return result


if __name__ == "__main__":
    r = run()
    print("bytedance_rows", r["rows"], r["status"], r["raw_path"])
