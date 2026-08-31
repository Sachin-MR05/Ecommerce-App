$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Starting Ecommerce app services..." -ForegroundColor Cyan

Start-Process powershell -ArgumentList @(
    '-NoExit',
    '-Command',
    "Set-Location '$root\ecommerce-frontend'; npm run dev"
)

Start-Process powershell -ArgumentList @(
    '-NoExit',
    '-Command',
    "Set-Location '$root\ecommerce-backend'; & '.\mvnw.cmd' spring-boot:run"
)

Start-Process powershell -ArgumentList @(
    '-NoExit',
    '-Command',
    "Set-Location '$root\merchant-agent-core'; python -m uvicorn main:app --port 8001"
)

Write-Host "Frontend, backend, and merchant agent have been launched in separate windows." -ForegroundColor Green
Write-Host "Check the new terminals for logs and startup status." -ForegroundColor Yellow
Write-Host "If one service fails, open the matching folder and run it manually." -ForegroundColor Yellow
