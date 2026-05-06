import json
import os
from datetime import datetime

import pandas as pd


BASE_DIR = r"c:\jz_code\internship_finding"
REPORT_DIR = os.path.join(BASE_DIR, "outputs", "reports")
RAW_DIR = os.path.join(BASE_DIR, "outputs", "raw")


def load_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path, keep_default_na=False)


def to_records(df: pd.DataFrame, limit: int = 20):
    if df.empty:
        return []
    return df.head(limit).to_dict(orient="records")


def build_metrics():
    master = load_csv(os.path.join(REPORT_DIR, "internship_all_master.csv"))
    target = load_csv(os.path.join(REPORT_DIR, "internship_target_jobs.csv"))
    quality = load_csv(os.path.join(REPORT_DIR, "data_quality_report.csv"))
    funnel = load_csv(os.path.join(REPORT_DIR, "funnel_diagnostics_by_company.csv"))
    skill = load_csv(os.path.join(REPORT_DIR, "internship_skill_gap_report.csv"))
    fetch_health = load_csv(os.path.join(REPORT_DIR, "source_fetch_health.csv"))
    param_audit = load_csv(os.path.join(REPORT_DIR, "source_param_audit.csv"))
    resume_match = load_csv(os.path.join(REPORT_DIR, "resume_job_match_topN.csv"))

    source_counts = master["source"].value_counts().to_dict() if not master.empty and "source" in master.columns else {}
    company_counts = target["company"].value_counts().to_dict() if not target.empty and "company" in target.columns else {}

    major_sources = [
        "official_bytedance",
        "official_tencent_api",
        "official_kuaishou_api",
        "official_xiaohongshu",
        "official_meituan",
        "official_alibaba",
        "official_jd_api",
        "official_bilibili",
    ]
    quality_major = quality[quality["source"].isin(major_sources)] if not quality.empty and "source" in quality.columns else pd.DataFrame()

    raw_rows = []
    for file_name in sorted(os.listdir(RAW_DIR)) if os.path.exists(RAW_DIR) else []:
        if not file_name.endswith("_official_raw.csv"):
            continue
        p = os.path.join(RAW_DIR, file_name)
        df = load_csv(p)
        raw_rows.append({"file": file_name, "rows": int(len(df))})
    raw_df = pd.DataFrame(raw_rows)

    tier_counts = resume_match["tier"].value_counts().to_dict() if not resume_match.empty and "tier" in resume_match.columns else {}
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "master_rows": int(len(master)),
        "target_rows": int(len(target)),
        "source_counts": source_counts,
        "target_company_counts": company_counts,
        "quality_major": to_records(
            quality_major[
                [
                    "source",
                    "rows",
                    "city_完整率",
                    "url_完整率",
                    "jd_raw_完整率",
                    "requirement_完整率",
                    "publish_time_可用率",
                    "publish_time_真实率",
                    "publish_time_代理率",
                ]
            ]
            if not quality_major.empty
            else pd.DataFrame()
        ),
        "funnel_top": to_records(funnel.sort_values("final_target_count", ascending=False) if not funnel.empty else pd.DataFrame(), 20),
        "skill_top15": to_records(skill.sort_values("count", ascending=False) if not skill.empty else pd.DataFrame(), 15),
        "fetch_health": to_records(fetch_health, 20),
        "param_audit": to_records(param_audit, 20),
        "raw_file_rows": to_records(raw_df, 20),
        "resume_tier_counts": tier_counts,
    }


def build_markdown(metrics: dict) -> str:
    md = []
    md.append("# 项目核心抓取与JD分析总报告")
    md.append("")
    md.append(f"- 生成时间：{metrics['generated_at']}")
    md.append(f"- 主库总量：{metrics['master_rows']}")
    md.append(f"- 目标池总量：{metrics['target_rows']}")
    md.append("")
    md.append("## 1) 核心抓取链路（端到端）")
    md.append("- 调度入口：`official_multi_crawler.py -> crawlers/run_all_official.py`")
    md.append("- 公司抓取：`crawlers/*_crawler.py` 分公司独立执行")
    md.append("- 标准协议：`crawlers/schema.py` 统一字段")
    md.append("- 清洗合并：`merge_file.py`（城市归一、27届规则、分层池、质量报表、看板）")
    md.append("- 简历匹配：`scripts/resume_job_match_pipeline.py`（硬门槛、ATS匹配、投递日历）")
    md.append("")
    md.append("## 2) 核心数据规模")
    md.append("### 来源规模")
    for k, v in metrics["source_counts"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("### 目标池公司分布")
    for k, v in metrics["target_company_counts"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## 3) 质量指标（官方源）")
    for item in metrics["quality_major"]:
        md.append(
            f"- {item['source']} rows={item['rows']} city={item['city_完整率']}% url={item['url_完整率']}% jd={item['jd_raw_完整率']}% req={item['requirement_完整率']}% publish={item['publish_time_可用率']}% real={item['publish_time_真实率']}% proxy={item['publish_time_代理率']}%"
        )
    md.append("")
    md.append("## 4) 当前抓取健康（运行态）")
    for item in metrics["fetch_health"]:
        md.append(f"- {item.get('company_slug','')}: rows={item.get('rows','')} status={item.get('status','')} elapsed_ms={item.get('elapsed_ms','')}")
    md.append("")
    md.append("### 原始文件行数")
    for item in metrics["raw_file_rows"]:
        md.append(f"- {item['file']}: {item['rows']}")
    md.append("")
    md.append("## 5) 关键词体系（当前统计Top15）")
    for item in metrics["skill_top15"]:
        md.append(f"- {item.get('skill','')}: count={item.get('count','')} coverage={item.get('coverage_pct','')}%")
    md.append("")
    md.append("## 6) 漏斗视角（Top公司）")
    for item in metrics["funnel_top"][:10]:
        md.append(
            f"- {item.get('company','')}: raw={item.get('raw_count','')} city_relaxed={item.get('city_relaxed_count','')} high={item.get('cohort_high','')} medium={item.get('cohort_medium','')} final={item.get('final_target_count','')}"
        )
    md.append("")
    md.append("## 7) 核心规则与业务逻辑")
    md.append("- 城市：`strict_shanghai / contains_shanghai / multi_base_contains_shanghai` 三层匹配")
    md.append("- 27届：`rules/cohort27_rules.py` 的高/中/低置信规则融合（时间窗、暑期实习、留用、来源信号）")
    md.append("- 分层：目标池按 `A/B/C` 与 `strict_27 / inferred_27` 双维导出")
    md.append("- 链接健康：`utils/link_checker.py` 异步校验并输出坏链报告")
    md.append("")
    md.append("## 8) JD深度分析方法（增强建议）")
    md.append("- 方法1：必选词/加分词分离（must-plus），将“要求/必须/掌握”与“优先/加分”拆分打分")
    md.append("- 方法2：句级职责-能力映射，将JD按句切分并映射到技能、业务场景、产出指标三元组")
    md.append("- 方法3：时间约束抽取，统一解析`每周天数/最短实习月数/到岗时间/截止时间`并做硬门槛过滤")
    md.append("- 方法4：岗位族聚类，按职责文本而非岗位名聚类（数分/数开/策略/算法）减少误判")
    md.append("- 方法5：竞争度估计，结合发布时间、岗位数量变化、公司历史关闭率构建投递优先级")
    md.append("- 方法6：证据强度评估，把简历项目中的量化结果映射到JD关键词，做“可解释缺口”输出")
    md.append("")
    md.append("## 9) 当前可见风险与补齐优先级")
    md.append("- 优先级P0：源级行数异常（某些raw文件为0）需执行单源重试与参数回退")
    md.append("- 优先级P1：发布时间真实率偏低源（如腾讯）继续补`update_time`代理策略")
    md.append("- 优先级P1：`requirement_完整率`偏低源需强化`split_jd`回填与详情补抓")
    md.append("- 优先级P2：关键词同义词扩展（如AB测试/A-B test/实验设计）提高JD解析召回")
    md.append("")
    return "\n".join(md)


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    metrics = build_metrics()
    md = build_markdown(metrics)
    md_path = os.path.join(REPORT_DIR, "project_core_logic_report.md")
    json_path = os.path.join(REPORT_DIR, "project_core_metrics.json")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print("done", md_path, json_path)


if __name__ == "__main__":
    main()

