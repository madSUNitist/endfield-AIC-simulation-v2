$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot

Write-Host "[1/2] Compiling TypeScript..." -ForegroundColor Cyan
Push-Location frontend
npm run build
Pop-Location

Write-Host "[2/2] Starting server..." -ForegroundColor Cyan
uv run python frontend/server.py
