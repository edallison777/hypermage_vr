variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "web_scenes_bucket_name" {
  type        = string
  default     = ""
  description = "Override S3 bucket name for web scenes. Defaults to {project}-web-scenes-{env}."
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "tags" {
  type    = map(string)
  default = {}
}
