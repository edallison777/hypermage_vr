# UnrealBridge Module (Phase 9)
# Creates an SSM Parameter placeholder for the bridge URL.
# The bridge itself runs on the dev PC — no cloud compute, zero idle cost.
#
# To enable: run scripts/unreal-bridge/start.sh --ngrok on the dev PC.
# The start script auto-updates this parameter with the ngrok URL.
# Or set manually:
#   aws ssm put-parameter --name /hypermage/unreal-bridge-url \
#       --value https://YOUR.ngrok.io --type String --overwrite --region eu-west-1

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_ssm_parameter" "bridge_url" {
  name  = var.bridge_url_ssm_path
  type  = "String"
  value = "NOT_SET"

  lifecycle {
    ignore_changes = [value]  # preserve manually set ngrok URLs
  }

  tags = merge(var.tags, { Environment = var.environment })
}
