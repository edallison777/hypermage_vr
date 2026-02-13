# Infra - Infrastructure as Code

## Overview

The Infra directory contains Terraform modules and configurations for deploying the complete AWS infrastructure required for the Unreal VR Multiplayer System. The infrastructure supports dedicated server architecture with GameLift, FlexMatch matchmaking, Cognito authentication, and DynamoDB session storage.

## Architecture

### Infrastructure Components

```
AWS Infrastructure (eu-west-1)
├── GameLift Fleet (Dedicated servers)
├── FlexMatch (Matchmaking)
├── Cognito User Pools (Authentication)
├── DynamoDB Tables (Session data, Rewards)
├── Lambda Functions (Session API)
├── API Gateway (REST API)
├── S3 Buckets (Build artifacts, Assets)
├── EC2 Build System (Unreal compilation)
├── CloudWatch (Monitoring, Logging)
└── IAM Roles (Service permissions)
```

### Directory Structure

```
Infra/
├── environments/              # Environment-specific configurations
│   ├── dev/                  # Development environment
│   ├── staging/              # Staging environment
│   └── prod/                 # Production environment
├── modules/                   # Reusable Terraform modules
│   ├── cognito/              # User authentication
│   ├── dynamodb/             # Database tables
│   ├── flexmatch/            # Matchmaking configuration
│   ├── gamelift-fleet/       # Server fleet management
│   ├── session-api/          # Session API endpoints
│   └── unreal-build/         # EC2 build infrastructure
├── shared/                    # Shared resources
│   ├── networking.tf         # VPC, subnets, security groups
│   ├── monitoring.tf         # CloudWatch, alarms
│   └── iam.tf               # IAM roles and policies
└── README.md                 # This file
```

## Terraform Modules

### 1. GameLift Fleet Module

**Path**: `modules/gamelift-fleet/`  
**Purpose**: Manages GameLift fleets for dedicated server hosting

**Resources**:
- GameLift Build (server executable)
- GameLift Fleet (server instances)
- GameLift Alias (fleet routing)
- Auto-scaling policies

**Variables**:
```hcl
variable "fleet_name" {
  description = "Name of the GameLift fleet"
  type        = string
}

variable "build_id" {
  description = "GameLift build ID for server executable"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for fleet"
  type        = string
  default     = "c5.large"
}

variable "max_instances" {
  description = "Maximum number of instances in fleet"
  type        = number
  default     = 3
}

variable "locations" {
  description = "AWS regions/zones for fleet deployment"
  type        = list(string)
  default     = ["eu-west-1a", "eu-west-1b"]
}
```

**Outputs**:
```hcl
output "fleet_id" {
  description = "GameLift fleet ID"
  value       = aws_gamelift_fleet.main.id
}

output "fleet_arn" {
  description = "GameLift fleet ARN"
  value       = aws_gamelift_fleet.main.arn
}

output "alias_id" {
  description = "GameLift alias ID"
  value       = aws_gamelift_alias.main.id
}
```

### 2. FlexMatch Module

**Path**: `modules/flexmatch/`  
**Purpose**: Configures matchmaking for 10-15 player matches

**Resources**:
- FlexMatch Configuration
- FlexMatch Rule Set
- GameLift Queue
- Queue destinations

**Rule Set Example**:
```json
{
  "ruleLanguageVersion": "1.0",
  "playerAttributes": [{
    "name": "skill",
    "type": "number",
    "default": 10
  }],
  "teams": [{
    "name": "red",
    "maxPlayers": 8,
    "minPlayers": 5
  }, {
    "name": "blue", 
    "maxPlayers": 8,
    "minPlayers": 5
  }],
  "rules": [{
    "name": "FairTeamSkill",
    "description": "Balance team skill levels",
    "type": "distance",
    "measurements": ["avg(teams[red].players.skill)", "avg(teams[blue].players.skill)"],
    "referenceValue": 2,
    "maxDistance": 5
  }],
  "expansions": [{
    "target": "rules[FairTeamSkill].maxDistance",
    "steps": [{
      "waitTimeSeconds": 10,
      "value": 10
    }, {
      "waitTimeSeconds": 20,
      "value": 20
    }]
  }]
}
```

### 3. Cognito Module

**Path**: `modules/cognito/`  
**Purpose**: User authentication and JWT token management

**Resources**:
- Cognito User Pool
- User Pool Client
- User Pool Domain
- Identity Pool (optional)

**Configuration**:
```hcl
resource "aws_cognito_user_pool" "main" {
  name = var.pool_name

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }

  mfa_configuration = var.mfa_enabled ? "ON" : "OFF"

  device_configuration {
    challenge_required_on_new_device      = true
    device_only_remembered_on_user_prompt = false
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
  }

  schema {
    attribute_data_type = "String"
    name               = "email"
    required           = true
    mutable            = true
  }

  tags = var.tags
}

resource "aws_cognito_user_pool_client" "main" {
  name         = "${var.pool_name}-client"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret = false
  
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  access_token_validity  = var.access_token_validity_hours
  refresh_token_validity = var.refresh_token_validity_days
  
  token_validity_units {
    access_token  = "hours"
    refresh_token = "days"
  }
}
```

### 4. DynamoDB Module

**Path**: `modules/dynamodb/`  
**Purpose**: Session data storage with TTL configuration

**Tables**:

#### PlayerSessions Table
```hcl
resource "aws_dynamodb_table" "player_sessions" {
  name           = "${var.environment}-player-sessions"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "playerId"
  range_key      = "sessionId"

  attribute {
    name = "playerId"
    type = "S"
  }

  attribute {
    name = "sessionId"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = var.tags
}
```

#### InteractionEvents Table
```hcl
resource "aws_dynamodb_table" "interaction_events" {
  name           = "${var.environment}-interaction-events"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "sessionId"
  range_key      = "timestamp"

  attribute {
    name = "sessionId"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = var.tags
}
```

#### PlayerRewards Table (No TTL)
```hcl
resource "aws_dynamodb_table" "player_rewards" {
  name           = "${var.environment}-player-rewards"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "playerId"
  range_key      = "rewardId"

  attribute {
    name = "playerId"
    type = "S"
  }

  attribute {
    name = "rewardId"
    type = "S"
  }

  # No TTL - rewards are persistent

  tags = var.tags
}
```

### 5. Session API Module

**Path**: `modules/session-api/`  
**Purpose**: REST API for matchmaking and session management

**Resources**:
- API Gateway REST API
- Lambda functions
- IAM roles for Lambda execution
- CloudWatch log groups

**Lambda Functions**:

#### Start Matchmaking
```javascript
// lambda/start-matchmaking/index.js
const AWS = require('aws-sdk');
const gamelift = new AWS.GameLift();

exports.handler = async (event) => {
    try {
        const { playerId, playerAttributes } = JSON.parse(event.body);
        
        const params = {
            ConfigurationName: process.env.MATCHMAKING_CONFIG_NAME,
            Players: [{
                PlayerId: playerId,
                PlayerAttributes: playerAttributes || {}
            }]
        };
        
        const result = await gamelift.startMatchmaking(params).promise();
        
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                ticketId: result.MatchmakingTicket.TicketId,
                status: result.MatchmakingTicket.Status
            })
        };
    } catch (error) {
        console.error('Error starting matchmaking:', error);
        return {
            statusCode: 500,
            body: JSON.stringify({ error: 'Internal server error' })
        };
    }
};
```

#### Get Matchmaking Status
```javascript
// lambda/get-matchmaking-status/index.js
const AWS = require('aws-sdk');
const gamelift = new AWS.GameLift();

exports.handler = async (event) => {
    try {
        const { ticketId } = event.pathParameters;
        
        const params = {
            TicketIds: [ticketId]
        };
        
        const result = await gamelift.describeMatchmaking(params).promise();
        const ticket = result.TicketList[0];
        
        if (!ticket) {
            return {
                statusCode: 404,
                body: JSON.stringify({ error: 'Ticket not found' })
            };
        }
        
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                ticketId: ticket.TicketId,
                status: ticket.Status,
                gameSessionInfo: ticket.GameSessionConnectionInfo
            })
        };
    } catch (error) {
        console.error('Error getting matchmaking status:', error);
        return {
            statusCode: 500,
            body: JSON.stringify({ error: 'Internal server error' })
        };
    }
};
```

#### Post Session Summary
```javascript
// lambda/post-session-summary/index.js
const AWS = require('aws-sdk');
const dynamodb = new AWS.DynamoDB.DocumentClient();

exports.handler = async (event) => {
    try {
        const { playerId, sessionId, rewards } = JSON.parse(event.body);
        
        // Store rewards (no TTL - persistent)
        const rewardPromises = rewards.map(rewardId => {
            return dynamodb.put({
                TableName: process.env.PLAYER_REWARDS_TABLE,
                Item: {
                    playerId,
                    rewardId,
                    grantedAt: new Date().toISOString()
                }
            }).promise();
        });
        
        await Promise.all(rewardPromises);
        
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                success: true,
                rewardsGranted: rewards.length
            })
        };
    } catch (error) {
        console.error('Error posting session summary:', error);
        return {
            statusCode: 500,
            body: JSON.stringify({ error: 'Internal server error' })
        };
    }
};
```

### 6. Unreal Build Module

**Path**: `modules/unreal-build/`  
**Purpose**: EC2-based Unreal Engine build system

**Resources**:
- EC2 Launch Template with UE5.3 AMI
- Auto Scaling Group (for build instances)
- S3 Bucket for build artifacts
- IAM roles for build instances
- Security groups

**AMI Configuration**:
```bash
#!/bin/bash
# User data script for UE5.3 build AMI

# Install dependencies
yum update -y
yum install -y git docker aws-cli

# Install Unreal Engine 5.3
cd /opt
git clone --depth 1 --branch 5.3 https://github.com/EpicGames/UnrealEngine.git
cd UnrealEngine
./Setup.sh
./GenerateProjectFiles.sh
make

# Install Android SDK for Quest 3 builds
cd /opt
wget https://dl.google.com/android/repository/commandlinetools-linux-8512546_latest.zip
unzip commandlinetools-linux-8512546_latest.zip
export ANDROID_HOME=/opt/android-sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/bin:$ANDROID_HOME/platform-tools

# Accept Android licenses
yes | sdkmanager --licenses

# Install GameLift SDK
cd /opt
wget https://gamelift-server-sdk-release.s3.us-west-2.amazonaws.com/cpp/GameLift-Cpp-ServerSDK-5.1.0.tar.gz
tar -xzf GameLift-Cpp-ServerSDK-5.1.0.tar.gz

# Create build script
cat > /opt/build-unreal-project.sh << 'EOF'
#!/bin/bash
set -e

PROJECT_PATH=$1
PLATFORM=$2
CONFIGURATION=$3
OUTPUT_BUCKET=$4

echo "Building Unreal project: $PROJECT_PATH"
echo "Platform: $PLATFORM, Configuration: $CONFIGURATION"

# Clone project repository
git clone $PROJECT_REPO_URL /tmp/project
cd /tmp/project

# Build project
/opt/UnrealEngine/Engine/Build/BatchFiles/RunUAT.sh BuildCookRun \
  -project=$PROJECT_PATH \
  -platform=$PLATFORM \
  -configuration=$CONFIGURATION \
  -cook -build -stage -package -archive \
  -archivedirectory=/tmp/builds

# Upload to S3
aws s3 sync /tmp/builds s3://$OUTPUT_BUCKET/builds/$(date +%Y%m%d-%H%M%S)/

echo "Build completed successfully"
EOF

chmod +x /opt/build-unreal-project.sh
```

## Environment Configurations

### Development Environment

**Path**: `environments/dev/`

```hcl
# dev/main.tf
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket = "vr-multiplayer-terraform-state-dev"
    key    = "dev/terraform.tfstate"
    region = "eu-west-1"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Environment = "dev"
      Project     = "unreal-vr-multiplayer"
      ManagedBy   = "terraform"
    }
  }
}

# GameLift Fleet
module "gamelift_fleet" {
  source = "../../modules/gamelift-fleet"
  
  fleet_name     = "vr-multiplayer-dev"
  build_id       = var.gamelift_build_id
  instance_type  = "c5.large"
  max_instances  = 1  # Reduced for dev
  locations      = ["eu-west-1a"]
  
  tags = local.common_tags
}

# FlexMatch
module "flexmatch" {
  source = "../../modules/flexmatch"
  
  configuration_name = "vr-multiplayer-dev"
  rule_set_name     = "vr-balance-rules-dev"
  queue_name        = "vr-multiplayer-queue-dev"
  fleet_arn         = module.gamelift_fleet.fleet_arn
  
  tags = local.common_tags
}

# Cognito
module "cognito" {
  source = "../../modules/cognito"
  
  pool_name                    = "vr-multiplayer-dev"
  access_token_validity_hours  = 1
  refresh_token_validity_days  = 7
  mfa_enabled                 = false
  
  tags = local.common_tags
}

# DynamoDB
module "dynamodb" {
  source = "../../modules/dynamodb"
  
  environment = "dev"
  
  tags = local.common_tags
}

# Session API
module "session_api" {
  source = "../../modules/session-api"
  
  api_name                = "vr-multiplayer-api-dev"
  cognito_user_pool_arn   = module.cognito.user_pool_arn
  matchmaking_config_name = module.flexmatch.configuration_name
  player_rewards_table    = module.dynamodb.player_rewards_table_name
  
  tags = local.common_tags
}

# Unreal Build System
module "unreal_build" {
  source = "../../modules/unreal-build"
  
  environment           = "dev"
  instance_type        = "g4dn.xlarge"
  build_artifacts_bucket = "vr-multiplayer-builds-dev"
  
  tags = local.common_tags
}
```

### Production Environment

**Path**: `environments/prod/`

```hcl
# prod/main.tf
# Similar structure but with production-grade settings

module "gamelift_fleet" {
  source = "../../modules/gamelift-fleet"
  
  fleet_name     = "vr-multiplayer-prod"
  build_id       = var.gamelift_build_id
  instance_type  = "c5.xlarge"  # Larger instances
  max_instances  = 10           # Higher capacity
  locations      = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
  
  # Production scaling policies
  scaling_policies = {
    target_capacity = 5
    scale_up_cooldown = 300
    scale_down_cooldown = 600
  }
  
  tags = local.common_tags
}

# Enhanced monitoring for production
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "VR-Multiplayer-Production"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/GameLift", "ActiveInstances", "FleetId", module.gamelift_fleet.fleet_id],
            ["AWS/GameLift", "ActiveGameSessions", "FleetId", module.gamelift_fleet.fleet_id],
            ["AWS/GameLift", "AvailableGameSessions", "FleetId", module.gamelift_fleet.fleet_id]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "GameLift Fleet Metrics"
        }
      }
    ]
  })
}
```

## Deployment

### Prerequisites

```bash
# Install Terraform
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt-get update && sudo apt-get install terraform

# Configure AWS CLI
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and region (eu-west-1)

# Verify access
aws sts get-caller-identity
```

### Development Deployment

```bash
cd Infra/environments/dev

# Initialize Terraform
terraform init

# Plan deployment
terraform plan -var="gamelift_build_id=build-12345"

# Apply changes
terraform apply -var="gamelift_build_id=build-12345"
```

### Production Deployment

```bash
cd Infra/environments/prod

# Initialize Terraform
terraform init

# Plan deployment (review carefully)
terraform plan -var="gamelift_build_id=build-67890"

# Apply with approval (production requires manual confirmation)
terraform apply -var="gamelift_build_id=build-67890"
```

### Variables Configuration

Create `terraform.tfvars` file:

```hcl
# terraform.tfvars
aws_region = "eu-west-1"
gamelift_build_id = "build-abc123def456"

# Environment-specific settings
environment = "dev"  # or "prod"

# Cost controls
budget_limit_gbp = 100  # Development limit
cost_alerts_enabled = true

# Monitoring
enable_detailed_monitoring = true
log_retention_days = 30

# Security
enable_vpc_flow_logs = true
enable_cloudtrail = true
```

## Cost Management

### Cost Optimization Features

1. **Spot Instances**: EC2 build instances use spot pricing when available
2. **Auto Scaling**: GameLift fleets scale down during low usage
3. **S3 Lifecycle**: Build artifacts expire after 30 days
4. **DynamoDB TTL**: Session data automatically expires after 72 hours
5. **Reserved Capacity**: Production uses reserved instances for predictable workloads

### Cost Monitoring

```hcl
# Cost anomaly detection
resource "aws_ce_anomaly_detector" "main" {
  name         = "vr-multiplayer-cost-anomaly"
  monitor_type = "DIMENSIONAL"
  
  specification = jsonencode({
    dimension = "SERVICE"
    match_options = ["EQUALS"]
    values = ["Amazon GameLift", "Amazon DynamoDB", "Amazon Cognito"]
  })
}

resource "aws_ce_anomaly_subscription" "main" {
  name      = "vr-multiplayer-cost-alerts"
  frequency = "DAILY"
  
  monitor_arn_list = [aws_ce_anomaly_detector.main.arn]
  
  subscriber {
    type    = "EMAIL"
    address = var.cost_alert_email
  }
  
  threshold_expression {
    and {
      dimension {
        key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
        values        = ["100"]  # Alert on £100+ anomalies
        match_options = ["GREATER_THAN_OR_EQUAL"]
      }
    }
  }
}
```

## Monitoring and Observability

### CloudWatch Dashboards

```hcl
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "VR-Multiplayer-${var.environment}"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/GameLift", "ActiveInstances", "FleetId", module.gamelift_fleet.fleet_id],
            ["AWS/GameLift", "ActiveGameSessions", "FleetId", module.gamelift_fleet.fleet_id],
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", module.dynamodb.player_sessions_table_name],
            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", module.dynamodb.player_sessions_table_name]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "System Metrics"
        }
      }
    ]
  })
}
```

### Alarms

```hcl
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "vr-multiplayer-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "4XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors API Gateway error rate"
  
  dimensions = {
    ApiName = module.session_api.api_name
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
}
```

## Security

### IAM Roles and Policies

```hcl
# GameLift fleet role
resource "aws_iam_role" "gamelift_fleet_role" {
  name = "vr-multiplayer-gamelift-fleet-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "gamelift.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "gamelift_fleet_policy" {
  name = "vr-multiplayer-gamelift-fleet-policy"
  role = aws_iam_role.gamelift_fleet_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          module.dynamodb.player_sessions_table_arn,
          module.dynamodb.interaction_events_table_arn,
          module.dynamodb.player_rewards_table_arn
        ]
      }
    ]
  })
}
```

### Network Security

```hcl
# VPC and security groups
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = merge(var.tags, {
    Name = "vr-multiplayer-vpc"
  })
}

resource "aws_security_group" "gamelift" {
  name_prefix = "vr-multiplayer-gamelift-"
  vpc_id      = aws_vpc.main.id
  
  # GameLift server ports
  ingress {
    from_port   = 7777
    to_port     = 7777
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  ingress {
    from_port   = 7777
    to_port     = 7777
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = var.tags
}
```

## Troubleshooting

### Common Issues

#### Terraform State Lock
```bash
# If state is locked, force unlock (use carefully)
terraform force-unlock <LOCK_ID>

# Better: Use proper state locking with DynamoDB
terraform {
  backend "s3" {
    bucket         = "vr-multiplayer-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
```

#### GameLift Build Upload Fails
```bash
# Check build size (must be < 5GB)
ls -lh /path/to/build.zip

# Verify AWS credentials have GameLift permissions
aws gamelift describe-builds

# Check build format (must be zip file with executable)
unzip -l build.zip
```

#### DynamoDB Throttling
```bash
# Check table metrics
aws dynamodb describe-table --table-name dev-player-sessions

# Enable auto-scaling
aws application-autoscaling register-scalable-target \
  --service-namespace dynamodb \
  --resource-id table/dev-player-sessions \
  --scalable-dimension dynamodb:table:WriteCapacityUnits \
  --min-capacity 5 \
  --max-capacity 100
```

This infrastructure provides a complete, scalable, and cost-effective foundation for the Unreal VR Multiplayer System with comprehensive monitoring, security, and cost controls.