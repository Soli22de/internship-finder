import os
from typing import Dict, List

import pandas as pd

from crawlers.schema import FIELD_ORDER


def ensure_output_dirs() -> Dict[str, str]:
    base = "outputs"
    raw_dir = os.path.join(base, "raw")
    reports_dir = os.path.join(base, "reports")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    return {"raw": raw_dir, "reports": reports_dir}


def rows_to_frame(rows: List[Dict[str, str]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        frame = pd.DataFrame(columns=FIELD_ORDER)
    for c in FIELD_ORDER:
        if c not in frame.columns:
            frame[c] = ""
    return frame[FIELD_ORDER].copy()


def write_rows_csv(rows: List[Dict[str, str]], output_path: str) -> str:
    frame = rows_to_frame(rows)
    frame.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def append_report_rows(output_path: str, rows: List[Dict[str, str]]) -> str:
    frame = pd.DataFrame(rows)
    if os.path.exists(output_path):
        old = pd.read_csv(output_path, keep_default_na=False)
        frame = pd.concat([old, frame], ignore_index=True)
    frame.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path

