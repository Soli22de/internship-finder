"""Unified crawl engine — wraps all crawler functions, writes to DB."""
import hashlib
import os
import sys
import time
import traceback
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import upsert_job, mark_inactive_stale, log_crawl_run


def _norm(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def _content_hash(row: Dict) -> str:
    seed = f"{_norm(row.get('title',''))}|{_norm(row.get('company',''))}|{_norm(row.get('jd_raw',''))[:200]}"
    return hashlib.md5(seed.encode()).hexdigest()


class CrawlResult:
    def __init__(self, source: str, rows: List[Dict], duration_ms: int, error: str = ""):
        self.source = source
        self.rows = rows
        self.duration_ms = duration_ms
        self.error = error
        self.new = 0
        self.updated = 0
        self.unchanged = 0


def ingest_rows(source: str, raw_rows: List[Dict]) -> Tuple[int, int, int]:
    """Normalize + upsert rows into DB. Returns (new, updated, unchanged)."""
    if not raw_rows:
        return 0, 0, 0

    active_ids = set()
    new = updated = unchanged = 0

    for r in raw_rows:
        external_id = _norm(r.get("external_job_id") or r.get("url") or "")
        if not external_id:
            external_id = hashlib.md5(
                f"{_norm(r.get('company'))}|{_norm(r.get('title'))}|{_norm(r.get('url'))}".encode()
            ).hexdigest()

        job = {
            "external_id": external_id,
            "source": source,
            "company": _norm(r.get("company", "未知")),
            "title": _norm(r.get("name") or r.get("title", "")),
            "city": _norm(r.get("city", "")),
            "jd_raw": _norm(r.get("jd_raw", "")),
            "salary": _norm(r.get("salary", "")),
            "url": _norm(r.get("url", "")),
            "publish_time": _norm(r.get("publish_time", "")),
            "deadline": _norm(r.get("deadline", "")),
            "recruit_type": _norm(r.get("recruit_type", "")),
            "raw_tags": _norm(r.get("raw_tags", "")),
            "content_hash": _content_hash(r),
        }
        result = upsert_job(job)
        active_ids.add(external_id)
        if result == "new":
            new += 1
        elif result == "updated":
            updated += 1
        else:
            unchanged += 1

    mark_inactive_stale(source, active_ids)
    return new, updated, unchanged


def run_source(source_name: str, fetch_fn, *args, **kwargs) -> CrawlResult:
    """Run one source crawler, ingest into DB, return result."""
    t0 = time.time()
    try:
        rows = fetch_fn(*args, **kwargs) or []
        elapsed = int((time.time() - t0) * 1000)
        new, updated, unchanged = ingest_rows(source_name, rows)
        result = CrawlResult(source_name, rows, elapsed)
        result.new = new
        result.updated = updated
        result.unchanged = unchanged
        log_crawl_run(source_name, "ok", len(rows), new, updated, elapsed)
        return result
    except Exception as e:
        elapsed = int((time.time() - t0) * 1000)
        error_msg = str(e)[:500]
        log_crawl_run(source_name, "failed", 0, 0, 0, elapsed, error_msg)
        return CrawlResult(source_name, [], elapsed, error_msg)


def run_all_sources(company_filter: List[str] = None) -> List[CrawlResult]:
    """Run all enabled source crawlers sequentially. Returns list of results."""
    from config import CRAWLER_CONFIG
    enabled = set(CRAWLER_CONFIG.get("enabled_companies", []))
    if company_filter:
        enabled = enabled & set(company_filter)
    if not enabled:
        return []

    results: List[CrawlResult] = []

    def _run(name, fn, *a, **kw):
        if name in enabled:
            r = run_source(name, fn, *a, **kw)
            results.append(r)
            print(f"  [{name}] {len(r.rows)} rows, {r.new} new, {r.updated} upd, {r.error or 'OK'} ({r.duration_ms}ms)")

    # API-based adapters
    from official_multi_crawler import (
        fetch_tencent_jobs, fetch_kuaishou_jobs_api, fetch_xiaohongshu_jobs_api,
        fetch_meituan_jobs_api, fetch_alibaba_jobs_api, fetch_jd_jobs,
        fetch_bilibili_jobs_api,
    )

    _run("tencent", fetch_tencent_jobs)
    _run("kuaishou", fetch_kuaishou_jobs_api)
    _run("xiaohongshu", fetch_xiaohongshu_jobs_api)
    _run("meituan", fetch_meituan_jobs_api)
    _run("alibaba", fetch_alibaba_jobs_api)
    _run("jd", fetch_jd_jobs)
    _run("bilibili", fetch_bilibili_jobs_api)

    # Playwright-based crawlers (headless self-launch)
    if "bytedance" in enabled:
        from crawlers.bytedance_crawler import _fetch_bytedance
        _run("bytedance", _fetch_bytedance)

    if "baidu" in enabled:
        from crawlers.baidu_crawler import _fetch_baidu
        _run("baidu", _fetch_baidu)

    if "shixiseng" in enabled:
        from crawlers.shixiseng_crawler import _fetch_shixiseng
        _run("shixiseng", lambda: _fetch_shixiseng(city="上海", max_pages=5))

    if "boss" in enabled:
        from crawlers.boss_crawler import _crawl_boss
        _run("boss", lambda: _crawl_boss(max_pages=5))

    return results
