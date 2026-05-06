import os
from datetime import datetime

import pandas as pd


REPORT_DIR = r"outputs\reports"
METRICS_HISTORY = os.path.join(REPORT_DIR, "task6_monitoring_metrics_history.csv")
BIWEEKLY_LOG = os.path.join(REPORT_DIR, "task6_biweekly_regression_log.csv")
BIWEEKLY_MD = os.path.join(REPORT_DIR, "task6_biweekly_regression_latest.md")


def ensure_dirs() -> None:
    os.makedirs(REPORT_DIR, exist_ok=True)


def _safe_read_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path, keep_default_na=False)


def _to_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _pick_baseline(history: pd.DataFrame, now: datetime) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=object)
    history = history.copy()
    history["generated_at_dt"] = pd.to_datetime(history["generated_at"], errors="coerce")
    history = history.dropna(subset=["generated_at_dt"]).sort_values("generated_at_dt")
    if history.empty:
        return pd.Series(dtype=object)
    threshold = now - pd.Timedelta(days=14)
    old = history[history["generated_at_dt"] <= threshold]
    if not old.empty:
        return old.iloc[-1]
    return history.iloc[0]


def _build_status(delta: float, lower_bound: float = -5.0) -> str:
    if delta >= 0:
        return "improved"
    if delta >= lower_bound:
        return "stable"
    return "degraded"


def _build_action(status_success: str, status_jd: str, status_delivery: str) -> str:
    actions = []
    if status_success == "degraded":
        actions.append("排查失败源并优化重试与兜底")
    if status_jd == "degraded":
        actions.append("优先治理发布时间代理与脏数据源")
    if status_delivery == "degraded":
        actions.append("提高must关键词命中并强化证据表达")
    if not actions:
        actions.append("保持策略并继续观察双周趋势")
    return "；".join(actions)


def write_markdown(row: dict) -> None:
    lines = [
        "# Task6 双周回归记录",
        "",
        f"- 记录时间：{row['run_at']}",
        f"- 基线时间：{row['baseline_at']}",
        f"- 源成功率：{row['source_success_rate']}%（Δ{row['delta_source_success_rate']}%，{row['status_source_success_rate']}）",
        f"- JD真实度：{row['jd_realness_rate']}%（Δ{row['delta_jd_realness_rate']}%，{row['status_jd_realness_rate']}）",
        f"- 投递命中率：{row['delivery_hit_rate']}%（Δ{row['delta_delivery_hit_rate']}%，{row['status_delivery_hit_rate']}）",
        f"- 本轮结论：{row['regression_result']}",
        f"- 改进动作：{row['improvement_action']}",
    ]
    with open(BIWEEKLY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    ensure_dirs()
    history = _safe_read_csv(METRICS_HISTORY)
    now = datetime.now()
    if history.empty:
        row = {
            "run_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "baseline_at": "",
            "source_success_rate": 0.0,
            "jd_realness_rate": 0.0,
            "delivery_hit_rate": 0.0,
            "delta_source_success_rate": 0.0,
            "delta_jd_realness_rate": 0.0,
            "delta_delivery_hit_rate": 0.0,
            "status_source_success_rate": "initialized",
            "status_jd_realness_rate": "initialized",
            "status_delivery_hit_rate": "initialized",
            "regression_result": "initialized",
            "improvement_action": "初始化基线，等待后续双周对比",
        }
    else:
        current = history.iloc[-1]
        baseline = _pick_baseline(history, now)
        cur_success = _to_float(current.get("source_success_rate", 0.0))
        cur_jd = _to_float(current.get("jd_realness_rate", 0.0))
        cur_delivery = _to_float(current.get("delivery_hit_rate", 0.0))
        base_success = _to_float(baseline.get("source_success_rate", cur_success))
        base_jd = _to_float(baseline.get("jd_realness_rate", cur_jd))
        base_delivery = _to_float(baseline.get("delivery_hit_rate", cur_delivery))
        delta_success = round(cur_success - base_success, 2)
        delta_jd = round(cur_jd - base_jd, 2)
        delta_delivery = round(cur_delivery - base_delivery, 2)
        status_success = _build_status(delta_success)
        status_jd = _build_status(delta_jd)
        status_delivery = _build_status(delta_delivery)
        degraded_count = [status_success, status_jd, status_delivery].count("degraded")
        if degraded_count == 0:
            result = "pass"
        elif degraded_count == 1:
            result = "pass_with_action"
        else:
            result = "risk"
        row = {
            "run_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "baseline_at": str(baseline.get("generated_at", "")),
            "source_success_rate": round(cur_success, 2),
            "jd_realness_rate": round(cur_jd, 2),
            "delivery_hit_rate": round(cur_delivery, 2),
            "delta_source_success_rate": delta_success,
            "delta_jd_realness_rate": delta_jd,
            "delta_delivery_hit_rate": delta_delivery,
            "status_source_success_rate": status_success,
            "status_jd_realness_rate": status_jd,
            "status_delivery_hit_rate": status_delivery,
            "regression_result": result,
            "improvement_action": _build_action(status_success, status_jd, status_delivery),
        }
    out = pd.DataFrame([row])
    if os.path.exists(BIWEEKLY_LOG):
        old = pd.read_csv(BIWEEKLY_LOG, keep_default_na=False)
        out = pd.concat([old, out], ignore_index=True)
    out.to_csv(BIWEEKLY_LOG, index=False, encoding="utf-8-sig")
    write_markdown(row)
    print("task6_biweekly", row["regression_result"], row["baseline_at"])


if __name__ == "__main__":
    main()
