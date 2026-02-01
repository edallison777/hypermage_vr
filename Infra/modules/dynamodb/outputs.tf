# DynamoDB Module Outputs

output "player_sessions_table_name" {
  description = "PlayerSessions table name"
  value       = aws_dynamodb_table.player_sessions.name
}

output "player_sessions_table_arn" {
  description = "PlayerSessions table ARN"
  value       = aws_dynamodb_table.player_sessions.arn
}

output "player_sessions_table_id" {
  description = "PlayerSessions table ID"
  value       = aws_dynamodb_table.player_sessions.id
}

output "interaction_events_table_name" {
  description = "InteractionEvents table name"
  value       = aws_dynamodb_table.interaction_events.name
}

output "interaction_events_table_arn" {
  description = "InteractionEvents table ARN"
  value       = aws_dynamodb_table.interaction_events.arn
}

output "interaction_events_table_id" {
  description = "InteractionEvents table ID"
  value       = aws_dynamodb_table.interaction_events.id
}

output "player_rewards_table_name" {
  description = "PlayerRewards table name"
  value       = aws_dynamodb_table.player_rewards.name
}

output "player_rewards_table_arn" {
  description = "PlayerRewards table ARN"
  value       = aws_dynamodb_table.player_rewards.arn
}

output "player_rewards_table_id" {
  description = "PlayerRewards table ID"
  value       = aws_dynamodb_table.player_rewards.id
}

output "all_table_arns" {
  description = "List of all DynamoDB table ARNs"
  value = [
    aws_dynamodb_table.player_sessions.arn,
    aws_dynamodb_table.interaction_events.arn,
    aws_dynamodb_table.player_rewards.arn
  ]
}

output "all_table_names" {
  description = "List of all DynamoDB table names"
  value = [
    aws_dynamodb_table.player_sessions.name,
    aws_dynamodb_table.interaction_events.name,
    aws_dynamodb_table.player_rewards.name
  ]
}

