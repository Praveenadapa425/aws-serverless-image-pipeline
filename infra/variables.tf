variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "unique_id" {
  description = "Unique suffix for globally unique S3 bucket names"
  type        = string
}

variable "target_width" {
  description = "Target width for resized images"
  type        = string
  default     = "200"
}

variable "watermark_text" {
  description = "Watermark text applied to resized image"
  type        = string
  default     = "© MyCompany"
}

variable "use_localstack" {
  description = "Use LocalStack endpoints when true"
  type        = bool
  default     = true
}

variable "localstack_endpoint" {
  description = "LocalStack gateway endpoint"
  type        = string
  default     = "http://localhost:4566"
}

variable "aws_profile" {
  description = "Optional AWS profile name for real AWS deployment"
  type        = string
  default     = ""
}
