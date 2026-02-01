# Outputs for Unreal Build EC2 Infrastructure Module

output "s3_bucket_name" {
  description = "Name of the S3 bucket for build artifacts"
  value       = aws_s3_bucket.build_artifacts.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for build artifacts"
  value       = aws_s3_bucket.build_artifacts.arn
}

output "s3_bucket_region" {
  description = "Region of the S3 bucket"
  value       = aws_s3_bucket.build_artifacts.region
}

output "launch_template_id" {
  description = "ID of the launch template for build instances"
  value       = aws_launch_template.build_instance.id
}

output "launch_template_latest_version" {
  description = "Latest version of the launch template"
  value       = aws_launch_template.build_instance.latest_version
}

output "iam_instance_profile_arn" {
  description = "ARN of the IAM instance profile for build instances"
  value       = aws_iam_instance_profile.build_instance.arn
}

output "iam_instance_profile_name" {
  description = "Name of the IAM instance profile for build instances"
  value       = aws_iam_instance_profile.build_instance.name
}

output "security_group_id" {
  description = "ID of the security group for build instances"
  value       = aws_security_group.build_instance.id
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for build logs"
  value       = aws_cloudwatch_log_group.build_logs.name
}

output "ami_id" {
  description = "AMI ID used for build instances"
  value       = var.ami_id != "" ? var.ami_id : data.aws_ami.unreal_build.id
}
