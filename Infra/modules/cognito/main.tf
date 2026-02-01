# Cognito User Pools Terraform Module
# Provisions Amazon Cognito for JWT-based player authentication

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Cognito User Pool
resource "aws_cognito_user_pool" "main" {
  name = "${var.project_name}-${var.environment}"

  # Username configuration
  username_attributes      = var.username_attributes
  auto_verified_attributes = var.auto_verified_attributes

  # Username case sensitivity
  username_configuration {
    case_sensitive = false
  }

  # Password policy
  password_policy {
    minimum_length                   = var.password_minimum_length
    require_lowercase                = var.password_require_lowercase
    require_uppercase                = var.password_require_uppercase
    require_numbers                  = var.password_require_numbers
    require_symbols                  = var.password_require_symbols
    temporary_password_validity_days = var.temporary_password_validity_days
  }

  # MFA configuration
  mfa_configuration = var.mfa_configuration

  dynamic "software_token_mfa_configuration" {
    for_each = var.mfa_configuration != "OFF" ? [1] : []
    content {
      enabled = true
    }
  }

  # Account recovery
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # Email configuration
  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  # User attribute schema
  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true

    string_attribute_constraints {
      min_length = 1
      max_length = 256
    }
  }

  schema {
    name                = "player_id"
    attribute_data_type = "String"
    required            = false
    mutable             = true

    string_attribute_constraints {
      min_length = 1
      max_length = 256
    }
  }

  schema {
    name                = "skill_level"
    attribute_data_type = "Number"
    required            = false
    mutable             = true

    number_attribute_constraints {
      min_value = 0
      max_value = 20
    }
  }

  # User pool add-ons
  user_pool_add_ons {
    advanced_security_mode = var.advanced_security_mode
  }

  # Deletion protection
  deletion_protection = var.deletion_protection

  tags = merge(var.tags, {
    Name        = "${var.project_name}-user-pool"
    Environment = var.environment
  })
}

# User Pool Domain
resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.project_name}-${var.environment}-${var.aws_region}"
  user_pool_id = aws_cognito_user_pool.main.id
}

# App Client for Game
resource "aws_cognito_user_pool_client" "game_client" {
  name         = "${var.project_name}-game-client-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id

  # Token validity
  access_token_validity  = var.access_token_validity_hours
  id_token_validity      = var.id_token_validity_hours
  refresh_token_validity = var.refresh_token_validity_days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # OAuth configuration
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code", "implicit"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  callback_urls                        = var.callback_urls
  logout_urls                          = var.logout_urls
  supported_identity_providers         = ["COGNITO"]

  # Security
  generate_secret               = false
  prevent_user_existence_errors = "ENABLED"

  # Read/write attributes
  read_attributes  = ["email", "email_verified", "custom:player_id", "custom:skill_level"]
  write_attributes = ["email", "custom:player_id", "custom:skill_level"]

  # Enable token revocation
  enable_token_revocation = true
}

# App Client for Admin/Backend
resource "aws_cognito_user_pool_client" "admin_client" {
  name         = "${var.project_name}-admin-client-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id

  # Token validity (shorter for admin)
  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 1

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # OAuth configuration
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes                 = ["openid"]
  supported_identity_providers         = ["COGNITO"]

  # Security
  generate_secret               = true
  prevent_user_existence_errors = "ENABLED"

  # Enable token revocation
  enable_token_revocation = true
}

# Identity Pool for AWS resource access
resource "aws_cognito_identity_pool" "main" {
  identity_pool_name               = "${var.project_name}-${var.environment}"
  allow_unauthenticated_identities = false
  allow_classic_flow               = false

  cognito_identity_providers {
    client_id               = aws_cognito_user_pool_client.game_client.id
    provider_name           = aws_cognito_user_pool.main.endpoint
    server_side_token_check = true
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-identity-pool"
    Environment = var.environment
  })
}

# IAM role for authenticated users
resource "aws_iam_role" "authenticated" {
  name = "${var.project_name}-cognito-authenticated-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "cognito-identity.amazonaws.com"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "cognito-identity.amazonaws.com:aud" = aws_cognito_identity_pool.main.id
          }
          "ForAnyValue:StringLike" = {
            "cognito-identity.amazonaws.com:amr" = "authenticated"
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-authenticated-role"
    Environment = var.environment
  })
}

# IAM policy for authenticated users (minimal permissions)
resource "aws_iam_role_policy" "authenticated" {
  name = "cognito-authenticated-policy"
  role = aws_iam_role.authenticated.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cognito-identity:GetId",
          "cognito-identity:GetCredentialsForIdentity"
        ]
        Resource = "*"
      }
    ]
  })
}

# Attach roles to identity pool
resource "aws_cognito_identity_pool_roles_attachment" "main" {
  identity_pool_id = aws_cognito_identity_pool.main.id

  roles = {
    authenticated = aws_iam_role.authenticated.arn
  }
}

# CloudWatch log group for Cognito events
resource "aws_cloudwatch_log_group" "cognito" {
  name              = "/aws/cognito/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name        = "${var.project_name}-cognito-logs"
    Environment = var.environment
  })
}

# CloudWatch metric alarms
resource "aws_cloudwatch_metric_alarm" "failed_sign_ins" {
  alarm_name          = "${var.project_name}-${var.environment}-cognito-failed-sign-ins"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UserAuthenticationFailure"
  namespace           = "AWS/Cognito"
  period              = 300
  statistic           = "Sum"
  threshold           = var.failed_sign_in_threshold
  alarm_description   = "Alert when failed sign-ins are high"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    UserPool = aws_cognito_user_pool.main.id
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-failed-sign-ins-alarm"
    Environment = var.environment
  })
}
