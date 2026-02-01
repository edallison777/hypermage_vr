# Outputs for Cognito Module

output "user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = aws_cognito_user_pool.main.id
}

output "user_pool_arn" {
  description = "ARN of the Cognito User Pool"
  value       = aws_cognito_user_pool.main.arn
}

output "user_pool_endpoint" {
  description = "Endpoint of the Cognito User Pool"
  value       = aws_cognito_user_pool.main.endpoint
}

output "user_pool_domain" {
  description = "Domain of the Cognito User Pool"
  value       = aws_cognito_user_pool_domain.main.domain
}

output "game_client_id" {
  description = "ID of the game app client"
  value       = aws_cognito_user_pool_client.game_client.id
}

output "game_client_name" {
  description = "Name of the game app client"
  value       = aws_cognito_user_pool_client.game_client.name
}

output "admin_client_id" {
  description = "ID of the admin app client"
  value       = aws_cognito_user_pool_client.admin_client.id
  sensitive   = true
}

output "admin_client_secret" {
  description = "Secret of the admin app client"
  value       = aws_cognito_user_pool_client.admin_client.client_secret
  sensitive   = true
}

output "identity_pool_id" {
  description = "ID of the Cognito Identity Pool"
  value       = aws_cognito_identity_pool.main.id
}

output "identity_pool_arn" {
  description = "ARN of the Cognito Identity Pool"
  value       = aws_cognito_identity_pool.main.arn
}

output "authenticated_role_arn" {
  description = "ARN of the authenticated IAM role"
  value       = aws_iam_role.authenticated.arn
}

output "authenticated_role_name" {
  description = "Name of the authenticated IAM role"
  value       = aws_iam_role.authenticated.name
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.cognito.name
}

output "jwks_uri" {
  description = "JWKS URI for JWT token validation"
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/jwks.json"
}

output "issuer" {
  description = "JWT token issuer"
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
}
