"""FastAPI backend — unified crawl API + job query + resume matching."""
import json
import os
import sys
import logging
from datetime import datetime
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Bypass VPN proxy — MUST be before any requests import
from utils.no_proxy import *

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from backend.db import get_db, init_db
from backend.matcher import match as llm_match
from backend.feed import FeedRequest, daily_feed

scheduler = BackgroundScheduler()

app = FastAPI(title="Internship Finder API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class CrawlRequest(BaseModel):
    sources: Optional[List[str]] = None


class MatchRequest(BaseModel):
    resume_text: str
    city: str = "上海"
    top_n: int = 20


@app.on_event("startup")
def startup():
    init_db()
    # Schedule: crawl all sources every 3 days at 2:00 AM
    def scheduled_crawl():
        from backend.crawl_engine import run_all_sources
        print(f"[Scheduler] Starting scheduled crawl at {datetime.now()}")
        try:
            results = run_all_sources()
            for r in results:
                print(f"  [{r.source}] {len(r.rows)} rows, {r.new} new, {r.error or 'OK'}")
        except Exception as e:
            print(f"[Scheduler] Crawl failed: {e}")

    scheduler.add_job(
        scheduled_crawl,
        CronTrigger(hour=2, minute=0, day="*/3"),
        id="scheduled_crawl",
        name="Crawl all sources every 3 days",
        replace_existing=True,
    )
    scheduler.start()
    print(f"[API] Scheduler started. Next crawl every 3 days at 2:00 AM")


@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown(wait=False)
    print("[API] Scheduler stopped.")


# ── Health ──────────────────────────────────────────────

@app.get("/api/health")
def health():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1").fetchone()[0]
    sources = db.execute(
        "SELECT source, COUNT(*) as cnt FROM jobs WHERE is_active=1 GROUP BY source ORDER BY cnt DESC"
    ).fetchall()
    last_run = db.execute(
        "SELECT source, MAX(finished_at) as last_run FROM crawl_runs WHERE status='ok' GROUP BY source"
    ).fetchall()
    db.close()
    return {
        "status": "ok",
        "total_active_jobs": total,
        "sources": {r["source"]: r["cnt"] for r in sources},
        "last_runs": {r["source"]: r["last_run"] for r in last_run},
    }


# ── Job Query ───────────────────────────────────────────

@app.get("/api/jobs")
def list_jobs(
    city: str = Query("上海"),
    source: Optional[str] = None,
    keyword: Optional[str] = None,
    active_only: bool = True,
    dedup: bool = True,
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    db = get_db()
    where = "WHERE 1=1"
    params = []
    if active_only:
        where += " AND is_active=1"
    if city:
        where += " AND city LIKE ?"
        params.append(f"%{city}%")
    if source:
        where += " AND source=?"
        params.append(source)
    if keyword:
        where += " AND (title LIKE ? OR jd_raw LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if dedup:
        sql = f"""
            SELECT * FROM (
                SELECT *, COUNT(*) OVER (PARTITION BY dedup_key) AS source_count,
                       ROW_NUMBER() OVER (PARTITION BY dedup_key 
                                          ORDER BY CASE WHEN source LIKE 'resuminer_%' THEN 0 ELSE 1 END,
                                                   first_seen DESC) AS rn
                FROM jobs {where}
            ) sub WHERE rn=1
            ORDER BY first_seen DESC LIMIT ? OFFSET ?
        """
    else:
        sql = f"SELECT * FROM jobs {where} ORDER BY first_seen DESC LIMIT ? OFFSET ?"

    params_ext = params + [limit, offset]
    rows = db.execute(sql, params_ext).fetchall()

    # Total count (dedup-aware)
    if dedup:
        total_sql = f"SELECT COUNT(DISTINCT dedup_key) FROM jobs {where}"
    else:
        total_sql = f"SELECT COUNT(*) FROM jobs {where}"
    total = db.execute(total_sql, params).fetchone()[0]
    db.close()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "jobs": [dict(r) for r in rows],
    }


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "Job not found")
    return dict(row)


# ── Crawl Triggers ──────────────────────────────────────

@app.post("/api/crawl")
def trigger_crawl(req: CrawlRequest = None):
    from backend.crawl_engine import run_all_sources

    sources = req.sources if req and req.sources else None
    results = run_all_sources(sources)
    return {
        "total_sources": len(results),
        "results": [
            {
                "source": r.source,
                "rows": len(r.rows),
                "new": r.new,
                "updated": r.updated,
                "unchanged": r.unchanged,
                "duration_ms": r.duration_ms,
                "error": r.error or "",
            }
            for r in results
        ],
    }


@app.post("/api/crawl/{source}")
def trigger_crawl_one(source: str):
    from backend.crawl_engine import run_all_sources

    results = run_all_sources([source])
    if not results:
        raise HTTPException(404, f"Source '{source}' not found or not enabled")
    r = results[0]
    return {
        "source": r.source,
        "rows": len(r.rows),
        "new": r.new,
        "updated": r.unchanged,
        "duration_ms": r.duration_ms,
        "error": r.error or "",
    }


# ── Resume Match (keyword-based, upgrade to semantic later) ──

@app.post("/api/match")
def match_resume(req: MatchRequest):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM jobs WHERE is_active=1 AND city LIKE ? ORDER BY first_seen DESC LIMIT 500",
        (f"%{req.city}%",),
    ).fetchall()
    db.close()

    resume_lower = req.resume_text.lower()
    scored = []
    for r in rows:
        jd = f"{r['title']} {r['jd_raw']}".lower()
        # Simple keyword overlap
        score = sum(1 for w in resume_lower.split() if w in jd)
        scored.append({**dict(r), "match_score": score})

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return {"total_matched": len(scored), "top_matches": scored[:req.top_n]}


# ── Resume Match (LLM-powered) ──────────────────────────

@app.post("/api/match/llm")
def match_resume_llm(req: MatchRequest):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM jobs WHERE is_active=1 AND city LIKE ? ORDER BY first_seen DESC LIMIT 500",
        (f"%{req.city}%",),
    ).fetchall()
    db.close()

    jobs = [dict(r) for r in rows]
    results = llm_match(req.resume_text, jobs, top_n=req.top_n)
    return {"total_scored": len(results), "top_matches": results}


# ── Daily Feed ─────────────────────────────────────────

@app.post("/api/feed/daily")
def feed(req: FeedRequest):
    return daily_feed(req)


# ── Applications ───────────────────────────────────────

@app.get("/api/me/applications")
def list_applications(openid: str = "dev_user_001"):
    db = get_db()
    rows = db.execute(
        "SELECT a.*, j.title, j.company, j.city, j.url, j.salary "
        "FROM applications a JOIN jobs j ON a.job_id=j.id "
        "WHERE a.openid=? ORDER BY a.updated_at DESC", (openid,)
    ).fetchall()
    db.close()
    return {"applications": [dict(r) for r in rows]}


@app.post("/api/me/applications")
def create_application(req: dict):
    db = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history = json.dumps([{"stage": req.get("stage", "saved"), "ts": now}])
    db.execute(
        "INSERT INTO applications (openid, job_id, stage, history, notes, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (req.get("openid", "dev_user_001"), req["job_id"], req.get("stage", "saved"),
         history, req.get("notes", ""), now, now),
    )
    db.commit()
    app_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()
    return {"id": app_id, "status": "created"}


@app.patch("/api/me/applications/{app_id}")
def update_application(app_id: int, req: dict):
    db = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = db.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(404, "application not found")

    new_stage = req.get("stage", existing["stage"])
    old_history = json.loads(existing["history"])
    old_history.append({"stage": new_stage, "ts": now})
    new_notes = req.get("notes", existing["notes"])

    db.execute(
        "UPDATE applications SET stage=?, history=?, notes=?, updated_at=? WHERE id=?",
        (new_stage, json.dumps(old_history, ensure_ascii=False), new_notes, now, app_id),
    )
    db.commit()
    db.close()
    return {"id": app_id, "status": "updated"}


@app.get("/api/stats")
def stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1").fetchone()[0]
    by_city = db.execute(
        "SELECT city, COUNT(*) as cnt FROM jobs WHERE is_active=1 GROUP BY city ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    by_source = db.execute(
        "SELECT source, COUNT(*) as cnt FROM jobs WHERE is_active=1 GROUP BY source ORDER BY cnt DESC"
    ).fetchall()
    recent = db.execute(
        "SELECT source, MAX(finished_at) as ts, SUM(rows_new) as new FROM crawl_runs WHERE status='ok' GROUP BY source ORDER BY ts DESC"
    ).fetchall()
    db.close()
    return {
        "total_active": total,
        "by_city": [dict(r) for r in by_city],
        "by_source": [dict(r) for r in by_source],
        "recent_runs": [dict(r) for r in recent],
    }


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
