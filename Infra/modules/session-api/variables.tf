# Session API Module Variables

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "eu-west-1"
}

variable "cognito_user_pool_arn" {
  description = "ARN of the Cognito User Pool for API authorization"
  type        = string
}

variable "matchmaking_configuration_name" {
  description = "Name of the FlexMatch matchmaking configuration"
  type        = string
}

variable "dynamodb_table_arns" {
  description = "List of DynamoDB table ARNs for Lambda access"
  type        = list(string)
  default     = []
}

variable "player_sessions_table_name" {
  description = "Name of the PlayerSessions DynamoDB table"
  type        = string
  default     = ""
}

variable "player_rewards_table_name" {
  description = "Name of the PlayerRewards DynamoDB table"
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "lambda_log_level" {
  description = "Log level for Lambda functions (DEBUG, INFO, WARN, ERROR)"
  type        = string
  default     = "INFO"
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}

# ── G5: ECS Godot server matchmaking ─────────────────────────────────────────

variable "ecs_cluster_arn" {
  description = "ARN of the ECS cluster that runs Godot dedicated server tasks"
  type        = string
  default     = ""
}

variable "ecs_task_def_arn" {
  description = "ARN of the Godot server ECS task definition"
  type        = string
  default     = ""
}

variable "ecs_task_role_arn" {
  description = "ARN of the ECS task role (for iam:PassRole)"
  type        = string
  default     = ""
}

variable "ecs_task_exec_role_arn" {
  description = "ARN of the ECS task execution role (for iam:PassRole)"
  type        = string
  default     = ""
}

variable "ecs_security_group_ids" {
  description = "Comma-separated security group IDs for ECS Fargate tasks"
  type        = string
  default     = ""
}

variable "ecs_subnet_ids" {
  description = "List of subnet IDs for ECS Fargate tasks"
  type        = list(string)
  default     = []
}

variable "matchmaking_tickets_table_name" {
  description = "DynamoDB table name for matchmaking tickets (ticketId → taskArn)"
  type        = string
  default     = ""
}

variable "matchmaking_tickets_table_arn" {
  description = "DynamoDB table ARN for matchmaking tickets"
  type        = string
  default     = ""
}
