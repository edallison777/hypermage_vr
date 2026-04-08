// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Interfaces/IHttpRequest.h"

/**
 * Minimal AWS SigV4 signer for server-to-server API Gateway calls.
 *
 * Usage (GameLift EC2 instances):
 *   Credentials are read from environment variables automatically set by the
 *   EC2 instance profile:
 *     AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
 *
 *   FAwsSigV4::SignRequest(HttpRequest, BodyBytes, "eu-west-1", "execute-api");
 *
 * Implements: https://docs.aws.amazon.com/general/latest/gr/sigv4_signing.html
 */
class HYPERMAGEVR_API FAwsSigV4
{
public:
	/**
	 * Sign an outgoing HTTP request with AWS SigV4.
	 * Adds Authorization, x-amz-date, and (if present) x-amz-security-token headers.
	 *
	 * @param Request     The prepared HTTP request (URL and verb already set)
	 * @param BodyBytes   Raw UTF-8 body bytes (used for payload hash)
	 * @param Region      AWS region, e.g. "eu-west-1"
	 * @param Service     AWS service name, e.g. "execute-api"
	 * @return true if credentials were found and signing succeeded
	 */
	static bool SignRequest(
		TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request,
		const TArray<uint8>& BodyBytes,
		const FString& Region,
		const FString& Service
	);

private:
	// Crypto primitives — self-contained SHA-256 (no OpenSSL or external headers)
	static TArray<uint8> Sha256Bytes(const TArray<uint8>& Data);
	static FString       Sha256Hex(const TArray<uint8>& Data);
	static TArray<uint8> HmacSha256(const TArray<uint8>& Key, const TArray<uint8>& Message);

	// SigV4 helpers
	static FString       ToHex(const TArray<uint8>& Bytes);
	static TArray<uint8> ToBytes(const FString& Str);   // UTF-8
};
