# Start IoT Docker stack and print next steps
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Starting IoT infrastructure..." -ForegroundColor Cyan
docker compose -f docker-compose.iot.yml up -d

Write-Host ""
Write-Host "Stack started. Run these in separate terminals:" -ForegroundColor Green
Write-Host "  python -m iot.simulators.run_all"
Write-Host "  python -m iot.services.telemetry_ingestion.main"
Write-Host "  python -m iot.services.telemetry_consumer.main --api"
Write-Host ""
Write-Host "API: http://localhost:8080/docs" -ForegroundColor Yellow
Write-Host "EMQX: http://localhost:18083" -ForegroundColor Yellow
