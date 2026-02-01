# Infrastructure as Code (Terraform)

This directory contains Terraform modules and configurations for deploying the Unreal VR Multiplayer System infrastructure to AWS.

## Directory Structure

```
Infra/
├── modules/              # Reusable Terraform modules
│   └── unreal-build/    # EC2 infrastructure for Unreal Engine builds
├── environments/         # Environment-specific configurations
│   ├── dev/             # Development environment
│   ├── staging/         # Staging environment (future)
│   └── prod/            # Production environment (future)
└── README.md            # This file
```

## Modules

### unreal-build

Provisions cloud-based infrastructure for building Unreal Engine 5.3 projects:
- EC2 g4dn.xlarge instances with spot instance support
- S3 bucket for build artifacts with lifecycle policies
- IAM roles and security groups
- CloudWatch logging

See [modules/unreal-build/README.md](modules/unreal-build/README.md) for details.

## Environments

### Development (dev)

The development environment uses:
- Default VPC for simplicity
- Spot instances for cost optimization
- Relaxed cost limits
- Autonomous operation without approval gates

**Deploy:**
```bash
cd environments/dev
terraform init
terraform plan
terraform apply
```

### Staging (staging)

Coming soon - reduced capacity environment for pre-production testing.

### Production (prod)

Coming soon - full capacity environment with strict approval gates.

## Prerequisites

1. **AWS Account**: Active AWS account with appropriate permissions
2. **AWS CLI**: Configured with credentials (`aws configure`)
3. **Terraform**: Version 1.5.0 or later installed
4. **Custom AMI**: Pre-configured AMI with UE5.3, Android SDK, GameLift SDK

## Getting Started

### 1. Configure AWS Credentials

```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and default region
```

### 2. Initialize Terraform

```bash
cd environments/dev
terraform init
```

### 3. Review Plan

```bash
terraform plan
```

### 4. Apply Configuration

```bash
terraform apply
```

### 5. Verify Deployment

```bash
# Check S3 bucket
aws s3 ls | grep unreal-build-artifacts

# Check launch template
aws ec2 describe-launch-templates --filters "Name=tag:Project,Values=HyperMage VR"
```

## Cost Estimation

**Development Environment:**
- EC2 g4dn.xlarge spot: ~$0.20-0.30/hour
- Typical build: 30-60 minutes = ~$0.10-0.30 per build
- S3 storage: ~$0.023/GB/month
- CloudWatch logs: ~$0.50/GB ingested

**Monthly estimate (10 builds/day):**
- Builds: 10 builds/day × 30 days × $0.20 = ~$60/month
- S3 storage: 50GB × $0.023 = ~$1.15/month
- Logs: 5GB × $0.50 = ~$2.50/month
- **Total: ~$65/month**

## State Management

For team collaboration, configure remote state storage:

1. Create S3 bucket for state:
```bash
aws s3 mb s3://hypermage-vr-terraform-state --region eu-west-1
aws s3api put-bucket-versioning --bucket hypermage-vr-terraform-state --versioning-configuration Status=Enabled
```

2. Create DynamoDB table for state locking:
```bash
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-west-1
```

3. Uncomment backend configuration in `environments/*/main.tf`

## Security Best Practices

- **Least Privilege**: IAM roles grant minimal required permissions
- **Encryption**: All data encrypted at rest and in transit
- **Private Resources**: S3 buckets block public access
- **IMDSv2**: Instance metadata service v2 required
- **Audit Logging**: CloudTrail enabled for all API calls

## Troubleshooting

**Error: "No valid credential sources found"**
- Run `aws configure` to set up credentials
- Or set environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

**Error: "AMI not found"**
- Create custom AMI with UE5.3 (see modules/unreal-build/README.md)
- Or provide explicit `ami_id` in module configuration

**Error: "VPC not found"**
- Ensure default VPC exists in your AWS account
- Or create custom VPC and update `vpc_id` variable

## Cleanup

To destroy all resources:

```bash
cd environments/dev
terraform destroy
```

**Warning**: This will delete all build artifacts in S3. Ensure you have backups if needed.

## Next Steps

After deploying the Unreal build infrastructure:

1. Create custom AMI with UE5.3 and dependencies
2. Test build workflow with UnrealMCP adapter
3. Deploy additional modules (GameLift, Cognito, DynamoDB)
4. Configure CI/CD pipelines for automated deployments

## Support

For issues or questions:
- Check module README files for detailed documentation
- Review Terraform logs: `TF_LOG=DEBUG terraform apply`
- Consult AWS documentation for service-specific issues
