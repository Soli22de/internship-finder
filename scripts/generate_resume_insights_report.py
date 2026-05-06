import argparse
import os
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


REPORT_DIR = r"outputs\reports"
FIG_DIR = os.path.join(REPORT_DIR, "figures")


def ensure_dirs() -> None:
    os.makedirs(FIG_DIR, exist_ok=True)


def load_data() -> dict:
    competition_path = os.path.join(REPORT_DIR, "high_competition_strategy_report.csv")
    contribution_path = os.path.join(REPORT_DIR, "skill_contribution_report.csv")
    sentence_map_path = os.path.join(REPORT_DIR, "jd_sentence_mapping.csv")
    time_constraint_path = os.path.join(REPORT_DIR, "time_constraints_report.csv")
    return {
        "match": pd.read_csv(os.path.join(REPORT_DIR, "resume_job_match_topN.csv"), keep_default_na=False),
        "screen": pd.read_csv(os.path.join(REPORT_DIR, "internship_post_screening_result.csv"), keep_default_na=False),
        "gap": pd.read_csv(os.path.join(REPORT_DIR, "resume_gap_analysis.csv"), keep_default_na=False),
        "calendar": pd.read_csv(os.path.join(REPORT_DIR, "delivery_calendar.csv"), keep_default_na=False),
        "summary": pd.read_csv(os.path.join(REPORT_DIR, "company_role_fit_summary.csv"), keep_default_na=False),
        "competition": pd.read_csv(competition_path, keep_default_na=False) if os.path.exists(competition_path) else pd.DataFrame(),
        "contribution": pd.read_csv(contribution_path, keep_default_na=False) if os.path.exists(contribution_path) else pd.DataFrame(),
        "sentence_map": pd.read_csv(sentence_map_path, keep_default_na=False) if os.path.exists(sentence_map_path) else pd.DataFrame(),
        "time_constraints": pd.read_csv(time_constraint_path, keep_default_na=False) if os.path.exists(time_constraint_path) else pd.DataFrame(),
    }


def save_plot(fig_name: str) -> str:
    path = os.path.join(FIG_DIR, fig_name)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def plot_tier_distribution(match: pd.DataFrame) -> str:
    order = ["A1", "A2", "B1", "B2", "C"]
    s = match["tier"].value_counts().reindex(order, fill_value=0)
    plt.figure(figsize=(8, 4))
    bars = plt.bar(s.index, s.values, color=["#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd", "#d62728"])
    plt.title("岗位分档分布")
    plt.ylabel("岗位数")
    for b in bars:
        plt.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{int(b.get_height())}", ha="center", va="bottom")
    return save_plot("tier_distribution.png")


def plot_company_a_tier(match: pd.DataFrame) -> str:
    a = match[match["tier"].isin(["A1", "A2"])].copy()
    s = a.groupby("company").size().sort_values(ascending=False).head(12)
    plt.figure(figsize=(10, 5))
    bars = plt.barh(s.index[::-1], s.values[::-1], color="#2ca02c")
    plt.title("A档岗位Top公司")
    plt.xlabel("A档岗位数")
    for b in bars:
        plt.text(b.get_width(), b.get_y() + b.get_height() / 2, f"{int(b.get_width())}", va="center")
    return save_plot("company_a_tier_top.png")


def plot_role_family_score(match: pd.DataFrame) -> str:
    s = match.groupby("role_family", as_index=False)["score"].mean().sort_values("score", ascending=False)
    plt.figure(figsize=(9, 4))
    bars = plt.bar(s["role_family"], s["score"], color="#1f77b4")
    plt.title("岗位族平均匹配分")
    plt.ylabel("平均分")
    plt.xticks(rotation=15, ha="right")
    for b in bars:
        plt.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{b.get_height():.1f}", ha="center", va="bottom")
    return save_plot("role_family_avg_score.png")


def plot_hard_screen_reasons(screen: pd.DataFrame) -> str:
    failed = screen[screen["hard_pass"] == False].copy()
    if failed.empty:
        plt.figure(figsize=(8, 4))
        plt.text(0.5, 0.5, "无硬门槛淘汰数据", ha="center", va="center")
        plt.axis("off")
        return save_plot("hard_screen_reasons.png")
    reasons = (
        failed["hard_reason"]
        .astype(str)
        .str.split("；")
        .explode()
        .value_counts()
        .head(10)
    )
    plt.figure(figsize=(10, 5))
    bars = plt.barh(reasons.index[::-1], reasons.values[::-1], color="#d62728")
    plt.title("硬门槛淘汰原因Top10")
    plt.xlabel("淘汰岗位数")
    for b in bars:
        plt.text(b.get_width(), b.get_y() + b.get_height() / 2, f"{int(b.get_width())}", va="center")
    return save_plot("hard_screen_reasons.png")


def plot_gap_keywords(gap: pd.DataFrame) -> str:
    g = gap.head(12)
    plt.figure(figsize=(10, 5))
    bars = plt.barh(g["missing_keyword"][::-1], g["affected_jobs"][::-1], color="#ff7f0e")
    plt.title("简历缺口关键词Top12")
    plt.xlabel("影响岗位数")
    for b in bars:
        plt.text(b.get_width(), b.get_y() + b.get_height() / 2, f"{int(b.get_width())}", va="center")
    return save_plot("gap_keywords_top.png")


def plot_delivery_timeline(calendar: pd.DataFrame) -> str:
    c = calendar.groupby("plan_date").size()
    plt.figure(figsize=(10, 4))
    bars = plt.bar(c.index, c.values, color="#9467bd")
    plt.title("投递日历（每日建议投递量）")
    plt.ylabel("岗位数")
    plt.xticks(rotation=30, ha="right")
    for b in bars:
        plt.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{int(b.get_height())}", ha="center", va="bottom")
    return save_plot("delivery_timeline.png")


def make_insights(data: dict) -> list:
    match = data["match"]
    screen = data["screen"]
    gap = data["gap"]
    calendar = data["calendar"]
    total = len(screen)
    passed = int((screen["hard_pass"] == True).sum())
    a_cnt = int(match["tier"].isin(["A1", "A2"]).sum())
    a_share = (a_cnt / len(match) * 100) if len(match) else 0
    top_company = (
        match[match["tier"].isin(["A1", "A2"])]
        .groupby("company")
        .size()
        .sort_values(ascending=False)
        .head(3)
    )
    top_company_text = "、".join([f"{k}({int(v)})" for k, v in top_company.items()]) if len(top_company) else "无"
    top_gap = "、".join(gap.head(5)["missing_keyword"].tolist()) if not gap.empty else "无"
    daily_avg = round(calendar.groupby("plan_date").size().mean(), 1) if not calendar.empty else 0
    return [
        f"硬门槛通过率为 {passed}/{total}（{(passed/max(1,total)*100):.1f}%），说明当前岗位池可投比例较高，但仍有明显淘汰噪声需要持续清洗。",
        f"A档岗位数量为 {a_cnt}（占评分岗位 {a_share:.1f}%），高优先岗位集中在：{top_company_text}。",
        f"简历当前最影响投递转化的关键词缺口为：{top_gap}，应优先在项目经历中补齐。",
        f"当前投递节奏建议日均约 {daily_avg} 个岗位，适合“少量高质量+快速微调”策略，避免海投。",
    ]


def get_role_templates(role: str, data: dict) -> list:
    match = data["match"]
    competition = data["competition"]
    contribution = data["contribution"]
    time_constraints = data["time_constraints"]
    if role == "data_engineer":
        hard_fail = int((data["screen"]["hard_pass"] == False).sum())
        return [
            f"- 运行规模：初筛 {len(data['screen'])}，评分 {len(match)}，硬淘汰 {hard_fail}",
            f"- 数据结构：句级映射 {len(data['sentence_map'])} 条，时间约束 {len(time_constraints)} 条",
            "- 建议优先治理 requirement 缺失源与发布时间代理源，持续提升JD解释质量",
        ]
    if role == "recruit_ops":
        high_comp = int((match["competition_level"] == "high").sum()) if "competition_level" in match.columns else 0
        top_comp = "、".join(competition.head(3)["company"].tolist()) if not competition.empty else "无"
        return [
            f"- 高竞争岗位数：{high_comp}，建议优先做快速邀约与内推协同",
            f"- 高竞争集中公司：{top_comp}",
            "- 可优先关注 must 命中率高且证据强度 strong 的岗位候选",
        ]
    if role == "business_analyst":
        fam_top = match.groupby("role_family")["score"].mean().sort_values(ascending=False).head(2)
        fam_text = "、".join([f"{k}({v:.1f})" for k, v in fam_top.items()]) if len(fam_top) else "无"
        return [
            f"- 高价值岗位族：{fam_text}",
            f"- 高频技能证据记录：{len(contribution)} 条，可用于识别核心能力贡献",
            "- 结合竞争度与缺口词可形成季度投递策略分层",
        ]
    low_comp = match[(match["tier"].isin(["A1", "A2"])) & (match["competition_level"] != "high")] if "competition_level" in match.columns else match.head(0)
    top_jobs = "、".join(low_comp.head(3)["name"].tolist()) if not low_comp.empty else "无"
    return [
        f"- 低竞争高匹配岗位示例：{top_jobs}",
        "- 建议先投 A1/A2 且证据强度 strong 的岗位，B档岗位先补关键词再投",
        "- 时间约束不满足岗位建议移出本周计划，避免低效投递",
    ]


def build_markdown_report(figs: dict, data: dict, insights: list, role: str) -> str:
    match = data["match"]
    screen = data["screen"]
    summary = data["summary"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_path = os.path.join(REPORT_DIR, f"resume_matching_visual_report_{role}.md")
    top10 = (
        match[match["tier"].isin(["A1", "A2"])]
        .sort_values(["tier", "score"], ascending=[True, False])
        .head(10)[["company", "name", "tier", "score", "resume_version", "url"]]
    )
    lines = []
    lines.append(f"# 简历-岗位匹配可视化报告")
    lines.append("")
    lines.append(f"- 生成时间：{now}")
    lines.append(f"- 样本规模：初筛样本 {len(screen)}，评分样本 {len(match)}")
    lines.append("")
    lines.append("## 一、全局看板")
    lines.append(f"![岗位分档分布](figures/{os.path.basename(figs['tier'])})")
    lines.append(f"![A档Top公司](figures/{os.path.basename(figs['company'])})")
    lines.append(f"![岗位族平均分](figures/{os.path.basename(figs['family'])})")
    lines.append("")
    lines.append("## 二、质量与风险")
    lines.append(f"![硬门槛淘汰原因](figures/{os.path.basename(figs['screen'])})")
    lines.append(f"![缺口关键词](figures/{os.path.basename(figs['gap'])})")
    lines.append("")
    lines.append("## 三、投递执行节奏")
    lines.append(f"![投递日历](figures/{os.path.basename(figs['calendar'])})")
    lines.append("")
    lines.append("## 四、关键Insights")
    for i in insights:
        lines.append(f"- {i}")
    lines.append("")
    lines.append("## 五、角色化结论")
    for i in get_role_templates(role, data):
        lines.append(i)
    lines.append("")
    lines.append("## 六、A档Top10建议岗位")
    lines.append(top10.to_markdown(index=False))
    lines.append("")
    lines.append("## 七、公司-岗位族总览（Top20）")
    lines.append(summary.head(20).to_markdown(index=False))
    if not data["competition"].empty:
        lines.append("")
        lines.append("## 八、高竞争岗位特征与建议")
        lines.append(data["competition"].head(15).to_markdown(index=False))
    if not data["contribution"].empty:
        lines.append("")
        lines.append("## 九、证据强度与技能贡献")
        lines.append(
            data["contribution"]
            .groupby(["skill", "evidence_strength"], as_index=False)["contribution_rate"]
            .mean()
            .sort_values("contribution_rate", ascending=False)
            .head(20)
            .to_markdown(index=False)
        )
    if not data["time_constraints"].empty:
        lines.append("")
        lines.append("## 十、时间约束概览")
        tc = data["time_constraints"]
        days_col = pd.to_numeric(tc["intern_days_required"], errors="coerce").fillna(0)
        months_col = pd.to_numeric(tc["intern_months_required"], errors="coerce").fillna(0)
        exp_col = pd.to_numeric(tc["experience_years_required"], errors="coerce").fillna(0)
        tc_summary = pd.DataFrame(
            [
                {
                    "每周天数约束岗位数": int((days_col > 0).sum()),
                    "实习月数约束岗位数": int((months_col > 0).sum()),
                    "经验年限约束岗位数": int((exp_col > 0).sum()),
                }
            ]
        )
        lines.append(tc_summary.to_markdown(index=False))
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return report_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--role", default="all", choices=["all", "data_engineer", "recruit_ops", "job_seeker", "business_analyst"])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dirs()
    data = load_data()
    figs = {
        "tier": plot_tier_distribution(data["match"]),
        "company": plot_company_a_tier(data["match"]),
        "family": plot_role_family_score(data["match"]),
        "screen": plot_hard_screen_reasons(data["screen"]),
        "gap": plot_gap_keywords(data["gap"]),
        "calendar": plot_delivery_timeline(data["calendar"]),
    }
    insights = make_insights(data)
    roles = ["data_engineer", "recruit_ops", "job_seeker", "business_analyst"] if args.role == "all" else [args.role]
    report_paths = [build_markdown_report(figs, data, insights, role=r) for r in roles]
    pd.DataFrame({"insight": insights}).to_csv(os.path.join(REPORT_DIR, "resume_matching_key_insights.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame({"role": roles, "report_path": report_paths}).to_csv(
        os.path.join(REPORT_DIR, "role_reports_index.csv"),
        index=False,
        encoding="utf-8-sig",
    )
    print("report", ",".join(report_paths))


if __name__ == "__main__":
    main()
