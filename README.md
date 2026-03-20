# Build a Serverless Event-Driven Image Processing Pipeline with AWS Lambda and SQS

This project implements a resilient event-driven image processing pipeline using:
- S3 for uploads and processed output
- Lambda for stateless compute
- SQS for asynchronous processing events
- DynamoDB for metadata persistence
- Terraform for IaC
- LocalStack + Docker Compose for local simulation

## Architecture

Flow:
1. Upload image to `input-image-bucket-<unique_id>`.
2. S3 event triggers `ImageProcessorLambda`.
3. Lambda validates file type, resizes image to `TARGET_WIDTH`, applies watermark, uploads to `processed-image-bucket-<unique_id>`.
4. Lambda sends success message to `ImageProcessedQueue`.
5. `MetadataUpdaterLambda` consumes SQS messages and stores metadata in `ImageMetadataTable`.
6. Errors from processor are pushed to `DLQProcessorErrors`.
7. Failed queue message retries end in `DLQProcessedMessages`.

## Project Structure

```text
.
├── infra/
│   ├── main.tf
│   ├── outputs.tf
│   ├── variables.tf
│   └── terraform.tfvars.example
├── src/
│   ├── image_processor/
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── tests/
│   │       └── test_processor.py
│   └── metadata_updater/
│       ├── app.py
│       ├── requirements.txt
│       └── tests/
│           └── test_updater.py
├── tests/
│   └── e2e_test.py
├── scripts/
│   ├── build_packages.py
│   ├── deploy_local.ps1
│   ├── destroy_local.ps1
│   └── deploy_aws.ps1
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements-dev.txt
└── README.md
```

## Stage-Based Implementation Plan

### Stage 1: Foundation and Local Tooling
- Set up Python environment.
- Start LocalStack with Docker Compose.
- Prepare Terraform and Lambda packaging tools.

### Stage 2: Infrastructure as Code
- Provision all core resources via Terraform:
	- `input-image-bucket-<unique_id>`
	- `processed-image-bucket-<unique_id>`
	- `ImageProcessedQueue`
	- `DLQProcessorErrors`
	- `DLQProcessedMessages`
	- `ImageMetadataTable`
	- `ImageProcessorLambda`
	- `MetadataUpdaterLambda`
	- IAM roles/policies with least privilege
	- S3 notification and SQS event source mapping

### Stage 3: Image Processor Lambda
- Validate extension (`jpg`, `jpeg`, `png`).
- Download object from input bucket.
- Resize while maintaining aspect ratio.
- Apply text watermark.
- Upload as `resized_<original_key>` to processed bucket.
- Publish success payload to `ImageProcessedQueue`.
- Publish structured error payload to `DLQProcessorErrors`.

### Stage 4: Metadata Updater Lambda
- Consume messages from `ImageProcessedQueue`.
- Parse and validate payload.
- Persist `originalKey`, `processedKey`, `timestamp`, `status`, and `processingDetails` to `ImageMetadataTable`.
- Use conditional write for idempotency.

### Stage 5: Tests and Validation
- Unit tests for image processing and message validation.
- End-to-end script that uploads image, validates processed image creation, and verifies DynamoDB record.

### Stage 6: Deployment and Submission Hardening
- Local deployment (`LocalStack`) and optional real AWS deployment.
- Add commands, assumptions, trade-offs, and future improvements to documentation.

## Prerequisites

- Docker Desktop
- Python 3.12+
- Terraform 1.6+
- PowerShell (Windows)

Optional for real AWS deploy:
- AWS CLI configured with credentials/profile

## Setup

1. Copy environment file:
```powershell
Copy-Item .env.example .env
```

Set a unique value in `.env` for `UNIQUE_ID` before first run to avoid bucket-name conflicts.

2. Create virtual environment and install dependencies:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

## Local Development with a Single Command

Run this from project root:
```powershell
docker compose up --build
```

If you changed Dockerfile/compose recently, force recreation:
```powershell
docker compose down
docker compose up --build --force-recreate
```

What this does automatically:
1. Starts LocalStack.
2. Waits for LocalStack health check.
3. Builds both Lambda zip packages.
4. Runs Terraform init + apply against LocalStack.

When bootstrap completes, your stack is ready.

Optional detached mode:
```powershell
docker compose up --build -d
```

To inspect bootstrap logs:
```powershell
docker compose logs -f bootstrap
```

Note: first run can take several minutes while Python packages download for Lambda zip creation.

## Upload and Trigger Pipeline (LocalStack)

Use AWS CLI with endpoint override:
```powershell
aws --endpoint-url=http://localhost:4566 s3 cp .\sample.png s3://input-image-bucket-yourname123/sample.png
```

Check processed image:
```powershell
aws --endpoint-url=http://localhost:4566 s3 ls s3://processed-image-bucket-yourname123/
```

Check DynamoDB:
```powershell
aws --endpoint-url=http://localhost:4566 dynamodb get-item --table-name ImageMetadataTable --key '{"originalKey":{"S":"sample.png"}}'
```

Check DLQ messages (if failures occur):
```powershell
aws --endpoint-url=http://localhost:4566 sqs receive-message --queue-url http://localhost:4566/000000000000/DLQProcessorErrors
```

## Testing

### Unit tests
Run from repo root:
```powershell
$env:PYTHONPATH = "."
pytest -q
```

### End-to-end integration test
```powershell
$env:AWS_ENDPOINT_URL="http://localhost:4566"
$env:AWS_REGION="us-east-1"
$env:AWS_ACCESS_KEY_ID="test"
$env:AWS_SECRET_ACCESS_KEY="test"
$env:INPUT_BUCKET="input-image-bucket-yourname123"
$env:PROCESSED_BUCKET="processed-image-bucket-yourname123"
$env:DDB_TABLE="ImageMetadataTable"
python .\tests\e2e_test.py
```

## Deploy to Real AWS

Use the AWS deployment script:
```powershell
.\scripts\deploy_aws.ps1 -UniqueId yourname123 -Region us-east-1 -TargetWidth 200 -WatermarkText "© MyCompany" -AwsProfile default
```

Notes:
- `unique_id` must be globally unique for S3 bucket names.
- For production, use stronger IAM controls and encrypted buckets (SSE-KMS), alarms, and X-Ray tracing.

## Core Requirement Mapping

- Two S3 buckets with required naming pattern: implemented.
- `ImageProcessorLambda` triggered by `s3:ObjectCreated:*`: implemented.
- File type validation (`jpg/jpeg/png`): implemented.
- Resize + watermark: implemented.
- Upload `resized_<original_key>`: implemented.
- `ImageProcessedQueue`, `DLQProcessorErrors`, `DLQProcessedMessages`: implemented.
- Queue DLQ redrive (`maxReceiveCount=5`): implemented.
- `MetadataUpdaterLambda` SQS consumer: implemented.
- `ImageMetadataTable` with `originalKey` partition key: implemented.
- IAM least privilege: implemented in Terraform policies.
- Full IaC in Terraform: implemented.
- `docker-compose.yml` with LocalStack: implemented.
- Unit tests and E2E script: implemented.

## Assumptions and Trade-offs

- Used Pillow for processing. This keeps implementation clear and testable.
- DynamoDB write uses conditional insert for idempotency; duplicate messages are ignored.
- S3 notification directly invokes processor Lambda.
- LocalStack behavior may vary slightly from AWS, but architecture and IaC are production-aligned.

## Future Improvements

1. Add structured JSON logging with correlation IDs.
2. Add CloudWatch alarms and failure metrics dashboards.
3. Add image metadata enrichment (EXIF extraction).
4. Add lifecycle policies on buckets and DLQ replay tooling.
5. Add CI pipeline for lint/test/terraform validation.

## Cleanup (Local)

```powershell
.\scripts\destroy_local.ps1 -UniqueId yourname123
docker compose down
```
