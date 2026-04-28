output "api_url" {
  description = "Base URL for the world-state API (no trailing slash)"
  value       = aws_apigatewayv2_stage.world_state.invoke_url
}

output "api_id" {
  description = "API Gateway HTTP API ID"
  value       = aws_apigatewayv2_api.world_state.id
}

output "table_name" {
  description = "DynamoDB world-state table name"
  value       = aws_dynamodb_table.world_state.name
}

output "ssm_path" {
  description = "SSM parameter path storing the world-state API base URL"
  value       = aws_ssm_parameter.world_state_api_url.name
}
