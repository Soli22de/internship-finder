# DeepSeek Batch 2 — Brain 验收 + 下一批任务

> Brain 验收日期：2026-05-08
> 上一批：B4 ✅ B5 ✅ B6 ✅
> 本批所有任务**仍不需要 DeepSeek API**

---

## 验收报告

| 任务 | 实测结果 |
|---|---|
| B4 dedup_key | 1716 unique 集群，42.2% 多源合并（724 个 ≥2 源），0 个 size>5 异常集群 |
| B5 semantic match | 0.3s 响应（模型已 cache），top-3 语义相关性高 |
| B6 applications | POST/GET/PATCH 三端点 CRUD 全通 |

之前 smoke test 报的 `/api/match` 返回 0 不是你的 bug，是 PowerShell 5.1 序列化中文丢编码。**你的代码是对的**。

---

## 本批任务（按顺序）

### M1 — matcher.py 无 key fallback（30 分钟）

**问题**：当 `DEEPSEEK_KEY=""` 时，`/api/match/llm` 返回的所有候选 `match_score=50`、`match_reason="API key not configured"`。前端显示一片 50 分卡片没法看。

**要做**：让 `match()` 在没 key 时返回真实 semantic 余弦分数。

修改 `backend/semantic_match.py`：
```python
def semantic_topk_with_scores(resume_text: str, k: int = 60):
    """Return [(id, cos_score), ...] sorted by score desc."""
    model, embs, ids = _load()
    rvec = model.encode([resume_text], normalize_embeddings=True)[0]
    sims = embs @ rvec  # cos in [-1, 1] since both normalized
    top_idx = np.argsort(-sims)[:k]
    return [(ids[i], float(sims[i])) for i in top_idx]
```

修改 `backend/matcher.py::match()`：
```python
def match(resume, jobs, top_n=20):
    from backend.semantic_match import semantic_topk_with_scores
    ranked = semantic_topk_with_scores(resume, k=max(top_n*3, 60))
    score_map = dict(ranked)

    candidates = []
    for j in jobs:
        key = f"{j['source']}::{j['external_id']}"
        if key in score_map:
            cos = score_map[key]
            j2 = {**j, '_cos': cos}
            candidates.append(j2)

    candidates.sort(key=lambda x: x['_cos'], reverse=True)
    candidates = candidates[:top_n]

    if not DEEPSEEK_KEY:
        # Fallback: use cosine score, no LLM rerank
        results = []
        for j in candidates:
            cos = j.pop('_cos')
            # Map [-1, 1] -> [40, 98]; clamp
            score = max(40, min(98, int(40 + (cos + 1) / 2 * 58)))
            results.append({
                **j,
                'match_score': score,
                'match_reason': '',
                'hit_skills': [],
                'gap_skills': []
            })
        return results

    # LLM path (unchanged)
    results = []
    for j in candidates:
        j.pop('_cos', None)
        llm = _call_deepseek(resume, j.get("title", ""), j.get("jd_raw", ""))
        results.append({
            **j,
            'match_score': llm['score'],
            'match_reason': llm['reason'],
            'hit_skills': llm['hit_skills'],
            'gap_skills': llm['gap_skills'],
        })
    results.sort(key=lambda x: x['match_score'], reverse=True)
    return results
```

**验收**：`DEEPSEEK_KEY=""` 时 curl `/api/match/llm`，top_matches 的 match_score 分布在 60-95（不是全 50）。

---

### M2 — list_jobs total 修正（10 分钟）

**问题**：`/api/jobs?dedup=true` 返回 `total=2456`（去重前），但 jobs 列表是去重后的 ~1716。前端显示偏大。

**要做**：改 `main.py::list_jobs()`，当 `dedup=True` 时 total 改为：
```python
total = db.execute(
    f"SELECT COUNT(DISTINCT dedup_key) FROM jobs {where}",
    params[:-2]  # 去掉最后的 LIMIT/OFFSET 参数
).fetchone()[0]
```

注意 where 子句里如果有 city/source/keyword 过滤，total 也要应用同样过滤。

**验收**：curl `/api/jobs?dedup=true&city=&limit=5`，total 应该 < 2456 且 ≈ 1716。

---

### M3 — PATCH 404 错误处理（5 分钟）

**问题**：`main.py:281` 行 `return {"error": "not found"}, 404` 不是 FastAPI 语法（这会返回 200 + 一个 tuple body）。

**要做**：
```python
from fastapi import HTTPException  # 已导入

# 在 update_application 里：
if not existing:
    db.close()
    raise HTTPException(404, "application not found")
```

**验收**：curl PATCH `/api/me/applications/99999`（不存在的 id）返回 HTTP 404 状态码。

---

### B7 — /api/feed/daily 每日精选（2-3 小时）

**目标**：首页顶部「今日为你精选」carousel 数据源。零 LLM 成本，纯 embedding cosine。

**新建** `backend/feed.py`，路由注册到 `main.py`：

```python
from datetime import date, datetime
import hashlib
from fastapi import Body
from pydantic import BaseModel

class FeedRequest(BaseModel):
    resume_text: str = ""
    city: str = "上海"
    dismissed_ids: list[int] = []
    k: int = 10

_FEED_CACHE = {}  # (resume_hash, city, date_str) -> result; in-memory, TTL 24h

@app.post("/api/feed/daily")
def daily_feed(req: FeedRequest):
    today = str(date.today())
    rhash = hashlib.sha1((req.resume_text or "").encode()).hexdigest()[:16]
    cache_key = (rhash, req.city, today, tuple(sorted(req.dismissed_ids)))
    if cache_key in _FEED_CACHE:
        return _FEED_CACHE[cache_key]

    db = get_db()
    rows = db.execute(
        "SELECT * FROM jobs WHERE is_active=1 AND city LIKE ? AND LENGTH(jd_raw) > 200",
        (f"%{req.city}%",)
    ).fetchall()
    db.close()

    if not req.resume_text.strip():
        # No resume — trending fallback (recent first)
        sorted_rows = sorted(rows, key=lambda r: r["first_seen"] or "", reverse=True)
        picks = [r for r in sorted_rows if r["id"] not in req.dismissed_ids][:req.k]
        result = {
            "date": today,
            "personalized": False,
            "jobs": [{**dict(r), "match_score": 70} for r in picks]
        }
    else:
        # Personalized: cosine + freshness + city_match
        from backend.semantic_match import semantic_topk_with_scores
        ranked = semantic_topk_with_scores(req.resume_text, k=200)
        score_map = dict(ranked)
        today_dt = datetime.now()
        scored = []
        for r in rows:
            if r["id"] in req.dismissed_ids: continue
            key = f"{r['source']}::{r['external_id']}"
            cos = score_map.get(key, 0)
            try:
                fs = datetime.strptime((r["first_seen"] or "1970-01-01")[:10], "%Y-%m-%d")
                days = (today_dt - fs).days
                fresh = max(0.0, 1 - days / 60)
            except Exception:
                fresh = 0.5
            city_match = 1 if req.city in (r["city"] or "") else 0
            final = 0.6 * cos + 0.3 * fresh + 0.1 * city_match
            scored.append((final, r))
        scored.sort(key=lambda x: -x[0])
        picks = scored[:req.k]
        result = {
            "date": today,
            "personalized": True,
            "jobs": [
                {**dict(r), "match_score": max(60, min(98, int((s + 1) / 2 * 98)))}
                for s, r in picks
            ]
        }

    _FEED_CACHE[cache_key] = result
    return result
```

**验收**：
- `curl -X POST /api/feed/daily -d '{"resume_text":"数据分析 Python SQL","city":"上海"}'` → 返回 10 条 with `match_score` 60-98 分布
- 同一 body 第二次调用 < 50ms（缓存命中）
- 加 `"dismissed_ids":[<某个 id>]` → 返回不含该 id

---

## 不要做的

- ❌ 不要碰 `miniprogram/`
- ❌ 不要重新设计 schema
- ❌ 不要在 push 前 git commit（Brain/用户审）
- ❌ 不要把 1190 条空 JD 当本批任务（属于 crawler enricher，单独工作流）

## 完成后

完成 M1/M2/M3/B7 后 ping Brain 验收。我会跑 verify_milestone_a.ps1（修了 UTF-8 后的版本）+ 加 feed 端点新测试。

如果用户接通 DeepSeek API（在 `.env` 加 `DEEPSEEK_API_KEY=...`），第三批会做 B9 简历定制。
