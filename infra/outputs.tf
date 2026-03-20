output "input_bucket_name" {
  value = aws_s3_bucket.input_bucket.bucket
}

output "processed_bucket_name" {
  value = aws_s3_bucket.processed_bucket.bucket
}

output "image_processed_queue_url" {
  value = aws_sqs_queue.image_processed_queue.url
}

output "dlq_processor_errors_url" {
  value = aws_sqs_queue.processor_errors_dlq.url
}

output "metadata_table_name" {
  value = aws_dynamodb_table.image_metadata.name
}

output "image_processor_lambda" {
  value = aws_lambda_function.image_processor.function_name
}

output "metadata_updater_lambda" {
  value = aws_lambda_function.metadata_updater.function_name
}
