# Cognito User Pools Terraform Module

This Terraform module provisions Amazon Cognito User Pools for JWT-based player authentication in the Unreal VR Multiplayer System.

## Overview

The module creates:
- **User Pool**: Manages player accounts and authentication
- **User Pool Domain**: Hosted UI for authentication flows
- **App Clients**: Game client and admin client configurations
- **Identity Pool**: AWS resource access for authenticated users
- **IAM Roles**: Permissions for authenticated users
- **CloudWatch Monitoring**: Metrics and alarms for authentication

## Features

- **JWT Authentication**: Industry-standard token-based auth
- **Email/Password**: Simple username/password authentication
- **MFA Support**: Optional multi-factor authentication
- **Token Management**: 1h access tokens, 7d refresh tokens
- **Custom Attributes**: Player ID and skill level tracking
- **Advanced Security**: Adaptive authentication and risk detection
- **OAuth 2.0**: Standard OAuth flows for web/mobile

## Prerequisites

None - this module is self-contained.

## Usage

```hcl
module "cognito" {
  source = "./modules/cognito"

  project_name = "hypermage-vr"
  environment  = "dev"
  aws_region   = "eu-west-1"

  # Token validity (1h access, 7d refresh)
  access_token_validity_hours  = 1
  id_token_validity_hours      = 1
  refresh_token_validity_days  = 7

  # MFA configuration
  mfa_configuration = "OPTIONAL"

  # Security
  advanced_security_mode = "AUDIT"
  deletion_protection    = "INACTIVE"

  # OAuth callbacks
  callback_urls = [
    "http://localhost:3000/callback",
    "hypermage://callback"
  ]

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
| username_attributes | Username attributes | list(string) | ["email"] | no |
| auto_verified_attributes | Auto-verify attributes | list(string) | ["email"] | no |
| password_minimum_length | Min password length | number | 8 | no |
| password_require_lowercase | Require lowercase | bool | true | no |
| password_require_uppercase | Require uppercase | bool | true | no |
| password_require_numbers | Require numbers | bool | true | no |
| password_require_symbols | Require symbols | bool | false | no |
| mfa_configuration | MFA mode | string | "OPTIONAL" | no |
| advanced_security_mode | Security mode | string | "AUDIT" | no |
| deletion_protection | Deletion protection | string | "INACTIVE" | no |
| access_token_validity_hours | Access token validity | number | 1 | no |
| id_token_validity_hours | ID token validity | number | 1 | no |
| refresh_token_validity_days | Refresh token validity | number | 7 | no |
| callback_urls | OAuth callback URLs | list(string) | ["http://localhost:3000/callback"] | no |
| logout_urls | OAuth logout URLs | list(string) | ["http://localhost:3000/logout"] | no |
| log_retention_days | Log retention days | number | 30 | no |
| failed_sign_in_threshold | Failed sign-in threshold | number | 10 | no |
| alarm_sns_topic_arns | Alarm SNS topics | list(string) | [] | no |
| tags | Additional tags | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| user_pool_id | Cognito User Pool ID |
| user_pool_arn | Cognito User Pool ARN |
| user_pool_endpoint | User Pool endpoint |
| user_pool_domain | User Pool domain |
| game_client_id | Game app client ID |
| admin_client_id | Admin app client ID (sensitive) |
| admin_client_secret | Admin client secret (sensitive) |
| identity_pool_id | Identity Pool ID |
| authenticated_role_arn | Authenticated IAM role ARN |
| jwks_uri | JWKS URI for JWT validation |
| issuer | JWT token issuer |

## Custom Attributes

Players have these custom attributes:

### player_id (String)
- Unique player identifier
- Mutable
- Used for cross-referencing with game data

### skill_level (Number)
- Player skill rating (0-20)
- Mutable
- Used for matchmaking

## Token Configuration

### Access Token
- **Validity**: 1 hour
- **Purpose**: API authentication
- **Contains**: User claims, custom attributes
- **Usage**: Include in Authorization header

### ID Token
- **Validity**: 1 hour
- **Purpose**: User identity information
- **Contains**: User profile, email, custom attributes
- **Usage**: Client-side user info

### Refresh Token
- **Validity**: 7 days
- **Purpose**: Obtain new access/ID tokens
- **Usage**: Refresh expired tokens without re-authentication

## Authentication Flow

### Sign Up

```typescript
import { CognitoIdentityProviderClient, SignUpCommand } from "@aws-sdk/client-cognito-identity-provider";

const client = new CognitoIdentityProviderClient({ region: "eu-west-1" });

const response = await client.send(new SignUpCommand({
  ClientId: "your-game-client-id",
  Username: "player@example.com",
  Password: "SecurePassword123",
  UserAttributes: [
    { Name: "email", Value: "player@example.com" },
    { Name: "custom:player_id", Value: "player-123" },
    { Name: "custom:skill_level", Value: "10" }
  ]
}));
```

### Sign In

```typescript
import { InitiateAuthCommand } from "@aws-sdk/client-cognito-identity-provider";

const response = await client.send(new InitiateAuthCommand({
  ClientId: "your-game-client-id",
  AuthFlow: "USER_PASSWORD_AUTH",
  AuthParameters: {
    USERNAME: "player@example.com",
    PASSWORD: "SecurePassword123"
  }
}));

const accessToken = response.AuthenticationResult.AccessToken;
const idToken = response.AuthenticationResult.IdToken;
const refreshToken = response.AuthenticationResult.RefreshToken;
```

### Refresh Tokens

```typescript
const response = await client.send(new InitiateAuthCommand({
  ClientId: "your-game-client-id",
  AuthFlow: "REFRESH_TOKEN_AUTH",
  AuthParameters: {
    REFRESH_TOKEN: refreshToken
  }
}));

const newAccessToken = response.AuthenticationResult.AccessToken;
```

## JWT Token Validation

### In Unreal Engine (C++)

The JWT validator (from Task 11.2) validates tokens:

```cpp
// JWTValidator.cpp validates:
// 1. Token signature using JWKS
// 2. Token expiration
// 3. Token issuer
// 4. Token audience (client ID)

bool UJWTValidator::ValidateToken(const FString& Token)
{
    // Fetch JWKS from Cognito
    FString JwksUri = "https://cognito-idp.eu-west-1.amazonaws.com/USER_POOL_ID/.well-known/jwks.json";
    
    // Validate signature, expiration, issuer
    // Extract player_id from custom claims
    
    return IsValid;
}
```

### JWKS Endpoint

```
https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json
```

## MFA Configuration

### OPTIONAL (Default)
- Users can enable MFA if desired
- Not required for authentication
- Recommended for production

### ON
- All users must use MFA
- Higher security
- May impact user experience

### OFF
- No MFA support
- Faster authentication
- Lower security

## Advanced Security

### AUDIT Mode (Default)
- Monitors for suspicious activity
- Logs security events
- No blocking
- Recommended for development

### ENFORCED Mode
- Blocks suspicious activity
- Adaptive authentication
- Risk-based challenges
- Recommended for production

## Cost Estimation

Cognito pricing:
- **MAU (Monthly Active Users)**: First 50,000 free, then $0.0055/MAU
- **Advanced Security**: $0.05/MAU (if enabled)

**Example:**
- 1,000 active players/month
- Advanced Security in AUDIT mode
- Cost: Free (under 50,000 MAU threshold)

Very cost-effective for authentication!

## Integration with GameLift

Players must authenticate before matchmaking:

```typescript
// 1. Sign in to Cognito
const authResponse = await cognito.signIn(username, password);
const accessToken = authResponse.AccessToken;

// 2. Start matchmaking with authenticated token
const matchResponse = await gamelift.startMatchmaking({
  ConfigurationName: "hypermage-vr-dev",
  Players: [{
    PlayerId: extractPlayerIdFromToken(accessToken),
    PlayerAttributes: {
      skill: { N: extractSkillFromToken(accessToken) }
    }
  }]
});
```

## Security Best Practices

- **HTTPS Only**: Always use HTTPS for authentication
- **Token Storage**: Store tokens securely (encrypted storage)
- **Token Rotation**: Refresh tokens before expiration
- **MFA**: Enable MFA for production
- **Advanced Security**: Use ENFORCED mode in production
- **Rate Limiting**: Implement client-side rate limiting
- **Monitoring**: Alert on failed authentication attempts

## Monitoring

### CloudWatch Metrics

- `UserAuthenticationSuccess`: Successful sign-ins
- `UserAuthenticationFailure`: Failed sign-ins
- `TokenRefreshSuccess`: Successful token refreshes
- `TokenRefreshFailure`: Failed token refreshes

### CloudWatch Alarms

1. **Failed Sign-Ins**: Alerts when >10 failures in 5 minutes

## Troubleshooting

**Users can't sign in:**
- Verify email is confirmed
- Check password meets policy requirements
- Verify user pool is active
- Check CloudWatch logs for errors

**JWT validation fails:**
- Verify JWKS URI is correct
- Check token hasn't expired
- Verify issuer matches user pool
- Ensure client ID is correct

**High authentication costs:**
- Review MAU count
- Disable advanced security if not needed
- Implement client-side caching

**MFA issues:**
- Verify MFA configuration
- Check user has MFA device registered
- Test with TOTP app (Google Authenticator, Authy)

## Next Steps

After deploying Cognito:

1. Create test users for development
2. Integrate with Unreal Engine client
3. Test authentication flow end-to-end
4. Configure production security settings
5. Set up monitoring and alerting

## Support

For issues or questions:
- Check Cognito User Pool events in AWS Console
- Review CloudWatch logs for authentication errors
- Consult AWS Cognito documentation
- Test with AWS Amplify for rapid prototyping
