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

variable "elevenlabs_api_key_ssm_path" {
  type        = string
  description = "SSM path for ElevenLabs API key (SFX + narration)"
  default     = "/hypermage/elevenlabs-api-key"
}

variable "stability_api_key_ssm_path" {
  type        = string
  description = "SSM path for Stability AI API key (ambient + score)"
  default     = "/hypermage/stability-api-key"
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "tags" {
  type    = map(string)
  default = {}
}
