# Asset Pipeline Module
# Provisions the S3-triggered ingestion pipeline, format converters, and asset catalogue.
#
# Flow: S3 incoming/ upload → asset-ingest-trigger Lambda → routes by extension:
#   Images (PNG/JPG/PSD) → image-processor Lambda     → WebP output + provenance in DynamoDB
#   Meshes (FBX/OBJ)     → ECS Fargate Blender task   → glTF output + provenance in DynamoDB
#   Concept art          → meshy-3d Lambda (Meshy API) → glTF output + provenance in DynamoDB
#
# Cost-safety: all resources are serverless/on-demand. ECS tasks terminate on completion.
# No idle compute cost. GameLift fleet untouched (stays at DESIRED=0).

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

# ── DynamoDB: Asset Catalogue ─────────────────────────────────────────────────

resource "aws_dynamodb_table" "asset_catalogue" {
  name         = "${var.project_name}-asset-catalogue-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "assetId"

  attribute {
    name = "assetId"
    type = "S"
  }

  attribute {
    name = "assetType"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  global_secondary_index {
    name            = "AssetTypeIndex"
    hash_key        = "assetType"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "StatusIndex"
    hash_key        = "status"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled = true
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-asset-catalogue"
    Environment = var.environment
  })
}

# ── IAM: Lambda execution role ────────────────────────────────────────────────

resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-asset-pipeline-lambda-${var.environment}"

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

resource "aws_iam_role_policy" "lambda_logs" {
  name = "lambda-logs"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "arn:aws:logs:*:*:*"
    }]
  })
}

resource "aws_iam_role_policy" "lambda_s3" {
  name = "lambda-s3"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:GetObject", "s3:PutObject", "s3:HeadObject"]
      Resource = "${var.build_s3_bucket_arn}/*"
    }]
  })
}

resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "lambda-dynamodb"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
        "dynamodb:Query", "dynamodb:Scan"
      ]
      Resource = [
        aws_dynamodb_table.asset_catalogue.arn,
        "${aws_dynamodb_table.asset_catalogue.arn}/index/*"
      ]
    }]
  })
}

resource "aws_iam_role_policy" "lambda_ecs" {
  name = "lambda-ecs-run-task"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecs:RunTask", "ecs:DescribeTasks"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = [aws_iam_role.ecs_task_execution.arn, aws_iam_role.ecs_task.arn]
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_lambda_invoke" {
  name = "lambda-invoke-sibling"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = [
        aws_lambda_function.image_processor.arn,
        aws_lambda_function.meshy_3d.arn,
      ]
    }]
  })
}

resource "aws_iam_role_policy" "lambda_ssm" {
  name = "lambda-ssm-meshy-key"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameter"]
      Resource = "arn:aws:ssm:${var.aws_region}:*:parameter${var.meshy_api_key_ssm_path}"
    }]
  })
}

# ── IAM: ECS execution and task roles ────────────────────────────────────────

resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-blender-task-exec-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  name = "${var.project_name}-blender-task-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "ecs-task-s3"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject"]
      Resource = "${var.build_s3_bucket_arn}/*"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_dynamodb" {
  name = "ecs-task-dynamodb"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"]
      Resource = aws_dynamodb_table.asset_catalogue.arn
    }]
  })
}

# ── Lambda: asset-ingest-trigger ─────────────────────────────────────────────

data "archive_file" "asset_ingest_trigger" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/asset-ingest-trigger"
  output_path = "${path.module}/lambda/dist/asset-ingest-trigger.zip"
}

resource "aws_cloudwatch_log_group" "asset_ingest_trigger" {
  name              = "/aws/lambda/${var.project_name}-asset-ingest-trigger-${var.environment}"
  retention_in_days = var.log_retention_days
  tags              = merge(var.tags, { Environment = var.environment })
}

resource "aws_lambda_function" "asset_ingest_trigger" {
  filename         = data.archive_file.asset_ingest_trigger.output_path
  function_name    = "${var.project_name}-asset-ingest-trigger-${var.environment}"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.asset_ingest_trigger.output_base64sha256
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 256

  environment {
    variables = {
      ASSET_CATALOGUE_TABLE = aws_dynamodb_table.asset_catalogue.name
      S3_BUCKET             = var.build_s3_bucket_name
      IMAGE_PROCESSOR_ARN   = aws_lambda_function.image_processor.arn
      MESHY_3D_ARN          = aws_lambda_function.meshy_3d.arn
      ECS_CLUSTER_ARN       = aws_ecs_cluster.blender.arn
      ECS_TASK_DEF_ARN      = aws_ecs_task_definition.blender_converter.arn
      ECS_TASK_ROLE_ARN     = aws_iam_role.ecs_task.arn
      ECS_EXEC_ROLE_ARN     = aws_iam_role.ecs_task_execution.arn
      AWS_REGION_NAME       = var.aws_region
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.asset_ingest_trigger,
    aws_iam_role_policy.lambda_logs,
    aws_iam_role_policy.lambda_s3,
    aws_iam_role_policy.lambda_dynamodb,
    aws_iam_role_policy.lambda_ecs,
    aws_iam_role_policy.lambda_lambda_invoke,
  ]

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_lambda_permission" "s3_invoke_ingest_trigger" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.asset_ingest_trigger.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = var.build_s3_bucket_arn
}

# ── Lambda: image-processor ───────────────────────────────────────────────────

data "archive_file" "image_processor" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/image-processor"
  output_path = "${path.module}/lambda/dist/image-processor.zip"
}

resource "aws_cloudwatch_log_group" "image_processor" {
  name              = "/aws/lambda/${var.project_name}-image-processor-${var.environment}"
  retention_in_days = var.log_retention_days
  tags              = merge(var.tags, { Environment = var.environment })
}

resource "aws_lambda_function" "image_processor" {
  filename         = data.archive_file.image_processor.output_path
  function_name    = "${var.project_name}-image-processor-${var.environment}"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.image_processor.output_base64sha256
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 512

  environment {
    variables = {
      ASSET_CATALOGUE_TABLE = aws_dynamodb_table.asset_catalogue.name
      S3_BUCKET             = var.build_s3_bucket_name
      AWS_REGION_NAME       = var.aws_region
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.image_processor,
    aws_iam_role_policy.lambda_logs,
    aws_iam_role_policy.lambda_s3,
    aws_iam_role_policy.lambda_dynamodb,
  ]

  tags = merge(var.tags, { Environment = var.environment })
}

# ── Lambda: meshy-3d ──────────────────────────────────────────────────────────

data "archive_file" "meshy_3d" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/meshy-3d"
  output_path = "${path.module}/lambda/dist/meshy-3d.zip"
}

resource "aws_cloudwatch_log_group" "meshy_3d" {
  name              = "/aws/lambda/${var.project_name}-meshy-3d-${var.environment}"
  retention_in_days = var.log_retention_days
  tags              = merge(var.tags, { Environment = var.environment })
}

resource "aws_lambda_function" "meshy_3d" {
  filename         = data.archive_file.meshy_3d.output_path
  function_name    = "${var.project_name}-meshy-3d-${var.environment}"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.lambda_handler"
  source_code_hash = data.archive_file.meshy_3d.output_base64sha256
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 256

  environment {
    variables = {
      ASSET_CATALOGUE_TABLE  = aws_dynamodb_table.asset_catalogue.name
      S3_BUCKET              = var.build_s3_bucket_name
      MESHY_API_KEY_SSM_PATH = var.meshy_api_key_ssm_path
      AWS_REGION_NAME        = var.aws_region
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.meshy_3d,
    aws_iam_role_policy.lambda_logs,
    aws_iam_role_policy.lambda_s3,
    aws_iam_role_policy.lambda_dynamodb,
    aws_iam_role_policy.lambda_ssm,
  ]

  tags = merge(var.tags, { Environment = var.environment })
}

# ── ECS: Blender FBX/OBJ → glTF converter ────────────────────────────────────
# Fargate tasks run to completion and exit — zero idle cost.

resource "aws_ecs_cluster" "blender" {
  name = "${var.project_name}-blender-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_cloudwatch_log_group" "blender_converter" {
  name              = "/ecs/${var.project_name}-blender-converter-${var.environment}"
  retention_in_days = var.log_retention_days
  tags              = merge(var.tags, { Environment = var.environment })
}

resource "aws_ecs_task_definition" "blender_converter" {
  family                   = "${var.project_name}-blender-converter-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "2048"
  memory                   = "4096"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "blender-converter"
    image     = var.blender_image_uri
    essential = true

    environment = [
      { name = "ASSET_CATALOGUE_TABLE", value = aws_dynamodb_table.asset_catalogue.name },
      { name = "S3_BUCKET",             value = var.build_s3_bucket_name },
      { name = "AWS_DEFAULT_REGION",    value = var.aws_region },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.blender_converter.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "blender"
      }
    }
  }])

  tags = merge(var.tags, { Environment = var.environment })
}

# ── S3 bucket notification: incoming/ prefix ──────────────────────────────────

resource "aws_s3_bucket_notification" "asset_ingest" {
  bucket = var.build_s3_bucket_name

  lambda_function {
    lambda_function_arn = aws_lambda_function.asset_ingest_trigger.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "assets/incoming/"
  }

  depends_on = [aws_lambda_permission.s3_invoke_ingest_trigger]
}
