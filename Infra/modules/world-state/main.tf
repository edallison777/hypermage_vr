# World State Module (Phase 20)
# Persistent interactable-object state: GET /world-state/{object_id} + POST /world-state
#
# Cost profile:
#   DynamoDB     — PAY_PER_REQUEST, zero idle cost
#   Lambda       — pay per invocation, free tier covers dev load
#   API GW HTTP  — $1/million requests, zero idle cost

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

locals {
  name_prefix = "${var.project_name}-world-state-${var.environment}"
}

# ── DynamoDB — world state table ──────────────────────────────────────────────

resource "aws_dynamodb_table" "world_state" {
  name         = local.name_prefix
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "object_id"

  attribute {
    name = "object_id"
    type = "S"
  }

  tags = merge(var.tags, { Environment = var.environment })
}

# ── IAM — Lambda execution role ───────────────────────────────────────────────

resource "aws_iam_role" "world_state_lambda" {
  name = "${local.name_prefix}-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_iam_role_policy" "world_state_lambda" {
  name = "${local.name_prefix}-lambda-policy"
  role = aws_iam_role.world_state_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Logs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Sid    = "WorldStateDynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem"
        ]
        Resource = aws_dynamodb_table.world_state.arn
      }
    ]
  })
}

# ── Lambda ─────────────────────────────────────────────────────────────────────

data "archive_file" "world_state" {
  type        = "zip"
  source_file = "${path.module}/lambda/world-state/handler.py"
  output_path = "${path.module}/lambda/world-state.zip"
}

resource "aws_lambda_function" "world_state" {
  function_name    = local.name_prefix
  role             = aws_iam_role.world_state_lambda.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.world_state.output_path
  source_code_hash = data.archive_file.world_state.output_base64sha256
  timeout          = 10

  environment {
    variables = {
      WORLD_STATE_TABLE = aws_dynamodb_table.world_state.name
    }
  }

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_cloudwatch_log_group" "world_state" {
  name              = "/aws/lambda/${aws_lambda_function.world_state.function_name}"
  retention_in_days = var.log_retention_days
}

# ── API Gateway HTTP API ───────────────────────────────────────────────────────

resource "aws_apigatewayv2_api" "world_state" {
  name          = "${local.name_prefix}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Content-Type"]
    max_age       = 300
  }

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_apigatewayv2_integration" "world_state" {
  api_id                 = aws_apigatewayv2_api.world_state.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.world_state.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_world_state" {
  api_id    = aws_apigatewayv2_api.world_state.id
  route_key = "GET /world-state/{object_id}"
  target    = "integrations/${aws_apigatewayv2_integration.world_state.id}"
}

resource "aws_apigatewayv2_route" "post_world_state" {
  api_id    = aws_apigatewayv2_api.world_state.id
  route_key = "POST /world-state"
  target    = "integrations/${aws_apigatewayv2_integration.world_state.id}"
}

resource "aws_apigatewayv2_stage" "world_state" {
  api_id      = aws_apigatewayv2_api.world_state.id
  name        = var.environment
  auto_deploy = true

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_lambda_permission" "world_state" {
  statement_id  = "AllowAPIGWWorldState"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.world_state.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.world_state.execution_arn}/*/*"
}

# ── SSM — store base URL for GameMode to read ─────────────────────────────────

resource "aws_ssm_parameter" "world_state_api_url" {
  name  = "/hypermage/world-state/api-url"
  type  = "String"
  value = aws_apigatewayv2_stage.world_state.invoke_url

  tags = merge(var.tags, { Environment = var.environment })
}
