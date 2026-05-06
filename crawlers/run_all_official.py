import json
import os
import sys
from datetime import datetime
from typing import Callable, Dict, List, Tuple

import pandas as pd
import requests

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from crawlers.alibaba_crawler import run as run_alibaba
from crawlers.baidu_crawler import run as run_baidu
from crawlers.bilibili_crawler import run as run_bilibili
from crawlers.bytedance_crawler import run as run_bytedance
from crawlers.io import ensure_output_dirs
from crawlers.jd_crawler import run as run_jd
from crawlers.kuaishou_crawler import run as run_kuaishou
from crawlers.meituan_crawler import run as run_meituan
from crawlers.shixiseng_crawler import run as run_shixiseng
from crawlers.tencent_crawler import run as run_tencent
from crawlers.xiaohongshu_crawler import run as run_xiaohongshu


RUNNERS: List[Tuple[str, Callable[[], Dict[str, str]]]] = [
    ("bytedance", run_bytedance),
    ("tencent", run_tencent),
    ("kuaishou", run_kuaishou),
    ("xiaohongshu", run_xiaohongshu),
    ("meituan", run_meituan),
    ("alibaba", run_alibaba),
    ("jd", run_jd),
    ("bilibili", run_bilibili),
    ("baidu", run_baidu),
    ("shixiseng", run_shixiseng),
]

SOURCE_HEALTH_URLS: Dict[str, str] = {
    "bytedance": "https://jobs.bytedance.com",
    "tencent": "https://join.qq.com",
    "kuaishou": "https://campus.kuaishou.cn",
    "xiaohongshu": "https://job.xiaohongshu.com",
    "meituan": "https://zhaopin.meituan.com",
    "alibaba": "https://talent.alibaba.com",
    "jd": "https://campus.jd.com",
    "bilibili": "https://jobs.bilibili.com/api/campus/position/positionList",
    "baidu": "https://talent.baidu.com",
    "shixiseng": "https://www.shixiseng.com",
}

FALLBACK_HEALTH_URLS: Dict[str, str] = {
    "bilibili": "https://jobs.bilibili.com/api/auth/v1/csrf/token",
}

RETRY_SOURCE_OVERRIDES: Dict[str, Dict[str, str]] = {
    "bilibili": {"BILIBILI_MAX_PAGES": "60"},
    "jd": {},
    "meituan": {"MEITUAN_MAX_PAGES": "100"},
}


def _selected_companies() -> List[str]:
    raw = (os.getenv("RUN_COMPANIES") or "").strip()
    if not raw:
        return [k for k, _ in RUNNERS]
    keep = {x.strip().lower() for x in raw.split(",") if x.strip()}
    return [k for k, _ in RUNNERS if k in keep]


def _classify_failure_reason(message: str) -> str:
    m = (message or "").strip().lower()
    if not m:
        return ""
    if "timed out" in m or "timeout" in m:
        return "timeout"
    if "connection" in m or "reset" in m or "dns" in m:
        return "network_error"
    if "403" in m or "forbidden" in m:
        return "blocked_403"
    if "429" in m:
        return "rate_limit_429"
    if "500" in m or "502" in m or "503" in m or "504" in m:
        return "upstream_5xx"
    return "unknown_error"


def _run_preflight_health(selected: set) -> pd.DataFrame:
    rows: List[Dict[str, str]] = []
    for slug, _ in RUNNERS:
        if slug not in selected:
            continue
        url = SOURCE_HEALTH_URLS.get(slug, "")
        fallback = FALLBACK_HEALTH_URLS.get(slug, "")
        status = "skip"
        reason = ""
        code = 0
        tried_url = url
        if url:
            for attempt_url in [url, fallback]:
                if not attempt_url:
                    continue
                tried_url = attempt_url
                try:
                    resp = requests.get(attempt_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                    code = int(resp.status_code)
                    if resp.status_code < 400:
                        status = "ok"
                        break
                    else:
                        status = "failed"
                        reason = f"http_{resp.status_code}"
                except requests.Timeout:
                    status = "failed"
                    reason = "timeout"
                except requests.RequestException as e:
                    status = "failed"
                    reason = _classify_failure_reason(str(e))
        rows.append({"company_slug": slug, "health_url": tried_url, "status": status, "http_status": code, "reason": reason})
    return pd.DataFrame(rows)


def _read_raw_frame(raw_path: str) -> pd.DataFrame:
    if not raw_path or not os.path.exists(raw_path):
        return pd.DataFrame()
    try:
        return pd.read_csv(raw_path, keep_default_na=False)
    except Exception:
        return pd.DataFrame()


def _load_failure_state(state_path: str) -> Dict[str, Dict[str, str]]:
    if not os.path.exists(state_path):
        return {}
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def _save_failure_state(state_path: str, state: Dict[str, Dict[str, str]]) -> None:
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _run_with_env_override(fn: Callable[[], Dict[str, str]], overrides: Dict[str, str]) -> Dict[str, str]:
    old_values: Dict[str, str] = {}
    for k, v in overrides.items():
        old_values[k] = os.environ.get(k, "")
        os.environ[k] = v
    try:
        return fn()
    finally:
        for k, old in old_values.items():
            if old == "":
                os.environ.pop(k, None)
            else:
                os.environ[k] = old


def _attach_fetch_meta(frame: pd.DataFrame, source_slug: str, fetch_status: str, cache_fallback_used: bool) -> pd.DataFrame:
    if frame.empty:
        return frame
    tagged = frame.copy()
    tagged["source_slug"] = source_slug
    tagged["fetch_status"] = fetch_status
    tagged["cache_fallback_tag"] = "cache_fallback" if cache_fallback_used else ""
    return tagged


def main() -> None:
    dirs = ensure_output_dirs()
    reports_dir = dirs["reports"]
    selected = set(_selected_companies())
    preflight = _run_preflight_health(selected)
    preflight.to_csv(os.path.join(reports_dir, "source_preflight_health.csv"), index=False, encoding="utf-8-sig")
    preflight_map = {str(x["company_slug"]): x for x in preflight.to_dict(orient="records")}

    failure_state_path = os.path.join(reports_dir, "source_failure_state.json")
    alert_path = os.path.join(reports_dir, "source_failure_alerts.csv")
    failure_state = _load_failure_state(failure_state_path)

    results: List[Dict[str, str]] = []
    alert_rows: List[Dict[str, str]] = []
    param_reports: List[pd.DataFrame] = []
    raw_frames: List[pd.DataFrame] = []
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for slug, fn in RUNNERS:
        if slug not in selected:
            continue
        primary = fn()
        attempt_count = 1
        strategy_used = "default"
        final = primary
        if primary.get("status") != "ok" and slug in RETRY_SOURCE_OVERRIDES:
            attempt_count = 2
            retry_overrides = RETRY_SOURCE_OVERRIDES.get(slug, {})
            retry = _run_with_env_override(fn, retry_overrides)
            retry["strategy"] = "retry_relaxed"
            if retry.get("status") == "ok":
                final = retry
                strategy_used = "retry_relaxed"
            else:
                final = retry
                strategy_used = "retry_relaxed_failed"
        raw_path = str(final.get("raw_path", ""))
        cache_fallback_used = False
        fallback_rows = 0
        cache_frame = pd.DataFrame()
        fetch_failed = final.get("status") != "ok"
        if fetch_failed:
            cache_frame = _read_raw_frame(raw_path)
            if not cache_frame.empty:
                cache_fallback_used = True
                fallback_rows = len(cache_frame)
                raw_frames.append(_attach_fetch_meta(cache_frame, slug, str(final.get("status", "")), True))
        else:
            current_frame = _read_raw_frame(raw_path)
            if not current_frame.empty:
                raw_frames.append(_attach_fetch_meta(current_frame, slug, str(final.get("status", "")), False))

        prev_state = failure_state.get(slug, {})
        prev_failures = int(prev_state.get("consecutive_failures", 0) or 0)
        consecutive_failures = prev_failures + 1 if fetch_failed else 0
        reason = _classify_failure_reason(str(final.get("message", "")))
        failure_state[slug] = {
            "consecutive_failures": consecutive_failures,
            "last_status": str(final.get("status", "")),
            "last_message": str(final.get("message", "")),
            "last_reason": reason,
            "updated_at": now_ts,
        }
        alert_level = ""
        if fetch_failed and consecutive_failures >= 3:
            alert_level = "critical"
            alert_rows.append(
                {
                    "time": now_ts,
                    "company_slug": slug,
                    "consecutive_failures": consecutive_failures,
                    "reason": reason,
                    "cache_fallback_used": cache_fallback_used,
                    "cache_rows": fallback_rows,
                }
            )

        pre = preflight_map.get(slug, {})
        r = {
            **final,
            "company_slug": slug,
            "strategy_used": strategy_used,
            "attempt_count": attempt_count,
            "cache_fallback_used": int(cache_fallback_used),
            "cache_fallback_rows": int(fallback_rows),
            "consecutive_failures": consecutive_failures,
            "alert_level": alert_level,
            "failure_reason_category": reason,
            "precheck_status": pre.get("status", ""),
            "precheck_reason": pre.get("reason", ""),
            "status": "cache_fallback" if cache_fallback_used and fetch_failed else final.get("status", ""),
        }
        results.append(r)
        p = final.get("param_audit_path", "")
        if p and os.path.exists(p):
            param_reports.append(pd.read_csv(p, keep_default_na=False))
    _save_failure_state(failure_state_path, failure_state)
    if alert_rows:
        alert_df = pd.DataFrame(alert_rows)
        if os.path.exists(alert_path):
            old_alert = pd.read_csv(alert_path, keep_default_na=False)
            alert_df = pd.concat([old_alert, alert_df], ignore_index=True)
        alert_df.to_csv(alert_path, index=False, encoding="utf-8-sig")
    if raw_frames:
        all_raw = pd.concat(raw_frames, ignore_index=True)
        all_raw.to_csv("official_jobs_raw.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(results).to_csv(os.path.join(reports_dir, "source_fetch_health.csv"), index=False, encoding="utf-8-sig")
    if param_reports:
        pd.concat(param_reports, ignore_index=True).to_csv(
            os.path.join(reports_dir, "source_param_audit.csv"), index=False, encoding="utf-8-sig"
        )
    failed = sum(1 for x in results if x.get("status") != "ok")
    print("run_all_done", len(results), "failed", failed, "selected", ",".join(sorted(selected)))


if __name__ == "__main__":
    main()
