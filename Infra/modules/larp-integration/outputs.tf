output "gm_event_url" {
  description = "HTTP POST endpoint for GM events: POST {url} {scene_id, hook_name, gm_message}"
  value       = "${aws_apigatewayv2_stage.gm.invoke_url}/gm/event"
}

output "gm_event_lambda_arn" {
  description = "ARN of the GM event Lambda function"
  value       = aws_lambda_function.gm_event.arn
}

output "gm_api_id" {
  description = "API Gateway HTTP API ID"
  value       = aws_apigatewayv2_api.gm.id
}

output "ws_management_endpoint" {
  description = "WebSocket management endpoint (https scheme, for ManageConnections calls)"
  value       = replace(var.ws_invoke_url, "wss://", "https://")
}

output "gm_event_url_ssm_path" {
  description = "SSM parameter path storing the GM event URL"
  value       = aws_ssm_parameter.gm_event_url.name
}
