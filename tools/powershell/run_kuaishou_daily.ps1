$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = "logs/run_$Timestamp.log"

if (-not (Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" | Out-Null }

Write-Host "[Daily] 开始执行: $Timestamp" -ForegroundColor Cyan
Write-Host "[Daily] 日志文件: $LogFile" -ForegroundColor Gray

try {
    Write-Host "[1/2] 正在抓取数据..." -ForegroundColor Yellow
    python official_multi_crawler.py 2>&1 | Tee-Object -FilePath $LogFile -Append
    if ($LASTEXITCODE -ne 0) { throw "抓取失败" }

    Write-Host "[2/2] 正在生成看板..." -ForegroundColor Yellow
    python merge_file.py 2>&1 | Tee-Object -FilePath $LogFile -Append
    if ($LASTEXITCODE -ne 0) { throw "合并失败" }

    Write-Host "[3/3] 正在整理产物目录..." -ForegroundColor Yellow
    powershell -ExecutionPolicy Bypass -File ".\organize_workspace.ps1" 2>&1 | Tee-Object -FilePath $LogFile -Append
    if ($LASTEXITCODE -ne 0) { throw "目录整理失败" }

    Write-Host "[Success] 全部完成！请查看 outputs/dashboard/dashboard_all_summary.csv" -ForegroundColor Green
} catch {
    Write-Host "[Error] 执行失败: $_" -ForegroundColor Red
    exit 1
}
