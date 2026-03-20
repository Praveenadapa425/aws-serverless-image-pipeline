param(
  [Parameter(Mandatory=$true)]
  [string]$UniqueId,
  [string]$Region = "us-east-1",
  [string]$TargetWidth = "200",
  [string]$WatermarkText = "© MyCompany",
  [string]$AwsProfile = ""
)

$ErrorActionPreference = "Stop"

Write-Host "Building Lambda packages..."
python ./scripts/build_packages.py

Write-Host "Initializing Terraform..."
terraform -chdir=infra init

Write-Host "Applying Terraform stack to AWS..."
terraform -chdir=infra apply -auto-approve `
  -var "unique_id=$UniqueId" `
  -var "region=$Region" `
  -var "use_localstack=false" `
  -var "target_width=$TargetWidth" `
  -var "watermark_text=$WatermarkText" `
  -var "aws_profile=$AwsProfile"

Write-Host "Done."
