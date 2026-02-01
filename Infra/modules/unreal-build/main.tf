# Unreal Build EC2 Infrastructure Module
# Provides cloud-based Unreal Engine 5.3 build infrastructure using EC2 g4dn instances

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# S3 bucket for build artifacts
resource "aws_s3_bucket" "build_artifacts" {
  bucket = "${var.project_name}-unreal-build-artifacts-${var.environment}"

  tags = merge(var.tags, {
    Name        = "${var.project_name}-build-artifacts"
    Environment = var.environment
    Purpose     = "Unreal Engine build artifacts storage"
  })
}

# S3 bucket versioning
resource "aws_s3_bucket_versioning" "build_artifacts" {
  bucket = aws_s3_bucket.build_artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

# S3 bucket lifecycle policy (30-day expiration)
resource "aws_s3_bucket_lifecycle_configuration" "build_artifacts" {
  bucket = aws_s3_bucket.build_artifacts.id

  rule {
    id     = "expire-old-builds"
    status = "Enabled"

    filter {
      prefix = ""
    }

    expiration {
      days = 30
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}

# S3 bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "build_artifacts" {
  bucket = aws_s3_bucket.build_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 bucket public access block
resource "aws_s3_bucket_public_access_block" "build_artifacts" {
  bucket = aws_s3_bucket.build_artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# IAM role for EC2 build instances
resource "aws_iam_role" "build_instance" {
  name = "${var.project_name}-unreal-build-instance-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
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
    Name        = "${var.project_name}-build-instance-role"
    Environment = var.environment
  })
}

# IAM policy for S3 artifact upload
resource "aws_iam_role_policy" "build_instance_s3" {
  name = "s3-artifact-upload"
  role = aws_iam_role.build_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.build_artifacts.arn,
          "${aws_s3_bucket.build_artifacts.arn}/*"
        ]
      }
    ]
  })
}

# IAM policy for CloudWatch logs
resource "aws_iam_role_policy" "build_instance_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.build_instance.id

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
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/aws/ec2/unreal-build/*"
      }
    ]
  })
}

# IAM instance profile
resource "aws_iam_instance_profile" "build_instance" {
  name = "${var.project_name}-unreal-build-instance-${var.environment}"
  role = aws_iam_role.build_instance.name

  tags = merge(var.tags, {
    Name        = "${var.project_name}-build-instance-profile"
    Environment = var.environment
  })
}

# Security group for build instances
resource "aws_security_group" "build_instance" {
  name        = "${var.project_name}-unreal-build-${var.environment}"
  description = "Security group for Unreal Engine build instances"
  vpc_id      = var.vpc_id

  # Outbound internet access for downloading dependencies
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-build-instance-sg"
    Environment = var.environment
  })
}

# Launch template for build instances
resource "aws_launch_template" "build_instance" {
  name_prefix   = "${var.project_name}-unreal-build-"
  image_id      = var.ami_id != "" ? var.ami_id : data.aws_ami.unreal_build.id
  instance_type = var.instance_type

  iam_instance_profile {
    arn = aws_iam_instance_profile.build_instance.arn
  }

  vpc_security_group_ids = [aws_security_group.build_instance.id]

  block_device_mappings {
    device_name = "/dev/sda1"

    ebs {
      volume_size           = var.root_volume_size
      volume_type           = "gp3"
      iops                  = 3000
      throughput            = 125
      delete_on_termination = true
      encrypted             = true
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  monitoring {
    enabled = true
  }

  tag_specifications {
    resource_type = "instance"

    tags = merge(var.tags, {
      Name        = "${var.project_name}-unreal-build"
      Environment = var.environment
      Purpose     = "Unreal Engine build"
      ManagedBy   = "UnrealMCP"
    })
  }

  user_data = base64encode(templatefile("${path.module}/user-data.sh", {
    s3_bucket   = aws_s3_bucket.build_artifacts.id
    aws_region  = var.aws_region
    environment = var.environment
  }))

  tags = merge(var.tags, {
    Name        = "${var.project_name}-build-launch-template"
    Environment = var.environment
  })
}

# Data source for latest Unreal build AMI (if custom AMI not provided)
data "aws_ami" "unreal_build" {
  most_recent = true
  owners      = ["self"]

  filter {
    name   = "name"
    values = ["unreal-5.3-build-*"]
  }

  filter {
    name   = "tag:Purpose"
    values = ["UnrealBuild"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

# CloudWatch log group for build logs
resource "aws_cloudwatch_log_group" "build_logs" {
  name              = "/aws/ec2/unreal-build/${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name        = "${var.project_name}-build-logs"
    Environment = var.environment
  })
}
