# Development Environment Terraform Configuration
# This configuration deploys the Unreal VR Multiplayer System to the dev environment

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "hypermage-vr-terraform-state"
    key            = "dev/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    dynamodb_table = "hypermage-vr-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "HyperMage VR"
      Environment = "dev"
      ManagedBy   = "Terraform"
      Repository  = "hypermage-vr-multiplayer"
    }
  }
}

# Data source for default VPC — used by unreal_build module when enabled
# data "aws_vpc" "default" { default = true }

# Unreal Build Infrastructure Module
# NOTE: Requires a custom AMI tagged "unreal-5.3-build-*" to exist in eu-west-1.
# Uncomment once the AMI has been created with UE5.3, Android SDK, and GameLift SDK.
# See: Infra/modules/unreal-build/README.md for AMI creation instructions.
# module "unreal_build" {
#   source                = "../../modules/unreal-build"
#   project_name          = var.project_name
#   environment           = "dev"
#   aws_region            = var.aws_region
#   vpc_id                = data.aws_vpc.default.id
#   instance_type         = "g4dn.xlarge"
#   enable_spot_instances = true
#   spot_max_price        = "0.50"
#   root_volume_size      = 150
#   log_retention_days    = 30
#   tags = { CostCenter = "Development", Owner = "DevOps Team" }
# }

# DynamoDB Tables Module
module "dynamodb" {
  source = "../../modules/dynamodb"

  project_name = var.project_name
  environment  = "dev"

  billing_mode                  = "PAY_PER_REQUEST"
  enable_point_in_time_recovery = false
  enable_cloudwatch_alarms      = false

  tags = {
    CostCenter = "Development"
    Owner      = "DevOps Team"
  }
}

# GameLift Fleet Module
# NOTE: Requires a compiled server build uploaded to S3 first.
# Uncomment once HyperMageVRServer.zip is available in the build bucket.
# module "gamelift_fleet" {
#   source = "../../modules/gamelift-fleet"
#   project_name         = var.project_name
#   environment          = "dev"
#   aws_region           = var.aws_region
#   build_s3_bucket_name = module.unreal_build.s3_bucket_name
#   build_s3_bucket_arn  = module.unreal_build.s3_bucket_arn
#   server_build_s3_key  = "builds/latest/HyperMageVRServer.zip"
#   fleet_type           = "SPOT"
#   ec2_instance_type    = "c5.large"
#   enable_auto_scaling  = true
#   min_fleet_capacity   = 1
#   max_fleet_capacity   = 3
#   desired_capacity     = 1
#   server_launch_path   = "/local/game/HyperMageVRServer.sh"
#   server_parameters    = "-log -port=7777"
#   tags = { CostCenter = "Development", Owner = "DevOps Team" }
# }

# FlexMatch Matchmaking Module
# NOTE: Depends on gamelift_fleet. Uncomment together with gamelift_fleet above.
# module "flexmatch" {
#   source                      = "../../modules/flexmatch"
#   project_name                = var.project_name
#   environment                 = "dev"
#   aws_region                  = var.aws_region
#   fleet_arns                  = [module.gamelift_fleet.fleet_arn]
#   min_players_per_match       = 10
#   max_players_per_match       = 15
#   matchmaking_timeout_seconds = 120
#   acceptance_timeout_seconds  = 30
#   acceptance_required         = true
#   skill_distance_threshold    = 5
#   max_latency_ms              = 100
#   backfill_mode               = "AUTOMATIC"
#   tags = { CostCenter = "Development", Owner = "DevOps Team" }
# }

# Cognito User Pools Module
module "cognito" {
  source = "../../modules/cognito"

  project_name = var.project_name
  environment  = "dev"
  aws_region   = var.aws_region

  # Token validity (1h access, 7d refresh)
  access_token_validity_hours = 1
  id_token_validity_hours     = 1
  refresh_token_validity_days = 7

  # MFA configuration (optional for dev)
  mfa_configuration = "OPTIONAL"

  # Security (audit mode for dev)
  advanced_security_mode = "AUDIT"
  deletion_protection    = "INACTIVE"

  # OAuth callbacks (update with actual URLs)
  callback_urls = [
    "http://localhost:3000/callback",
    "hypermage://callback"
  ]
  logout_urls = [
    "http://localhost:3000/logout",
    "hypermage://logout"
  ]

  tags = {
    CostCenter = "Development"
    Owner      = "DevOps Team"
  }
}

# Session API Module
module "session_api" {
  source = "../../modules/session-api"

  project_name = var.project_name
  environment  = "dev"
  aws_region   = var.aws_region

  # Cognito integration
  cognito_user_pool_arn = module.cognito.user_pool_arn

  # FlexMatch integration — hardcoded until gamelift_fleet/flexmatch modules are enabled
  matchmaking_configuration_name = "${var.project_name}-dev"

  # DynamoDB integration
  dynamodb_table_arns        = module.dynamodb.all_table_arns
  player_sessions_table_name = module.dynamodb.player_sessions_table_name
  player_rewards_table_name  = module.dynamodb.player_rewards_table_name

  # Logging
  log_retention_days = 30
  lambda_log_level   = "INFO"

  tags = {
    CostCenter = "Development"
    Owner      = "DevOps Team"
  }

  # API Gateway stage logging requires the account-level CloudWatch role to be set first
  depends_on = [aws_api_gateway_account.main]
}

# API Gateway Account — sets the CloudWatch Logs role ARN at the account level
# Required for API Gateway stage access logging to work
resource "aws_iam_role" "api_gateway_cloudwatch" {
  name = "${var.project_name}-apigateway-cloudwatch-dev"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "apigateway.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  role       = aws_iam_role.api_gateway_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

resource "aws_api_gateway_account" "main" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch.arn
  depends_on          = [aws_iam_role_policy_attachment.api_gateway_cloudwatch]
}

# Outputs
# Unreal build outputs — uncomment when unreal_build module is enabled
# output "build_s3_bucket"       { value = module.unreal_build.s3_bucket_name }
# output "build_launch_template" { value = module.unreal_build.launch_template_id }
# output "build_iam_profile"     { value = module.unreal_build.iam_instance_profile_name }

# GameLift/FlexMatch outputs — uncomment when those modules are enabled
# output "gamelift_fleet_id" {
#   value = module.gamelift_fleet.fleet_id
# }
# output "gamelift_alias_id" {
#   value = module.gamelift_fleet.alias_id
# }
# output "gamelift_fleet_arn" {
#   value = module.gamelift_fleet.fleet_arn
# }
# output "matchmaking_configuration_name" {
#   value = module.flexmatch.matchmaking_configuration_name
# }
# output "matchmaking_deployment_instructions" {
#   value = module.flexmatch.deployment_instructions
# }
# output "game_session_queue_arn" {
#   value = module.flexmatch.game_session_queue_arn
# }

output "dynamodb_table_names" {
  description = "All DynamoDB table names"
  value       = module.dynamodb.all_table_names
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID for authentication"
  value       = module.cognito.user_pool_id
}

output "cognito_game_client_id" {
  description = "Cognito game client ID for client integration"
  value       = module.cognito.game_client_id
}

output "cognito_jwks_uri" {
  description = "JWKS URI for JWT token validation"
  value       = module.cognito.jwks_uri
}

output "cognito_issuer" {
  description = "JWT token issuer"
  value       = module.cognito.issuer
}

output "session_api_endpoint" {
  description = "Session API endpoint URL"
  value       = module.session_api.api_endpoint
}

output "session_api_id" {
  description = "Session API Gateway ID"
  value       = module.session_api.api_id
}
