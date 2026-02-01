# Outputs for GameLift Fleet Module

output "fleet_id" {
  description = "ID of the GameLift fleet"
  value       = aws_gamelift_fleet.main.id
}

output "fleet_arn" {
  description = "ARN of the GameLift fleet"
  value       = aws_gamelift_fleet.main.arn
}

output "fleet_name" {
  description = "Name of the GameLift fleet"
  value       = aws_gamelift_fleet.main.name
}

output "build_id" {
  description = "ID of the GameLift build"
  value       = aws_gamelift_build.server.id
}

output "build_arn" {
  description = "ARN of the GameLift build"
  value       = aws_gamelift_build.server.arn
}

output "alias_id" {
  description = "ID of the GameLift alias"
  value       = aws_gamelift_alias.main.id
}

output "alias_arn" {
  description = "ARN of the GameLift alias"
  value       = aws_gamelift_alias.main.arn
}

output "alias_name" {
  description = "Name of the GameLift alias"
  value       = aws_gamelift_alias.main.name
}

output "iam_role_arn" {
  description = "ARN of the IAM role for fleet instances"
  value       = aws_iam_role.fleet.arn
}

output "iam_role_name" {
  description = "Name of the IAM role for fleet instances"
  value       = aws_iam_role.fleet.name
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.gamelift.name
}

output "fleet_locations" {
  description = "List of fleet locations"
  value       = var.fleet_locations
}
