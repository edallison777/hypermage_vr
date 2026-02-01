# DynamoDB Tables Terraform Module

This module provisions DynamoDB tables for the Unreal VR Multiplayer System, including session management and reward tracking with TTL-based expiration.

## Features

- **PlayerSessions Table**: Stores ephemeral session data with 72-hour TTL
- **InteractionEvents Table**: Stores player interaction events with 72-hour TTL
- **PlayerRewards Table**: Stores persistent reward flags (no TTL)
- **TTL Configuration**: Automatic data expiration for ephemeral tables
- **Server-Side Encryption**: All tables encrypted at rest
- **Point-in-Time Recovery**: Optional backup capability for production
- **CloudWatch Alarms**: Optional monitoring for throttle events
- **Flexible Billing**: Supports both on-demand and provisioned capacity

## Table Schemas

### PlayerSessions Table

Stores ephemeral session data that automatically expires 72 hours after session end.

**Keys:**
- **Partition Key**: `playerId` (String) - Player identifier
- **Sort Key**: `sessionId` (String) - Session identifier

**Attributes:**
- `endTime` (String) - ISO 8601 timestamp of session end
- `rewards` (List) - Array of reward IDs granted during session
- `ttl` (Number) - Unix timestamp for automatic deletion (72h after endTime)
- `createdAt` (String) - ISO 8601 timestamp of record creation

**TTL**: Enabled on `ttl` attribute (72 hours after session end)

**Example Item:**
```json
{
  "playerId": "player-123",
  "sessionId": "session-xyz789",
  "endTime": "2026-02-01T13:00:00Z",
  "rewards": ["first_objective_complete", "session_complete"],
  "ttl": 1738501200,
  "createdAt": "2026-02-01T13:00:05Z"
}
```

### InteractionEvents Table

Stores player interaction events that automatically expire 72 hours after session end.

**Keys:**
- **Partition Key**: `sessionId` (String) - Session identifier
- **Sort Key**: `timestamp` (String) - ISO 8601 timestamp of event

**Global Secondary Index:**
- **Name**: `PlayerIdIndex`
- **Partition Key**: `playerId` (String)
- **Sort Key**: `timestamp` (String)
- **Projection**: ALL

**Attributes:**
- `playerId` (String) - Player identifier
- `eventType` (String) - Type of interaction event
- `data` (Map) - Event-specific data
- `ttl` (Number) - Unix timestamp for automatic deletion (72h after session end)

**TTL**: Enabled on `ttl` attribute (72 hours after session end)

**Example Item:**
```json
{
  "sessionId": "session-xyz789",
  "timestamp": "2026-02-01T12:30:15Z",
  "playerId": "player-123",
  "eventType": "objective_completed",
  "data": {
    "objectiveId": "obj-001",
    "position": {"x": 100, "y": 50, "z": 200}
  },
  "ttl": 1738501200
}
```

### PlayerRewards Table

Stores persistent reward flags that never expire.

**Keys:**
- **Partition Key**: `playerId` (String) - Player identifier
- **Sort Key**: `rewardId` (String) - Reward identifier from catalog

**Attributes:**
- `granted` (Boolean) - Always true (reward granted)
- `grantedAt` (String) - ISO 8601 timestamp when reward was granted
- `sessionId` (String) - Session where reward was granted

**TTL**: None (rewards persist indefinitely)

**Example Item:**
```json
{
  "playerId": "player-123",
  "rewardId": "first_objective_complete",
  "granted": true,
  "grantedAt": "2026-02-01T12:30:15Z",
  "sessionId": "session-xyz789"
}
```

## Usage

```hcl
module "dynamodb" {
  source = "../../modules/dynamodb"

  project_name = "hypermage-vr"
  environment  = "dev"

  # Billing configuration
  billing_mode = "PAY_PER_REQUEST"  # On-demand billing (recommended)
  # billing_mode = "PROVISIONED"    # Provisioned capacity (uncomment for fixed capacity)
  # read_capacity  = 10
  # write_capacity = 10

  # Backup and recovery
  enable_point_in_time_recovery = true  # Enable for production

  # Encryption (optional custom KMS key)
  # kms_key_arn = "arn:aws:kms:eu-west-1:123456789012:key/..."

  # Monitoring
  enable_cloudwatch_alarms = true
  alarm_sns_topic_arns     = ["arn:aws:sns:eu-west-1:123456789012:alerts"]

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
| billing_mode | DynamoDB billing mode (PROVISIONED or PAY_PER_REQUEST) | string | "PAY_PER_REQUEST" | no |
| read_capacity | Read capacity units (only for PROVISIONED mode) | number | 5 | no |
| write_capacity | Write capacity units (only for PROVISIONED mode) | number | 5 | no |
| gsi_read_capacity | GSI read capacity units (only for PROVISIONED mode) | number | 5 | no |
| gsi_write_capacity | GSI write capacity units (only for PROVISIONED mode) | number | 5 | no |
| enable_point_in_time_recovery | Enable point-in-time recovery | bool | false | no |
| kms_key_arn | KMS key ARN for encryption (optional) | string | null | no |
| enable_cloudwatch_alarms | Enable CloudWatch alarms | bool | false | no |
| alarm_sns_topic_arns | SNS topic ARNs for alarm notifications | list(string) | [] | no |
| tags | Additional tags for resources | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| player_sessions_table_name | PlayerSessions table name |
| player_sessions_table_arn | PlayerSessions table ARN |
| player_sessions_table_id | PlayerSessions table ID |
| interaction_events_table_name | InteractionEvents table name |
| interaction_events_table_arn | InteractionEvents table ARN |
| interaction_events_table_id | InteractionEvents table ID |
| player_rewards_table_name | PlayerRewards table name |
| player_rewards_table_arn | PlayerRewards table ARN |
| player_rewards_table_id | PlayerRewards table ID |
| all_table_arns | List of all DynamoDB table ARNs |
| all_table_names | List of all DynamoDB table names |

## TTL Behavior

### How TTL Works

DynamoDB's Time-To-Live (TTL) feature automatically deletes items after a specified timestamp:

1. **TTL Attribute**: Each item has a `ttl` attribute containing a Unix timestamp (seconds since epoch)
2. **Automatic Deletion**: DynamoDB scans for expired items and deletes them within 48 hours of expiration
3. **No Cost**: TTL deletions are free (no write capacity consumed)
4. **Background Process**: Deletions happen asynchronously in the background

### TTL Configuration in This Module

**PlayerSessions Table:**
- TTL enabled on `ttl` attribute
- Set to 72 hours (259,200 seconds) after session end
- Example: Session ends at 2026-02-01 13:00:00 → TTL = 2026-02-04 13:00:00

**InteractionEvents Table:**
- TTL enabled on `ttl` attribute
- Set to 72 hours after session end (same as session)
- All events from a session expire together

**PlayerRewards Table:**
- NO TTL configured
- Rewards persist indefinitely
- Must be manually deleted if needed

### Setting TTL Values

When writing items to tables with TTL:

```javascript
// Calculate TTL: 72 hours from now
const ttl = Math.floor(Date.now() / 1000) + (72 * 60 * 60);

// Or 72 hours from session end
const sessionEndTime = new Date('2026-02-01T13:00:00Z');
const ttl = Math.floor(sessionEndTime.getTime() / 1000) + (72 * 60 * 60);

// Store item with TTL
await dynamodb.putItem({
  TableName: 'player-sessions',
  Item: {
    playerId: 'player-123',
    sessionId: 'session-xyz',
    ttl: ttl,  // Unix timestamp
    // ... other attributes
  }
});
```

## Billing Modes

### PAY_PER_REQUEST (On-Demand)

**Recommended for:**
- Development and testing
- Variable or unpredictable workloads
- Applications with spiky traffic

**Pricing:**
- $1.25 per million write requests
- $0.25 per million read requests
- No minimum capacity

**Example Cost (Dev Environment):**
- 100,000 writes/month: $0.13
- 500,000 reads/month: $0.13
- Total: ~$0.26/month

### PROVISIONED

**Recommended for:**
- Production with predictable traffic
- Cost optimization for steady workloads

**Pricing:**
- $0.00065 per WCU-hour
- $0.00013 per RCU-hour
- Auto-scaling available

**Example Cost (Prod Environment):**
- 10 WCU, 10 RCU: ~$5.70/month per table
- Total (3 tables): ~$17/month

## Security

- **Encryption at Rest**: All tables encrypted using AWS managed keys (or custom KMS key)
- **Encryption in Transit**: All API calls use TLS 1.3
- **IAM Policies**: Fine-grained access control via IAM roles
- **VPC Endpoints**: Optional VPC endpoint for private access
- **Audit Logging**: CloudTrail logs all API calls

## Monitoring

### CloudWatch Metrics

Automatically available metrics:
- `ConsumedReadCapacityUnits`
- `ConsumedWriteCapacityUnits`
- `ReadThrottleEvents`
- `WriteThrottleEvents`
- `UserErrors`
- `SystemErrors`

### CloudWatch Alarms

When `enable_cloudwatch_alarms = true`:
- Read throttle events > 10 in 5 minutes
- Write throttle events > 10 in 5 minutes

### Viewing Metrics

```bash
# View table metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=hypermage-vr-player-sessions-dev \
  --start-time 2026-02-01T00:00:00Z \
  --end-time 2026-02-01T23:59:59Z \
  --period 3600 \
  --statistics Sum
```

## Backup and Recovery

### Point-in-Time Recovery (PITR)

When `enable_point_in_time_recovery = true`:
- Continuous backups for 35 days
- Restore to any point in time within backup window
- No performance impact
- Additional cost: ~$0.20 per GB-month

### On-Demand Backups

Create manual backups:
```bash
aws dynamodb create-backup \
  --table-name hypermage-vr-player-sessions-dev \
  --backup-name player-sessions-backup-2026-02-01
```

## Performance Optimization

### Best Practices

1. **Use On-Demand Billing for Dev**: Simplifies capacity planning
2. **Enable Auto-Scaling for Prod**: Automatically adjusts capacity
3. **Use GSI Wisely**: InteractionEvents has PlayerIdIndex for efficient queries
4. **Batch Operations**: Use BatchWriteItem for multiple writes
5. **Consistent Reads**: Use eventually consistent reads when possible (cheaper)

### Query Patterns

**Get player's current session:**
```javascript
const result = await dynamodb.query({
  TableName: 'player-sessions',
  KeyConditionExpression: 'playerId = :playerId',
  ExpressionAttributeValues: { ':playerId': 'player-123' },
  ScanIndexForward: false,  // Most recent first
  Limit: 1
});
```

**Get player's interaction events:**
```javascript
const result = await dynamodb.query({
  TableName: 'interaction-events',
  IndexName: 'PlayerIdIndex',
  KeyConditionExpression: 'playerId = :playerId',
  ExpressionAttributeValues: { ':playerId': 'player-123' }
});
```

**Get player's rewards:**
```javascript
const result = await dynamodb.query({
  TableName: 'player-rewards',
  KeyConditionExpression: 'playerId = :playerId',
  ExpressionAttributeValues: { ':playerId': 'player-123' }
});
```

## Requirements

- Terraform >= 1.5.0
- AWS Provider >= 5.0

## Related Modules

- [session-api](../session-api/) - API for session management
- [cognito](../cognito/) - User authentication
- [gamelift-fleet](../gamelift-fleet/) - Game server fleet

## References

- [DynamoDB TTL Documentation](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [DynamoDB Pricing](https://aws.amazon.com/dynamodb/pricing/)

