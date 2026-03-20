#!/usr/bin/env bash
set -euo pipefail

UNIQUE_ID="${UNIQUE_ID:-yourname123}"
REGION="${AWS_REGION:-us-east-1}"
TARGET_WIDTH="${TARGET_WIDTH:-200}"
WATERMARK_TEXT="${WATERMARK_TEXT:-© MyCompany}"

echo "[bootstrap] Waiting for LocalStack health endpoint..."
until curl -sf "http://localstack:4566/_localstack/health" >/dev/null; do
  sleep 2
done

echo "[bootstrap] Building Lambda packages..."
python -u ./scripts/build_packages.py

echo "[bootstrap] Running Terraform init/apply against LocalStack..."
terraform -chdir=infra init -input=false
terraform -chdir=infra apply -auto-approve -input=false \
  -var "unique_id=${UNIQUE_ID}" \
  -var "region=${REGION}" \
  -var "use_localstack=true" \
  -var "localstack_endpoint=http://localstack:4566" \
  -var "target_width=${TARGET_WIDTH}" \
  -var "watermark_text=${WATERMARK_TEXT}"

echo "[bootstrap] Stack is ready."
