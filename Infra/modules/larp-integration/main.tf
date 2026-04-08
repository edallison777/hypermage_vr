# LARP Integration Module (Phase 11b)
# GM Event API: POST /gm/event → Lambda → DynamoDB state update + WebSocket broadcast
#
# Cost profile:
#   Lambda       — pay per invocation, free tier covers dev load
#   API GW HTTP  — $1/million requests, zero idle cost
#   All serverless — zero idle compute cost

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
  name_prefix = "${var.project_name}-larp-${var.environment}"
}

# ── IAM — Lambda execution role ───────────────────────────────────────────────

resource "aws_iam_role" "gm_event_lambda" {
  name = "${local.name_prefix}-gm-event-lambda"

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

resource "aws_iam_role_policy" "gm_event_lambda" {
  name = "${local.name_prefix}-gm-event-lambda-policy"
  role = aws_iam_role.gm_event_lambda.id

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
        Sid    = "WebScenesDynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:*:table/${var.web_scenes_table_name}"
      },
      {
        Sid    = "ConnectionsDynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          "arn:aws:dynamodb:${var.aws_region}:*:table/${var.ws_connections_table_name}",
          "arn:aws:dynamodb:${var.aws_region}:*:table/${var.ws_connections_table_name}/index/*"
        ]
      },
      {
        Sid      = "S3ScenePlanRead"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "arn:aws:s3:::${var.build_s3_bucket}/*"
      },
      {
        Sid    = "WSManagement"
        Effect = "Allow"
        Action = ["execute-api:ManageConnections"]
        Resource = "arn:aws:execute-api:${var.aws_region}:*:*/*/@connections/*"
      }
    ]
  })
}

# ── Lambda — GM Event handler ──────────────────────────────────────────────────

data "archive_file" "gm_event" {
  type        = "zip"
  source_file = "${path.module}/lambda/gm-event/handler.py"
  output_path = "${path.module}/lambda/gm-event.zip"
}

resource "aws_lambda_function" "gm_event" {
  function_name    = "${local.name_prefix}-gm-event"
  role             = aws_iam_role.gm_event_lambda.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.gm_event.output_path
  source_code_hash = data.archive_file.gm_event.output_base64sha256
  timeout          = 15

  environment {
    variables = {
      WEB_SCENES_TABLE   = var.web_scenes_table_name
      CONNECTIONS_TABLE  = var.ws_connections_table_name
      WS_ENDPOINT        = replace(var.ws_invoke_url, "wss://", "https://")
      BUILD_S3_BUCKET    = var.build_s3_bucket
    }
  }

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_cloudwatch_log_group" "gm_event" {
  name              = "/aws/lambda/${aws_lambda_function.gm_event.function_name}"
  retention_in_days = var.log_retention_days
}

# ── API Gateway HTTP API ───────────────────────────────────────────────────────

resource "aws_apigatewayv2_api" "gm" {
  name          = "${local.name_prefix}-gm-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
    max_age       = 300
  }

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_apigatewayv2_integration" "gm_event" {
  api_id                 = aws_apigatewayv2_api.gm.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.gm_event.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "gm_event" {
  api_id    = aws_apigatewayv2_api.gm.id
  route_key = "POST /gm/event"
  target    = "integrations/${aws_apigatewayv2_integration.gm_event.id}"
}

resource "aws_apigatewayv2_stage" "gm" {
  api_id      = aws_apigatewayv2_api.gm.id
  name        = var.environment
  auto_deploy = true

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_lambda_permission" "gm_event" {
  statement_id  = "AllowAPIGWGMEvent"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.gm_event.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.gm.execution_arn}/*/*"
}

# ── SSM — store GM event URL + WS management endpoint ─────────────────────────

resource "aws_ssm_parameter" "gm_event_url" {
  name  = "/hypermage/larp/gm-event-url"
  type  = "String"
  value = "${aws_apigatewayv2_stage.gm.invoke_url}/gm/event"

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_ssm_parameter" "ws_management_endpoint" {
  name  = "/hypermage/larp/ws-management-endpoint"
  type  = "String"
  value = replace(var.ws_invoke_url, "wss://", "https://")

  tags = merge(var.tags, { Environment = var.environment })
}
