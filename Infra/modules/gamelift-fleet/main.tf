# GameLift Fleet Terraform Module
# Provisions Amazon GameLift fleet for dedicated server hosting

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# IAM role for GameLift fleet instances
resource "aws_iam_role" "fleet" {
  name = "${var.project_name}-gamelift-fleet-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "gamelift.amazonaws.com"
        }
      },
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-gamelift-fleet-role"
    Environment = var.environment
  })
}

# IAM policy for CloudWatch logs
resource "aws_iam_role_policy" "fleet_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.fleet.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/aws/gamelift/*"
      }
    ]
  })
}

# IAM policy for S3 access (for downloading server builds)
resource "aws_iam_role_policy" "fleet_s3" {
  name = "s3-build-access"
  role = aws_iam_role.fleet.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.build_s3_bucket_arn,
          "${var.build_s3_bucket_arn}/*"
        ]
      }
    ]
  })
}

# GameLift build resource
resource "aws_gamelift_build" "server" {
  name             = "${var.project_name}-server-${var.environment}"
  operating_system = "AMAZON_LINUX_2023"

  storage_location {
    bucket   = var.build_s3_bucket_name
    key      = var.server_build_s3_key
    role_arn = aws_iam_role.fleet.arn
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-server-build"
    Environment = var.environment
    BuildType   = "DedicatedServer"
  })
}

# GameLift fleet
resource "aws_gamelift_fleet" "main" {
  name        = "${var.project_name}-fleet-${var.environment}"
  description = "GameLift fleet for ${var.project_name} ${var.environment} environment"

  build_id = aws_gamelift_build.server.id

  # Fleet configuration
  fleet_type        = var.fleet_type
  ec2_instance_type = var.ec2_instance_type

  # Capacity configuration
  new_game_session_protection_policy = "FullProtection"

  # Runtime configuration
  runtime_configuration {
    server_process {
      concurrent_executions = var.concurrent_executions
      launch_path           = var.server_launch_path
      parameters            = var.server_parameters
    }

    game_session_activation_timeout_seconds = 300
    max_concurrent_game_session_activations = 1
  }

  # Resource creation limits
  resource_creation_limit_policy {
    new_game_sessions_per_creator = var.max_sessions_per_creator
    policy_period_in_minutes      = 15
  }

  # Inbound permissions for client connections
  dynamic "ec2_inbound_permission" {
    for_each = var.inbound_permissions
    content {
      from_port = ec2_inbound_permission.value.from_port
      to_port   = ec2_inbound_permission.value.to_port
      ip_range  = ec2_inbound_permission.value.ip_range
      protocol  = ec2_inbound_permission.value.protocol
    }
  }

  # Metric groups for CloudWatch
  metric_groups = ["${var.project_name}-${var.environment}"]

  tags = merge(var.tags, {
    Name        = "${var.project_name}-fleet"
    Environment = var.environment
  })
}

# GameLift fleet locations (multi-region support)
# Note: Fleet locations are configured via fleet_locations variable
# Additional locations can be added after fleet creation via AWS Console or CLI

# Alias for fleet (allows zero-downtime updates)
resource "aws_gamelift_alias" "main" {
  name        = "${var.project_name}-${var.environment}"
  description = "Alias for ${var.project_name} ${var.environment} fleet"

  routing_strategy {
    type     = "SIMPLE"
    fleet_id = aws_gamelift_fleet.main.id
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-alias"
    Environment = var.environment
  })
}

# CloudWatch log group for GameLift logs
resource "aws_cloudwatch_log_group" "gamelift" {
  name              = "/aws/gamelift/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name        = "${var.project_name}-gamelift-logs"
    Environment = var.environment
  })
}

# CloudWatch alarms for fleet monitoring
resource "aws_cloudwatch_metric_alarm" "fleet_capacity_low" {
  alarm_name          = "${var.project_name}-${var.environment}-fleet-capacity-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ActiveInstances"
  namespace           = "AWS/GameLift"
  period              = 300
  statistic           = "Average"
  threshold           = var.min_capacity_alarm_threshold
  alarm_description   = "Alert when fleet capacity is too low"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    FleetId = aws_gamelift_fleet.main.id
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-capacity-low-alarm"
    Environment = var.environment
  })
}

resource "aws_cloudwatch_metric_alarm" "fleet_utilization_high" {
  alarm_name          = "${var.project_name}-${var.environment}-fleet-utilization-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "PercentAvailableGameSessions"
  namespace           = "AWS/GameLift"
  period              = 300
  statistic           = "Average"
  threshold           = var.high_utilization_threshold
  alarm_description   = "Alert when fleet utilization is high"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    FleetId = aws_gamelift_fleet.main.id
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-utilization-high-alarm"
    Environment = var.environment
  })
}
