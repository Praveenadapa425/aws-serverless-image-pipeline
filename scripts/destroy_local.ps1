param(
  [string]$UniqueId = "yourname123",
  [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"

terraform -chdir=infra destroy -auto-approve `
  -var "unique_id=$UniqueId" `
  -var "region=$Region" `
  -var "use_localstack=true"
