"""Run quick crawl of all sources and populate DB."""
import os, sys, time, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
config.CRAWLER_CONFIG["request_delay_seconds"] = 0.5

from utils.no_proxy import *
from backend.db import init_db, upsert_job
from official_multi_crawler import (
    fetch_tencent_jobs, fetch_kuaishou_jobs_api, fetch_xiaohongshu_jobs_api,
    fetch_meituan_jobs_api, fetch_alibaba_jobs_api, fetch_jd_jobs,
    fetch_bilibili_jobs_api,
)


def run_crawler(name, fn):
    t0 = time.time()
    try:
        rows = fn() or []
        elapsed = time.time() - t0
        print(f"  {name:12s}: {len(rows):4d} rows in {elapsed:.1f}s")
        return rows
    except Exception as e:
        print(f"  {name:12s}: ERROR {str(e)[:60]}")
        return []


def ingest(source, rows):
    new = 0
    for row in rows:
        ext_id = str(row.get("external_job_id", "") or row.get("url", ""))
        job = {
            "external_id": ext_id,
            "source": source,
            "company": str(row.get("company", "") or ""),
            "title": str(row.get("name", "") or row.get("title", "")),
            "city": str(row.get("city", "") or ""),
            "jd_raw": str(row.get("jd_raw", "") or ""),
            "salary": str(row.get("salary", "") or ""),
            "url": str(row.get("url", "") or ""),
            "publish_time": str(row.get("publish_time", "") or ""),
            "deadline": str(row.get("deadline", "") or ""),
            "recruit_type": str(row.get("recruit_type", "") or ""),
            "raw_tags": str(row.get("raw_tags", "") or ""),
            "content_hash": hashlib.md5((source + "|" + ext_id).encode()).hexdigest(),
        }
        r = upsert_job(job)
        if r == "new":
            new += 1
    print(f"    DB: {new} new")
    return new


print("=== Full Crawl ===")
init_db()

all_data = {}

# Fast API crawlers — limited pages for speed
for name, fn, pages in [
    ("kuaishou", lambda: fetch_kuaishou_jobs_api(max_pages=20), 20),
    ("xiaohongshu", lambda: fetch_xiaohongshu_jobs_api(max_pages=20), 20),
    ("jd", fetch_jd_jobs, None),
    ("bilibili", lambda: fetch_bilibili_jobs_api(max_pages=20), 20),
    ("alibaba", lambda: fetch_alibaba_jobs_api(max_pages=20), 20),
    ("tencent", lambda: fetch_tencent_jobs(max_pages=20), 20),
    ("meituan", lambda: fetch_meituan_jobs_api(max_pages=30), 30),
]:
    rows = run_crawler(name, fn)
    if rows:
        ingest(name, rows)

# Playwright crawlers
os.environ["SHIXISENG_MAX_PAGES"] = "3"
os.environ["SHIXISENG_MAX_DETAILS"] = "10"
os.environ["LIEPIN_MAX_PAGES"] = "3"

from crawlers.shixiseng_crawler import _fetch_shixiseng
rows = run_crawler("shixiseng", _fetch_shixiseng, city="上海", max_pages=3, max_details=10)
if rows:
    ingest("shixiseng", rows)

from crawlers.liepin_crawler import _crawl_liepin
rows = run_crawler("liepin", _crawl_liepin, city="010", keyword="实习", max_pages=3)
if rows:
    ingest("liepin", rows)

# Summary
from backend.db import get_db
db = get_db()
total = db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
by_source = db.execute("SELECT source, COUNT(*) FROM jobs GROUP BY source ORDER BY COUNT(*) DESC").fetchall()
db.close()

print(f"\n=== DB Total: {total} rows ===")
for s in by_source:
    print(f"  {s[0]:12s}: {s[1]}")
