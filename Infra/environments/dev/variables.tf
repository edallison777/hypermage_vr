# Variables for Development Environment

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "hypermage-vr"
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "eu-west-1"
}
