"""B1: Ingest ResuMiner parquet into SQLite."""
import os, sys, hashlib
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.no_proxy import *
from backend.db import init_db, upsert_job

PARQUET = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ResuMiner", "data", "unified", "jobs.parquet")


def ingest():
    df = pd.read_parquet(PARQUET)
    print(f"ResuMiner parquet: {len(df)} rows, {len(df.columns)} cols")

    new = 0
    for _, row in df.iterrows():
        platform = str(row.get("platform", "unknown"))
        source = f"resuminer_{platform}"
        ext_id = str(row.get("source_job_id", "") or row.get("job_id", ""))

        smin = row.get("salary_min")
        smax = row.get("salary_max")
        unit = str(row.get("salary_unit", ""))
        salary = ""
        if pd.notna(smin) and pd.notna(smax):
            salary = f"{int(smin)}-{int(smax)}"
            if unit and unit != "unknown":
                salary += f"/{unit}"

        skills = row.get("skills", "")
        skills_str = ", ".join(str(s) for s in skills) if hasattr(skills, "__iter__") and not isinstance(skills, str) else str(skills)

        job = {
            "external_id": ext_id,
            "source": source,
            "company": str(row.get("company", "") or ""),
            "title": str(row.get("title", "") or ""),
            "city": str(row.get("city", "") or ""),
            "jd_raw": str(row.get("jd_text", "") or ""),
            "salary": salary,
            "url": str(row.get("url", "") or ""),
            "publish_time": str(row.get("publish_date", "") or "unknown"),
            "deadline": "",
            "recruit_type": str(row.get("job_type", "") or ""),
            "raw_tags": skills_str,
            "content_hash": hashlib.sha1(
                f"{source}|{ext_id}".encode()
            ).hexdigest(),
        }
        r = upsert_job(job)
        if r == "new":
            new += 1

    print(f"De-duped result: {new} new jobs ingested")


if __name__ == "__main__":
    init_db()
    ingest()

    from backend.db import get_db
    db = get_db()
    rows = db.execute("SELECT source, COUNT(*) FROM jobs GROUP BY source ORDER BY COUNT(*) DESC").fetchall()
    db.close()
    print(f"\nDB total after B1: {sum(r[1] for r in rows)}")
    for s in rows:
        print(f"  {s[0]}: {s[1]}")
