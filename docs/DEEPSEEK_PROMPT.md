# DeepSeek V4 任务书 — 后端 + 数据 + LLM 工程

> 本文档由 Brain（Claude Opus 4.7）于 2026-05-08 起草。  
> 你（DeepSeek V4）负责 `backend/`、爬虫、ResuMiner 集成。前端由 Opus 负责，**不要碰 `miniprogram/`**。

---

## 你的 mission

3 周内把这个项目从「能爬数据」推到「能给学生用」。具体：
1. 把 `ResuMiner` 384 条大厂数据合并进 `data/internship.db`（让小程序看得到字节/腾讯/阿里）
2. 用 LLM 一次性 backfill 薪资 + 发布时间（这是 0/709 全空的字段，不修连基础卡片都丑）
3. 把现有 `/api/match/llm` 升级到 semantic + LLM rerank（recall 翻 30%）
4. 加 2 个新接口：`/api/feed/daily`（每日精选）和 `/api/resume/tailor`（AI 简历定制）

成本预算：MVP 月开销 < 100 CNY（仅 `/api/match/llm` + `/api/resume/tailor` 用 DeepSeek，其他纯本地计算）。

---

## 当前后端事实（不要假设，凭这个写）

**FastAPI** 入口：`backend/main.py`，端口 8000，`uvicorn backend.main:app`。

**SQLite** 路径：`data/internship.db`（项目根 `data/`）。Schema 在 `backend/db.py`：
```sql
jobs (
  id, external_id, source, company, title, city, jd_raw, salary, url,
  publish_time, deadline, recruit_type, raw_tags, crawled_at,
  content_hash, is_active, first_seen, last_seen,
  UNIQUE(source, external_id)
)
crawl_runs (id, source, status, rows_total, rows_new, rows_updated, duration_ms, error, started_at, finished_at)
browser_sessions (id, name, profile_path, last_used, status)
```
当前 709 条记录，5 个源：xiaohongshu(304) / kuaishou(230) / bilibili(90) / shixiseng(60) / jd(25)。**字段 `salary` 0% 有值**，**`publish_time` 100% 是 `"unknown"` 字符串**。

**ResuMiner**：`ResuMiner/data/unified/jobs.parquet`（384 条），含字节/腾讯/阿里/美团等大厂；embeddings 在 `ResuMiner/index/jobs_embeddings.npz` + `ResuMiner/index/jobs_meta.parquet`。Schema 见 `ResuMiner/pipeline/schema.py::Job`。

**DeepSeek matcher**：`backend/matcher.py::match()` 已实现，keyword 预筛 top-60 → DeepSeek rerank top-N，每次约 0.15 CNY/用户。System prompt 已稳定（line 12-23），别动它。

---

## 任务清单（B1-B9）

按顺序做。B1 是其他所有任务的前提。

### B1 — `backend/ingest_resuminer.py`（**Day 1**，0.5 天）

**目标**：把 ResuMiner parquet 灌进 SQLite，让 `/api/health` 显示 ≥ 1090 条。

**实现**：
```python
import pandas as pd, hashlib
from backend.db import upsert_job

def ingest():
    df = pd.read_parquet('ResuMiner/data/unified/jobs.parquet')
    for _, row in df.iterrows():
        # ResuMiner schema → backend SQLite schema
        original_source = row.get('platform') or row.get('source') or 'unknown'
        job = {
            'source': f'resuminer_{original_source}',  # 关键：前缀避免和现有 jd/xiaohongshu 等冲突
            'external_id': str(row.get('source_job_id') or row.get('id')),
            'company': row['company'],
            'title': row['title'],
            'city': row.get('city', ''),
            'jd_raw': row.get('jd_text', '') or row.get('jd_raw', ''),
            'salary': format_salary(row),  # 见下
            'url': row.get('url', ''),
            'publish_time': row.get('publish_date', '') or 'unknown',
            'deadline': row.get('deadline', ''),
            'recruit_type': row.get('job_type', ''),
            'raw_tags': '',
            'content_hash': hashlib.sha1(f"{row['company']}|{row['title']}|{row.get('jd_text','')[:500]}".encode()).hexdigest()
        }
        upsert_job(job)

def format_salary(row):
    smin = row.get('salary_min'); smax = row.get('salary_max'); unit = row.get('salary_unit', '')
    if pd.notna(smin) and pd.notna(smax):
        return f"{int(smin)}-{int(smax)}{unit}"
    return ''

if __name__ == '__main__':
    ingest()
```

**注意**：ResuMiner Job schema 你要去 `ResuMiner/pipeline/schema.py` 实际看（字段名可能是 `salary_min/salary_max/salary_unit` 或别的）。**不要假设字段名，先 `df.columns` 打印一下**。

**验收**：
```powershell
python -m backend.ingest_resuminer
sqlite3 data/internship.db "SELECT source, COUNT(*) FROM jobs GROUP BY source"
# 期望: resuminer_bytedance, resuminer_tencent, ... 加 5 个原有源
```

---

### B2 — `backend/enrich_salary.py`（**Day 1-2**，1 天）

**目标**：用 DeepSeek 一次性扫所有 `salary=''` 的行，从 `jd_raw` 提取薪资 → 写三列 `salary_min_kday/salary_max_kday/salary_unit`。

**Schema migration**（先做）：
```python
# backend/migrations/001_salary_columns.py
from backend.db import get_db

def migrate():
    conn = get_db()
    for col, type_ in [
        ('salary_min_kday', 'REAL'),
        ('salary_max_kday', 'REAL'),
        ('salary_unit', 'TEXT DEFAULT "unknown"'),
    ]:
        try:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {type_}")
        except Exception as e:
            if 'duplicate column' not in str(e): raise
    conn.commit()
    conn.close()
```
也在 `backend/db.py::init_db()` 的 `CREATE TABLE` 里加这三列，新建 DB 时一次到位。

**LLM 提取 prompt**（中文，强制 JSON）：
```
你是薪资信息提取助手。从下面的实习岗位 JD 中提取薪资范围。

岗位标题: {title}
JD: {jd_raw[:1500]}

只返回 JSON，格式：
{"min": 200, "max": 300, "unit": "日"}  // 元/日
{"min": 6000, "max": 8000, "unit": "月"}  // 元/月
{"min": null, "max": null, "unit": "unknown"}  // 未提及

unit 只能是: 日 / 月 / unknown
不要解释，只返回 JSON。
```

**实现**：
```python
def enrich_all():
    conn = get_db()
    rows = conn.execute("SELECT id, title, jd_raw FROM jobs WHERE salary_unit='unknown' OR salary_unit IS NULL").fetchall()
    print(f"Backfilling {len(rows)} rows...")
    for r in rows:
        if not r['jd_raw'] or len(r['jd_raw']) < 50: continue
        result = _call_deepseek_salary(r['title'], r['jd_raw'])
        # 转换：月薪 → 日薪 (×1/22)
        smin, smax = result['min'], result['max']
        unit = result['unit']
        if unit == '月' and smin and smax:
            smin_kday = round(smin / 22, 1)
            smax_kday = round(smax / 22, 1)
            stored_unit = '月'
        elif unit == '日':
            smin_kday, smax_kday, stored_unit = smin, smax, '日'
        else:
            smin_kday = smax_kday = None
            stored_unit = 'unknown'
        conn.execute(
            "UPDATE jobs SET salary_min_kday=?, salary_max_kday=?, salary_unit=? WHERE id=?",
            (smin_kday, smax_kday, stored_unit, r['id'])
        )
        conn.commit()
```

**成本估算**：1100 行 × ~600 tokens/调用 × 0.014 CNY/1k tokens ≈ **9 CNY 一次性**。便宜得离谱。

**重试 + 限流**：
- 单次失败重试 2 次（指数退避 1s/3s）
- 每秒最多 5 个并发（用 `asyncio.Semaphore` 或 `concurrent.futures.ThreadPoolExecutor(max_workers=5)`）
- 进度持久化：每 50 行 commit + 打印 `[B2] 350/1093 done`，中断可续跑

**验收**：
```sql
SELECT COUNT(*) FROM jobs WHERE salary_unit != 'unknown';
-- 期望 ≥ 0.85 * 总行数
SELECT salary_min_kday, salary_max_kday, salary_unit, title FROM jobs WHERE salary_unit='日' LIMIT 5;
-- 期望: 看起来合理 (100-500 元/天 区间)
```

---

### B3 — `backend/enrich_publish_time.py`（**Day 2**，1 天）

**目标**：把 `publish_time='unknown'` 的行改为 ISO 日期，新列 `publish_time_iso TEXT`。

**两条路径**：
1. **xiaohongshu / shixiseng / liepin 等列表页本来就有时间戳**：扩展对应爬虫的 parser，把 timestamp 直接写入 `publish_time`。这些是 60% 的来源。
2. **video 平台 (kuaishou, bilibili) 列表页只有「3 天前」「上周」之类**：和 B2 同批 prompt 让 LLM 从 JD 末尾或 `crawled_at` 推断（比如 JD 写「2026 春招」就推 `2026-03-01`，没线索就 fallback 到 `crawled_at`）。

**Schema migration**：
```sql
ALTER TABLE jobs ADD COLUMN publish_time_iso TEXT;
```

**LLM prompt**（合并到 B2 的同次调用，省一半成本）：
```
请同时返回 publish_date_hint：从 JD 推断发布日期。
- 如果 JD 明确提到「2026 春招」「秋招」，输出对应季度首日 (2026-03-01 / 2026-09-01)
- 如果有明确 "2026-XX-XX" 字样，输出该日期
- 否则输出 null

完整 JSON 格式：
{"min":..., "max":..., "unit":..., "publish_date_hint": "2026-03-01" 或 null}
```

**Fallback 优先级**：列表页时间戳 > LLM hint > `crawled_at` 截到日期。

**验收**：
```sql
SELECT COUNT(*) FROM jobs WHERE publish_time_iso IS NOT NULL;
-- 期望 ≥ 0.6 * 总行数
SELECT MIN(publish_time_iso), MAX(publish_time_iso) FROM jobs;
-- 期望: 都在 2025-09 ~ 2026-05 之间，没有明显 outlier
```

---

### B4 — `dedup_key` 多源去重（**Day 3**，0.5 天）

**目标**：同一个公司同标题同城市的岗位（来自不同源）合并显示，前端卡片右上显示「{N} 源」徽标。

**Schema migration**：
```sql
ALTER TABLE jobs ADD COLUMN dedup_key TEXT;
CREATE INDEX idx_jobs_dedup ON jobs(dedup_key);
```

**Backfill**：
```python
import hashlib, re

def normalize(s):
    if not s: return ''
    s = s.lower().strip()
    s = re.sub(r'[\s\(\)（）·\-_/,，。.]+', '', s)
    s = re.sub(r'(实习生|实习岗|2026|2025|春招|秋招)', '', s)
    return s

def make_dedup_key(company, title, city):
    raw = f"{normalize(company)}|{normalize(title)}|{normalize(city)}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]

def backfill():
    conn = get_db()
    for r in conn.execute("SELECT id, company, title, city FROM jobs"):
        key = make_dedup_key(r['company'], r['title'], r['city'])
        conn.execute("UPDATE jobs SET dedup_key=? WHERE id=?", (key, r['id']))
    conn.commit()
```

**修改 `backend/db.py::upsert_job()`**：插入/更新时也算 dedup_key。

**修改 `backend/main.py::list_jobs()`**：
```python
# 改为：每个 dedup_key 只返回 1 条（优先 source 以 resuminer_ 开头的，否则任意一条）
# 同时返回 source_count = 该 dedup_key 下的源数
sql = """
SELECT *, COUNT(*) OVER (PARTITION BY dedup_key) AS source_count,
       ROW_NUMBER() OVER (PARTITION BY dedup_key 
                          ORDER BY CASE WHEN source LIKE 'resuminer_%' THEN 0 ELSE 1 END,
                                   first_seen DESC) AS rn
FROM jobs WHERE is_active=1 AND ...
"""
# 然后 WHERE rn=1
```

**验收**：
```sql
SELECT dedup_key, COUNT(*) c, GROUP_CONCAT(source) FROM jobs GROUP BY dedup_key HAVING c >= 2 LIMIT 5;
-- 期望: 至少几条 multi-source 重复，比如「字节-数据分析-上海」同时来自 resuminer_bytedance + shixiseng
```

---

### B5 — Semantic match upgrade（**Day 3-4**，1.5 天）

**目标**：把 `backend/matcher.py::match()` 第一阶段从「关键词预筛」升级为「embedding cosine 预筛」。recall 翻 30%。

**新模块** `backend/semantic_match.py`：
```python
import numpy as np, pickle
from sentence_transformers import SentenceTransformer
from pathlib import Path

_MODEL = None
_EMBEDDINGS = None  # shape (N, D)
_META_IDS = None    # parquet job ids 对应的 SQLite job 的 external_id 映射

def _load():
    global _MODEL, _EMBEDDINGS, _META_IDS
    if _MODEL is None:
        _MODEL = SentenceTransformer('BAAI/bge-small-zh-v1.5')  # 中文语义比 en-v1.5 好
        npz = np.load('ResuMiner/index/jobs_embeddings.npz')
        _EMBEDDINGS = npz['embeddings']
        _META_IDS = npz['job_ids']  # 看实际字段名
    return _MODEL, _EMBEDDINGS, _META_IDS

def semantic_topk(resume_text: str, k=60) -> list[str]:
    model, embs, ids = _load()
    rvec = model.encode([resume_text], normalize_embeddings=True)[0]
    sims = embs @ rvec  # (N,)
    top_idx = np.argsort(-sims)[:k]
    return [ids[i] for i in top_idx]
```

**注意**：
- `bge-small-zh-v1.5` 比 ResuMiner 默认的 `bge-small-en-v1.5` 在中文 JD/简历上效果更好。要确认 ResuMiner 当时建索引用的是哪个模型——必须用同一个，否则向量空间不一致。如果旧索引是 en，**重建一次**（脚本：`ResuMiner/pipeline/build_index.py`，但要改模型名）。
- 但是！ResuMiner embeddings 只覆盖 384 条 ResuMiner 数据，不覆盖原 backend 的 709 条。需要扩展：把 SQLite 全量 1093 条都生成 embedding，存到 `data/embeddings.npz`。这是新的真理来源，不复用 ResuMiner index。

**新建 backend/build_embeddings.py**：
```python
def build():
    conn = get_db()
    rows = conn.execute("SELECT external_id, source, title, jd_raw FROM jobs WHERE is_active=1").fetchall()
    texts = [f"{r['title']}\n{r['jd_raw'][:800]}" for r in rows]
    model = SentenceTransformer('BAAI/bge-small-zh-v1.5')
    embs = model.encode(texts, normalize_embeddings=True, batch_size=32)
    np.savez('data/embeddings.npz', 
             ids=np.array([f"{r['source']}::{r['external_id']}" for r in rows]),
             embeddings=embs)
```
B1-B4 完成后跑一次。后续每次 ingest 后 incremental 更新（先简单：每 200 条新数据 rebuild 全量）。

**改 `backend/matcher.py::match()`**：
```python
from backend.semantic_match import semantic_topk

def match(resume, jobs, top_n=20):
    # Step 1: semantic top-60 (free, ~50ms)
    top_keys = semantic_topk(resume, k=60)
    candidates = [j for j in jobs if f"{j['source']}::{j['external_id']}" in set(top_keys)]
    
    # Step 2: LLM rerank (paid)
    results = []
    for job in candidates:
        llm = _call_deepseek(resume, job.get('title',''), job.get('jd_raw',''))
        results.append({**job, 'match_score': llm['score'], 'match_reason': llm['reason'],
                        'hit_skills': llm['hit_skills'], 'gap_skills': llm['gap_skills']})
    results.sort(key=lambda x: x['match_score'], reverse=True)
    return results[:top_n]
```

**验收**：用同一份简历分别走 keyword（旧）和 semantic（新）预筛，top-60 重合率 < 70%，且新版本 top-20 final 中包含旧版本漏掉的至少 5 条（语义相关但关键词不直接命中的）。

---

### B6 — applications 表 + 3 个端点（**Day 5-6**，1 天）

**目标**：投递追踪状态机持久化（前端 store 是本地的，server 侧也要有，方便后期跨设备）。

**Schema**（追加到 `init_db()`）：
```sql
CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  openid TEXT NOT NULL,
  job_id INTEGER NOT NULL,
  stage TEXT NOT NULL,  -- saved | submitted | oa | interview | offer | rejected | archived
  history TEXT NOT NULL,  -- JSON: [{"stage":"submitted","ts":"2026-05-08T10:00"}]
  notes TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (job_id) REFERENCES jobs(id)
);
CREATE INDEX idx_applications_openid ON applications(openid);
```

**Endpoints**：
- `GET /api/me/applications?openid=...` → `{applications: [...]}`
- `POST /api/me/applications` body `{openid, job_id, stage, note?}` → `{id, ...}`
- `PATCH /api/me/applications/{id}` body `{stage?, note?}` → 自动 append 到 history

**MVP 阶段 openid 处理**：前端没接微信登录，开发期 openid 写死 `dev_user_001`。Phase 4 接 wx.login 时再改。

---

### B7 — `/api/feed/daily` 每日精选 10（**Day 5-6**，1 天）

**目标**：基于用户简历 embedding × 岗位 embedding × 新鲜度衰减 × 城市加权，每天给一个固定的 top 10 推荐。**纯本地计算，零 LLM 成本**。

**实现**：
```python
@app.get('/api/feed/daily')
def daily_feed(city: str = '上海', resume_hash: str = ''):
    cache_key = f"{resume_hash}::{city}::{datetime.utcnow().date()}"
    if cached := _CACHE.get(cache_key): return cached
    
    # 取用户简历（前端会先 POST 简历 hash 后 GET feed；Phase 1 简化：直接前端把 resume_text 也传过来当 query 参数太长，用 POST 改一下）
    # 改成 POST 更合理：
    pass
```

**改成 POST 接口**（前端 OPUS_PROMPT 也要同步改）：
```python
class DailyFeedRequest(BaseModel):
    resume_text: str
    city: str = '上海'
    dismissed_ids: list[str] = []

@app.post('/api/feed/daily')
def daily_feed(req: DailyFeedRequest):
    # 1. 简历 embedding
    rvec = _model.encode([req.resume_text], normalize_embeddings=True)[0]
    # 2. 取所有未 dismiss、城市匹配的岗位
    conn = get_db()
    rows = conn.execute(
        "SELECT j.*, e.embedding FROM jobs j ... WHERE city LIKE ?", (f'%{req.city}%',)
    ).fetchall()
    # 3. score = 0.6*cos_sim + 0.2*freshness + 0.2*city_match
    today = datetime.utcnow().date()
    scored = []
    for r in rows:
        if r['external_id'] in req.dismissed_ids: continue
        cos = float(np.dot(rvec, np.frombuffer(r['embedding'])))
        freshness = max(0, 1 - (today - parse(r['publish_time_iso'])).days / 60)
        score = 0.6 * cos + 0.3 * freshness + 0.1 * (1 if req.city in r['city'] else 0)
        scored.append((score, r))
    scored.sort(reverse=True)
    top10 = [{**dict(r), 'match_score': int(s*100)} for s, r in scored[:10]]
    return {'date': today.isoformat(), 'jobs': top10}
```

**缓存**：内存 dict by `(resume_hash, city, date)`，每天清空。

**验收**：同一份简历调两次返回完全相同结果；删掉某 dismissed_id 后返回结果替换为新一条。

---

### B8（可选 / Phase 4 再做）— `/api/skills/upskill_advice`

用户决策：MVP 不做，前端显示「即将上线」即可。**跳过本任务**。

---

### B9 — `/api/resume/tailor`（**Day 7-9**，1.5 天）

**目标**：详情页「优化简历」按钮的后端，DeepSeek 给 3 个改写版本。这是杀手锏，每次约 0.4 CNY。

**Endpoint**：
```python
class TailorRequest(BaseModel):
    resume_text: str
    job_id: int

@app.post('/api/resume/tailor')
def tailor(req: TailorRequest):
    conn = get_db()
    job = dict(conn.execute("SELECT * FROM jobs WHERE id=?", (req.job_id,)).fetchone())
    sections = _split_resume(req.resume_text)  # 见下，简单按「项目经历」「实习经历」段
    out = {'original_sections': sections, 'suggestions': []}
    for sec in sections:
        if sec['type'] not in ('project', 'experience'): continue  # 只改这两类
        candidates = _call_deepseek_tailor(sec['text'], job['title'], job['jd_raw'])
        out['suggestions'].append({'section_id': sec['id'], 'candidates': candidates})
    return out
```

**简历分段**：朴素正则切分。学生简历常见 section 标题：
```python
SECTION_HEADERS = ['教育背景', '实习经历', '项目经历', '技能', '获奖', '社团']
def _split_resume(text):
    # 按 SECTION_HEADERS 切，返回 [{id, type, text}]
    ...
```

**LLM prompt**：
```
你是简历优化专家。给定一段实习/项目经历，针对目标岗位 JD 改写出 3 个版本。

原文：
{section_text}

目标岗位：{title}
JD：{jd_raw[:1500]}

要求：
1. 保留所有事实（公司、项目名、量化数字）
2. 改写动词使用、技能词使用，让 JD 中的硬技能词在简历中显式出现
3. 每个版本不超过原文长度 1.2 倍
4. rationale 用一句话说清「这个版本为什么适合这个岗位」

只返回 JSON：
{
  "candidates": [
    {"text": "改写版1...", "rationale": "突出 SQL 数据分析", "matched_skills": ["SQL", "AB测试"]},
    {"text": "改写版2...", "rationale": "...", "matched_skills": [...]},
    {"text": "改写版3...", "rationale": "...", "matched_skills": [...]}
  ]
}
```

**频率限制**（避免被刷）：
- 同一 openid 每天最多 5 次（保存到 SQLite 一张 `tailor_usage` 表）
- 同一 (resume_hash, job_id) 缓存 24h（避免反复重生成）

**验收**：用张靖恒数据分析简历 + 字节数据分析岗位调用，返回 3 个改写版本，每版本要求技能词覆盖至少 ≥ 60% JD 中显式列出的硬技能。

---

## Cost dashboard（贯穿所有任务）

加 `backend/cost_tracker.py`：
```python
import json, os
from datetime import date
TRACK_FILE = 'data/llm_spend.json'

def log_call(endpoint: str, tokens_in: int, tokens_out: int):
    cost = (tokens_in * 0.0014 + tokens_out * 0.0028) / 1000  # CNY (DeepSeek-chat 价格)
    today = str(date.today())
    data = json.load(open(TRACK_FILE)) if os.path.exists(TRACK_FILE) else {}
    data.setdefault(today, {}).setdefault(endpoint, {'calls': 0, 'cost': 0})
    data[today][endpoint]['calls'] += 1
    data[today][endpoint]['cost'] += cost
    json.dump(data, open(TRACK_FILE, 'w'))
```

在 `_call_deepseek()` 末尾调用。`/api/stats` 加返回 `llm_spend_today_cny`。

---

## 工程纪律

1. **不破坏现有 endpoint 的 response shape**：已有的 `/api/jobs`、`/api/match/llm` 等在 Phase 1 内**只能加字段，不能删/改字段类型**。前端 Opus 在并行开发，不能让她返工。
2. **SQLite ALTER 必须可重复执行**：所有 migration 用 `try except duplicate column` 包起来。`init_db()` 也要加新列定义，让新部署一次到位。
3. **API key 检查**：所有 LLM 模块顶部 `if not DEEPSEEK_KEY: raise RuntimeError("DEEPSEEK_API_KEY missing in .env")`。不要在调用时才挂掉。
4. **进度持久化**：B2/B3/B5 等批量任务必须每 50 行 commit 并 print 进度，挂了能续跑。
5. **不引入新依赖**：`requirements.txt` 已有 fastapi/uvicorn/pandas/numpy/sentence-transformers/requests/apscheduler/sqlite3。新增包必须先和 Brain 商量。
6. **不动 `miniprogram/`**：哪怕看到前端有 bug 也不许碰，提到 `docs/HANDOFF_NOTES.md`。
7. **不动现有爬虫的解析逻辑**：B2/B3 是 LLM backfill，不是 parser 修改。爬虫扩展（B3 第 1 路径）只在 user 明确批准后做。

---

## 任务依赖图

```
B1 (ingest) ──┬──> B2 (salary)  ──┐
              ├──> B3 (publish)  ──┤
              ├──> B4 (dedup)    ──┤
              └──> B5 (semantic) ──┴──> B7 (daily feed)
                                          
                  B6 (applications) (independent)
                  B9 (tailor)       (independent，但需要 B5 的 semantic 帮助 fallback)
```

B1-B5 是 Day 1-4 的核心；B6/B7 在 Day 5-6；B9 在 Day 7-9。

## Smoke tests

每完成一个任务跑一次：
```powershell
# B1
sqlite3 data/internship.db "SELECT source, COUNT(*) FROM jobs GROUP BY source"

# B2
sqlite3 data/internship.db "SELECT COUNT(*) FROM jobs WHERE salary_unit != 'unknown'"

# B3
sqlite3 data/internship.db "SELECT COUNT(*) FROM jobs WHERE publish_time_iso IS NOT NULL"

# B4
sqlite3 data/internship.db "SELECT dedup_key, COUNT(*) FROM jobs GROUP BY dedup_key HAVING COUNT(*) >= 2 LIMIT 5"

# B5
curl -X POST http://127.0.0.1:8000/api/match/llm -H 'Content-Type: application/json' \
  -d '{"resume_text":"数据分析实习生 Python SQL Tableau","top_n":5}' | jq '.top_matches[].match_score'

# B7
curl -X POST http://127.0.0.1:8000/api/feed/daily -H 'Content-Type: application/json' \
  -d '{"resume_text":"...","city":"上海"}'
```

整套通过后告诉 Brain，Brain 跑全套 Milestone A 验收。

## 沟通

- Schema 改了 → 立即 ping Brain，Brain 通知 Opus 同步 prop 类型
- API contract 改了 → **必须** 先在 `docs/API_CONTRACT.md` 写下新旧对比，等 Brain 批
- DeepSeek 单次调用超 0.5 CNY → 找 Brain 复审，可能要拆 prompt
- 卡 > 30min → `docs/HANDOFF_NOTES.md` 写卡点 + 当前数据状态

## 不要做的

- ❌ 不要重写 `backend/main.py` 整个文件（改局部、加路由即可）
- ❌ 不要给 ResuMiner 加 API（它退役了，只当 library）
- ❌ 不要把 `data/internship.db` 切到 PostgreSQL（MVP SQLite 够用）
- ❌ 不要做 B8 upskill_advice（用户决策延后）
- ❌ 不要在生产 push 前 `git commit`（Brain/用户审）
