# DynamoDB Tables Terraform Module
# Provisions DynamoDB tables for session management and rewards

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# PlayerSessions Table (with TTL)
# Stores ephemeral session data that expires 72 hours after session end
resource "aws_dynamodb_table" "player_sessions" {
  name           = "${var.project_name}-player-sessions-${var.environment}"
  billing_mode   = var.billing_mode
  hash_key       = "playerId"
  range_key      = "sessionId"

  # On-demand capacity (no need to specify read/write capacity)
  # For provisioned mode, uncomment below:
  # read_capacity  = var.read_capacity
  # write_capacity = var.write_capacity

  attribute {
    name = "playerId"
    type = "S"
  }

  attribute {
    name = "sessionId"
    type = "S"
  }

  # TTL configuration - automatically delete records after expiration
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  # Point-in-time recovery for production
  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  # Server-side encryption
  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-player-sessions"
    Environment = var.environment
    TTL         = "72h"
  })
}

# InteractionEvents Table (with TTL)
# Stores player interaction events that expire 72 hours after session end
resource "aws_dynamodb_table" "interaction_events" {
  name           = "${var.project_name}-interaction-events-${var.environment}"
  billing_mode   = var.billing_mode
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

  attribute {
    name = "playerId"
    type = "S"
  }

  # Global Secondary Index for querying by playerId
  global_secondary_index {
    name            = "PlayerIdIndex"
    hash_key        = "playerId"
    range_key       = "timestamp"
    projection_type = "ALL"

    # For on-demand billing, no need to specify read/write capacity
    # For provisioned mode, uncomment below:
    # read_capacity  = var.gsi_read_capacity
    # write_capacity = var.gsi_write_capacity
  }

  # TTL configuration - automatically delete records after expiration
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  # Point-in-time recovery for production
  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  # Server-side encryption
  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-interaction-events"
    Environment = var.environment
    TTL         = "72h"
  })
}

# PlayerRewards Table (NO TTL - persistent)
# Stores reward flags that persist indefinitely
resource "aws_dynamodb_table" "player_rewards" {
  name           = "${var.project_name}-player-rewards-${var.environment}"
  billing_mode   = var.billing_mode
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

  # NO TTL - rewards persist indefinitely

  # Point-in-time recovery for production
  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  # Server-side encryption
  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-player-rewards"
    Environment = var.environment
    Persistent  = "true"
  })
}

# CloudWatch Alarms for table monitoring
resource "aws_cloudwatch_metric_alarm" "player_sessions_read_throttle" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-player-sessions-read-throttle-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ReadThrottleEvents"
  namespace           = "AWS/DynamoDB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Alert when PlayerSessions table read throttle events exceed threshold"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    TableName = aws_dynamodb_table.player_sessions.name
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-player-sessions-read-throttle-alarm"
    Environment = var.environment
  })
}

resource "aws_cloudwatch_metric_alarm" "player_sessions_write_throttle" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-player-sessions-write-throttle-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "WriteThrottleEvents"
  namespace           = "AWS/DynamoDB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Alert when PlayerSessions table write throttle events exceed threshold"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    TableName = aws_dynamodb_table.player_sessions.name
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-player-sessions-write-throttle-alarm"
    Environment = var.environment
  })
}

