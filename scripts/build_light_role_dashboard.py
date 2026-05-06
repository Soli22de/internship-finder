import json
import os

import pandas as pd


REPORT_DIR = r"outputs\reports"
DASHBOARD_DIR = r"outputs\dashboard"
MATCH_FILE = os.path.join(REPORT_DIR, "resume_job_match_topN.csv")
METRICS_FILE = os.path.join(REPORT_DIR, "jd_decision_metrics.json")
OUTPUT_FILE = os.path.join(DASHBOARD_DIR, "role_dashboard_light.html")


def ensure_dirs() -> None:
    os.makedirs(DASHBOARD_DIR, exist_ok=True)


def load_inputs() -> tuple[pd.DataFrame, dict]:
    if not os.path.exists(MATCH_FILE):
        raise FileNotFoundError(MATCH_FILE)
    match = pd.read_csv(MATCH_FILE, keep_default_na=False)
    metrics = {}
    if os.path.exists(METRICS_FILE):
        with open(METRICS_FILE, "r", encoding="utf-8") as f:
            metrics = json.load(f)
    return match, metrics


def build_html(match: pd.DataFrame, metrics: dict) -> str:
    records = match[
        [
            "company",
            "name",
            "role_family",
            "tier",
            "score",
            "competition_level",
            "evidence_strength",
            "url",
        ]
    ].to_dict(orient="records")
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>轻量角色化看板</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 16px; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin-bottom: 12px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 13px; }}
    th {{ background: #f5f5f5; }}
    select {{ margin-right: 8px; }}
  </style>
</head>
<body>
  <h2>角色化轻量看板</h2>
  <div class="card">
    <div>生成时间：{metrics.get("generated_at", "")}</div>
    <div>岗位总量：{metrics.get("topn_rows", len(records))}</div>
    <div>竞争度分布：{json.dumps(metrics.get("competition_level_counts", {}), ensure_ascii=False)}</div>
    <div>证据强度分布：{json.dumps(metrics.get("evidence_strength_counts", {}), ensure_ascii=False)}</div>
  </div>
  <div class="card">
    <label>角色：</label>
    <select id="role">
      <option value="all">all</option>
      <option value="data_engineer">data_engineer</option>
      <option value="recruit_ops">recruit_ops</option>
      <option value="job_seeker">job_seeker</option>
      <option value="business_analyst">business_analyst</option>
    </select>
    <label>公司：</label>
    <select id="company"></select>
    <label>分档：</label>
    <select id="tier">
      <option value="">全部</option>
      <option value="A1">A1</option>
      <option value="A2">A2</option>
      <option value="B1">B1</option>
      <option value="B2">B2</option>
      <option value="C">C</option>
    </select>
  </div>
  <table>
    <thead>
      <tr>
        <th>公司</th><th>岗位</th><th>岗位族</th><th>分档</th><th>评分</th><th>竞争度</th><th>证据强度</th><th>链接</th>
      </tr>
    </thead>
    <tbody id="rows"></tbody>
  </table>
  <script>
    const rawData = {json.dumps(records, ensure_ascii=False)};
    const roleEl = document.getElementById("role");
    const companyEl = document.getElementById("company");
    const tierEl = document.getElementById("tier");
    const tbody = document.getElementById("rows");

    function roleFilter(data, role) {{
      if (role === "job_seeker") return data.filter(x => ["A1","A2","B1"].includes(x.tier));
      if (role === "recruit_ops") return data.filter(x => x.competition_level === "high");
      if (role === "business_analyst") return data.filter(x => ["策略分析/增长分析","数据分析/商业分析"].includes(x.role_family));
      return data;
    }}

    function refreshCompanyOptions(data) {{
      const companies = [...new Set(data.map(x => x.company))].sort();
      companyEl.innerHTML = '<option value="">全部</option>' + companies.map(x => `<option value="${{x}}">${{x}}</option>`).join("");
    }}

    function render() {{
      let data = roleFilter(rawData, roleEl.value);
      refreshCompanyOptions(data);
      if (companyEl.value) data = data.filter(x => x.company === companyEl.value);
      if (tierEl.value) data = data.filter(x => x.tier === tierEl.value);
      tbody.innerHTML = data.slice(0, 300).map(r => `
        <tr>
          <td>${{r.company}}</td>
          <td>${{r.name}}</td>
          <td>${{r.role_family}}</td>
          <td>${{r.tier}}</td>
          <td>${{r.score}}</td>
          <td>${{r.competition_level || ""}}</td>
          <td>${{r.evidence_strength || ""}}</td>
          <td><a href="${{r.url}}" target="_blank">link</a></td>
        </tr>
      `).join("");
    }}

    roleEl.addEventListener("change", render);
    companyEl.addEventListener("change", render);
    tierEl.addEventListener("change", render);
    render();
  </script>
</body>
</html>
"""
    return html


def main() -> None:
    ensure_dirs()
    match, metrics = load_inputs()
    html = build_html(match, metrics)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print("done", OUTPUT_FILE)


if __name__ == "__main__":
    main()
