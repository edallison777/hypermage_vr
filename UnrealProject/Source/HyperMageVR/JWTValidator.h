// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "UObject/NoExportTypes.h"
#include "JWTValidator.generated.h"

/**
 * JWT Token Claims
 */
USTRUCT(BlueprintType)
struct FJWTClaims
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "JWT")
	FString Subject; // "sub" - Player ID

	UPROPERTY(BlueprintReadOnly, Category = "JWT")
	FString Issuer; // "iss" - Cognito issuer

	UPROPERTY(BlueprintReadOnly, Category = "JWT")
	FString Audience; // "aud" - Client ID

	UPROPERTY(BlueprintReadOnly, Category = "JWT")
	int64 ExpirationTime; // "exp" - Unix timestamp

	UPROPERTY(BlueprintReadOnly, Category = "JWT")
	int64 IssuedAt; // "iat" - Unix timestamp

	UPROPERTY(BlueprintReadOnly, Category = "JWT")
	FString TokenUse; // "token_use" - "access" or "id"

	UPROPERTY(BlueprintReadOnly, Category = "JWT")
	FString Username; // "cognito:username"

	UPROPERTY(BlueprintReadOnly, Category = "JWT")
	TArray<FString> Groups; // "cognito:groups"
};

/**
 * JWT Validation Result
 */
USTRUCT(BlueprintType)
struct FJWTValidationResult
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "JWT")
	bool bIsValid = false;

	UPROPERTY(BlueprintReadOnly, Category = "JWT")
	FString ErrorMessage;

	UPROPERTY(BlueprintReadOnly, Category = "JWT")
	FJWTClaims Claims;
};

/**
 * JWT Validator for Cognito tokens
 * Implements Requirements 3.1-3.4: JWT-based authentication
 */
UCLASS()
class HYPERMAGEVR_API UJWTValidator : public UObject
{
	GENERATED_BODY()

public:
	/**
	 * Validate a JWT token from AWS Cognito
	 * @param Token The JWT token string
	 * @param OutResult Validation result with claims if successful
	 * @return True if token is valid
	 */
	UFUNCTION(BlueprintCallable, Category = "Authentication")
	static bool ValidateToken(const FString& Token, FJWTValidationResult& OutResult);

	/**
	 * Decode JWT token without validation (for development/testing)
	 * @param Token The JWT token string
	 * @param OutClaims Decoded claims
	 * @return True if token could be decoded
	 */
	UFUNCTION(BlueprintCallable, Category = "Authentication")
	static bool DecodeToken(const FString& Token, FJWTClaims& OutClaims);

	/**
	 * Check if token is expired
	 * @param ExpirationTime Unix timestamp from token
	 * @return True if token is expired
	 */
	UFUNCTION(BlueprintCallable, Category = "Authentication")
	static bool IsTokenExpired(int64 ExpirationTime);

	/**
	 * Set Cognito configuration for validation
	 * @param UserPoolId AWS Cognito User Pool ID
	 * @param Region AWS Region (e.g., "eu-west-1")
	 * @param ClientId App Client ID
	 */
	UFUNCTION(BlueprintCallable, Category = "Authentication")
	static void SetCognitoConfig(const FString& UserPoolId, const FString& Region, const FString& ClientId);

protected:
	// Parse JWT token into header, payload, signature
	static bool ParseToken(const FString& Token, FString& OutHeader, FString& OutPayload, FString& OutSignature);

	// Decode Base64URL encoded string
	static bool DecodeBase64URL(const FString& Input, FString& OutDecoded);

	// Parse JSON claims from payload
	static bool ParseClaims(const FString& PayloadJson, FJWTClaims& OutClaims);

	// Verify token signature (requires Cognito public keys)
	static bool VerifySignature(const FString& Header, const FString& Payload, const FString& Signature);

	// Validate token claims
	static bool ValidateClaims(const FJWTClaims& Claims, FString& OutErrorMessage);

private:
	// Cognito configuration
	static FString CognitoUserPoolId;
	static FString CognitoRegion;
	static FString CognitoClientId;
	static FString CognitoIssuer;
};
