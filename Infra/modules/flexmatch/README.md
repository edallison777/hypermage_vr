# FlexMatch Matchmaking Terraform Module

This Terraform module provisions Amazon FlexMatch for player matchmaking in the Unreal VR Multiplayer System.

## Overview

The module creates:
- **Game Session Queue**: Routes matchmaking requests to available fleets
- **Matchmaking Rule Set**: Defines player matching rules and criteria
- **Matchmaking Configuration**: Configures matchmaking behavior and timeouts
- **IAM Roles**: Permissions for matchmaking operations
- **CloudWatch Monitoring**: Metrics and alarms for matchmaking health

## Features

- **Skill-Based Matching**: Matches players with similar skill levels
- **Latency-Based Matching**: Ensures acceptable network latency
- **Region Preference**: Prefers players from same region
- **Progressive Relaxation**: Gradually relaxes rules to find matches faster
- **Automatic Backfill**: Fills empty slots in ongoing matches
- **Match Acceptance**: Players can accept/reject matches

## Prerequisites

1. **GameLift Fleet**: Deployed GameLift fleet (from Task 15.1)
2. **Fleet ARN**: ARN of the GameLift fleet for routing

## Usage

```hcl
module "flexmatch" {
  source = "./modules/flexmatch"

  project_name = "hypermage-vr"
  environment  = "dev"
  aws_region   = "eu-west-1"

  # Fleet configuration
  fleet_arns = [module.gamelift_fleet.fleet_arn]

  # Match size (10-15 players per shard)
  min_players_per_match = 10
  max_players_per_match = 15

  # Matchmaking timeouts
  matchmaking_timeout_seconds = 120
  acceptance_timeout_seconds  = 30
  acceptance_required         = true

  # Skill matching
  skill_distance_threshold = 5
  max_latency_ms          = 100

  # Backfill
  backfill_mode = "AUTOMATIC"

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
| fleet_arns | GameLift fleet ARNs | list(string) | - | yes |
| queue_timeout_seconds | Queue placement timeout | number | 600 | no |
| player_latency_policies | Latency policies | list(object) | See below | no |
| min_players_per_match | Minimum players | number | 10 | no |
| max_players_per_match | Maximum players | number | 15 | no |
| matchmaking_timeout_seconds | Matchmaking timeout | number | 120 | no |
| acceptance_timeout_seconds | Acceptance timeout | number | 30 | no |
| acceptance_required | Require match acceptance | bool | true | no |
| backfill_mode | Backfill mode | string | "AUTOMATIC" | no |
| skill_distance_threshold | Max skill difference | number | 5 | no |
| max_latency_ms | Max latency | number | 100 | no |
| enable_notifications | Enable SNS notifications | bool | false | no |
| notification_sns_topic_arn | SNS topic ARN | string | "" | no |
| log_retention_days | Log retention days | number | 30 | no |
| alarm_sns_topic_arns | Alarm SNS topics | list(string) | [] | no |
| tags | Additional tags | map(string) | {} | no |

### Default Player Latency Policies

```hcl
[
  {
    max_latency_ms   = 100
    duration_seconds = 30
  },
  {
    max_latency_ms   = 150
    duration_seconds = 60
  },
  {
    max_latency_ms   = 200
    duration_seconds = 0
  }
]
```

This means:
- First 30 seconds: Only accept players with <100ms latency
- Next 30 seconds: Accept players with <150ms latency
- After 60 seconds: Accept players with <200ms latency

## Outputs

| Name | Description |
|------|-------------|
| matchmaking_configuration_name | Matchmaking configuration name |
| matchmaking_configuration_arn | Matchmaking configuration ARN |
| rule_set_name | Rule set name |
| rule_set_arn | Rule set ARN |
| game_session_queue_name | Game session queue name |
| game_session_queue_arn | Game session queue ARN |
| iam_role_arn | IAM role ARN |
| cloudwatch_log_group_name | CloudWatch log group name |

## Matchmaking Rules

### 1. Fair Team Skill

Ensures players have similar skill levels:
- Initial threshold: ±5 skill points
- After 10s: ±7.5 skill points
- After 20s: ±10 skill points

### 2. Fast Connection

Ensures acceptable network latency:
- Initial: <100ms
- After 10s: <120ms
- After 20s: <150ms

### 3. Region Preference

Prefers players from the same region but doesn't require it.

## Matchmaking Flow

1. **Player Requests Match**: Client calls StartMatchmaking API
2. **Rule Evaluation**: FlexMatch evaluates rules against player pool
3. **Progressive Relaxation**: Rules gradually relax over time
4. **Match Found**: When enough compatible players found
5. **Match Acceptance**: Players have 30s to accept (if enabled)
6. **Session Creation**: GameLift creates game session on fleet
7. **Player Connection**: Players connect to game server

## Player Attributes

Players can provide these attributes for matchmaking:

```json
{
  "skill": 10,
  "region": "eu-west-1"
}
```

### Skill Attribute

- Type: Number
- Default: 10
- Range: 0-20 (recommended)
- Purpose: Skill-based matching

### Region Attribute

- Type: String
- Default: "eu-west-1"
- Values: AWS region codes
- Purpose: Regional preference

## Backfill Mode

**AUTOMATIC** (default):
- FlexMatch automatically fills empty slots in ongoing matches
- Reduces wait time for new players
- Maintains match quality

**MANUAL**:
- Game server must request backfill explicitly
- More control over when to fill slots
- Useful for custom backfill logic

## Match Acceptance

When `acceptance_required = true`:
- Players receive match notification
- Players have 30 seconds to accept
- All players must accept for match to proceed
- If any player rejects/times out, matchmaking restarts

When `acceptance_required = false`:
- Match proceeds immediately when found
- Faster matchmaking
- Risk of AFK players

## Monitoring

### CloudWatch Metrics

- `MatchmakingSearching`: Players currently searching
- `MatchmakingSucceeded`: Successful matches
- `MatchmakingTimedOut`: Timed out searches
- `MatchmakingCancelled`: Cancelled searches
- `TimeToMatch`: Average time to find match

### CloudWatch Alarms

1. **Timeout High**: Alerts when >10 timeouts in 5 minutes
2. **Success Low**: Alerts when <5 successes in 5 minutes

## Cost Estimation

FlexMatch pricing:
- $1.00 per 1,000 player-hours of matchmaking
- Player-hour = 1 player searching for 1 hour

**Example:**
- 100 concurrent players
- Average search time: 2 minutes
- Daily cost: 100 × (2/60) × 24 × ($1/1000) = $0.08/day
- Monthly cost: ~$2.40/month

Very cost-effective for matchmaking!

## Integration with Client

### Starting Matchmaking

```typescript
// Client-side code (TypeScript)
import { GameLiftClient, StartMatchmakingCommand } from "@aws-sdk/client-gamelift";

const client = new GameLiftClient({ region: "eu-west-1" });

const response = await client.send(new StartMatchmakingCommand({
  ConfigurationName: "hypermage-vr-dev",
  Players: [
    {
      PlayerId: "player-123",
      PlayerAttributes: {
        skill: { N: 12 },
        region: { S: "eu-west-1" }
      },
      LatencyInMs: {
        "eu-west-1": 45,
        "us-west-2": 150
      }
    }
  ]
}));

const ticketId = response.MatchmakingTicket.TicketId;
```

### Checking Match Status

```typescript
import { DescribeMatchmakingCommand } from "@aws-sdk/client-gamelift";

const status = await client.send(new DescribeMatchmakingCommand({
  TicketIds: [ticketId]
}));

console.log(status.TicketList[0].Status);
// Possible values: QUEUED, SEARCHING, REQUIRES_ACCEPTANCE, PLACING, COMPLETED, FAILED, CANCELLED, TIMED_OUT
```

### Accepting Match

```typescript
import { AcceptMatchCommand } from "@aws-sdk/client-gamelift";

await client.send(new AcceptMatchCommand({
  TicketId: ticketId,
  PlayerIds: ["player-123"],
  AcceptanceType: "ACCEPT"
}));
```

## Integration with Unreal Engine

### C++ Example

```cpp
// In your game instance or matchmaking manager
#include "GameLiftClientSDK.h"

void UMyGameInstance::StartMatchmaking()
{
    Aws::GameLift::Model::StartMatchmakingRequest Request;
    Request.SetConfigurationName("hypermage-vr-dev");
    
    Aws::GameLift::Model::Player Player;
    Player.SetPlayerId(GetPlayerID());
    
    // Set player attributes
    Aws::GameLift::Model::AttributeValue SkillAttr;
    SkillAttr.SetN(GetPlayerSkill());
    Player.AddPlayerAttributes("skill", SkillAttr);
    
    Request.AddPlayers(Player);
    
    auto Outcome = GameLiftClient->StartMatchmaking(Request);
    if (Outcome.IsSuccess())
    {
        TicketId = Outcome.GetResult().GetMatchmakingTicket().GetTicketId();
        StartPollingMatchStatus();
    }
}
```

## Troubleshooting

**Matchmaking always times out:**
- Check fleet has available capacity
- Verify fleet is in ACTIVE state
- Reduce skill_distance_threshold
- Increase max_latency_ms
- Check player pool size

**Players not matched despite being compatible:**
- Verify player attributes are set correctly
- Check latency data is provided
- Review rule set logic
- Check CloudWatch logs for errors

**High matchmaking costs:**
- Reduce matchmaking_timeout_seconds
- Implement client-side cancellation
- Use acceptance_required to filter AFK players

**Matches have high latency:**
- Reduce max_latency_ms threshold
- Add more fleet locations
- Adjust player_latency_policies

## Security Best Practices

- **Authentication**: Integrate with Cognito (Task 15.3)
- **Authorization**: Validate player IDs before matchmaking
- **Rate Limiting**: Prevent matchmaking spam
- **Monitoring**: Alert on unusual matchmaking patterns

## Next Steps

After deploying FlexMatch:

1. Test matchmaking with simulated players
2. Integrate with Cognito for authentication (Task 15.3)
3. Implement client-side matchmaking UI
4. Monitor matchmaking metrics
5. Tune rules based on player feedback

## Support

For issues or questions:
- Check matchmaking ticket status in AWS Console
- Review CloudWatch logs for errors
- Consult AWS GameLift FlexMatch documentation
- Test with AWS GameLift Local for development
