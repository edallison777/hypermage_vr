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

  # Backend configuration for state storage
  # Uncomment and configure for team collaboration
  # backend "s3" {
  #   bucket         = "hypermage-vr-terraform-state"
  #   key            = "dev/terraform.tfstate"
  #   region         = "eu-west-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-state-lock"
  # }
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

# Data source for default VPC (for development)
data "aws_vpc" "default" {
  default = true
}

# Unreal Build Infrastructure Module
module "unreal_build" {
  source = "../../modules/unreal-build"

  project_name = var.project_name
  environment  = "dev"
  aws_region   = var.aws_region
  vpc_id       = data.aws_vpc.default.id

  # Development settings
  instance_type         = "g4dn.xlarge"
  enable_spot_instances = true
  spot_max_price        = "0.50" # Maximum $0.50/hour for spot instances
  root_volume_size      = 150
  log_retention_days    = 30

  tags = {
    CostCenter = "Development"
    Owner      = "DevOps Team"
  }
}

# GameLift Fleet Module
module "gamelift_fleet" {
  source = "../../modules/gamelift-fleet"

  project_name = var.project_name
  environment  = "dev"
  aws_region   = var.aws_region

  # S3 build configuration
  build_s3_bucket_name = module.unreal_build.s3_bucket_name
  build_s3_bucket_arn  = module.unreal_build.s3_bucket_arn
  server_build_s3_key  = "builds/latest/HyperMageVRServer.zip"

  # Fleet configuration
  fleet_type        = "SPOT"
  ec2_instance_type = "c5.large"

  # Scaling configuration (max 3 shards initially)
  enable_auto_scaling = true
  min_fleet_capacity  = 1
  max_fleet_capacity  = 3
  desired_capacity    = 1

  # Server configuration
  server_launch_path = "/local/game/HyperMageVRServer.sh"
  server_parameters  = "-log -port=7777"

  tags = {
    CostCenter = "Development"
    Owner      = "DevOps Team"
  }
}

# FlexMatch Matchmaking Module
module "flexmatch" {
  source = "../../modules/flexmatch"

  project_name = var.project_name
  environment  = "dev"
  aws_region   = var.aws_region

  # Fleet configuration
  fleet_arns = [module.gamelift_fleet.fleet_arn]

  # Match size (10-15 players per shard)
  min_players_per_match = 10
  max_players_per_match = 15

  # Matchmaking timeouts
  matchmaking_timeout_seconds = 120
  acceptance_timeout_seconds  = 30
  acceptance_required         = true

  # Skill matching
  skill_distance_threshold = 5
  max_latency_ms          = 100

  # Backfill
  backfill_mode = "AUTOMATIC"

  tags = {
    CostCenter = "Development"
    Owner      = "DevOps Team"
  }
}

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

  # FlexMatch integration
  matchmaking_configuration_name = module.flexmatch.matchmaking_configuration_name

  # DynamoDB integration (tables will be created in task 15.5)
  # dynamodb_table_arns = [
  #   aws_dynamodb_table.player_sessions.arn,
  #   aws_dynamodb_table.player_rewards.arn
  # ]
  # player_sessions_table_name = aws_dynamodb_table.player_sessions.name
  # player_rewards_table_name  = aws_dynamodb_table.player_rewards.name

  # Logging
  log_retention_days = 30
  lambda_log_level   = "INFO"

  tags = {
    CostCenter = "Development"
    Owner      = "DevOps Team"
  }
}

# Outputs
output "build_s3_bucket" {
  description = "S3 bucket for build artifacts"
  value       = module.unreal_build.s3_bucket_name
}

output "build_launch_template" {
  description = "Launch template ID for build instances"
  value       = module.unreal_build.launch_template_id
}

output "build_iam_profile" {
  description = "IAM instance profile for build instances"
  value       = module.unreal_build.iam_instance_profile_name
}

output "gamelift_fleet_id" {
  description = "GameLift fleet ID"
  value       = module.gamelift_fleet.fleet_id
}

output "gamelift_alias_id" {
  description = "GameLift alias ID for client connections"
  value       = module.gamelift_fleet.alias_id
}

output "gamelift_fleet_arn" {
  description = "GameLift fleet ARN"
  value       = module.gamelift_fleet.fleet_arn
}

output "matchmaking_configuration_name" {
  description = "FlexMatch configuration name for client integration"
  value       = module.flexmatch.matchmaking_configuration_name
}

output "matchmaking_deployment_instructions" {
  description = "Instructions for deploying FlexMatch resources"
  value       = module.flexmatch.deployment_instructions
}

output "game_session_queue_arn" {
  description = "Game session queue ARN"
  value       = module.flexmatch.game_session_queue_arn
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
