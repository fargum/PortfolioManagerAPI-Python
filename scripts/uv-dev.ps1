param(
    [switch]$NoTests
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv is not installed. Install it first with: python -m pip install uv" -ForegroundColor Red
    exit 1
}

Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "Syncing development dependencies with uv..." -ForegroundColor Cyan
uv sync --extra dev

Write-Host "Running Ruff..." -ForegroundColor Cyan
uv run ruff check src/

Write-Host "Running mypy..." -ForegroundColor Cyan
uv run mypy src/

if (-not $NoTests) {
    Write-Host "Running pytest..." -ForegroundColor Cyan
    uv run pytest
}

Write-Host "Done." -ForegroundColor Green
