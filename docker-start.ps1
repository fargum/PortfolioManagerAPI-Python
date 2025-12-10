# Portfolio Manager API - Docker Quick Start

Write-Host "Portfolio Manager Python API - Docker Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (!(Test-Path ".env")) {
    Write-Host "Creating .env file from .env.docker template..." -ForegroundColor Yellow
    Copy-Item ".env.docker" ".env"
    Write-Host "✓ Created .env file" -ForegroundColor Green
    Write-Host ""
    Write-Host "IMPORTANT: Edit .env and add your:" -ForegroundColor Red
    Write-Host "  - AZURE_FOUNDRY_ENDPOINT" -ForegroundColor Red
    Write-Host "  - AZURE_FOUNDRY_API_KEY" -ForegroundColor Red
    Write-Host "  - EOD_API_TOKEN" -ForegroundColor Red
    Write-Host ""
    $continue = Read-Host "Press Enter when ready to continue (or Ctrl+C to exit)"
}

# Check Docker is running
Write-Host "Checking Docker..." -ForegroundColor Yellow
try {
    docker info | Out-Null
    Write-Host "✓ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Building and starting services..." -ForegroundColor Yellow
docker-compose up -d --build

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ Services started successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Waiting for services to be healthy..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    
    Write-Host ""
    Write-Host "API is available at:" -ForegroundColor Cyan
    Write-Host "  - API: http://localhost:8000" -ForegroundColor White
    Write-Host "  - Swagger Docs: http://localhost:8000/docs" -ForegroundColor White
    Write-Host "  - Health Check: http://localhost:8000/health" -ForegroundColor White
    Write-Host ""
    Write-Host "Database:" -ForegroundColor Cyan
    Write-Host "  - Host: localhost:5432" -ForegroundColor White
    Write-Host "  - Database: portfoliomanager" -ForegroundColor White
    Write-Host "  - User: portfoliouser" -ForegroundColor White
    Write-Host ""
    Write-Host "Useful commands:" -ForegroundColor Cyan
    Write-Host "  - View logs: docker-compose logs -f api" -ForegroundColor White
    Write-Host "  - Stop services: docker-compose down" -ForegroundColor White
    Write-Host "  - Restart API: docker-compose restart api" -ForegroundColor White
    Write-Host ""
    
    # Test health endpoint
    Write-Host "Testing API health..." -ForegroundColor Yellow
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
        Write-Host "✓ API is healthy!" -ForegroundColor Green
        Write-Host ($response | ConvertTo-Json -Depth 3)
    } catch {
        Write-Host "⚠ API may still be starting up. Check logs with: docker-compose logs -f api" -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "✗ Failed to start services. Check the output above for errors." -ForegroundColor Red
    exit 1
}
