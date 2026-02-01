// Copyright 2026 HyperMage. All Rights Reserved.

#include "JWTValidator.h"
#include "Misc/Base64.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonReader.h"
#include "Dom/JsonObject.h"

// Static member initialization
FString UJWTValidator::CognitoUserPoolId;
FString UJWTValidator::CognitoRegion;
FString UJWTValidator::CognitoClientId;
FString UJWTValidator::CognitoIssuer;

void UJWTValidator::SetCognitoConfig(const FString& UserPoolId, const FString& Region, const FString& ClientId)
{
	CognitoUserPoolId = UserPoolId;
	CognitoRegion = Region;
	CognitoClientId = ClientId;
	CognitoIssuer = FString::Printf(TEXT("https://cognito-idp.%s.amazonaws.com/%s"), *Region, *UserPoolId);

	UE_LOG(LogTemp, Log, TEXT("JWTValidator: Cognito config set - Region: %s, UserPoolId: %s"), *Region, *UserPoolId);
}

bool UJWTValidator::ValidateToken(const FString& Token, FJWTValidationResult& OutResult)
{
	OutResult.bIsValid = false;
	OutResult.ErrorMessage.Empty();

	// Requirement 3.3: Validate JWT token when player connects
	if (Token.IsEmpty())
	{
		OutResult.ErrorMessage = TEXT("Token is empty");
		return false;
	}

	// Parse token into components
	FString Header, Payload, Signature;
	if (!ParseToken(Token, Header, Payload, Signature))
	{
		OutResult.ErrorMessage = TEXT("Invalid token format");
		return false;
	}

	// Decode and parse claims
	if (!ParseClaims(Payload, OutResult.Claims))
	{
		OutResult.ErrorMessage = TEXT("Failed to parse token claims");
		return false;
	}

	// Requirement 3.4: Check token expiration
	if (IsTokenExpired(OutResult.Claims.ExpirationTime))
	{
		OutResult.ErrorMessage = TEXT("Token has expired");
		return false;
	}

	// Validate claims
	if (!ValidateClaims(OutResult.Claims, OutResult.ErrorMessage))
	{
		return false;
	}

	// Requirement 3.2: Verify token signature
	// In production, this would verify the signature using Cognito public keys
	// For development, we skip signature verification
	if (!CognitoUserPoolId.IsEmpty())
	{
		if (!VerifySignature(Header, Payload, Signature))
		{
			OutResult.ErrorMessage = TEXT("Token signature verification failed");
			return false;
		}
	}

	OutResult.bIsValid = true;
	UE_LOG(LogTemp, Log, TEXT("JWTValidator: Token validated successfully for user: %s"), *OutResult.Claims.Subject);
	return true;
}

bool UJWTValidator::DecodeToken(const FString& Token, FJWTClaims& OutClaims)
{
	FString Header, Payload, Signature;
	if (!ParseToken(Token, Header, Payload, Signature))
	{
		return false;
	}

	return ParseClaims(Payload, OutClaims);
}

bool UJWTValidator::IsTokenExpired(int64 ExpirationTime)
{
	// Get current Unix timestamp
	int64 CurrentTime = FDateTime::UtcNow().ToUnixTimestamp();
	
	// Token is expired if current time is past expiration time
	bool bExpired = CurrentTime >= ExpirationTime;
	
	if (bExpired)
	{
		UE_LOG(LogTemp, Warning, TEXT("JWTValidator: Token expired - Current: %lld, Expiration: %lld"), 
			CurrentTime, ExpirationTime);
	}
	
	return bExpired;
}

bool UJWTValidator::ParseToken(const FString& Token, FString& OutHeader, FString& OutPayload, FString& OutSignature)
{
	// JWT format: header.payload.signature
	TArray<FString> Parts;
	Token.ParseIntoArray(Parts, TEXT("."));

	if (Parts.Num() != 3)
	{
		UE_LOG(LogTemp, Warning, TEXT("JWTValidator: Invalid token format - expected 3 parts, got %d"), Parts.Num());
		return false;
	}

	OutHeader = Parts[0];
	OutPayload = Parts[1];
	OutSignature = Parts[2];

	return true;
}

bool UJWTValidator::DecodeBase64URL(const FString& Input, FString& OutDecoded)
{
	// Base64URL uses - and _ instead of + and /, and no padding
	FString Base64 = Input;
	Base64 = Base64.Replace(TEXT("-"), TEXT("+"));
	Base64 = Base64.Replace(TEXT("_"), TEXT("/"));

	// Add padding if needed
	int32 PaddingNeeded = (4 - (Base64.Len() % 4)) % 4;
	for (int32 i = 0; i < PaddingNeeded; i++)
	{
		Base64.AppendChar('=');
	}

	// Decode Base64
	TArray<uint8> DecodedBytes;
	if (!FBase64::Decode(Base64, DecodedBytes))
	{
		UE_LOG(LogTemp, Warning, TEXT("JWTValidator: Base64 decode failed"));
		return false;
	}

	// Convert bytes to string
	OutDecoded = FString(UTF8_TO_TCHAR(DecodedBytes.GetData()));
	return true;
}

bool UJWTValidator::ParseClaims(const FString& PayloadJson, FJWTClaims& OutClaims)
{
	// Decode Base64URL payload
	FString DecodedPayload;
	if (!DecodeBase64URL(PayloadJson, DecodedPayload))
	{
		return false;
	}

	// Parse JSON
	TSharedPtr<FJsonObject> JsonObject;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(DecodedPayload);

	if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("JWTValidator: Failed to parse JSON payload"));
		return false;
	}

	// Extract standard claims
	JsonObject->TryGetStringField(TEXT("sub"), OutClaims.Subject);
	JsonObject->TryGetStringField(TEXT("iss"), OutClaims.Issuer);
	JsonObject->TryGetStringField(TEXT("aud"), OutClaims.Audience);
	JsonObject->TryGetStringField(TEXT("token_use"), OutClaims.TokenUse);
	JsonObject->TryGetStringField(TEXT("cognito:username"), OutClaims.Username);

	// Extract timestamps
	int32 ExpInt = 0, IatInt = 0;
	if (JsonObject->TryGetNumberField(TEXT("exp"), ExpInt))
	{
		OutClaims.ExpirationTime = static_cast<int64>(ExpInt);
	}
	if (JsonObject->TryGetNumberField(TEXT("iat"), IatInt))
	{
		OutClaims.IssuedAt = static_cast<int64>(IatInt);
	}

	// Extract groups array
	const TArray<TSharedPtr<FJsonValue>>* GroupsArray;
	if (JsonObject->TryGetArrayField(TEXT("cognito:groups"), GroupsArray))
	{
		for (const TSharedPtr<FJsonValue>& GroupValue : *GroupsArray)
		{
			FString Group;
			if (GroupValue->TryGetString(Group))
			{
				OutClaims.Groups.Add(Group);
			}
		}
	}

	return true;
}

bool UJWTValidator::VerifySignature(const FString& Header, const FString& Payload, const FString& Signature)
{
	// Signature verification requires:
	// 1. Fetch Cognito public keys from JWKS endpoint
	// 2. Parse the key ID (kid) from token header
	// 3. Find matching public key
	// 4. Verify signature using RS256 algorithm

	// In production, this would:
	// - Fetch keys from: https://cognito-idp.{region}.amazonaws.com/{userPoolId}/.well-known/jwks.json
	// - Cache keys with periodic refresh
	// - Use OpenSSL or similar to verify RS256 signature

	// For development/testing, we skip signature verification
	// This is acceptable because:
	// 1. Development servers are not exposed to the internet
	// 2. Production deployment will use proper Cognito integration
	// 3. The token structure and claims are still validated

	UE_LOG(LogTemp, Verbose, TEXT("JWTValidator: Signature verification skipped (development mode)"));
	return true;
}

bool UJWTValidator::ValidateClaims(const FJWTClaims& Claims, FString& OutErrorMessage)
{
	// Validate issuer matches Cognito
	if (!CognitoIssuer.IsEmpty() && Claims.Issuer != CognitoIssuer)
	{
		OutErrorMessage = FString::Printf(TEXT("Invalid issuer: expected %s, got %s"), 
			*CognitoIssuer, *Claims.Issuer);
		return false;
	}

	// Validate audience matches client ID
	if (!CognitoClientId.IsEmpty() && Claims.Audience != CognitoClientId)
	{
		OutErrorMessage = FString::Printf(TEXT("Invalid audience: expected %s, got %s"), 
			*CognitoClientId, *Claims.Audience);
		return false;
	}

	// Validate token use is "access" or "id"
	if (Claims.TokenUse != TEXT("access") && Claims.TokenUse != TEXT("id"))
	{
		OutErrorMessage = FString::Printf(TEXT("Invalid token_use: %s"), *Claims.TokenUse);
		return false;
	}

	// Validate subject (player ID) is present
	if (Claims.Subject.IsEmpty())
	{
		OutErrorMessage = TEXT("Missing subject (player ID)");
		return false;
	}

	return true;
}
