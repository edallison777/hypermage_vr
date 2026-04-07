output "audio_assets_table_name" {
  description = "DynamoDB audio assets table name"
  value       = aws_dynamodb_table.audio_assets.name
}

output "audio_assets_table_arn" {
  description = "DynamoDB audio assets table ARN"
  value       = aws_dynamodb_table.audio_assets.arn
}

output "elevenlabs_key_ssm_path" {
  description = "SSM path for ElevenLabs API key"
  value       = aws_ssm_parameter.elevenlabs_key_placeholder.name
}

output "stability_key_ssm_path" {
  description = "SSM path for Stability AI API key"
  value       = aws_ssm_parameter.stability_key_placeholder.name
}
