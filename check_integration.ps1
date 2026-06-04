$ErrorActionPreference = "Stop"

Write-Host "Checking Docker services..."
docker compose up -d
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

Write-Host "Applying database migrations..."
Push-Location "$PSScriptRoot\backend"
try {
    $previousDatabaseUrl = $env:DATABASE_URL
    $previousDirectUrl = $env:DIRECT_URL
    $previousRedisUrl = $env:REDIS_URL
    $previousQdrantUrl = $env:QDRANT_URL
    $previousQdrantApiKey = $env:QDRANT_API_KEY

    $env:DATABASE_URL = "postgresql+asyncpg://sourcecast:sourcecast_dev@localhost:5432/sourcecast"
    $env:DIRECT_URL = $env:DATABASE_URL
    $env:REDIS_URL = "redis://localhost:6379/0"
    $env:QDRANT_URL = "http://localhost:6333"
    $env:QDRANT_API_KEY = ""

    .\.venv\Scripts\python.exe -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "alembic migration failed" }
    .\.venv\Scripts\python.exe -m pytest -m integration -q
    if ($LASTEXITCODE -ne 0) { throw "integration tests failed" }
}
finally {
    $env:DATABASE_URL = $previousDatabaseUrl
    $env:DIRECT_URL = $previousDirectUrl
    $env:REDIS_URL = $previousRedisUrl
    $env:QDRANT_URL = $previousQdrantUrl
    $env:QDRANT_API_KEY = $previousQdrantApiKey
    Pop-Location
}

Write-Host "Infrastructure integration gate passed."
