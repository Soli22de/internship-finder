import os
import sys
import time
import json
import subprocess
from datetime import datetime
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TASKS = [
    {
        "id": "cdp_scraper",
        "name": "泛化 CDP 动态抓取引擎",
        "command": [sys.executable, os.path.join(ROOT, "tools", "cdp", "cdp_scraper.py")],
        "cwd": ROOT,
        "timeout": 3600,
        "enabled": True
    },
    {
        "id": "official_multi_crawler",
        "name": "官方多源爬虫 (基于 API/Playwright)",
        "command": [sys.executable, os.path.join(ROOT, "official_multi_crawler.py")],
        "cwd": ROOT,
        "timeout": 7200,
        "enabled": True
    },
    {
        "id": "foreign_pipeline",
        "name": "外企高优岗爬取流水线",
        "command": [sys.executable, os.path.join(ROOT, "ResuMiner", "scripts", "foreign_pipeline_v2.py")],
        "cwd": os.path.join(ROOT, "ResuMiner"),
        "timeout": 7200,
        "enabled": True
    },
    {
        "id": "shixiseng_crawler",
        "name": "第三方平台: 实习僧",
        "command": [sys.executable, os.path.join(ROOT, "ResuMiner", "scripts", "crawl.py"), "--site", "shixiseng"],
        "cwd": os.path.join(ROOT, "ResuMiner"),
        "timeout": 3600,
        "enabled": True
    },
    {
        "id": "liepin_crawler",
        "name": "第三方平台: 猎聘",
        "command": [sys.executable, os.path.join(ROOT, "ResuMiner", "scripts", "crawl.py"), "--site", "liepin"],
        "cwd": os.path.join(ROOT, "ResuMiner"),
        "timeout": 3600,
        "enabled": True
    },
    {
        "id": "yingjiesheng_crawler",
        "name": "第三方平台: 应届生",
        "command": [sys.executable, os.path.join(ROOT, "ResuMiner", "scripts", "crawl.py"), "--site", "yingjiesheng"],
        "cwd": os.path.join(ROOT, "ResuMiner"),
        "timeout": 3600,
        "enabled": True
    },
    {
        "id": "job51_crawler",
        "name": "第三方平台: 前程无忧(51job)",
        "command": [sys.executable, os.path.join(ROOT, "ResuMiner", "scripts", "run_foreign_thirdparty_fetch.py")],
        "cwd": os.path.join(ROOT, "ResuMiner"),
        "timeout": 3600,
        "enabled": True
    }
]

def send_alert(message: str):
    """
    Push alert notification to user. 
    Can be configured via WxPusher / ServerChan / Bark etc.
    """
    print("\n" + "="*50)
    print("🚨 爬虫调度器报警 🚨")
    print(message)
    print("="*50 + "\n")
    # TODO: Add real Webhook push here (e.g. ServerChan)
    # requests.post("https://sctapi.ftqq.com/YOUR_KEY.send", data={"title": "爬虫报警", "desp": message})

def generate_health_report(reports_dir: str, results: list):
    """Generate a markdown health report."""
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, "crawler_health_report.md")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 爬虫统一调度与健康监控报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## 任务执行状态\n\n")
        f.write("| 任务 ID | 任务名称 | 状态 | 耗时 (s) | 错误信息 |\n")
        f.write("|---------|----------|------|----------|----------|\n")
        
        for res in results:
            status_icon = "✅ 成功" if res['status'] == 'success' else "❌ 失败"
            error_msg = res.get('error', '-')
            f.write(f"| {res['id']} | {res['name']} | {status_icon} | {res['duration']:.1f} | {error_msg} |\n")
            
        f.write("\n## 数据源健康度快照 (Latest)\n\n")
        
        # Try to read official raw file
        official_raw_path = os.path.join(ROOT, "official_jobs_raw.csv")
        if os.path.exists(official_raw_path):
            try:
                df = pd.read_csv(official_raw_path)
                f.write("### 官方多源数据 (official_jobs_raw.csv)\n")
                f.write(f"- **总记录数**: {len(df)}\n")
                f.write("- **各公司分布**:\n")
                counts = df['company'].value_counts()
                for company, count in counts.items():
                    f.write(f"  - {company}: {count} 条\n")
                
                # Missing fields audit
                f.write("- **关键字段缺失率**:\n")
                for col in ['jd_raw', 'city', 'publish_time']:
                    if col in df.columns:
                        missing = df[col].isna().sum() + (df[col] == '').sum()
                        rate = missing / len(df) * 100
                        f.write(f"  - `{col}` 缺失率: {rate:.2f}%\n")
                f.write("\n")
            except Exception as e:
                f.write(f"读取官方源数据出错: {e}\n\n")
                
        # Try to read foreign master
        foreign_master_path = os.path.join(ROOT, "ResuMiner", "release_data", "foreign_master_database_v2.csv")
        if os.path.exists(foreign_master_path):
            try:
                df = pd.read_csv(foreign_master_path)
                f.write("### 外企高优岗数据 (foreign_master_database_v2.csv)\n")
                f.write(f"- **总记录数**: {len(df)}\n")
                if 'jd_visibility' in df.columns:
                    clear = (df['jd_visibility'] == '清晰可见').sum()
                    f.write(f"- **详情页清晰可见数**: {clear} (占比 {clear/len(df)*100:.1f}%)\n")
            except Exception as e:
                f.write(f"读取外企源数据出错: {e}\n\n")

    print(f"\n[+] Health report generated at: {report_path}")
    
    # Check for failures and send alert
    failed_tasks = [r for r in results if r['status'] == 'failed']
    if failed_tasks:
        msg = "以下爬虫任务执行失败：\n"
        for ft in failed_tasks:
            msg += f"- {ft['name']} ({ft['id']}): {ft.get('error', 'Unknown Error')}\n"
        msg += "\n请使用 `python tools/crawler_generator.py <URL>` 修复对应站点的选择器。"
        send_alert(msg)

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Crawler Dispatcher...")
    
    results = []
    
    for task in TASKS:
        if not task.get("enabled", True):
            print(f"[-] Skipping disabled task: {task['name']}")
            continue
            
        print(f"\n[*] Running task: {task['name']} ({task['id']})")
        start_time = time.time()
        
        try:
            # We don't capture output here so user can see progress in terminal
            proc = subprocess.run(
                task["command"], 
                cwd=task["cwd"], 
                timeout=task.get("timeout", 3600),
                check=True
            )
            duration = time.time() - start_time
            print(f"[+] Task {task['id']} completed successfully in {duration:.1f}s")
            results.append({
                "id": task["id"],
                "name": task["name"],
                "status": "success",
                "duration": duration
            })
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"[!] Task {task['id']} TIMEOUT after {duration:.1f}s")
            results.append({
                "id": task["id"],
                "name": task["name"],
                "status": "failed",
                "duration": duration,
                "error": "Timeout"
            })
        except subprocess.CalledProcessError as e:
            duration = time.time() - start_time
            print(f"[!] Task {task['id']} FAILED with exit code {e.returncode}")
            results.append({
                "id": task["id"],
                "name": task["name"],
                "status": "failed",
                "duration": duration,
                "error": f"Exit code {e.returncode}"
            })
        except Exception as e:
            duration = time.time() - start_time
            print(f"[!] Task {task['id']} ERROR: {e}")
            results.append({
                "id": task["id"],
                "name": task["name"],
                "status": "failed",
                "duration": duration,
                "error": str(e)
            })

    print("\n[*] All tasks finished. Generating health report...")
    reports_dir = os.path.join(ROOT, "reports")
    generate_health_report(reports_dir, results)
    
if __name__ == "__main__":
    main()
