# GameLift Fleet Terraform Module

This Terraform module provisions an Amazon GameLift fleet for hosting dedicated Unreal Engine VR multiplayer servers.

## Overview

The module creates:
- **GameLift Build**: Server build artifact from S3
- **GameLift Fleet**: Managed fleet of dedicated server instances
- **GameLift Alias**: Routing alias for zero-downtime updates
- **Auto-Scaling**: Target tracking based on fleet utilization
- **IAM Roles**: Permissions for fleet instances
- **CloudWatch Monitoring**: Metrics and alarms for fleet health

## Features

- **Dedicated Server Architecture**: Server-authoritative gameplay
- **Auto-Scaling**: Scales based on player demand (1-3 instances initially)
- **Spot Instance Support**: Up to 70% cost savings
- **Multi-Region**: Support for additional fleet locations
- **Zero-Downtime Updates**: Alias-based routing for seamless updates
- **Monitoring**: CloudWatch metrics and alarms

## Prerequisites

1. **Server Build**: Packaged Unreal Engine dedicated server in S3
2. **S3 Bucket**: Bucket containing server build artifacts
3. **Network Configuration**: Proper inbound port configuration

## Usage

```hcl
module "gamelift_fleet" {
  source = "./modules/gamelift-fleet"

  project_name = "hypermage-vr"
  environment  = "dev"
  aws_region   = "eu-west-1"

  # S3 build configuration
  build_s3_bucket_name = module.unreal_build.s3_bucket_name
  build_s3_bucket_arn  = module.unreal_build.s3_bucket_arn
  server_build_s3_key  = "builds/latest/HyperMageVRServer.zip"

  # Fleet configuration
  fleet_type        = "SPOT"
  ec2_instance_type = "c5.large"

  # Scaling configuration
  enable_auto_scaling = true
  min_fleet_capacity  = 1
  max_fleet_capacity  = 3
  desired_capacity    = 1

  # Server configuration
  server_launch_path = "/local/game/HyperMageVRServer.sh"
  server_parameters  = "-log -port=7777"

  tags = {
    Project = "HyperMage VR"
    Team    = "DevOps"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project_name | Name of the project | string | "hypermage-vr" | no |
| environment | Environment name | string | - | yes |
| aws_region | AWS region | string | "eu-west-1" | no |
| build_s3_bucket_name | S3 bucket with server build | string | - | yes |
| build_s3_bucket_arn | S3 bucket ARN | string | - | yes |
| server_build_s3_key | S3 key for server build | string | "builds/latest/..." | no |
| fleet_type | Fleet type (ON_DEMAND or SPOT) | string | "SPOT" | no |
| ec2_instance_type | EC2 instance type | string | "c5.large" | no |
| concurrent_executions | Server processes per instance | number | 1 | no |
| server_launch_path | Path to server executable | string | "/local/game/..." | no |
| server_parameters | Server command-line parameters | string | "-log" | no |
| enable_auto_scaling | Enable auto-scaling | bool | true | no |
| min_fleet_capacity | Minimum instances | number | 1 | no |
| max_fleet_capacity | Maximum instances | number | 3 | no |
| desired_capacity | Desired instances (manual) | number | 1 | no |
| target_utilization_percentage | Target utilization for scaling | number | 70 | no |
| inbound_permissions | Client connection permissions | list(object) | See below | no |
| fleet_locations | Additional regions | list(string) | [] | no |
| log_retention_days | Log retention days | number | 30 | no |
| alarm_sns_topic_arns | SNS topics for alarms | list(string) | [] | no |
| tags | Additional tags | map(string) | {} | no |

### Default Inbound Permissions

```hcl
[
  {
    from_port = 7777
    to_port   = 7777
    ip_range  = "0.0.0.0/0"
    protocol  = "UDP"
  },
  {
    from_port = 7778
    to_port   = 7778
    ip_range  = "0.0.0.0/0"
    protocol  = "TCP"
  }
]
```

## Outputs

| Name | Description |
|------|-------------|
| fleet_id | GameLift fleet ID |
| fleet_arn | GameLift fleet ARN |
| fleet_name | GameLift fleet name |
| build_id | GameLift build ID |
| alias_id | GameLift alias ID |
| alias_arn | GameLift alias ARN |
| iam_role_arn | IAM role ARN |
| cloudwatch_log_group_name | CloudWatch log group name |

## Server Build Requirements

The server build must be packaged as a ZIP file containing:

```
HyperMageVRServer.zip
├── HyperMageVRServer.sh      # Launch script
├── HyperMageVRServer          # Server executable
├── Engine/                    # Unreal Engine runtime
├── HyperMageVR/              # Game content
└── install.sh                 # GameLift install script
```

### Launch Script Example (HyperMageVRServer.sh)

```bash
#!/bin/bash
./HyperMageVRServer HyperMageVR -log -port=7777
```

### Install Script Example (install.sh)

```bash
#!/bin/bash
# GameLift install script
chmod +x HyperMageVRServer.sh
chmod +x HyperMageVRServer
```

## Capacity Planning

**Per-Shard Requirements:**
- Players: 10-15 per shard
- Instance: 1 c5.large per shard
- Memory: ~4GB per shard
- CPU: ~2 vCPUs per shard

**Initial Deployment (3 shards max):**
- Min capacity: 1 instance
- Max capacity: 3 instances
- Total players: 30-45 concurrent

**Cost Estimates:**
- c5.large on-demand: ~$0.085/hour
- c5.large spot: ~$0.025-0.040/hour (70% savings)
- 3 instances × 24h × $0.035 = ~$2.50/day
- Monthly (continuous): ~$75/month

## Auto-Scaling Behavior

The fleet auto-scales based on utilization:

1. **Scale Out**: When utilization > 70% for 1 minute
   - Adds instances to handle increased load
   - Cooldown: 60 seconds

2. **Scale In**: When utilization < 70% for 5 minutes
   - Removes instances to reduce costs
   - Cooldown: 300 seconds (protects against flapping)

3. **Limits**: Always maintains 1-3 instances

## Monitoring

### CloudWatch Metrics

- `ActiveInstances`: Number of active fleet instances
- `PercentAvailableGameSessions`: Available session capacity
- `ActiveGameSessions`: Number of active game sessions
- `CurrentPlayerSessions`: Number of connected players

### CloudWatch Alarms

1. **Capacity Low**: Alerts when active instances < 1
2. **Utilization High**: Alerts when utilization > 80%

## Multi-Region Deployment

To deploy fleet to multiple regions:

```hcl
module "gamelift_fleet" {
  # ... other configuration

  fleet_locations = [
    "us-west-2",
    "ap-southeast-1"
  ]
}
```

## Zero-Downtime Updates

To update server build without downtime:

1. Upload new build to S3
2. Update `server_build_s3_key` variable
3. Run `terraform apply`
4. GameLift creates new fleet with new build
5. Alias routes traffic to new fleet
6. Old fleet drains and terminates

## Troubleshooting

**Fleet stuck in "Activating" state:**
- Check server build is valid and executable
- Verify install.sh runs successfully
- Check CloudWatch logs for server errors

**Players cannot connect:**
- Verify inbound_permissions are correct
- Check security group allows UDP/TCP traffic
- Ensure server is listening on correct port

**High costs:**
- Enable spot instances (`fleet_type = "SPOT"`)
- Reduce max_fleet_capacity
- Implement auto-scaling to scale down during low usage

**Auto-scaling not working:**
- Verify enable_auto_scaling = true
- Check CloudWatch metrics are being reported
- Adjust target_utilization_percentage if needed

## Security Best Practices

- **Least Privilege**: IAM roles grant minimal permissions
- **Network Isolation**: Use VPC for fleet instances (GameLift managed)
- **Encryption**: All data encrypted in transit
- **Audit Logging**: CloudTrail enabled for API calls
- **DDoS Protection**: AWS Shield Standard included

## Integration with Matchmaking

This fleet integrates with FlexMatch (Task 15.2):

```hcl
# In FlexMatch configuration
game_session_queue_arns = [
  aws_gamelift_game_session_queue.main.arn
]

# Queue references this fleet
resource "aws_gamelift_game_session_queue" "main" {
  destinations {
    destination_arn = module.gamelift_fleet.fleet_arn
  }
}
```

## Next Steps

After deploying the GameLift fleet:

1. Upload server build to S3
2. Test fleet activation and server startup
3. Configure FlexMatch for matchmaking (Task 15.2)
4. Integrate with Cognito for authentication (Task 15.3)
5. Set up monitoring and alerting

## Support

For issues or questions:
- Check GameLift fleet events in AWS Console
- Review CloudWatch logs for server errors
- Consult AWS GameLift documentation
- Check Unreal Engine GameLift plugin documentation
