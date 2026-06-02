output "ecr_repository_uri" {
  description = "ECR repository URI for the Godot server image"
  value       = aws_ecr_repository.godot_server.repository_url
}

output "ecr_repository_name" {
  description = "ECR repository name"
  value       = aws_ecr_repository.godot_server.name
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN"
  value       = aws_ecs_cluster.godot.arn
}

output "ecs_task_def_arn" {
  description = "ECS task definition ARN (latest revision)"
  value       = aws_ecs_task_definition.godot_server.arn
}

output "ecs_task_exec_role_arn" {
  description = "ECS task execution role ARN"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_role_arn" {
  description = "ECS task role ARN"
  value       = aws_iam_role.ecs_task.arn
}

output "security_group_id" {
  description = "Security group ID allowing game traffic on server_port"
  value       = aws_security_group.godot_server.id
}

output "subnet_ids" {
  description = "Subnet IDs for ECS Fargate tasks (default VPC)"
  value       = tolist(data.aws_subnets.default.ids)
}

output "matchmaking_tickets_table_name" {
  description = "DynamoDB matchmaking tickets table name"
  value       = aws_dynamodb_table.matchmaking_tickets.name
}

output "matchmaking_tickets_table_arn" {
  description = "DynamoDB matchmaking tickets table ARN"
  value       = aws_dynamodb_table.matchmaking_tickets.arn
}

output "server_log_group" {
  description = "CloudWatch log group for game server containers"
  value       = aws_cloudwatch_log_group.godot_server.name
}
