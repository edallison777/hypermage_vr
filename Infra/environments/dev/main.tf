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
