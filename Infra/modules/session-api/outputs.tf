# Session API Module Outputs

output "api_id" {
  description = "API Gateway REST API ID"
  value       = aws_api_gateway_rest_api.session_api.id
}

output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_api_gateway_stage.session_api.invoke_url
}

output "api_arn" {
  description = "API Gateway ARN"
  value       = aws_api_gateway_rest_api.session_api.arn
}

output "start_matchmaking_function_name" {
  description = "Start matchmaking Lambda function name"
  value       = aws_lambda_function.start_matchmaking.function_name
}

output "start_matchmaking_function_arn" {
  description = "Start matchmaking Lambda function ARN"
  value       = aws_lambda_function.start_matchmaking.arn
}

output "get_matchmaking_status_function_name" {
  description = "Get matchmaking status Lambda function name"
  value       = aws_lambda_function.get_matchmaking_status.function_name
}

output "get_matchmaking_status_function_arn" {
  description = "Get matchmaking status Lambda function ARN"
  value       = aws_lambda_function.get_matchmaking_status.arn
}

output "post_session_summary_function_name" {
  description = "Post session summary Lambda function name"
  value       = aws_lambda_function.post_session_summary.function_name
}

output "post_session_summary_function_arn" {
  description = "Post session summary Lambda function ARN"
  value       = aws_lambda_function.post_session_summary.arn
}

output "lambda_role_arn" {
  description = "IAM role ARN for Lambda functions"
  value       = aws_iam_role.lambda.arn
}

output "api_gateway_log_group" {
  description = "CloudWatch log group for API Gateway"
  value       = aws_cloudwatch_log_group.api_gateway.name
}
