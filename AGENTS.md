# AGENTS.md — Project Memory for AI Assistants

> Read this first before any work. Keeps context without re-explaining.

## Project: 实习平台数据聚合 (Internship Aggregation Platform)

**Goal**: Build a Shanghai-area internship data platform that aggregates postings from major tech companies and job boards, then matches resumes to the most relevant positions. Eventually a WeChat mini-program.

**Owner**: 张靖恒 (2027届 graduate, targeting data/analytics roles in Shanghai)

**Path**: `C:\jz_code\internship_finding`

---

## Architecture Overview

```
Crawl Layer                    Process Layer               Output Layer
─────────────                  ─────────────               ────────────
crawlers/run_all_official.py → official_jobs_raw.csv  ┐
  ├─ 7 API adapters          (per-company runners)      │
  ├─ 2 Playwright headless   (bytedance, baidu)         ├→ merge_file.py
  └─ CDP mode (deprecated)   (used to need Chrome 9222) │   ├─ cleaning
                                                         │   ├─ cohort27 scoring
ResuMiner/ (submodule)                                   │   ├─ link health
  ├─ 实习僧/猎聘/51job/应届生 crawlers                   │   └─ release_data/
  └─ resume matching engine                              │
                                                         └→ outputs/reports/
                                                             outputs/dashboard/
```

**Two crawling modes**:
- **API mode** (7 companies): Direct `requests.post()` to internal APIs, no browser needed. Fast & reliable.
- **Playwright headless** (2 companies): Launch own Chromium, intercept XHR. ByteDance, Baidu. No manual Chrome needed anymore.

## Current State (2026-05-06)

### Working crawlers (9/9):
| # | Company | Source | Mode | Status |
|---|---------|--------|------|--------|
| 1 | 字节跳动 | official_bytedance | Playwright headless | **Just fixed** (was broken CDP) |
| 2 | 腾讯 | official_tencent_api | API adapter | OK |
| 3 | 快手 | official_kuaishou_api | API adapter | OK |
| 4 | 小红书 | official_xiaohongshu | API adapter | OK |
| 5 | 美团 | official_meituan | API adapter | OK |
| 6 | 阿里 | official_alibaba | API adapter | OK |
| 7 | 京东 | official_jd_api | API adapter | OK |
| 8 | 哔哩哔哩 | official_bilibili | API adapter | OK (preflight fixed) |
| 9 | 百度 | official_baidu | Playwright Firefox | **Fixed** (was 0 rows, now Firefox+DOM) |
| 10 | 实习僧 | shixiseng | Playwright headless | **Working** (fonts decoded, list 40 rows) |
| 11 | BOSS直聘 | boss | Playwright Firefox | **Working** (cookies + double-nav) |
| 12 | 猎聘 | liepin | Playwright API intercept | **New** (44 rows, no anti-bot) |

### Pending / Future:
- [ ] 猎聘 real-time (ResuMiner skeleton, needs RPC server)
- [ ] 51job / 应届生 (lower priority)
- [ ] Font map auto-extraction for shixiseng (currently salary shows garbled)
- [ ] Database migration (post-CSV cleanup)
- [ ] Semantic resume matching (currently keyword-based)
- [ ] FastAPI backend + WeChat mini-program

---

## Key Files Map

```
internship_finding/
├── config.py                  # Enable/disable companies, strict mode flags
├── official_multi_crawler.py  # Core: SOURCES config, crawl_one_source(), all fetch_*_jobs() functions
├── merge_file.py              # 1408 lines: cleaning, enrichment, scoring, dashboards
├── requirements.txt           # Python dependencies
├── .env                       # DEEPSEEK_API_KEY (gitignored)
│
├── crawlers/                  # Split crawler architecture (per-company runners)
│   ├── run_all_official.py    # Orchestrator: runs all 9 crawlers, preflight health, retry, cache fallback
│   ├── base_runner.py         # run_single_source() + dedup_rows()
│   ├── io.py                  # CSV I/O helpers
│   ├── schema.py              # FIELD_ORDER (21-column canonical schema)
│   ├── bytedance_crawler.py   # ByteDance: Playwright headless via crawl_one_source()
│   ├── baidu_crawler.py       # Baidu: Playwright headless via crawl_one_source()
│   ├── tencent_crawler.py     # Tencent: wraps fetch_tencent_jobs()
│   ├── kuaishou_crawler.py    # Kuaishou: wraps fetch_kuaishou_jobs_api()
│   ├── xiaohongshu_crawler.py # Xiaohongshu: wraps fetch_xiaohongshu_jobs_api()
│   ├── meituan_crawler.py     # Meituan: wraps fetch_meituan_jobs_api()
│   ├── alibaba_crawler.py     # Alibaba: wraps fetch_alibaba_jobs_api()
│   ├── jd_crawler.py          # JD: wraps fetch_jd_jobs()
│   ├── bilibili_crawler.py    # Bilibili: wraps fetch_bilibili_jobs_api()
│   └── cdp/                   # CDP-based crawlers (legacy, for manual Chrome scraping)
│
├── parsers/
│   ├── base_adapter.py        # Abstract BaseCompanyAdapter (fetch_list, parse, get_27_signal)
│   ├── company_adapters.py    # Concrete adapters: Kuaishou, Tencent, XHS, Bilibili, Alibaba, Meituan
│   └── company_registry.py    # ADAPTER_REGISTRY dict + get_adapter() factory
│
├── rules/
│   ├── cohort27_rules.py      # Rule-based 27届 classifier (high/medium/low/none)
│   └── location_normalizer.py # City alias normalization (望京→北京, etc.)
│
├── scripts/
│   ├── resume_job_match_pipeline.py  # Resume-to-JD matching (keyword-based scoring)
│   ├── build_shanghai_internship_latest.py
│   ├── task6_monitoring_metrics.py
│   └── ... (analysis scripts)
│
├── tools/
│   ├── crawler_dispatcher.py  # Unified scheduler (7 tasks, sequential, health report)
│   ├── crawler_generator.py   # AI-assisted adapter generator (Playwright + DeepSeek)
│   ├── run_pipeline.bat       # Daily pipeline: crawl → parse → merge → ingest → index
│   ├── setup_daily_crawler.ps1
│   └── cdp/                   # CDP parsing + scraper tools
│
├── utils/
│   └── link_checker.py        # Async batch URL validation (OK/RISKY/BROKEN)
│
├── ResuMiner/                 # Git submodule: resume matching + foreign crawlers
│   ├── scripts/foreign_pipeline_v2.py  # 51job/猎聘/实习僧 unified pipeline
│   ├── matcher/               # Resume scoring engine
│   ├── pipeline/              # normalize, clean_jd, dedupe, build_index
│   └── api/                   # FastAPI matcher service
│
├── .trae/                     # AI planning docs + skills (gitignored)
│   ├── skills/crawler-check/SKILL.md
│   └── skills/cdp-crawler-optimizer/SKILL.md
│
├── outputs/
│   ├── raw/                   # Per-company CSVs (bytedance_official_raw.csv, etc.)
│   ├── reports/               # ~40 generated reports
│   ├── dashboard/             # Per-company dashboards
│   └── health/                # Link health reports
│
├── release_data/              # Final delivery CSVs/XLSXs
├── archive/history/           # Historical snapshots + 实习僧 data
├── data/                      # Resume files (张靖恒*.docx)
└── cdp_data/                  # CDP intercepted payloads (gitignored)
```

---

## How to Run

```powershell
# Full pipeline (daily):
.\tools\run_pipeline.bat

# Just crawlers:
python crawlers\run_all_official.py

# Just merge/scoring:
python merge_file.py

# Single company test:
python crawlers\bytedance_crawler.py

# Resume matching:
python scripts\resume_job_match_pipeline.py
```

**Env vars**: `HEADLESS=1`, `RUN_COMPANIES=bytedance,tencent`, `KUAISHOU_MAX_PAGES=120`, etc.

---

## Conventions

- **Adapter pattern**: Every company with an API gets a `BaseCompanyAdapter` subclass. `fetch_list(page)` → `parse(raw_item)` → `get_27_signal(parsed)`
- **CSV is the database**: Everything flows through CSV files. `official_jobs_raw.csv` is the source of truth for official crawlers.
- **Source tags**: API adapters use `official_*_api`, CDP/Playwright uses `official_*`. Merge pipeline uses `str.contains("official|bytedance")` to identify official sources.
- **27届 classification**: rule-based (cohort27_rules.py), not LLM. Has false negatives.
- **Resume matching**: keyword overlap scoring (not semantic). 4 dimensions: ATS (must-have skills), scene, evidence, value.
- **Shanghai-only**: All target output filtered to 上海. Hard-coded in merge_file.py.
- **No commiting without asking**: NEVER commit unless user explicitly requests.

---

## P0 Fixes Applied (2026-05-06)

1. **ByteDance**: `crawl_one_source()` now defaults to `use_cdp=False` (launches own headless Chromium instead of connecting to manual Chrome on port 9222)
2. **Bilibili preflight**: Health check URL changed to API endpoint, added fallback URL mechanism
3. **Baidu**: New `crawlers/baidu_crawler.py`, registered in `run_all_official.py` RUNNERS, added to config, merge_file.py company lists
4. **Cleanup**: Removed 12.4MB `node_modules/`, all `__pycache__/` dirs, added `requirements.txt`, `.env` in `.gitignore`
