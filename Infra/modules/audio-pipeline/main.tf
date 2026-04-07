# Audio Pipeline Module
# Provisions the DynamoDB table for audio asset tracking and SSM parameter
# stubs for API keys (ElevenLabs SFX/TTS, Stability AI ambient/score).
#
# Audio generation happens inside the TechArtVFXAudioAgent container — no
# Lambda or ECS needed. Zero idle cost: DynamoDB on-demand + API calls only.
#
# SSM keys: set these manually before running the end-to-end test:
#   aws ssm put-parameter --name /hypermage/elevenlabs-api-key --value YOUR_KEY --type SecureString
#   aws ssm put-parameter --name /hypermage/stability-api-key  --value YOUR_KEY --type SecureString
# Agent skips gracefully if keys are absent.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ── DynamoDB: Audio Assets Catalogue ─────────────────────────────────────────

resource "aws_dynamodb_table" "audio_assets" {
  name         = "${var.project_name}-audio-assets-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "audioId"

  attribute {
    name = "audioId"
    type = "S"
  }

  attribute {
    name = "sceneId"
    type = "S"
  }

  attribute {
    name = "audioType"
    type = "S"
  }

  # Query all audio assets for a given scene
  global_secondary_index {
    name            = "SceneIdIndex"
    hash_key        = "sceneId"
    projection_type = "ALL"
  }

  # Query by audio type (ambient/score/sfx/narration)
  global_secondary_index {
    name            = "AudioTypeIndex"
    hash_key        = "audioType"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled = true
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-audio-assets"
    Environment = var.environment
  })
}

# ── SSM: API key placeholders ─────────────────────────────────────────────────
# Created as String type with placeholder value so the path exists.
# Overwrite with SecureString + real key value before using audio generation.

resource "aws_ssm_parameter" "elevenlabs_key_placeholder" {
  name  = var.elevenlabs_api_key_ssm_path
  type  = "String"
  value = "NOT_SET"

  # Do not overwrite if it already has a real value
  lifecycle {
    ignore_changes = [value]
  }

  tags = merge(var.tags, { Environment = var.environment })
}

resource "aws_ssm_parameter" "stability_key_placeholder" {
  name  = var.stability_api_key_ssm_path
  type  = "String"
  value = "NOT_SET"

  lifecycle {
    ignore_changes = [value]
  }

  tags = merge(var.tags, { Environment = var.environment })
}
