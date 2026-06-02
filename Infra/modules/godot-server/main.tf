# Godot Dedicated Server Module (G5)
# On-demand ECS Fargate tasks for Godot multiplayer game sessions.
# Each match spawns one task; task exits when all players disconnect.
# Cost-safety: zero idle cost (RunTask model, no persistent service).

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ── ECR ───────────────────────────────────────────────────────────────────────

resource "aws_ecr_repository" "godot_server" {
  name                 = "${var.project_name}-godot-server-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = false
  }

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_ecr_lifecycle_policy" "godot_server" {
  repository = aws_ecr_repository.godot_server.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

# ── DynamoDB: matchmaking tickets ─────────────────────────────────────────────

resource "aws_dynamodb_table" "matchmaking_tickets" {
  name         = "${var.project_name}-matchmaking-tickets-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "ticketId"

  attribute {
    name = "ticketId"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-matchmaking-tickets"
    Environment = var.environment
  })
}

# ── Networking ────────────────────────────────────────────────────────────────

data "aws_vpc" "default" { default = true }

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "godot_server" {
  name        = "${var.project_name}-godot-server-${var.environment}"
  description = "Godot game server: UDP/TCP ${var.server_port} inbound"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "Game traffic UDP"
    from_port   = var.server_port
    to_port     = var.server_port
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Game traffic TCP"
    from_port   = var.server_port
    to_port     = var.server_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-godot-server-sg"
    Environment = var.environment
  })
}

# ── IAM ───────────────────────────────────────────────────────────────────────

resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-godot-task-exec-${var.environment}"

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
  name = "${var.project_name}-godot-task-${var.environment}"

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

# ── ECS ───────────────────────────────────────────────────────────────────────

resource "aws_ecs_cluster" "godot" {
  name = "${var.project_name}-godot-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_cloudwatch_log_group" "godot_server" {
  name              = "/ecs/${var.project_name}-godot-server-${var.environment}"
  retention_in_days = var.log_retention_days
  tags              = merge(var.tags, { Environment = var.environment })
}

resource "aws_ecs_task_definition" "godot_server" {
  family                   = "${var.project_name}-godot-server-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "godot-server"
    image     = "${aws_ecr_repository.godot_server.repository_url}:${var.image_tag}"
    essential = true

    portMappings = [
      { containerPort = var.server_port, protocol = "udp" },
      { containerPort = var.server_port, protocol = "tcp" }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.godot_server.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "server"
      }
    }
  }])

  tags = merge(var.tags, { Environment = var.environment })
}
