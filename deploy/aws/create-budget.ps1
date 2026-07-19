param(
  [string]$Region = "us-east-1",
  [decimal]$LimitUsd = 40,
  [ValidateSet("MONTHLY", "QUARTERLY", "ANNUALLY")]
  [string]$TimeUnit = "ANNUALLY",
  [string]$BudgetName = "SourceCast annual cap",
  [Parameter(Mandatory = $true)]
  [string]$AlertEmail
)

$ErrorActionPreference = "Stop"

$accountId = (& aws sts get-caller-identity `
  --region $Region `
  --query "Account" `
  --output text).Trim()

if (-not $accountId) {
  throw "Could not resolve AWS account ID."
}

$budgetFile = New-TemporaryFile
$notificationsFile = New-TemporaryFile

try {
  @{
    BudgetName = $BudgetName
    BudgetLimit = @{
      Amount = "$LimitUsd"
      Unit = "USD"
    }
    TimeUnit = $TimeUnit
    BudgetType = "COST"
    CostFilters = @{}
  } | ConvertTo-Json -Depth 5 | Set-Content -Path $budgetFile -Encoding UTF8

  @(
    @{
      Notification = @{
        NotificationType = "ACTUAL"
        ComparisonOperator = "GREATER_THAN"
        Threshold = 50
        ThresholdType = "PERCENTAGE"
      }
      Subscribers = @(
        @{
          SubscriptionType = "EMAIL"
          Address = $AlertEmail
        }
      )
    },
    @{
      Notification = @{
        NotificationType = "ACTUAL"
        ComparisonOperator = "GREATER_THAN"
        Threshold = 90
        ThresholdType = "PERCENTAGE"
      }
      Subscribers = @(
        @{
          SubscriptionType = "EMAIL"
          Address = $AlertEmail
        }
      )
    },
    @{
      Notification = @{
        NotificationType = "FORECASTED"
        ComparisonOperator = "GREATER_THAN"
        Threshold = 100
        ThresholdType = "PERCENTAGE"
      }
      Subscribers = @(
        @{
          SubscriptionType = "EMAIL"
          Address = $AlertEmail
        }
      )
    }
  ) | ConvertTo-Json -Depth 6 | Set-Content -Path $notificationsFile -Encoding UTF8

  & aws budgets create-budget `
    --account-id $accountId `
    --budget "file://$budgetFile" `
    --notifications-with-subscribers "file://$notificationsFile"

  if ($LASTEXITCODE -ne 0) {
    Write-Host "Budget may already exist. Updating budget limit and keeping existing notifications."
    & aws budgets update-budget `
      --account-id $accountId `
      --new-budget "file://$budgetFile"

    if ($LASTEXITCODE -ne 0) {
      throw "Failed to create or update AWS budget."
    }
  }

  Write-Host "Configured '$BudgetName' budget for $LimitUsd USD ($TimeUnit)."
  Write-Host "AWS will send confirmation mail to $AlertEmail before alerts activate."
} finally {
  Remove-Item $budgetFile, $notificationsFile -Force -ErrorAction SilentlyContinue
}
