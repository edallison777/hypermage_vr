# WebPlatform Module (Phase 10)
# S3 static site + CloudFront + DynamoDB scene catalogue
# + API Gateway WebSocket API for participant presence
#
# Cost profile:
#   S3 storage    — ~$0.023/GB/month (scenes are small HTML files)
#   CloudFront    — no idle cost, pay per request
#   DynamoDB      — PAY_PER_REQUEST, zero idle cost
#   API GW WS     — $0.00025/min per active connection, $1/million messages
#   Lambda        — pay per invocation, free tier covers dev load
#
# All resources are serverless — zero idle compute cost.

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
  bucket_name = var.web_scenes_bucket_name != "" ? var.web_scenes_bucket_name : "${var.project_name}-web-scenes-${var.environment}"
  name_prefix = "${var.project_name}-web-${var.environment}"
}

# ── S3 bucket for static web scenes ───────────────────────────────────────────

resource "aws_s3_bucket" "web_scenes" {
  bucket = local.bucket_name

  tags = merge(var.tags, {
    Environment = var.environment
    Purpose     = "Web scene static assets"
  })
}

resource "aws_s3_bucket_versioning" "web_scenes" {
  bucket = aws_s3_bucket.web_scenes.id
  versioning_configuration {
    status = "Suspended"
  }
}

resource "aws_s3_bucket_public_access_block" "web_scenes" {
  bucket = aws_s3_bucket.web_scenes.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# CloudFront Origin Access Control
resource "aws_cloudfront_origin_access_control" "web_scenes" {
  name                              = "${local.name_prefix}-oac"
  description                       = "OAC for Hypermage web scenes bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Allow CloudFront to read S3
resource "aws_s3_bucket_policy" "web_scenes" {
  bucket = aws_s3_bucket.web_scenes.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AllowCloudFrontServicePrincipal"
      Effect = "Allow"
      Principal = {
        Service = "cloudfront.amazonaws.com"
      }
      Action   = "s3:GetObject"
      Resource = "${aws_s3_bucket.web_scenes.arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.web_scenes.arn
        }
      }
    }]
  })

  depends_on = [aws_cloudfront_distribution.web_scenes]
}

# ── CloudFront distribution ────────────────────────────────────────────────────

resource "aws_cloudfront_distribution" "web_scenes" {
  enabled             = true
  comment             = "Hypermage VR web scenes (${var.environment})"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"  # US + EU only — cheapest tier

  origin {
    domain_name              = aws_s3_bucket.web_scenes.bucket_regional_domain_name
    origin_id                = "s3-web-scenes"
    origin_access_control_id = aws_cloudfront_origin_access_control.web_scenes.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-web-scenes"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = merge(var.tags, { Environment = var.environment })
}

# ── DynamoDB — web scene deployments catalogue ─────────────────────────────────

resource "aws_dynamodb_table" "web_scenes" {
  name         = "hypermage-vr-web-scenes-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "sceneId"

  attribute {
    name = "sceneId"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "deployedAt"
    type = "S"
  }

  global_secondary_index {
    name            = "StatusDeployedAtIndex"
    hash_key        = "status"
    range_key       = "deployedAt"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = merge(var.tags, { Environment = var.environment })
}

# ── DynamoDB — WebSocket connections (ephemeral, short TTL) ───────────────────

resource "aws_dynamodb_table" "ws_connections" {
  name         = "hypermage-vr-ws-connections-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "connectionId"

  attribute {
    name = "connectionId"
    type = "S"
  }

  attribute {
    name = "sceneId"
    type = "S"
  }

  global_secondary_index {
    name            = "SceneIdIndex"
    hash_key        = "sceneId"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = merge(var.tags, { Environment = var.environment })
}

# ── IAM — Lambda execution role for WebSocket handlers ────────────────────────

resource "aws_iam_role" "ws_lambda" {
  name = "${local.name_prefix}-ws-lambda"

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

resource "aws_iam_role_policy" "ws_lambda" {
  name = "${local.name_prefix}-ws-lambda-policy"
  role = aws_iam_role.ws_lambda.id

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
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.ws_connections.arn,
          "${aws_dynamodb_table.ws_connections.arn}/index/*",
          aws_dynamodb_table.web_scenes.arn,
          "${aws_dynamodb_table.web_scenes.arn}/index/*"
        ]
      },
      {
        Sid    = "APIGatewayManage"
        Effect = "Allow"
        Action = ["execute-api:ManageConnections"]
        Resource = "${aws_apigatewayv2_api.ws.execution_arn}/*"
      }
    ]
  })
}

# ── Lambda — WebSocket connect ─────────────────────────────────────────────────

data "archive_file" "ws_connect" {
  type        = "zip"
  source_file = "${path.module}/lambda/ws-connect/handler.py"
  output_path = "${path.module}/lambda/ws-connect.zip"
}

resource "aws_lambda_function" "ws_connect" {
  function_name    = "${local.name_prefix}-ws-connect"
  role             = aws_iam_role.ws_lambda.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.ws_connect.output_path
  source_code_hash = data.archive_file.ws_connect.output_base64sha256
  timeout          = 10

  environment {
    variables = {
      CONNECTIONS_TABLE = aws_dynamodb_table.ws_connections.name
    }
  }

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_cloudwatch_log_group" "ws_connect" {
  name              = "/aws/lambda/${aws_lambda_function.ws_connect.function_name}"
  retention_in_days = var.log_retention_days
}

# ── Lambda — WebSocket disconnect ──────────────────────────────────────────────

data "archive_file" "ws_disconnect" {
  type        = "zip"
  source_file = "${path.module}/lambda/ws-disconnect/handler.py"
  output_path = "${path.module}/lambda/ws-disconnect.zip"
}

resource "aws_lambda_function" "ws_disconnect" {
  function_name    = "${local.name_prefix}-ws-disconnect"
  role             = aws_iam_role.ws_lambda.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.ws_disconnect.output_path
  source_code_hash = data.archive_file.ws_disconnect.output_base64sha256
  timeout          = 10

  environment {
    variables = {
      CONNECTIONS_TABLE = aws_dynamodb_table.ws_connections.name
    }
  }

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_cloudwatch_log_group" "ws_disconnect" {
  name              = "/aws/lambda/${aws_lambda_function.ws_disconnect.function_name}"
  retention_in_days = var.log_retention_days
}

# ── Lambda — WebSocket message ─────────────────────────────────────────────────

data "archive_file" "ws_message" {
  type        = "zip"
  source_file = "${path.module}/lambda/ws-message/handler.py"
  output_path = "${path.module}/lambda/ws-message.zip"
}

resource "aws_lambda_function" "ws_message" {
  function_name    = "${local.name_prefix}-ws-message"
  role             = aws_iam_role.ws_lambda.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.ws_message.output_path
  source_code_hash = data.archive_file.ws_message.output_base64sha256
  timeout          = 10

  environment {
    variables = {
      CONNECTIONS_TABLE = aws_dynamodb_table.ws_connections.name
      WEB_SCENES_TABLE  = aws_dynamodb_table.web_scenes.name
    }
  }

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_cloudwatch_log_group" "ws_message" {
  name              = "/aws/lambda/${aws_lambda_function.ws_message.function_name}"
  retention_in_days = var.log_retention_days
}

# ── API Gateway WebSocket API ──────────────────────────────────────────────────

resource "aws_apigatewayv2_api" "ws" {
  name                       = "${local.name_prefix}-ws"
  protocol_type              = "WEBSOCKET"
  route_selection_expression = "$request.body.action"

  tags = merge(var.tags, { Environment = var.environment })
}

# Connect route
resource "aws_apigatewayv2_integration" "ws_connect" {
  api_id           = aws_apigatewayv2_api.ws.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.ws_connect.invoke_arn
}

resource "aws_apigatewayv2_route" "ws_connect" {
  api_id    = aws_apigatewayv2_api.ws.id
  route_key = "$connect"
  target    = "integrations/${aws_apigatewayv2_integration.ws_connect.id}"
}

resource "aws_lambda_permission" "ws_connect" {
  statement_id  = "AllowAPIGWConnect"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ws_connect.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ws.execution_arn}/*/*"
}

# Disconnect route
resource "aws_apigatewayv2_integration" "ws_disconnect" {
  api_id           = aws_apigatewayv2_api.ws.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.ws_disconnect.invoke_arn
}

resource "aws_apigatewayv2_route" "ws_disconnect" {
  api_id    = aws_apigatewayv2_api.ws.id
  route_key = "$disconnect"
  target    = "integrations/${aws_apigatewayv2_integration.ws_disconnect.id}"
}

resource "aws_lambda_permission" "ws_disconnect" {
  statement_id  = "AllowAPIGWDisconnect"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ws_disconnect.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ws.execution_arn}/*/*"
}

# Message/default route
resource "aws_apigatewayv2_integration" "ws_message" {
  api_id           = aws_apigatewayv2_api.ws.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.ws_message.invoke_arn
}

resource "aws_apigatewayv2_route" "ws_default" {
  api_id    = aws_apigatewayv2_api.ws.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.ws_message.id}"
}

resource "aws_lambda_permission" "ws_message" {
  statement_id  = "AllowAPIGWMessage"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ws_message.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ws.execution_arn}/*/*"
}

# Deploy the WebSocket API
resource "aws_apigatewayv2_stage" "ws" {
  api_id      = aws_apigatewayv2_api.ws.id
  name        = var.environment
  auto_deploy = true

  tags = merge(var.tags, { Environment = var.environment })
}

# ── SSM — store CloudFront domain + WS URL for agent use ──────────────────────

resource "aws_ssm_parameter" "cloudfront_domain" {
  name  = "/hypermage/web-platform/cloudfront-domain"
  type  = "String"
  value = aws_cloudfront_distribution.web_scenes.domain_name

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_ssm_parameter" "ws_url" {
  name  = "/hypermage/web-platform/ws-url"
  type  = "String"
  value = "${aws_apigatewayv2_stage.ws.invoke_url}"

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_ssm_parameter" "web_scenes_bucket" {
  name  = "/hypermage/web-platform/scenes-bucket"
  type  = "String"
  value = aws_s3_bucket.web_scenes.bucket

  tags = merge(var.tags, { Environment = var.environment })
}
