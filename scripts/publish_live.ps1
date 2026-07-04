#!/usr/bin/env pwsh
# Publish Global Education and Development Dashboard to GitHub + Streamlit Cloud
$ErrorActionPreference = "Stop"
$repoName = "global-education-dashboard"
$owner = "sumitbharaj2462-hub"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

Write-Host "=== Global Education and Development Dashboard ===" -ForegroundColor Cyan

$gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $gh) {
    Write-Host "Install GitHub CLI: winget install GitHub.cli" -ForegroundColor Yellow
    exit 1
}

$auth = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Log in to GitHub (browser will open)..." -ForegroundColor Yellow
    gh auth login --hostname github.com --git-protocol https --web --scopes repo
}

$exists = gh repo view "$owner/$repoName" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating repository $owner/$repoName ..." -ForegroundColor Green
    gh repo create "$owner/$repoName" `
        --public `
        --description "Global Education and Development Dashboard — interactive Streamlit app" `
        --source . `
        --remote origin `
        --push
} else {
    Write-Host "Repository exists. Pushing latest main..." -ForegroundColor Green
    git remote set-url origin "https://github.com/$owner/$repoName.git"
    git push -u origin main
}

$deployUrl = "https://share.streamlit.io/deploy?repository=$owner/$repoName&branch=main&mainModule=streamlit_dashboard/app.py&subdomain=global-education-dashboard"
Write-Host ""
Write-Host "GitHub: https://github.com/$owner/$repoName" -ForegroundColor Cyan
Write-Host "Deploy (one click): $deployUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "Open the deploy link, sign in with GitHub, click Deploy." -ForegroundColor Yellow
Write-Host "Live URL will be: https://global-education-dashboard.streamlit.app" -ForegroundColor Green
Start-Process $deployUrl
