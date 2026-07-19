param(
  [string]$Region = "us-east-1",
  [string]$InstanceType = "t4g.small",
  [string]$KeyName = "sourcecast-ec2",
  [string]$SecurityGroupName = "sourcecast-ec2-sg",
  [string]$AllowedSshCidr = "",
  [int]$VolumeSizeGb = 20
)

$ErrorActionPreference = "Stop"

function Invoke-AwsJson {
  param([string[]]$Arguments)
  $output = & aws @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "aws $($Arguments -join ' ') failed"
  }
  if ($output) {
    return $output | ConvertFrom-Json
  }
  return $null
}

if (-not $AllowedSshCidr) {
  $publicIp = (Invoke-RestMethod -Uri "https://checkip.amazonaws.com").Trim()
  $AllowedSshCidr = "$publicIp/32"
}

Write-Host "Using region: $Region"
Write-Host "Using SSH CIDR: $AllowedSshCidr"

Invoke-AwsJson -Arguments @("sts", "get-caller-identity", "--region", $Region) | Out-Null

$vpcId = (& aws ec2 describe-vpcs `
  --region $Region `
  --filters "Name=isDefault,Values=true" `
  --query "Vpcs[0].VpcId" `
  --output text).Trim()

if (-not $vpcId -or $vpcId -eq "None") {
  throw "No default VPC found in $Region. Create/select a VPC manually or choose another region."
}

$amiId = (& aws ssm get-parameter `
  --region $Region `
  --name "/aws/service/canonical/ubuntu/server/24.04/stable/current/arm64/hvm/ebs-gp3/ami-id" `
  --query "Parameter.Value" `
  --output text).Trim()

if (-not $amiId) {
  throw "Could not resolve Ubuntu 24.04 ARM64 AMI in $Region."
}

$keyPath = Join-Path $PSScriptRoot "$KeyName.pem"
$existingKeyOutput = & aws ec2 describe-key-pairs `
  --region $Region `
  --key-names $KeyName `
  --query "KeyPairs[0].KeyName" `
  --output text 2>$null
$existingKey = if ($existingKeyOutput) { $existingKeyOutput.Trim() } else { "" }

if ($LASTEXITCODE -ne 0 -or $existingKey -eq "None" -or -not $existingKey) {
  Write-Host "Creating key pair: $KeyName"
  & aws ec2 create-key-pair `
    --region $Region `
    --key-name $KeyName `
    --query "KeyMaterial" `
    --output text | Set-Content -NoNewline -Path $keyPath
  Write-Host "Saved private key to $keyPath"
} else {
  Write-Host "Using existing key pair: $KeyName"
  if (-not (Test-Path $keyPath)) {
    Write-Warning "AWS key pair exists, but $keyPath is not present locally. You need the matching private key to SSH."
  }
}

$sgIdOutput = & aws ec2 describe-security-groups `
  --region $Region `
  --filters "Name=group-name,Values=$SecurityGroupName" "Name=vpc-id,Values=$vpcId" `
  --query "SecurityGroups[0].GroupId" `
  --output text
$sgId = if ($sgIdOutput) { $sgIdOutput.Trim() } else { "" }

if (-not $sgId -or $sgId -eq "None") {
  Write-Host "Creating security group: $SecurityGroupName"
  $sgId = (& aws ec2 create-security-group `
    --region $Region `
    --group-name $SecurityGroupName `
    --description "SourceCast web instance" `
    --vpc-id $vpcId `
    --query "GroupId" `
    --output text).Trim()
}

foreach ($rule in @(
  @{ Port = 22; Cidr = $AllowedSshCidr },
  @{ Port = 80; Cidr = "0.0.0.0/0" },
  @{ Port = 443; Cidr = "0.0.0.0/0" }
)) {
  & aws ec2 authorize-security-group-ingress `
    --region $Region `
    --group-id $sgId `
    --protocol tcp `
    --port $rule.Port `
    --cidr $rule.Cidr 2>$null | Out-Null
}

$userDataPath = Join-Path $PSScriptRoot "bootstrap-ec2.sh"
$instanceId = (& aws ec2 run-instances `
  --region $Region `
  --image-id $amiId `
  --instance-type $InstanceType `
  --key-name $KeyName `
  --security-group-ids $sgId `
  --user-data "file://$userDataPath" `
  --block-device-mappings "[{`"DeviceName`":`"/dev/sda1`",`"Ebs`":{`"VolumeSize`":$VolumeSizeGb,`"VolumeType`":`"gp3`",`"DeleteOnTermination`":true}}]" `
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=sourcecast-app}]" `
  --query "Instances[0].InstanceId" `
  --output text).Trim()

Write-Host "Launched instance: $instanceId"
& aws ec2 wait instance-running --region $Region --instance-ids $instanceId

$publicIp = (& aws ec2 describe-instances `
  --region $Region `
  --instance-ids $instanceId `
  --query "Reservations[0].Instances[0].PublicIpAddress" `
  --output text).Trim()

Write-Host ""
Write-Host "SourceCast EC2 instance is running."
Write-Host "Instance ID: $instanceId"
Write-Host "Public IP:   $publicIp"
Write-Host ""
Write-Host "SSH:"
Write-Host "ssh -i `"$keyPath`" ubuntu@$publicIp"
Write-Host ""
Write-Host "Then configure /opt/sourcecast/deploy/aws/.env and run docker compose up -d --build."
