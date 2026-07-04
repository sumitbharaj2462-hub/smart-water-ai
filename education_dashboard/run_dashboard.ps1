$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path "education_dashboard\data\dashboard_data.json")) {
    python scripts\build_education_dashboard_data.py
}

Write-Host ""
Write-Host "Dashboard running at http://127.0.0.1:8765"
Write-Host "Keep this window open while using the dashboard."
Write-Host ""

python -m http.server 8765 --bind 127.0.0.1 --directory education_dashboard
