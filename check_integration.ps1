$ErrorActionPreference = "Stop"

Write-Host "Checking Docker services..."
docker compose up -d
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

Write-Host "Applying database migrations..."
Push-Location "$PSScriptRoot\backend"
try {
    .\.venv\Scripts\python.exe -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "alembic migration failed" }
    .\.venv\Scripts\python.exe -m pytest -m integration -q
    if ($LASTEXITCODE -ne 0) { throw "integration tests failed" }
}
finally {
    Pop-Location
}

Write-Host "Infrastructure integration gate passed."
