# Variables for FlexMatch Module

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
  description = "AWS region for FlexMatch"
  type        = string
  default     = "eu-west-1"
}

variable "fleet_arns" {
  description = "List of GameLift fleet ARNs for game session queue"
  type        = list(string)
}

# Queue configuration
variable "queue_timeout_seconds" {
  description = "Timeout for game session queue placement"
  type        = number
  default     = 600
}

variable "player_latency_policies" {
  description = "Player latency policies for queue"
  type = list(object({
    max_latency_ms    = number
    duration_seconds  = number
  }))
  default = [
    {
      max_latency_ms   = 100
      duration_seconds = 30
    },
    {
      max_latency_ms   = 150
      duration_seconds = 60
    },
    {
      max_latency_ms   = 200
      duration_seconds = 0
    }
  ]
}

# Matchmaking configuration
variable "min_players_per_match" {
  description = "Minimum players required for a match"
  type        = number
  default     = 10
}

variable "max_players_per_match" {
  description = "Maximum players allowed in a match"
  type        = number
  default     = 15
}

variable "matchmaking_timeout_seconds" {
  description = "Maximum time to wait for matchmaking"
  type        = number
  default     = 120
}

variable "acceptance_timeout_seconds" {
  description = "Time players have to accept match"
  type        = number
  default     = 30
}

variable "acceptance_required" {
  description = "Whether players must accept match"
  type        = bool
  default     = true
}

variable "backfill_mode" {
  description = "Backfill mode (AUTOMATIC or MANUAL)"
  type        = string
  default     = "AUTOMATIC"
  validation {
    condition     = contains(["AUTOMATIC", "MANUAL"], var.backfill_mode)
    error_message = "Backfill mode must be AUTOMATIC or MANUAL."
  }
}

variable "additional_player_count" {
  description = "Additional players to search for during backfill"
  type        = number
  default     = 0
}

variable "custom_event_data" {
  description = "Custom event data for matchmaking"
  type        = string
  default     = ""
}

variable "game_session_data" {
  description = "Game session data to pass to server"
  type        = string
  default     = ""
}

# Rule set configuration
variable "skill_distance_threshold" {
  description = "Maximum skill difference between players"
  type        = number
  default     = 5
}

variable "max_latency_ms" {
  description = "Maximum acceptable latency in milliseconds"
  type        = number
  default     = 100
}

# Notifications
variable "enable_notifications" {
  description = "Enable SNS notifications for matchmaking events"
  type        = bool
  default     = false
}

variable "notification_sns_topic_arn" {
  description = "SNS topic ARN for matchmaking notifications"
  type        = string
  default     = ""
}

# Monitoring
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "timeout_alarm_threshold" {
  description = "Threshold for matchmaking timeout alarm"
  type        = number
  default     = 10
}

variable "success_alarm_threshold" {
  description = "Threshold for matchmaking success alarm"
  type        = number
  default     = 5
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
