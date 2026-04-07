variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "bridge_url_ssm_path" {
  type        = string
  default     = "/hypermage/unreal-bridge-url"
  description = "SSM path where the UnrealBridge URL will be stored (e.g. https://abc.ngrok.io)"
}

variable "tags" {
  type    = map(string)
  default = {}
}
