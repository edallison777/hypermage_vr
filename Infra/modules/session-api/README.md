# Session API Terraform Module

This module provisions the Session API infrastructure for the Unreal VR Multiplayer System, including API Gateway, Lambda functions, and IAM roles for matchmaking and session management.

## Features

- **API Gateway REST API** with Cognito authorization
- **Lambda Functions** for matchmaking and session management:
  - `start-matchmaking`: Initiates FlexMatch matchmaking
  - `get-matchmaking-status`: Retrieves matchmaking ticket status
  - `post-session-summary`: Stores session summaries with rewards
- **IAM Roles and Policies** for Lambda execution
- **CloudWatch Logs** for API Gateway and Lambda functions
- **Integration** with GameLift FlexMatch and DynamoDB

## API Endpoints

### POST /matchmaking/start
Starts a matchmaking request for a player.

**Authorization**: Cognito User Pool (JWT token required)

**Request Body**:
```json
{
  "playerId": "player-123",
  "playerAttributes": {
    "skill": 10,
    "region": "eu-west-1",
    "latencyInMs": {
      "eu-west-1": 50,
      "us-east-1": 150
    }
  }
}
```

**Response**:
```json
{
  "ticketId": "ticket-abc123",
  "status": "QUEUED",
  "estimatedWaitTime": 30,
  "startTime": "2026-02-01T12:00:00Z"
}
```

### GET /matchmaking/status/{ticketId}
Retrieves the status of a matchmaking ticket.

**Authorization**: Cognito User Pool (JWT token required)

**Response**:
```json
{
  "ticketId": "ticket-abc123",
  "status": "COMPLETED",
  "statusReason": "MatchFound",
  "startTime": "2026-02-01T12:00:00Z",
  "endTime": "2026-02-01T12:00:45Z",
  "gameSessionConnectionInfo": {
    "gameSessionArn": "arn:aws:gamelift:...",
    "ipAddress": "54.123.45.67",
    "port": 7777,
    "matchedPlayerSessions": [...]
  }
}
```

**Possible Status Values**:
- `QUEUED`: Matchmaking request is queued
- `SEARCHING`: Actively searching for match
- `REQUIRES_ACCEPTANCE`: Match found, waiting for player acceptance
- `PLACING`: Creating game session
- `COMPLETED`: Match complete, game session ready
- `FAILED`: Matchmaking failed
- `CANCELLED`: Matchmaking cancelled
- `TIMED_OUT`: Matchmaking timed out

### POST /session-summary
Stores a player session summary with rewards.

**Authorization**: AWS IAM (for GameLift server calls)

**Request Body**:
```json
{
  "playerId": "player-123",
  "sessionId": "session-xyz789",
  "rewards": ["first_objective_complete", "session_complete"],
  "endTime": "2026-02-01T13:00:00Z"
}
```

**Response**:
```json
{
  "success": true,
  "playerId": "player-123",
  "sessionId": "session-xyz789",
  "rewardsStored": 2,
  "ttl": 1738501200
}
```

## Usage

```hcl
module "session_api" {
  source = "../../modules/session-api"

  project_name = "hypermage-vr"
  environment  = "dev"
  aws_region   = "eu-west-1"

  # Cognito integration
  cognito_user_pool_arn = module.cognito.user_pool_arn

  # FlexMatch integration
  matchmaking_configuration_name = module.flexmatch.matchmaking_configuration_name

  # DynamoDB integration
  dynamodb_table_arns = [
    aws_dynamodb_table.player_sessions.arn,
    aws_dynamodb_table.player_rewards.arn
  ]
  player_sessions_table_name = aws_dynamodb_table.player_sessions.name
  player_rewards_table_name  = aws_dynamodb_table.player_rewards.name

  # Logging
  log_retention_days = 30
  lambda_log_level   = "INFO"

  tags = {
    CostCenter = "Development"
    Owner      = "DevOps Team"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project_name | Project name for resource naming | string | - | yes |
| environment | Environment name (dev, staging, prod) | string | - | yes |
| aws_region | AWS region for resources | string | "eu-west-1" | no |
| cognito_user_pool_arn | ARN of the Cognito User Pool | string | - | yes |
| matchmaking_configuration_name | FlexMatch configuration name | string | - | yes |
| dynamodb_table_arns | List of DynamoDB table ARNs | list(string) | [] | no |
| player_sessions_table_name | PlayerSessions table name | string | "" | no |
| player_rewards_table_name | PlayerRewards table name | string | "" | no |
| log_retention_days | CloudWatch log retention in days | number | 30 | no |
| lambda_log_level | Lambda log level (DEBUG, INFO, WARN, ERROR) | string | "INFO" | no |
| tags | Additional tags for resources | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| api_id | API Gateway REST API ID |
| api_endpoint | API Gateway endpoint URL |
| api_arn | API Gateway ARN |
| start_matchmaking_function_name | Start matchmaking Lambda function name |
| start_matchmaking_function_arn | Start matchmaking Lambda function ARN |
| get_matchmaking_status_function_name | Get matchmaking status Lambda function name |
| get_matchmaking_status_function_arn | Get matchmaking status Lambda function ARN |
| post_session_summary_function_name | Post session summary Lambda function name |
| post_session_summary_function_arn | Post session summary Lambda function ARN |
| lambda_role_arn | IAM role ARN for Lambda functions |
| api_gateway_log_group | CloudWatch log group for API Gateway |

## Lambda Function Deployment

The Lambda functions are automatically packaged and deployed by Terraform. Before deploying, ensure you have Node.js dependencies installed:

```bash
cd lambda/start-matchmaking && npm install && cd ../..
cd lambda/get-matchmaking-status && npm install && cd ../..
cd lambda/post-session-summary && npm install && cd ../..
```

Terraform will automatically create deployment packages from the `lambda/` directories.

## Session Data Model

### PlayerSessions Table
Stores ephemeral session data with 72-hour TTL:
- **Partition Key**: `playerId` (String)
- **Sort Key**: `sessionId` (String)
- **TTL Attribute**: `ttl` (Number) - Unix timestamp for auto-deletion
- **Attributes**: `endTime`, `rewards`, `createdAt`

### PlayerRewards Table
Stores persistent reward flags (no TTL):
- **Partition Key**: `playerId` (String)
- **Sort Key**: `rewardId` (String)
- **Attributes**: `granted` (Boolean), `grantedAt` (String), `sessionId` (String)

## Security

- **API Gateway Authorization**: Cognito User Pool JWT tokens for player endpoints
- **IAM Authorization**: AWS IAM for server-to-server calls (session summary)
- **Lambda Execution Role**: Minimal permissions (GameLift, DynamoDB, CloudWatch Logs)
- **CloudWatch Logs**: All API calls and Lambda executions logged
- **Encryption**: Data encrypted in transit (TLS 1.3) and at rest (DynamoDB encryption)

## Monitoring

CloudWatch metrics and alarms are automatically configured for:
- API Gateway request count and latency
- Lambda function errors and duration
- DynamoDB read/write capacity

View logs:
```bash
# API Gateway logs
aws logs tail /aws/apigateway/hypermage-vr-dev --follow

# Lambda logs
aws logs tail /aws/lambda/hypermage-vr-start-matchmaking-dev --follow
aws logs tail /aws/lambda/hypermage-vr-get-matchmaking-status-dev --follow
aws logs tail /aws/lambda/hypermage-vr-post-session-summary-dev --follow
```

## Cost Optimization

- **Lambda**: Pay per request, 256MB memory, 30s timeout
- **API Gateway**: Pay per request
- **CloudWatch Logs**: 30-day retention (configurable)
- **DynamoDB**: On-demand billing recommended for variable workloads
- **Estimated Cost**: ~$5-20/month for dev environment with moderate usage

## Requirements

- Terraform >= 1.5.0
- AWS Provider >= 5.0
- Archive Provider >= 2.0
- Node.js 20+ (for Lambda functions)
- AWS SDK for JavaScript v3

## Notes

- Lambda functions use Node.js 20.x runtime
- All Lambda functions have 30-second timeout
- API Gateway uses regional endpoints
- Session data automatically expires after 72 hours via DynamoDB TTL
- Reward data persists indefinitely (no TTL)

## Related Modules

- [cognito](../cognito/) - User authentication
- [flexmatch](../flexmatch/) - Matchmaking configuration
- [gamelift-fleet](../gamelift-fleet/) - Game server fleet

## References

- [AWS API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [Amazon GameLift FlexMatch](https://docs.aws.amazon.com/gamelift/latest/flexmatchguide/)
- [DynamoDB TTL](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html)
