"""B4: Backfill dedup_key for all jobs."""
import sys, re, hashlib
sys.path.insert(0, r"C:\jz_code\internship_finding")
from backend.db import get_db


def normalize(s: str) -> str:
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"[\s\(\)（）·\-_/,，。.]+", "", s)
    s = re.sub(r"(实习生|实习岗|2025|2026|2027|春招|秋招|校招)", "", s)
    return s


def make_dedup_key(company: str, title: str, city: str) -> str:
    raw = f"{normalize(company)}|{normalize(title)}|{normalize(city)}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def backfill():
    conn = get_db()
    rows = conn.execute("SELECT id, company, title, city FROM jobs").fetchall()
    done = 0
    for r in rows:
        key = make_dedup_key(str(r["company"] or ""), str(r["title"] or ""), str(r["city"] or ""))
        conn.execute("UPDATE jobs SET dedup_key=? WHERE id=?", (key, r["id"]))
        done += 1
        if done % 500 == 0:
            conn.commit()
    conn.commit()
    conn.close()
    print(f"Backfilled {done} dedup_keys")


if __name__ == "__main__":
    backfill()

    # Verify
    from backend.db import get_db
    db = get_db()
    multi = db.execute(
        "SELECT dedup_key, COUNT(*) c, GROUP_CONCAT(source) FROM jobs GROUP BY dedup_key HAVING c >= 2 LIMIT 5"
    ).fetchall()
    print(f"\nMulti-source dedup groups (sample):")
    for r in multi:
        print(f"  dedup={r[0]} count={r[1]} sources={r[2][:60]}")
    db.close();
