# Frequently Asked Questions

## Can I complete this project without installing UE 5.3 locally?

**YES!** The project is specifically designed to work WITHOUT local UE5.3 installation.

### How it works:

1. **Cloud Builds (Default)**: All Unreal Engine compilation happens on AWS EC2 g4dn instances
   - Pre-configured AMIs include UE5.3, Android SDK, and GameLift SDK
   - Build artifacts are uploaded to S3
   - EC2 instances terminate after build completion
   - Cost: ~$0.50-$2.00 per build

2. **Mock Mode (Development/Testing)**: Simulates builds without any EC2 usage
   - Perfect for testing workflows
   - No AWS costs
   - Instant "builds" with mock artifacts

3. **Local Builds (Optional)**: If you DO have UE5.3 installed
   - Faster build times (no EC2 spin-up)
   - No EC2 costs
   - Purely optional optimization

### What you need:

- A development machine (Windows, Mac, or Linux)
- Node.js 20+ for running the Orchestrator and Agents
- AWS account for cloud builds (or use mock mode)
- Git for version control

### What you DON'T need:

- ❌ Local Unreal Engine installation
- ❌ High-end gaming PC
- ❌ Large disk space for UE5.3 (100+ GB)
- ❌ Android SDK or GameLift SDK locally

**See Requirement 8a in requirements.md for full details.**

---

## What does TTL stand for?

**TTL = Time-To-Live**

TTL is an expiration timestamp for ephemeral data records. After the TTL expires, DynamoDB automatically deletes the record.

### How TTL works in this system:

1. **Session ends** (player disconnects, match completes, or timeout)
2. **TTL is set** to 72 hours from session end time
3. **Data remains available** for 72 hours for queries and processing
4. **Automatic deletion** happens after 72 hours via DynamoDB TTL feature

### What has TTL (ephemeral):

- **PlayerSessions table**: Session metadata (sessionId, playerId, state, timestamps)
- **InteractionEvents table**: Player actions during session (eventType, data, timestamp)

### What does NOT have TTL (persistent):

- **PlayerRewards table**: Granted rewards stored as boolean flags forever

---

## Can I gather information on player actions after session end?

**YES!** You have 72 hours to query session data after the session ends.

### Timeline:

```
Session Active → Session Ends → 72 Hours Available → Automatic Deletion
                      ↓
                 TTL Set to:
                 current_time + 72 hours
```

### What you can do during the 72-hour window:

1. **Query session events**: Get all InteractionEvents for analysis
2. **Generate reports**: Create analytics on player behavior
3. **Process rewards**: Validate reward grants and summaries
4. **Debug issues**: Investigate gameplay problems
5. **Export data**: Move data to long-term storage if needed

### Example use cases:

- **Analytics**: "Show me all objective completions from yesterday's sessions"
- **Debugging**: "What events led to this player's disconnect?"
- **Reporting**: "Generate a summary of all sessions from the weekend event"
- **Compliance**: "Export session data for player support ticket #12345"

### After 72 hours:

- Session events are automatically deleted by DynamoDB
- Rewards remain in PlayerRewards table forever
- No manual cleanup required
- Storage costs reduced automatically

### Why 72 hours?

- Balances data availability with storage costs
- Sufficient time for post-event analysis
- Meets typical analytics and debugging needs
- Complies with data minimization principles (GDPR)

---

## How do I run builds during development?

### Option 1: Mock Mode (Recommended for early development)

```bash
# Set mock mode in environment
export MCP_MOCK_MODE=true

# Run orchestrator
npm run orchestrator

# Request a build - it will simulate instantly
```

### Option 2: Cloud Builds (Recommended for testing real builds)

```bash
# Configure AWS credentials
export AWS_PROFILE=my-dev-profile

# Run orchestrator
npm run orchestrator

# Request a build - it will launch EC2 and build
# Cost: ~$0.50-$2.00 per build
```

### Option 3: Local Builds (If you have UE5.3 installed)

```bash
# UnrealMCP will auto-detect local UE5.3
# Builds will run locally instead of EC2
npm run orchestrator
```

---

## What are the cost implications?

### Development (Mock Mode):
- **Cost**: $0
- **Use for**: Testing workflows, agent development, schema validation

### Development (Cloud Builds):
- **EC2 g4dn.xlarge**: ~$0.50-$2.00 per build
- **S3 Storage**: ~$0.01/GB/month (artifacts expire after 30 days)
- **Total**: ~$5-20/day for active development

### Staging Environment:
- **GameLift**: 1 shard, 5 players = ~$10-20/day
- **DynamoDB**: ~$1-5/day
- **Other AWS services**: ~$5-10/day
- **Budget limit**: £100/day (configurable)

### Production (72-hour event):
- **GameLift**: 3 shards, 15 players each = ~£300-500
- **DynamoDB**: ~£50-100
- **Other AWS services**: ~£100-200
- **Total**: ~£500-800 for 72-hour event
- **Budget limit**: £1000 (default, configurable)

**See Requirement 7 and BudgetPolicy.schema.json for cost governance details.**

---

## How do I get started?

1. **Clone the repository**
2. **Install dependencies**: `npm install`
3. **Run in mock mode**: `export MCP_MOCK_MODE=true && npm run orchestrator`
4. **Create your first level**: Send natural language spec to orchestrator API
5. **Review the plan**: Orchestrator generates execution plan
6. **Approve and execute**: Plan runs with mock builds
7. **Test locally**: Run multiplayer test with mock GameLift

**See the Getting Started guide (Task 21.3) for detailed instructions.**

---

## Where can I find more information?

- **Requirements**: `.kiro/specs/unreal-vr-multiplayer-system/requirements.md`
- **Design**: `.kiro/specs/unreal-vr-multiplayer-system/design.md`
- **Tasks**: `.kiro/specs/unreal-vr-multiplayer-system/tasks.md`
- **Schemas**: `Specs/schemas/`
- **Examples**: `Specs/examples/`

---

**Last Updated**: January 31, 2026
