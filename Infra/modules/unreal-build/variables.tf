# Variables for Unreal Build EC2 Infrastructure Module

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "hypermage-vr"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "eu-west-1"
}

variable "vpc_id" {
  description = "VPC ID for build instances"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for builds (g4dn.xlarge recommended)"
  type        = string
  default     = "g4dn.xlarge"
}

variable "ami_id" {
  description = "Custom AMI ID with UE5.3, Android SDK, GameLift SDK (leave empty to use latest)"
  type        = string
  default     = ""
}

variable "root_volume_size" {
  description = "Root volume size in GB (UE5.3 requires significant space)"
  type        = number
  default     = 150
}

variable "enable_spot_instances" {
  description = "Enable spot instances for cost optimization"
  type        = bool
  default     = true
}

variable "spot_max_price" {
  description = "Maximum spot price per hour (empty for on-demand price)"
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}
