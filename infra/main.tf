terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.91"
    }
  }
}

provider "aws" {
  region  = var.region
  profile = var.aws_profile == "" ? null : var.aws_profile

  access_key = var.use_localstack ? "test" : null
  secret_key = var.use_localstack ? "test" : null

  s3_use_path_style           = var.use_localstack
  skip_credentials_validation = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  skip_requesting_account_id  = var.use_localstack

  endpoints {
    s3       = var.use_localstack ? var.localstack_endpoint : null
    sqs      = var.use_localstack ? var.localstack_endpoint : null
    lambda   = var.use_localstack ? var.localstack_endpoint : null
    dynamodb = var.use_localstack ? var.localstack_endpoint : null
    iam      = var.use_localstack ? var.localstack_endpoint : null
    sts      = var.use_localstack ? var.localstack_endpoint : null
  }
}

locals {
  input_bucket_name     = "input-image-bucket-${var.unique_id}"
  processed_bucket_name = "processed-image-bucket-${var.unique_id}"
  image_zip_path        = "${path.module}/../dist/image_processor.zip"
  metadata_zip_path     = "${path.module}/../dist/metadata_updater.zip"
}

resource "aws_s3_bucket" "input_bucket" {
  bucket = local.input_bucket_name
}

resource "aws_s3_bucket" "processed_bucket" {
  bucket = local.processed_bucket_name
}

resource "aws_sqs_queue" "processed_messages_dlq" {
  name = "DLQProcessedMessages"
}

resource "aws_sqs_queue" "processor_errors_dlq" {
  name = "DLQProcessorErrors"
}

resource "aws_sqs_queue" "image_processed_queue" {
  name = "ImageProcessedQueue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.processed_messages_dlq.arn
    maxReceiveCount     = 5
  })
}

resource "aws_dynamodb_table" "image_metadata" {
  name         = "ImageMetadataTable"
  billing_mode = "PROVISIONED"
  hash_key     = "originalKey"
  read_capacity  = 5
  write_capacity = 5

  attribute {
    name = "originalKey"
    type = "S"
  }
}

resource "aws_iam_role" "image_processor_role" {
  name = "ImageProcessorLambdaRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "image_processor_policy" {
  name = "ImageProcessorPolicy"
  role = aws_iam_role.image_processor_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadInputBucket"
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = ["${aws_s3_bucket.input_bucket.arn}/*"]
      },
      {
        Sid    = "WriteProcessedBucket"
        Effect = "Allow"
        Action = ["s3:PutObject"]
        Resource = ["${aws_s3_bucket.processed_bucket.arn}/*"]
      },
      {
        Sid    = "PublishQueues"
        Effect = "Allow"
        Action = ["sqs:SendMessage"]
        Resource = [
          aws_sqs_queue.image_processed_queue.arn,
          aws_sqs_queue.processor_errors_dlq.arn
        ]
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = ["arn:aws:logs:*:*:*"]
      }
    ]
  })
}

resource "aws_iam_role" "metadata_updater_role" {
  name = "MetadataUpdaterLambdaRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "metadata_updater_policy" {
  name = "MetadataUpdaterPolicy"
  role = aws_iam_role.metadata_updater_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadProcessedQueue"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = [aws_sqs_queue.image_processed_queue.arn]
      },
      {
        Sid    = "WriteDynamoMetadata"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = [aws_dynamodb_table.image_metadata.arn]
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = ["arn:aws:logs:*:*:*"]
      }
    ]
  })
}

resource "aws_lambda_function" "image_processor" {
  function_name = "ImageProcessorLambda"
  role          = aws_iam_role.image_processor_role.arn
  runtime       = "python3.12"
  handler       = "app.handler"
  timeout       = 30
  memory_size   = 512

  filename         = local.image_zip_path
  source_code_hash = filebase64sha256(local.image_zip_path)

  environment {
    variables = {
      TARGET_WIDTH          = var.target_width
      WATERMARK_TEXT        = var.watermark_text
      SQS_QUEUE_URL         = aws_sqs_queue.image_processed_queue.url
      DLQ_QUEUE_URL         = aws_sqs_queue.processor_errors_dlq.url
      PROCESSED_BUCKET_NAME = aws_s3_bucket.processed_bucket.bucket
    }
  }
}

resource "aws_lambda_function" "metadata_updater" {
  function_name = "MetadataUpdaterLambda"
  role          = aws_iam_role.metadata_updater_role.arn
  runtime       = "python3.12"
  handler       = "app.handler"
  timeout       = 30
  memory_size   = 256

  filename         = local.metadata_zip_path
  source_code_hash = filebase64sha256(local.metadata_zip_path)

  environment {
    variables = {
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.image_metadata.name
    }
  }
}

resource "aws_lambda_permission" "allow_s3_trigger" {
  statement_id  = "AllowS3InvokeImageProcessor"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.image_processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.input_bucket.arn
}

resource "aws_s3_bucket_notification" "input_bucket_notification" {
  bucket = aws_s3_bucket.input_bucket.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.image_processor.arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.allow_s3_trigger]
}

resource "aws_lambda_event_source_mapping" "metadata_queue_mapping" {
  event_source_arn = aws_sqs_queue.image_processed_queue.arn
  function_name    = aws_lambda_function.metadata_updater.arn
  batch_size       = 10
  enabled          = true
}
