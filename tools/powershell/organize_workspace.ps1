$ErrorActionPreference = "Stop"

$root = "c:\jz_code\internship_finding"
$reportDir = Join-Path $root "outputs\reports"
$dashboardDir = Join-Path $root "outputs\dashboard"
$healthDir = Join-Path $root "outputs\health"

foreach ($d in @($reportDir, $dashboardDir, $healthDir)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
}

$reportPatterns = @(
    "internship_*.csv",
    "data_quality_report.csv"
)

$dashboardPatterns = @(
    "dashboard_*.csv"
)

$healthPatterns = @(
    "broken_links_report.csv",
    "link_health_latest.csv"
)

foreach ($p in $reportPatterns) {
    Get-ChildItem -Path $root -Filter $p -File -ErrorAction SilentlyContinue | ForEach-Object {
        Move-Item -Path $_.FullName -Destination (Join-Path $reportDir $_.Name) -Force
    }
}

foreach ($p in $dashboardPatterns) {
    Get-ChildItem -Path $root -Filter $p -File -ErrorAction SilentlyContinue | ForEach-Object {
        Move-Item -Path $_.FullName -Destination (Join-Path $dashboardDir $_.Name) -Force
    }
}

foreach ($p in $healthPatterns) {
    Get-ChildItem -Path $root -Filter $p -File -ErrorAction SilentlyContinue | ForEach-Object {
        Move-Item -Path $_.FullName -Destination (Join-Path $healthDir $_.Name) -Force
    }
}

Write-Host "[Organize] Workspace artifacts moved to outputs/" -ForegroundColor Green
