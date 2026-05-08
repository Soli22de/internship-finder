"""B7: Daily feed — personalized job recommendations, zero LLM cost."""
import hashlib
from datetime import date, datetime
from pydantic import BaseModel
from backend.db import get_db

_FEED_CACHE = {}


class FeedRequest(BaseModel):
    resume_text: str = ""
    city: str = "上海"
    dismissed_ids: list[int] = []
    k: int = 10


def daily_feed(req: FeedRequest) -> dict:
    today = str(date.today())
    rhash = hashlib.sha1((req.resume_text or "").encode()).hexdigest()[:16]
    cache_key = (rhash, req.city, today, tuple(sorted(req.dismissed_ids)))
    if cache_key in _FEED_CACHE:
        return _FEED_CACHE[cache_key]

    db = get_db()
    rows = db.execute(
        "SELECT id, source, external_id, title, company, city, jd_raw, salary, first_seen "
        "FROM jobs WHERE is_active=1 AND LENGTH(jd_raw) > 100 "
        "ORDER BY first_seen DESC LIMIT 200"
    ).fetchall()
    db.close()

    if not req.resume_text.strip():
        sorted_rows = sorted(rows, key=lambda r: r["first_seen"] or "", reverse=True)
        picks = [r for r in sorted_rows if r["id"] not in req.dismissed_ids][:req.k]
        result = {"date": today, "personalized": False,
                  "jobs": [{**dict(r), "match_score": 70} for r in picks]}
    else:
        from backend.semantic_match import semantic_topk_with_scores
        ranked = semantic_topk_with_scores(req.resume_text, k=min(len(rows), 200))
        score_map = dict(ranked)
        now = datetime.now()
        scored = []
        for r in rows:
            if r["id"] in req.dismissed_ids:
                continue
            key = f"{r['source']}::{r['external_id']}"
            cos = score_map.get(key, -0.2)
            city_match = 1 if req.city in (r["city"] or "") else 0
            final = 0.6 * max(0, cos) + 0.4 * city_match
            scored.append((final, r))
        scored.sort(key=lambda x: -x[0])
        picks = scored[:req.k]
        result = {
            "date": today,
            "personalized": True,
            "jobs": [
                {**dict(r), "match_score": max(60, min(98, int((s + 1) / 2 * 98)))}
                for s, r in picks
            ],
        }

    _FEED_CACHE[cache_key] = result
    return result
