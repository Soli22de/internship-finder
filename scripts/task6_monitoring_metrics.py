import json
import os
from datetime import datetime

import pandas as pd


REPORT_DIR = r"outputs\reports"
LATEST_JSON = os.path.join(REPORT_DIR, "task6_monitoring_metrics_latest.json")
HISTORY_CSV = os.path.join(REPORT_DIR, "task6_monitoring_metrics_history.csv")

SUCCESS_RATE_THRESHOLD = 85.0
JD_REALNESS_THRESHOLD = 15.0
DELIVERY_HIT_RATE_THRESHOLD = 55.0


def ensure_dirs() -> None:
    os.makedirs(REPORT_DIR, exist_ok=True)


def _safe_read_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path, keep_default_na=False)


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_native(value):
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def compute_success_rate() -> dict:
    fetch_path = os.path.join(REPORT_DIR, "source_fetch_health.csv")
    df = _safe_read_csv(fetch_path)
    if df.empty:
        return {
            "source_rows": 0,
            "source_success_rows": 0,
            "source_success_rate": 0.0,
        }
    status = df.get("status", pd.Series([""] * len(df))).astype(str).str.strip().str.lower()
    ok = status.isin(["ok", "cache_fallback"])
    rate = round(ok.mean() * 100, 2) if len(df) else 0.0
    return {
        "source_rows": int(len(df)),
        "source_success_rows": int(ok.sum()),
        "source_success_rate": rate,
    }


def compute_jd_realness() -> dict:
    quality_path = os.path.join(REPORT_DIR, "data_quality_report.csv")
    quality = _safe_read_csv(quality_path)
    if quality.empty:
        return {
            "jd_realness_rate": 0.0,
            "trust_score_mean": 0.0,
            "dirty_ratio": 0.0,
        }
    all_row = quality[quality["source"].astype(str) == "all"]
    if all_row.empty:
        all_row = quality.tail(1)
    row = all_row.iloc[0].to_dict()
    return {
        "jd_realness_rate": round(_to_float(row.get("publish_time_真实率", 0.0)), 2),
        "trust_score_mean": round(_to_float(row.get("可信度均值", 0.0)), 2),
        "dirty_ratio": round(_to_float(row.get("脏数据占比", 0.0)), 2),
    }


def compute_delivery_hit_rate() -> dict:
    topn_path = os.path.join(REPORT_DIR, "resume_job_match_topN.csv")
    topn = _safe_read_csv(topn_path)
    if topn.empty:
        return {
            "delivery_candidate_rows": 0,
            "delivery_hit_rows": 0,
            "delivery_hit_rate": 0.0,
        }
    tier = topn.get("tier", pd.Series([""] * len(topn))).astype(str)
    must_hit_rate = pd.to_numeric(topn.get("must_hit_rate", pd.Series([0] * len(topn))), errors="coerce").fillna(0.0)
    evidence = topn.get("evidence_strength", pd.Series([""] * len(topn))).astype(str).str.lower()
    candidate = tier.isin(["A1", "A2", "B1", "B2"])
    hit = candidate & (must_hit_rate >= 0.6) & evidence.isin(["strong", "medium"])
    rate = round(hit.sum() / max(1, candidate.sum()) * 100, 2)
    return {
        "delivery_candidate_rows": int(candidate.sum()),
        "delivery_hit_rows": int(hit.sum()),
        "delivery_hit_rate": rate,
    }


def build_deviation_reasons(metrics: dict) -> list:
    reasons = []
    if metrics["source_success_rate"] < SUCCESS_RATE_THRESHOLD:
        reasons.append("源成功率未达阈值，建议排查失败源并关注连续失败告警。")
    if metrics["jd_realness_rate"] < JD_REALNESS_THRESHOLD:
        reasons.append("JD真实度低于阈值，建议优先治理发布时间代理源与缺失字段。")
    if metrics["delivery_hit_rate"] < DELIVERY_HIT_RATE_THRESHOLD:
        reasons.append("投递命中率低于阈值，建议先补齐must关键词与证据强度。")
    return reasons


def write_outputs(payload: dict) -> None:
    payload = {k: _to_native(v) for k, v in payload.items()}
    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    row = pd.DataFrame([payload])
    if os.path.exists(HISTORY_CSV):
        old = pd.read_csv(HISTORY_CSV, keep_default_na=False)
        row = pd.concat([old, row], ignore_index=True)
    row.to_csv(HISTORY_CSV, index=False, encoding="utf-8-sig")


def main() -> None:
    ensure_dirs()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    success = compute_success_rate()
    realness = compute_jd_realness()
    delivery = compute_delivery_hit_rate()
    merged = {
        "generated_at": now,
        **success,
        **realness,
        **delivery,
        "source_success_rate_threshold": SUCCESS_RATE_THRESHOLD,
        "jd_realness_rate_threshold": JD_REALNESS_THRESHOLD,
        "delivery_hit_rate_threshold": DELIVERY_HIT_RATE_THRESHOLD,
    }
    merged["is_source_success_rate_ok"] = merged["source_success_rate"] >= SUCCESS_RATE_THRESHOLD
    merged["is_jd_realness_rate_ok"] = merged["jd_realness_rate"] >= JD_REALNESS_THRESHOLD
    merged["is_delivery_hit_rate_ok"] = merged["delivery_hit_rate"] >= DELIVERY_HIT_RATE_THRESHOLD
    merged["is_all_metrics_ok"] = bool(
        merged["is_source_success_rate_ok"] and merged["is_jd_realness_rate_ok"] and merged["is_delivery_hit_rate_ok"]
    )
    reasons = build_deviation_reasons(merged)
    merged["deviation_reason"] = "；".join(reasons)
    write_outputs(merged)
    print("task6_metrics", merged["source_success_rate"], merged["jd_realness_rate"], merged["delivery_hit_rate"], merged["is_all_metrics_ok"])


if __name__ == "__main__":
    main()
