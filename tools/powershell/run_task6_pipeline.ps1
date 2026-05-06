param(
    [switch]$SkipCrawl
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogDir = "logs"
$LogFile = Join-Path $LogDir "task6_pipeline_$Timestamp.log"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

function Invoke-Step {
    param(
        [string]$Name,
        [string]$Command
    )
    Write-Host "[Task6] $Name" -ForegroundColor Yellow
    powershell -NoProfile -ExecutionPolicy Bypass -Command $Command 2>&1 | Tee-Object -FilePath $LogFile -Append
    if ($LASTEXITCODE -ne 0) { throw "$Name 失败" }
}

Write-Host "[Task6] 开始执行: $Timestamp" -ForegroundColor Cyan
Write-Host "[Task6] 日志文件: $LogFile" -ForegroundColor Gray

if (-not $SkipCrawl) {
    Invoke-Step -Name "抓取汇总 run_all_official" -Command "python crawlers/run_all_official.py"
}
Invoke-Step -Name "清洗与看板 merge_file" -Command "python merge_file.py"
Invoke-Step -Name "匹配分析 resume_job_match_pipeline" -Command "python scripts/resume_job_match_pipeline.py"
Invoke-Step -Name "角色化报告 generate_resume_insights_report" -Command "python scripts/generate_resume_insights_report.py --role all"
Invoke-Step -Name "轻量看板 build_light_role_dashboard" -Command "python scripts/build_light_role_dashboard.py"
Invoke-Step -Name "监控指标 task6_monitoring_metrics" -Command "python scripts/task6_monitoring_metrics.py"
Invoke-Step -Name "双周回归记录 task6_biweekly_regression" -Command "python scripts/task6_biweekly_regression.py"
Invoke-Step -Name "整理产物目录 organize_workspace" -Command "powershell -ExecutionPolicy Bypass -File .\organize_workspace.ps1"
Write-Host "[Task6] 全流程完成，可验证文件已更新到 outputs/reports 与 logs" -ForegroundColor Green
