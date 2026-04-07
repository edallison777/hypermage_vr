variable "project_name" {
  type        = string
  description = "Project name prefix for all resources"
}

variable "environment" {
  type        = string
  description = "Deployment environment (dev, staging, prod)"
}

variable "aws_region" {
  type        = string
  description = "AWS region"
}

variable "build_s3_bucket_name" {
  type        = string
  description = "Name of the S3 bucket for build artifacts and assets"
}

variable "build_s3_bucket_arn" {
  type        = string
  description = "ARN of the S3 bucket for build artifacts and assets"
}

variable "blender_image_uri" {
  type        = string
  description = "ECR or Docker Hub URI for the Blender converter container"
  default     = "linuxserver/blender:latest"
}

variable "meshy_api_key_ssm_path" {
  type        = string
  description = "SSM Parameter Store path for Meshy.ai API key"
  default     = "/hypermage/meshy-api-key"
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention in days"
  default     = 14
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Additional tags to apply to resources"
}
