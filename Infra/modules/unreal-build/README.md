# Unreal Build EC2 Infrastructure Module

This Terraform module provisions cloud-based infrastructure for building Unreal Engine 5.3 projects on AWS EC2 instances.

## Overview

The module creates:
- **S3 Bucket**: Storage for build artifacts with 30-day lifecycle policy
- **EC2 Launch Template**: Configuration for g4dn.xlarge build instances
- **IAM Roles**: Permissions for S3 upload and CloudWatch logging
- **Security Group**: Network access for build instances
- **CloudWatch Logs**: Centralized logging for build operations

## Features

- **Cloud-Based Builds**: No local UE5.3 installation required
- **Spot Instance Support**: Cost optimization through spot instances
- **Automatic Cleanup**: Build artifacts expire after 30 days
- **Secure by Default**: Encrypted storage, IMDSv2, private S3 bucket
- **Cost Tracking**: CloudWatch metrics for build duration and costs

## Prerequisites

1. **Custom AMI**: Pre-configured AMI with:
   - Unreal Engine 5.3+
   - Android SDK for Quest 3 builds
   - GameLift SDK
   - Build tools (CMake, Visual Studio Build Tools, etc.)

2. **VPC**: Existing VPC with internet gateway for dependency downloads

3. **AWS Credentials**: Appropriate permissions to create EC2, S3, IAM resources

## Usage

```hcl
module "unreal_build" {
  source = "./modules/unreal-build"

  project_name = "hypermage-vr"
  environment  = "dev"
  aws_region   = "eu-west-1"
  vpc_id       = "vpc-xxxxx"

  # Optional: Use custom AMI
  ami_id = "ami-xxxxx"

  # Optional: Enable spot instances for cost savings
  enable_spot_instances = true
  spot_max_price        = "0.50"

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
| environment | Environment name (dev, staging, prod) | string | - | yes |
| aws_region | AWS region for resources | string | "eu-west-1" | no |
| vpc_id | VPC ID for build instances | string | - | yes |
| instance_type | EC2 instance type | string | "g4dn.xlarge" | no |
| ami_id | Custom AMI ID (leave empty to use latest) | string | "" | no |
| root_volume_size | Root volume size in GB | number | 150 | no |
| enable_spot_instances | Enable spot instances | bool | true | no |
| spot_max_price | Maximum spot price per hour | string | "" | no |
| log_retention_days | CloudWatch log retention in days | number | 30 | no |
| tags | Additional tags for resources | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| s3_bucket_name | Name of the S3 bucket for build artifacts |
| s3_bucket_arn | ARN of the S3 bucket |
| launch_template_id | ID of the launch template |
| iam_instance_profile_arn | ARN of the IAM instance profile |
| security_group_id | ID of the security group |
| cloudwatch_log_group_name | Name of the CloudWatch log group |

## Build Workflow

The UnrealMCP adapter uses this infrastructure as follows:

1. **Launch Instance**: Create EC2 instance from launch template
2. **Clone Repository**: Clone project repository to instance
3. **Execute Build**: Run UE5 build commands (compile, cook, package)
4. **Upload Artifacts**: Upload build artifacts to S3 bucket
5. **Terminate Instance**: Terminate instance to minimize costs
6. **Return URLs**: Return S3 URLs to calling agent

## Cost Optimization

- **Spot Instances**: Up to 70% cost savings vs on-demand
- **Automatic Termination**: Instances terminate after build completion
- **Lifecycle Policies**: Old artifacts automatically deleted after 30 days
- **Right-Sized Instances**: g4dn.xlarge provides optimal price/performance

**Estimated Costs:**
- g4dn.xlarge spot: ~$0.20-0.30/hour
- Typical build time: 30-60 minutes
- Cost per build: ~$0.10-0.30
- S3 storage: ~$0.023/GB/month

## Security

- **Encrypted Storage**: S3 bucket uses AES256 encryption
- **Private Bucket**: Public access blocked by default
- **IMDSv2**: Instance metadata service v2 required
- **Least Privilege**: IAM roles grant minimal required permissions
- **VPC Isolation**: Instances run in private subnets (recommended)

## Creating a Custom AMI

To create a custom AMI with UE5.3:

1. Launch a base Amazon Linux 2023 or Ubuntu 22.04 instance
2. Install Unreal Engine 5.3+ from source or Epic Games Launcher
3. Install Android SDK and NDK for Quest 3 builds
4. Install GameLift SDK
5. Install build tools (CMake, compilers, etc.)
6. Create AMI from configured instance
7. Tag AMI with `Purpose=UnrealBuild`

## Monitoring

Build logs are sent to CloudWatch Logs:
- Log Group: `/aws/ec2/unreal-build/{environment}`
- Log Stream: `{instance_id}`
- Retention: 30 days (configurable)

## Troubleshooting

**Build fails with "out of disk space":**
- Increase `root_volume_size` variable (default: 150GB)

**Spot instance terminated during build:**
- Set `enable_spot_instances = false` for critical builds
- Or increase `spot_max_price` to reduce interruption risk

**AMI not found:**
- Ensure custom AMI exists and is tagged correctly
- Or provide explicit `ami_id` variable

## License

This module is part of the Unreal VR Multiplayer System project.
