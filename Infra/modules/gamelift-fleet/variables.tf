# Variables for GameLift Fleet Module

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
  description = "AWS region for GameLift fleet"
  type        = string
  default     = "eu-west-1"
}

variable "build_s3_bucket_name" {
  description = "S3 bucket name containing server build"
  type        = string
}

variable "build_s3_bucket_arn" {
  description = "S3 bucket ARN containing server build"
  type        = string
}

variable "server_build_s3_key" {
  description = "S3 key for server build artifact"
  type        = string
  default     = "builds/latest/HyperMageVRServer.zip"
}

variable "fleet_type" {
  description = "Fleet type (ON_DEMAND or SPOT)"
  type        = string
  default     = "SPOT"
  validation {
    condition     = contains(["ON_DEMAND", "SPOT"], var.fleet_type)
    error_message = "Fleet type must be ON_DEMAND or SPOT."
  }
}

variable "ec2_instance_type" {
  description = "EC2 instance type for fleet (c5.large recommended for VR)"
  type        = string
  default     = "c5.large"
}

variable "concurrent_executions" {
  description = "Number of concurrent server processes per instance"
  type        = number
  default     = 1
}

variable "server_launch_path" {
  description = "Path to server executable"
  type        = string
  default     = "/local/game/HyperMageVRServer.sh"
}

variable "server_parameters" {
  description = "Command-line parameters for server"
  type        = string
  default     = "-log"
}

variable "max_sessions_per_creator" {
  description = "Maximum game sessions per creator in 15 minutes"
  type        = number
  default     = 10
}

variable "inbound_permissions" {
  description = "Inbound connection permissions for clients"
  type = list(object({
    from_port = number
    to_port   = number
    ip_range  = string
    protocol  = string
  }))
  default = [
    {
      from_port = 7777
      to_port   = 7777
      ip_range  = "0.0.0.0/0"
      protocol  = "UDP"
    },
    {
      from_port = 7778
      to_port   = 7778
      ip_range  = "0.0.0.0/0"
      protocol  = "TCP"
    }
  ]
}

variable "fleet_locations" {
  description = "Additional AWS regions for fleet locations"
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "min_capacity_alarm_threshold" {
  description = "Minimum active instances before alarm"
  type        = number
  default     = 1
}

variable "high_utilization_threshold" {
  description = "Utilization percentage threshold for alarm"
  type        = number
  default     = 80
}

variable "alarm_sns_topic_arns" {
  description = "SNS topic ARNs for alarm notifications"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}

# Auto-scaling variables
variable "enable_auto_scaling" {
  description = "Enable auto-scaling for the fleet"
  type        = bool
  default     = true
}

variable "min_fleet_capacity" {
  description = "Minimum number of instances in fleet"
  type        = number
  default     = 1
}

variable "max_fleet_capacity" {
  description = "Maximum number of instances in fleet (3 for initial deployment)"
  type        = number
  default     = 3
}

variable "desired_capacity" {
  description = "Desired number of instances (used when auto-scaling is disabled)"
  type        = number
  default     = 1
}

variable "target_utilization_percentage" {
  description = "Target utilization percentage for auto-scaling"
  type        = number
  default     = 70
}

variable "scale_in_cooldown_seconds" {
  description = "Cooldown period after scale-in activity"
  type        = number
  default     = 300
}

variable "scale_out_cooldown_seconds" {
  description = "Cooldown period after scale-out activity"
  type        = number
  default     = 60
}
