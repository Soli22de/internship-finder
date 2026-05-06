import os
import re
from datetime import datetime

import pandas as pd


REPORT_DIR = r"outputs\reports"
SOURCE_FILE = os.path.join(REPORT_DIR, "internship_post_screening_result.csv")
TARGET_FILE = os.path.join(REPORT_DIR, "time_constraints_report.csv")


def extract_time_constraints(text: str) -> dict:
    t = str(text)
    days = 0
    months = 0
    exp_years = 0
    grad_year = 0
    arrival = ""
    m_day = re.search(r"每周.{0,6}?(\d)\s*天", t)
    if m_day:
        days = int(m_day.group(1))
    m_month = re.search(r"(\d+)\s*个?月", t)
    if m_month:
        months = int(m_month.group(1))
    m_exp = re.search(r"(\d+)\s*年.{0,4}经验", t)
    if m_exp:
        exp_years = int(m_exp.group(1))
    m_grad = re.search(r"(202[5-9])届", t)
    if m_grad:
        grad_year = int(m_grad.group(1))
    if "尽快到岗" in t or "立即到岗" in t:
        arrival = "immediate"
    elif "一周内到岗" in t:
        arrival = "within_1_week"
    elif "两周内到岗" in t or "2周内到岗" in t:
        arrival = "within_2_weeks"
    return {
        "intern_days_required": days,
        "intern_months_required": months,
        "experience_years_required": exp_years,
        "grad_year_required": grad_year,
        "arrival_required": arrival,
    }


def main() -> None:
    if not os.path.exists(SOURCE_FILE):
        raise FileNotFoundError(SOURCE_FILE)
    df = pd.read_csv(SOURCE_FILE, keep_default_na=False)
    rows = []
    for _, r in df.iterrows():
        text = f"{r.get('name','')} {r.get('jd_raw','')} {r.get('requirement','')}"
        info = extract_time_constraints(text)
        rows.append(
            {
                "company": r.get("company", ""),
                "job_name": r.get("name", ""),
                "url": r.get("url", ""),
                "intern_days_required": info["intern_days_required"],
                "intern_months_required": info["intern_months_required"],
                "experience_years_required": info["experience_years_required"],
                "grad_year_required": info["grad_year_required"],
                "arrival_required": info["arrival_required"],
                "is_hard_pass": bool(r.get("hard_pass", False)),
                "extract_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    pd.DataFrame(rows).to_csv(TARGET_FILE, index=False, encoding="utf-8-sig")
    print("done", TARGET_FILE, len(rows))


if __name__ == "__main__":
    main()
