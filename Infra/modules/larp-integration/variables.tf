variable "project_name" {
  type        = string
  description = "Project name prefix for resource naming"
}

variable "environment" {
  type        = string
  description = "Deployment environment (dev, staging, prod)"
}

variable "aws_region" {
  type        = string
  description = "AWS region for resource deployment"
}

variable "web_scenes_table_name" {
  type        = string
  description = "DynamoDB table name for web scenes catalogue"
}

variable "ws_connections_table_name" {
  type        = string
  description = "DynamoDB table name for WebSocket connections"
}

variable "ws_invoke_url" {
  type        = string
  description = "WebSocket API invoke URL (wss://...) — used to derive the management endpoint"
}

variable "build_s3_bucket" {
  type        = string
  description = "S3 bucket containing ScenePlan JSON files (scene-plans/{id}/scene_plan.json)"
}

variable "log_retention_days" {
  type        = number
  default     = 14
  description = "CloudWatch log retention in days"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags to apply to all resources"
}
