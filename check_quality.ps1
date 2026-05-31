$ErrorActionPreference = "Stop"

Write-Host "Running backend tests with coverage..."
Push-Location "$PSScriptRoot\backend"
try {
    .\.venv\Scripts\python.exe -m pytest -m "not integration" --cov=app --cov-report=term-missing -q
    if ($LASTEXITCODE -ne 0) { throw "backend tests failed" }
    .\.venv\Scripts\python.exe -m compileall app tests
    if ($LASTEXITCODE -ne 0) { throw "python compilation failed" }
}
finally {
    Pop-Location
}

Write-Host "Running frontend lint and production build..."
Push-Location "$PSScriptRoot\frontend"
try {
    npm run test
    if ($LASTEXITCODE -ne 0) { throw "frontend tests failed" }
    npm run lint
    if ($LASTEXITCODE -ne 0) { throw "frontend lint failed" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }
}
finally {
    Pop-Location
}

Write-Host "Quality gate passed."
