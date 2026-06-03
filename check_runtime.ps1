param(
    [string]$BackendUrl = "http://localhost:8000",
    [string]$FrontendUrl = "http://localhost:3000",
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"

Write-Host "Checking Docker Compose services..."
$runningServices = docker compose ps --services --filter "status=running"
if ($LASTEXITCODE -ne 0) { throw "docker compose status check failed" }

$requiredServices = @("postgres", "redis", "qdrant")
foreach ($service in $requiredServices) {
    if ($runningServices -notcontains $service) {
        throw "Docker Compose service '$service' is not running"
    }
}

Write-Host "Checking backend health..."
$health = Invoke-RestMethod -Uri "$BackendUrl/health" -TimeoutSec 5
if ($health.status -ne "ok") {
    throw "backend health check failed"
}

if (-not $SkipFrontend) {
    Write-Host "Checking frontend..."
    $frontend = Invoke-WebRequest -Uri $FrontendUrl -TimeoutSec 10 -UseBasicParsing
    if ($frontend.StatusCode -lt 200 -or $frontend.StatusCode -ge 400) {
        throw "frontend returned HTTP $($frontend.StatusCode)"
    }
}

Write-Host "Runtime smoke check passed."
