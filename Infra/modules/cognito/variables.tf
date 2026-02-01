# Variables for Cognito Module

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
  description = "AWS region for Cognito"
  type        = string
  default     = "eu-west-1"
}

# User Pool Configuration
variable "username_attributes" {
  description = "Attributes to use as username (email or phone_number)"
  type        = list(string)
  default     = ["email"]
}

variable "auto_verified_attributes" {
  description = "Attributes to auto-verify"
  type        = list(string)
  default     = ["email"]
}

# Password Policy
variable "password_minimum_length" {
  description = "Minimum password length"
  type        = number
  default     = 8
}

variable "password_require_lowercase" {
  description = "Require lowercase characters"
  type        = bool
  default     = true
}

variable "password_require_uppercase" {
  description = "Require uppercase characters"
  type        = bool
  default     = true
}

variable "password_require_numbers" {
  description = "Require numbers"
  type        = bool
  default     = true
}

variable "password_require_symbols" {
  description = "Require symbols"
  type        = bool
  default     = false
}

variable "temporary_password_validity_days" {
  description = "Temporary password validity in days"
  type        = number
  default     = 7
}

# MFA Configuration
variable "mfa_configuration" {
  description = "MFA configuration (OFF, OPTIONAL, ON)"
  type        = string
  default     = "OPTIONAL"
  validation {
    condition     = contains(["OFF", "OPTIONAL", "ON"], var.mfa_configuration)
    error_message = "MFA configuration must be OFF, OPTIONAL, or ON."
  }
}

# Security
variable "advanced_security_mode" {
  description = "Advanced security mode (OFF, AUDIT, ENFORCED)"
  type        = string
  default     = "AUDIT"
  validation {
    condition     = contains(["OFF", "AUDIT", "ENFORCED"], var.advanced_security_mode)
    error_message = "Advanced security mode must be OFF, AUDIT, or ENFORCED."
  }
}

variable "deletion_protection" {
  description = "Enable deletion protection"
  type        = string
  default     = "INACTIVE"
  validation {
    condition     = contains(["ACTIVE", "INACTIVE"], var.deletion_protection)
    error_message = "Deletion protection must be ACTIVE or INACTIVE."
  }
}

# Token Configuration
variable "access_token_validity_hours" {
  description = "Access token validity in hours"
  type        = number
  default     = 1
}

variable "id_token_validity_hours" {
  description = "ID token validity in hours"
  type        = number
  default     = 1
}

variable "refresh_token_validity_days" {
  description = "Refresh token validity in days"
  type        = number
  default     = 7
}

# OAuth Configuration
variable "callback_urls" {
  description = "OAuth callback URLs"
  type        = list(string)
  default     = ["http://localhost:3000/callback"]
}

variable "logout_urls" {
  description = "OAuth logout URLs"
  type        = list(string)
  default     = ["http://localhost:3000/logout"]
}

# Monitoring
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "failed_sign_in_threshold" {
  description = "Threshold for failed sign-in alarm"
  type        = number
  default     = 10
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
