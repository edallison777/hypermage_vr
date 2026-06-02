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

variable "server_port" {
  type        = number
  description = "UDP/TCP port the Godot dedicated server listens on"
  default     = 7777
}

variable "image_tag" {
  type        = string
  description = "Docker image tag (ECR tag pushed by deploy script)"
  default     = "latest"
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
