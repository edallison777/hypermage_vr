# Outputs for FlexMatch Module

output "matchmaking_configuration_name" {
  description = "Name of the matchmaking configuration (deploy via AWS CLI)"
  value       = "${var.project_name}-${var.environment}"
}

output "matchmaking_configuration_file" {
  description = "Path to matchmaking configuration JSON file"
  value       = local_file.matchmaking_config.filename
}

output "rule_set_name" {
  description = "Name of the matchmaking rule set (deploy via AWS CLI)"
  value       = "${var.project_name}-${var.environment}-rules"
}

output "rule_set_file" {
  description = "Path to rule set JSON file"
  value       = local_file.rule_set.filename
}

output "game_session_queue_name" {
  description = "Name of the game session queue"
  value       = aws_gamelift_game_session_queue.main.name
}

output "game_session_queue_arn" {
  description = "ARN of the game session queue"
  value       = aws_gamelift_game_session_queue.main.arn
}

output "iam_role_arn" {
  description = "ARN of the IAM role for matchmaking"
  value       = aws_iam_role.matchmaking.arn
}

output "iam_role_name" {
  description = "Name of the IAM role for matchmaking"
  value       = aws_iam_role.matchmaking.name
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.matchmaking.name
}

output "deployment_instructions" {
  description = "Instructions for deploying matchmaking resources"
  value       = <<-EOT
    Deploy FlexMatch resources using AWS CLI:
    
    1. Create rule set:
       aws gamelift create-matchmaking-rule-set --cli-input-json file://${local_file.rule_set.filename}
    
    2. Create matchmaking configuration:
       aws gamelift create-matchmaking-configuration --cli-input-json file://${local_file.matchmaking_config.filename}
    
    Note: These resources are not managed by Terraform due to AWS provider limitations.
  EOT
}
