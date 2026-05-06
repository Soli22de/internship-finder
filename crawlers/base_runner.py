import time
from typing import Callable, Dict, List

from crawlers.io import ensure_output_dirs, write_rows_csv


def dedup_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    out: List[Dict[str, str]] = []
    for r in rows:
        key = (
            str(r.get("company", "")),
            str(r.get("name", "")),
            str(r.get("city", "")),
            str(r.get("external_job_id", "")),
            str(r.get("jd_raw", ""))[:200],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def run_single_source(
    company_slug: str,
    fetch_fn: Callable[[], List[Dict[str, str]]],
    output_raw_path: str,
) -> Dict[str, str]:
    start = time.time()
    status = "ok"
    message = ""
    rows: List[Dict[str, str]] = []
    try:
        rows = fetch_fn() or []
        rows = dedup_rows(rows)
        write_rows_csv(rows, output_raw_path)
        if not rows:
            status = "failed"
            message = "no_rows"
    except Exception as e:
        status = "failed"
        message = str(e)
    elapsed_ms = int((time.time() - start) * 1000)
    return {
        "company_slug": company_slug,
        "rows": len(rows),
        "status": status,
        "message": message,
        "elapsed_ms": elapsed_ms,
        "raw_path": output_raw_path,
    }


def default_paths(company_slug: str) -> Dict[str, str]:
    d = ensure_output_dirs()
    return {
        "raw": f"{d['raw']}/{company_slug}_official_raw.csv",
        "health": f"{d['reports']}/{company_slug}_fetch_health.csv",
        "param_audit": f"{d['reports']}/{company_slug}_param_audit.csv",
    }

