output "asset_catalogue_table_name" {
  description = "DynamoDB asset catalogue table name"
  value       = aws_dynamodb_table.asset_catalogue.name
}

output "asset_catalogue_table_arn" {
  description = "DynamoDB asset catalogue table ARN"
  value       = aws_dynamodb_table.asset_catalogue.arn
}

output "ingest_trigger_lambda_arn" {
  description = "ARN of the asset ingest trigger Lambda"
  value       = aws_lambda_function.asset_ingest_trigger.arn
}

output "image_processor_lambda_arn" {
  description = "ARN of the image processor Lambda"
  value       = aws_lambda_function.image_processor.arn
}

output "meshy_3d_lambda_arn" {
  description = "ARN of the Meshy.ai 3D conversion Lambda"
  value       = aws_lambda_function.meshy_3d.arn
}

output "blender_ecs_cluster_arn" {
  description = "ARN of the ECS cluster for Blender conversions"
  value       = aws_ecs_cluster.blender.arn
}

output "blender_task_definition_arn" {
  description = "ARN of the Blender ECS task definition"
  value       = aws_ecs_task_definition.blender_converter.arn
}
