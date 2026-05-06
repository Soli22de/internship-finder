import os
import sys

import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from crawlers.base_runner import default_paths, run_single_source
from official_multi_crawler import build_source_param_audit, fetch_bilibili_jobs_api


def run() -> dict:
    paths = default_paths("bilibili")
    max_pages = int(os.getenv("BILIBILI_MAX_PAGES", "120"))
    result = run_single_source("bilibili", lambda: fetch_bilibili_jobs_api(max_pages=max_pages), paths["raw"])
    pd.DataFrame([result]).to_csv(paths["health"], index=False, encoding="utf-8-sig")
    audit = build_source_param_audit()
    audit.to_csv(paths["param_audit"], index=False, encoding="utf-8-sig")
    result["param_audit_path"] = paths["param_audit"]
    return result


if __name__ == "__main__":
    r = run()
    print("bilibili_rows", r["rows"], r["status"], r["raw_path"])
