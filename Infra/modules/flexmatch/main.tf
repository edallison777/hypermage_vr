# FlexMatch Matchmaking Terraform Module
# Provisions Amazon FlexMatch for player matchmaking

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

# IAM role for matchmaking configuration
resource "aws_iam_role" "matchmaking" {
  name = "${var.project_name}-flexmatch-${var.environment}"

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

  tags = merge(var.tags, {
    Name        = "${var.project_name}-flexmatch-role"
    Environment = var.environment
  })
}

# IAM policy for SNS notifications
resource "aws_iam_role_policy" "matchmaking_sns" {
  count = var.enable_notifications ? 1 : 0

  name = "sns-notifications"
  role = aws_iam_role.matchmaking.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = var.notification_sns_topic_arn
      }
    ]
  })
}

# Game session queue
resource "aws_gamelift_game_session_queue" "main" {
  name = "${var.project_name}-${var.environment}-queue"

  timeout_in_seconds = var.queue_timeout_seconds

  # Destinations (GameLift fleets)
  destinations = var.fleet_arns

  # Player latency policies
  dynamic "player_latency_policy" {
    for_each = var.player_latency_policies
    content {
      maximum_individual_player_latency_milliseconds = player_latency_policy.value.max_latency_ms
      policy_duration_seconds                        = player_latency_policy.value.duration_seconds
    }
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-session-queue"
    Environment = var.environment
  })
}

# Matchmaking rule set (stored as JSON file for AWS CLI deployment)
# Note: aws_gamelift_matchmaking_rule_set is not available in Terraform AWS provider
# Deploy using AWS CLI: aws gamelift create-matchmaking-rule-set --cli-input-json file://rule-set.json

locals {
  rule_set_body = jsonencode({
    name = "${var.project_name}-${var.environment}-rules"
    ruleLanguageVersion = "1.0"
    
    playerAttributes = [
      {
        name = "skill"
        type = "number"
        default = 10
      },
      {
        name = "region"
        type = "string"
        default = "eu-west-1"
      }
    ]

    teams = [
      {
        name = "players"
        minPlayers = var.min_players_per_match
        maxPlayers = var.max_players_per_match
      }
    ]

    rules = [
      {
        name = "FairTeamSkill"
        description = "Ensure players have similar skill levels"
        type = "distance"
        measurements = ["skill"]
        referenceValue = 10
        maxDistance = var.skill_distance_threshold
      },
      {
        name = "FastConnection"
        description = "Ensure players have acceptable latency"
        type = "latency"
        maxLatency = var.max_latency_ms
      },
      {
        name = "RegionPreference"
        description = "Prefer players from same region"
        type = "collection"
        measurements = ["region"]
        operation = "intersection"
        minCount = 1
      }
    ]

    expansions = [
      {
        target = "rules[FairTeamSkill].maxDistance"
        steps = [
          {
            waitTimeSeconds = 10
            value = var.skill_distance_threshold * 1.5
          },
          {
            waitTimeSeconds = 20
            value = var.skill_distance_threshold * 2
          }
        ]
      },
      {
        target = "rules[FastConnection].maxLatency"
        steps = [
          {
            waitTimeSeconds = 10
            value = var.max_latency_ms * 1.2
          },
          {
            waitTimeSeconds = 20
            value = var.max_latency_ms * 1.5
          }
        ]
      }
    ]
  })
}

# Output rule set for manual deployment
resource "local_file" "rule_set" {
  content  = local.rule_set_body
  filename = "${path.module}/generated/rule-set-${var.environment}.json"
}

# Matchmaking configuration (stored as JSON file for AWS CLI deployment)
# Note: aws_gamelift_matchmaking_configuration is not available in Terraform AWS provider
# Deploy using AWS CLI: aws gamelift create-matchmaking-configuration --cli-input-json file://matchmaking-config.json

locals {
  matchmaking_config = jsonencode({
    Name = "${var.project_name}-${var.environment}"
    Description = "FlexMatch configuration for ${var.project_name} ${var.environment}"
    GameSessionQueueArns = [aws_gamelift_game_session_queue.main.arn]
    RuleSetName = "${var.project_name}-${var.environment}-rules"
    RequestTimeoutSeconds = var.matchmaking_timeout_seconds
    AcceptanceTimeoutSeconds = var.acceptance_timeout_seconds
    AcceptanceRequired = var.acceptance_required
    BackfillMode = var.backfill_mode
    AdditionalPlayerCount = var.additional_player_count
    CustomEventData = var.custom_event_data
    GameSessionData = var.game_session_data
    NotificationTarget = var.enable_notifications ? var.notification_sns_topic_arn : null
  })
}

# Output matchmaking configuration for manual deployment
resource "local_file" "matchmaking_config" {
  content  = local.matchmaking_config
  filename = "${path.module}/generated/matchmaking-config-${var.environment}.json"
}

# CloudWatch log group for matchmaking events
resource "aws_cloudwatch_log_group" "matchmaking" {
  name              = "/aws/gamelift/matchmaking/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name        = "${var.project_name}-matchmaking-logs"
    Environment = var.environment
  })
}

# CloudWatch metric alarms
# Note: These alarms reference matchmaking configuration that must be deployed via AWS CLI
# Update ConfigurationName dimension after deploying matchmaking configuration

resource "aws_cloudwatch_metric_alarm" "matchmaking_timeout_high" {
  alarm_name          = "${var.project_name}-${var.environment}-matchmaking-timeout-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MatchmakingTimedOut"
  namespace           = "AWS/GameLift"
  period              = 300
  statistic           = "Sum"
  threshold           = var.timeout_alarm_threshold
  alarm_description   = "Alert when matchmaking timeouts are high"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    ConfigurationName = "${var.project_name}-${var.environment}"
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-matchmaking-timeout-alarm"
    Environment = var.environment
  })
}

resource "aws_cloudwatch_metric_alarm" "matchmaking_success_low" {
  alarm_name          = "${var.project_name}-${var.environment}-matchmaking-success-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MatchmakingSucceeded"
  namespace           = "AWS/GameLift"
  period              = 300
  statistic           = "Sum"
  threshold           = var.success_alarm_threshold
  alarm_description   = "Alert when matchmaking success rate is low"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    ConfigurationName = "${var.project_name}-${var.environment}"
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-matchmaking-success-alarm"
    Environment = var.environment
  })
}
