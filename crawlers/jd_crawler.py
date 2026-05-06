import os
import sys

import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from crawlers.base_runner import default_paths, run_single_source
from official_multi_crawler import fetch_jd_jobs


def run() -> dict:
    paths = default_paths("jd")
    result = run_single_source("jd", fetch_jd_jobs, paths["raw"])
    pd.DataFrame([result]).to_csv(paths["health"], index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [{"company": "京东", "source": "official_jd_api", "strategy": "default", "total": result["rows"], "status": result["status"]}]
    ).to_csv(paths["param_audit"], index=False, encoding="utf-8-sig")
    result["param_audit_path"] = paths["param_audit"]
    return result


if __name__ == "__main__":
    r = run()
    print("jd_rows", r["rows"], r["status"], r["raw_path"])
