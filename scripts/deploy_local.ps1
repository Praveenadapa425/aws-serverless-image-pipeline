param(
  [string]$UniqueId = "yourname123",
  [string]$Region = "us-east-1",
  [string]$TargetWidth = "200",
  [string]$WatermarkText = "© MyCompany"
)

$ErrorActionPreference = "Stop"

Write-Host "Building Lambda packages..."
python ./scripts/build_packages.py

Write-Host "Initializing Terraform..."
terraform -chdir=infra init

Write-Host "Applying Terraform stack to LocalStack..."
terraform -chdir=infra apply -auto-approve `
  -var "unique_id=$UniqueId" `
  -var "region=$Region" `
  -var "use_localstack=true" `
  -var "target_width=$TargetWidth" `
  -var "watermark_text=$WatermarkText"

Write-Host "Done."
