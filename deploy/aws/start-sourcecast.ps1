param(
  [string]$Region = "us-east-1",
  [string]$InstanceId = "i-02cb5c76364e04e86",
  [string]$KeyPath = "",
  [string]$RemoteComposeDir = "/opt/sourcecast/deploy/aws",
  [switch]$SkipRemoteUpdate
)

$ErrorActionPreference = "Stop"

function Invoke-AwsText {
  param([string[]]$Arguments)

  $output = & aws @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "aws $($Arguments -join ' ') failed"
  }

  return ($output | Out-String).Trim()
}

function Wait-ForSsh {
  param(
    [string]$PublicIp,
    [string]$ResolvedKeyPath
  )

  for ($attempt = 1; $attempt -le 18; $attempt++) {
    & ssh `
      -i $ResolvedKeyPath `
      -o StrictHostKeyChecking=no `
      -o ConnectTimeout=8 `
      "ubuntu@$PublicIp" `
      "true" 2>$null

    if ($LASTEXITCODE -eq 0) {
      return
    }

    Start-Sleep -Seconds 10
  }

  throw "SSH did not become ready for $PublicIp."
}

function Wait-ForHealth {
  param([string]$Url)

  $healthUrl = "$Url/health"
  for ($attempt = 1; $attempt -le 18; $attempt++) {
    try {
      Invoke-RestMethod -Uri $healthUrl -TimeoutSec 10 | Out-Null
      return
    } catch {
      Start-Sleep -Seconds 10
    }
  }

  throw "Health check did not pass at $healthUrl."
}

if (-not $KeyPath) {
  $KeyPath = Join-Path $PSScriptRoot "sourcecast-ec2.pem"
}

$KeyPath = (Resolve-Path $KeyPath).Path
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Write-Host "Starting SourceCast EC2 instance $InstanceId in $Region..."
& aws ec2 start-instances --region $Region --instance-ids $InstanceId | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Failed to start EC2 instance $InstanceId."
}

& aws ec2 wait instance-running --region $Region --instance-ids $InstanceId
if ($LASTEXITCODE -ne 0) {
  throw "Timed out waiting for EC2 instance $InstanceId to run."
}

$publicIp = Invoke-AwsText -Arguments @(
  "ec2",
  "describe-instances",
  "--region",
  $Region,
  "--instance-ids",
  $InstanceId,
  "--query",
  "Reservations[0].Instances[0].PublicIpAddress",
  "--output",
  "text"
)

if (-not $publicIp -or $publicIp -eq "None") {
  throw "AWS did not return a public IP for $InstanceId."
}

$hostName = "$($publicIp -replace '\.', '-').sslip.io"
$url = "https://$hostName"

Write-Host "Public IP: $publicIp"
Write-Host "Live URL:  $url"

if (-not $SkipRemoteUpdate) {
  Write-Host "Waiting for SSH..."
  Wait-ForSsh -PublicIp $publicIp -ResolvedKeyPath $KeyPath

  $remoteCommand = @"
set -e
cd "$RemoteComposeDir"
if grep -q '^SOURCECAST_SITE_ADDRESS=' .env; then
  sed -i 's#^SOURCECAST_SITE_ADDRESS=.*#SOURCECAST_SITE_ADDRESS=$hostName#' .env
else
  printf '\nSOURCECAST_SITE_ADDRESS=$hostName\n' >> .env
fi
if grep -q '^FRONTEND_URL=' .env; then
  sed -i 's#^FRONTEND_URL=.*#FRONTEND_URL=$url#' .env
else
  printf '\nFRONTEND_URL=$url\n' >> .env
fi
sudo docker compose up -d --force-recreate backend caddy
"@

  Write-Host "Updating remote app origin and restarting backend/Caddy..."
  & ssh `
    -i $KeyPath `
    -o StrictHostKeyChecking=no `
    "ubuntu@$publicIp" `
    $remoteCommand

  if ($LASTEXITCODE -ne 0) {
    throw "Remote app update failed. Check SSH access and container logs."
  }

  Write-Host "Waiting for HTTPS health..."
  Wait-ForHealth -Url $url
}

$demoAccessPath = Join-Path $repoRoot "DEMO_ACCESS.md"
if (Test-Path $demoAccessPath) {
  $content = Get-Content -Path $demoAccessPath -Raw
  $replacement = "- Current live URL: ``$url``"
  $content = $content -replace '- Current live URL: `[^`]+`', $replacement
  Set-Content -Path $demoAccessPath -Value $content -Encoding UTF8
}

Write-Host ""
Write-Host "SourceCast is ready:"
Write-Host $url
Write-Host ""
Write-Host "Demo login:"
Write-Host "demo1@sourcecast.app / SourceCastDemo2026!A"
