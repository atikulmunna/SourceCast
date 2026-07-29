param(
  [string]$Region = "us-east-1",
  [string]$InstanceId = "i-0ce4d03572b49ee4f"
)

$ErrorActionPreference = "Stop"

Write-Host "Stopping SourceCast EC2 instance $InstanceId in $Region..."
& aws ec2 stop-instances --region $Region --instance-ids $InstanceId | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Failed to stop EC2 instance $InstanceId."
}

& aws ec2 wait instance-stopped --region $Region --instance-ids $InstanceId
if ($LASTEXITCODE -ne 0) {
  throw "Timed out waiting for EC2 instance $InstanceId to stop."
}

$state = (& aws ec2 describe-instances `
  --region $Region `
  --instance-ids $InstanceId `
  --query "Reservations[0].Instances[0].State.Name" `
  --output text).Trim()

Write-Host "SourceCast EC2 state: $state"
Write-Host "Compute billing is stopped. The public URL may change next time you start it."
