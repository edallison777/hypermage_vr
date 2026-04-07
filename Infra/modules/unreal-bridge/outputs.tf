output "bridge_url_ssm_path" {
  description = "SSM path for the UnrealBridge URL"
  value       = aws_ssm_parameter.bridge_url.name
}
