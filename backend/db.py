"""Database — SQLite for local dev, PostgreSQL-ready for production."""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "internship.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT NOT NULL,
            source TEXT NOT NULL,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            city TEXT DEFAULT '',
            jd_raw TEXT DEFAULT '',
            salary TEXT DEFAULT '',
            url TEXT DEFAULT '',
            publish_time TEXT DEFAULT '',
            deadline TEXT DEFAULT '',
            recruit_type TEXT DEFAULT '',
            raw_tags TEXT DEFAULT '',
            crawled_at TEXT DEFAULT '',
            content_hash TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            first_seen TEXT DEFAULT '',
            last_seen TEXT DEFAULT '',
            salary_min_kday REAL,
            salary_max_kday REAL,
            salary_unit TEXT DEFAULT 'unknown',
            publish_time_iso TEXT,
            dedup_key TEXT,
            UNIQUE(source, external_id)
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
        CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
        CREATE INDEX IF NOT EXISTS idx_jobs_city ON jobs(city);
        CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_active);
        CREATE INDEX IF NOT EXISTS idx_jobs_hash ON jobs(content_hash);

        CREATE TABLE IF NOT EXISTS crawl_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            rows_total INTEGER DEFAULT 0,
            rows_new INTEGER DEFAULT 0,
            rows_updated INTEGER DEFAULT 0,
            duration_ms INTEGER DEFAULT 0,
            error TEXT DEFAULT '',
            started_at TEXT DEFAULT '',
            finished_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS browser_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            profile_path TEXT NOT NULL,
            last_used TEXT DEFAULT '',
            status TEXT DEFAULT 'inactive'
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            openid TEXT NOT NULL,
            job_id INTEGER NOT NULL,
            stage TEXT NOT NULL DEFAULT 'saved',
            history TEXT NOT NULL DEFAULT '[]',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_apps_openid ON applications(openid);
    """)
    conn.commit()
    conn.close()


def upsert_job(job: dict) -> str:
    """Insert or update. Returns 'new' / 'updated' / 'unchanged'."""
    conn = get_db()
    cur = conn.execute(
        "SELECT id, content_hash FROM jobs WHERE source=? AND external_id=?",
        (job["source"], job["external_id"]),
    )
    row = cur.fetchone()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Compute dedup_key
    from backend.migrations.dedup_backfill import make_dedup_key
    dedup_key = make_dedup_key(job.get("company", ""), job.get("title", ""), job.get("city", ""))

    if row is None:
        conn.execute(
            """INSERT INTO jobs (external_id, source, company, title, city, jd_raw, salary,
               url, publish_time, deadline, recruit_type, raw_tags, crawled_at,
               content_hash, first_seen, last_seen, dedup_key)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (job["external_id"], job["source"], job["company"], job["title"],
             job.get("city", ""), job.get("jd_raw", ""), job.get("salary", ""),
             job.get("url", ""), job.get("publish_time", ""), job.get("deadline", ""),
             job.get("recruit_type", ""), job.get("raw_tags", ""), now,
             job["content_hash"], now, now, dedup_key),
        )
        conn.commit()
        conn.close()
        return "new"

    if row["content_hash"] != job["content_hash"]:
        conn.execute(
            """UPDATE jobs SET title=?, company=?, city=?, jd_raw=?, salary=?,
               url=?, publish_time=?, deadline=?, recruit_type=?, raw_tags=?,
               content_hash=?, last_seen=?, is_active=1, dedup_key=?
               WHERE id=?""",
            (job["title"], job["company"], job.get("city", ""), job.get("jd_raw", ""),
             job.get("salary", ""), job.get("url", ""), job.get("publish_time", ""),
             job.get("deadline", ""), job.get("recruit_type", ""), job.get("raw_tags", ""),
             job["content_hash"], now, dedup_key, row["id"]),
        )
        conn.commit()
        conn.close()
        return "updated"

    conn.execute("UPDATE jobs SET last_seen=? WHERE id=?", (now, row["id"]))
    conn.commit()
    conn.close()
    return "unchanged"


def mark_inactive_stale(source: str, active_ids: set):
    """Mark jobs not seen in this crawl as inactive."""
    conn = get_db()
    placeholders = ",".join("?" * len(active_ids)) if active_ids else "''"
    conn.execute(
        f"UPDATE jobs SET is_active=0 WHERE source=? AND external_id NOT IN ({placeholders})",
        [source] + list(active_ids),
    )
    conn.commit()
    conn.close()


def log_crawl_run(source: str, status: str, rows_total: int, rows_new: int,
                  rows_updated: int, duration_ms: int, error: str = ""):
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO crawl_runs (source, status, rows_total, rows_new, rows_updated, duration_ms, error, started_at, finished_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (source, status, rows_total, rows_new, rows_updated, duration_ms, error, now, now),
    )
    conn.commit()
    conn.close()
