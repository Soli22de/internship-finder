"""FastAPI backend — unified crawl API + job query + resume matching."""
import os
import sys
from datetime import datetime
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from backend.db import get_db, init_db

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
    print("[API] Database initialized.")


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
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    db = get_db()
    sql = "SELECT * FROM jobs WHERE 1=1"
    params = []
    if active_only:
        sql += " AND is_active=1"
    if city:
        sql += " AND city LIKE ?"
        params.append(f"%{city}%")
    if source:
        sql += " AND source=?"
        params.append(source)
    if keyword:
        sql += " AND (title LIKE ? OR jd_raw LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    sql += " ORDER BY first_seen DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = db.execute(sql, params).fetchall()
    total = db.execute(
        "SELECT COUNT(*) FROM jobs WHERE is_active=1" + (" AND city LIKE ?" if city else ""),
        [f"%{city}%"] if city else [],
    ).fetchone()[0]
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


# ── Stats ───────────────────────────────────────────────

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
