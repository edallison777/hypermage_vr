# Session API Terraform Module
# Provisions API Gateway and Lambda functions for matchmaking and session management

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

# API Gateway REST API
resource "aws_api_gateway_rest_api" "session_api" {
  name        = "${var.project_name}-session-api-${var.environment}"
  description = "Session API for ${var.project_name} ${var.environment}"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-session-api"
    Environment = var.environment
  })
}

# API Gateway Authorizer (Cognito)
resource "aws_api_gateway_authorizer" "cognito" {
  name            = "cognito-authorizer"
  rest_api_id     = aws_api_gateway_rest_api.session_api.id
  type            = "COGNITO_USER_POOLS"
  provider_arns   = [var.cognito_user_pool_arn]
  identity_source = "method.request.header.Authorization"
}

# /matchmaking resource
resource "aws_api_gateway_resource" "matchmaking" {
  rest_api_id = aws_api_gateway_rest_api.session_api.id
  parent_id   = aws_api_gateway_rest_api.session_api.root_resource_id
  path_part   = "matchmaking"
}

# /matchmaking/start resource
resource "aws_api_gateway_resource" "matchmaking_start" {
  rest_api_id = aws_api_gateway_rest_api.session_api.id
  parent_id   = aws_api_gateway_resource.matchmaking.id
  path_part   = "start"
}

# POST /matchmaking/start
resource "aws_api_gateway_method" "start_matchmaking" {
  rest_api_id   = aws_api_gateway_rest_api.session_api.id
  resource_id   = aws_api_gateway_resource.matchmaking_start.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "start_matchmaking" {
  rest_api_id             = aws_api_gateway_rest_api.session_api.id
  resource_id             = aws_api_gateway_resource.matchmaking_start.id
  http_method             = aws_api_gateway_method.start_matchmaking.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.start_matchmaking.invoke_arn
}

# /matchmaking/status/{ticketId} resource
resource "aws_api_gateway_resource" "matchmaking_status" {
  rest_api_id = aws_api_gateway_rest_api.session_api.id
  parent_id   = aws_api_gateway_resource.matchmaking.id
  path_part   = "status"
}

resource "aws_api_gateway_resource" "matchmaking_status_ticket" {
  rest_api_id = aws_api_gateway_rest_api.session_api.id
  parent_id   = aws_api_gateway_resource.matchmaking_status.id
  path_part   = "{ticketId}"
}

# GET /matchmaking/status/{ticketId}
resource "aws_api_gateway_method" "get_matchmaking_status" {
  rest_api_id   = aws_api_gateway_rest_api.session_api.id
  resource_id   = aws_api_gateway_resource.matchmaking_status_ticket.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id

  request_parameters = {
    "method.request.path.ticketId" = true
  }
}

resource "aws_api_gateway_integration" "get_matchmaking_status" {
  rest_api_id             = aws_api_gateway_rest_api.session_api.id
  resource_id             = aws_api_gateway_resource.matchmaking_status_ticket.id
  http_method             = aws_api_gateway_method.get_matchmaking_status.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.get_matchmaking_status.invoke_arn
}

# /session-summary resource
resource "aws_api_gateway_resource" "session_summary" {
  rest_api_id = aws_api_gateway_rest_api.session_api.id
  parent_id   = aws_api_gateway_rest_api.session_api.root_resource_id
  path_part   = "session-summary"
}

# POST /session-summary
resource "aws_api_gateway_method" "post_session_summary" {
  rest_api_id   = aws_api_gateway_rest_api.session_api.id
  resource_id   = aws_api_gateway_resource.session_summary.id
  http_method   = "POST"
  authorization = "AWS_IAM"
}

resource "aws_api_gateway_integration" "post_session_summary" {
  rest_api_id             = aws_api_gateway_rest_api.session_api.id
  resource_id             = aws_api_gateway_resource.session_summary.id
  http_method             = aws_api_gateway_method.post_session_summary.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.post_session_summary.invoke_arn
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "session_api" {
  rest_api_id = aws_api_gateway_rest_api.session_api.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.matchmaking.id,
      aws_api_gateway_resource.matchmaking_start.id,
      aws_api_gateway_method.start_matchmaking.id,
      aws_api_gateway_integration.start_matchmaking.id,
      aws_api_gateway_resource.matchmaking_status_ticket.id,
      aws_api_gateway_method.get_matchmaking_status.id,
      aws_api_gateway_integration.get_matchmaking_status.id,
      aws_api_gateway_resource.session_summary.id,
      aws_api_gateway_method.post_session_summary.id,
      aws_api_gateway_integration.post_session_summary.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

# API Gateway Stage
resource "aws_api_gateway_stage" "session_api" {
  deployment_id = aws_api_gateway_deployment.session_api.id
  rest_api_id   = aws_api_gateway_rest_api.session_api.id
  stage_name    = var.environment

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-api-stage"
    Environment = var.environment
  })
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name        = "${var.project_name}-api-gateway-logs"
    Environment = var.environment
  })
}

# CloudWatch Log Group for Lambda functions
resource "aws_cloudwatch_log_group" "lambda_start_matchmaking" {
  name              = "/aws/lambda/${var.project_name}-start-matchmaking-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name        = "${var.project_name}-start-matchmaking-logs"
    Environment = var.environment
  })
}

resource "aws_cloudwatch_log_group" "lambda_get_status" {
  name              = "/aws/lambda/${var.project_name}-get-matchmaking-status-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name        = "${var.project_name}-get-matchmaking-status-logs"
    Environment = var.environment
  })
}

resource "aws_cloudwatch_log_group" "lambda_post_summary" {
  name              = "/aws/lambda/${var.project_name}-post-session-summary-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name        = "${var.project_name}-post-session-summary-logs"
    Environment = var.environment
  })
}

# IAM role for Lambda functions
resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-session-api-lambda-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-lambda-role"
    Environment = var.environment
  })
}

# IAM policy for Lambda CloudWatch Logs
resource "aws_iam_role_policy" "lambda_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      }
    ]
  })
}

# IAM policy for GameLift access
resource "aws_iam_role_policy" "lambda_gamelift" {
  name = "gamelift-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "gamelift:StartMatchmaking",
          "gamelift:DescribeMatchmaking",
          "gamelift:StopMatchmaking"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM policy for DynamoDB access
resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "dynamodb-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = var.dynamodb_table_arns
      }
    ]
  })
}

# Lambda function deployment packages
data "archive_file" "start_matchmaking" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/start-matchmaking"
  output_path = "${path.module}/lambda/dist/start-matchmaking.zip"
}

data "archive_file" "get_matchmaking_status" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/get-matchmaking-status"
  output_path = "${path.module}/lambda/dist/get-matchmaking-status.zip"
}

data "archive_file" "post_session_summary" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/post-session-summary"
  output_path = "${path.module}/lambda/dist/post-session-summary.zip"
}

# Lambda function: Start Matchmaking
resource "aws_lambda_function" "start_matchmaking" {
  filename         = data.archive_file.start_matchmaking.output_path
  function_name    = "${var.project_name}-start-matchmaking-${var.environment}"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.start_matchmaking.output_base64sha256
  runtime          = "nodejs20.x"
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      MATCHMAKING_CONFIG_NAME = var.matchmaking_configuration_name
      ENVIRONMENT             = var.environment
      LOG_LEVEL               = var.lambda_log_level
    }
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-start-matchmaking"
    Environment = var.environment
  })

  depends_on = [
    aws_cloudwatch_log_group.lambda_start_matchmaking,
    aws_iam_role_policy.lambda_logs,
    aws_iam_role_policy.lambda_gamelift
  ]
}

# Lambda function: Get Matchmaking Status
resource "aws_lambda_function" "get_matchmaking_status" {
  filename         = data.archive_file.get_matchmaking_status.output_path
  function_name    = "${var.project_name}-get-matchmaking-status-${var.environment}"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.get_matchmaking_status.output_base64sha256
  runtime          = "nodejs20.x"
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      ENVIRONMENT = var.environment
      LOG_LEVEL   = var.lambda_log_level
    }
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-get-matchmaking-status"
    Environment = var.environment
  })

  depends_on = [
    aws_cloudwatch_log_group.lambda_get_status,
    aws_iam_role_policy.lambda_logs,
    aws_iam_role_policy.lambda_gamelift
  ]
}

# Lambda function: Post Session Summary
resource "aws_lambda_function" "post_session_summary" {
  filename         = data.archive_file.post_session_summary.output_path
  function_name    = "${var.project_name}-post-session-summary-${var.environment}"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.post_session_summary.output_base64sha256
  runtime          = "nodejs20.x"
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      PLAYER_SESSIONS_TABLE = var.player_sessions_table_name
      PLAYER_REWARDS_TABLE  = var.player_rewards_table_name
      ENVIRONMENT           = var.environment
      LOG_LEVEL             = var.lambda_log_level
    }
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-post-session-summary"
    Environment = var.environment
  })

  depends_on = [
    aws_cloudwatch_log_group.lambda_post_summary,
    aws_iam_role_policy.lambda_logs,
    aws_iam_role_policy.lambda_dynamodb
  ]
}

# Lambda permissions for API Gateway
resource "aws_lambda_permission" "start_matchmaking" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.start_matchmaking.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.session_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "get_matchmaking_status" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.get_matchmaking_status.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.session_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "post_session_summary" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.post_session_summary.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.session_api.execution_arn}/*/*"
}
