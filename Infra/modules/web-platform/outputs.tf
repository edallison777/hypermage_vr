output "web_scenes_bucket_name" {
  description = "S3 bucket for web scene HTML files"
  value       = aws_s3_bucket.web_scenes.bucket
}

output "web_scenes_bucket_arn" {
  description = "ARN of the web scenes S3 bucket"
  value       = aws_s3_bucket.web_scenes.arn
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.web_scenes.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (for cache invalidation)"
  value       = aws_cloudfront_distribution.web_scenes.id
}

output "web_scenes_table_name" {
  description = "DynamoDB web scenes catalogue table"
  value       = aws_dynamodb_table.web_scenes.name
}

output "ws_connections_table_name" {
  description = "DynamoDB WebSocket connections table"
  value       = aws_dynamodb_table.ws_connections.name
}

output "ws_api_id" {
  description = "API Gateway WebSocket API ID"
  value       = aws_apigatewayv2_api.ws.id
}

output "ws_invoke_url" {
  description = "WebSocket API endpoint URL"
  value       = aws_apigatewayv2_stage.ws.invoke_url
}
