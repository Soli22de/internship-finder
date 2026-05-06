param(
    [string]$TaskName = "InternshipFinding_Task6_DailyPipeline",
    [string]$StartTime = "09:00"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $Root "run_task6_pipeline.ps1"
$Command = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$Runner`""

schtasks /Create /F /SC DAILY /TN $TaskName /TR $Command /ST $StartTime | Out-Null

Write-Host "[Task6] 已创建/更新计划任务: $TaskName" -ForegroundColor Green
Write-Host "[Task6] 执行时间: 每日 $StartTime" -ForegroundColor Green
Write-Host "[Task6] 执行脚本: $Runner" -ForegroundColor Gray
