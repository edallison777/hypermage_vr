// Copyright 2026 HyperMage. All Rights Reserved.

#include "AwsSigV4.h"
#include "Misc/DateTime.h"
#include "Misc/SecureHash.h"   // FSHA256Hasher — no OpenSSL header conflict

// ── Crypto primitives (pure UE5, no direct OpenSSL includes) ─────────────────
//
// HMAC-SHA256 is implemented here using FSHA256Hasher so we never need to
// include ossl_typ.h, which redefines 'UI' and conflicts with UE5 Slate.
// Algorithm: https://www.rfc-editor.org/rfc/rfc2104

TArray<uint8> FAwsSigV4::Sha256Bytes(const TArray<uint8>& Data)
{
	FSHA256Hasher Hasher;
	Hasher.Update(Data.GetData(), static_cast<uint64>(Data.Num()));
	Hasher.Final();
	TArray<uint8> Out;
	Out.SetNumUninitialized(32);
	Hasher.GetHash(Out.GetData());
	return Out;
}

FString FAwsSigV4::Sha256Hex(const TArray<uint8>& Data)
{
	return ToHex(Sha256Bytes(Data));
}

TArray<uint8> FAwsSigV4::HmacSha256(const TArray<uint8>& Key, const TArray<uint8>& Message)
{
	constexpr int32 BlockSize = 64; // SHA-256 block size in bytes

	// Normalize key: hash it if longer than block size, then zero-pad to block size
	TArray<uint8> K;
	if (Key.Num() > BlockSize)
	{
		K = Sha256Bytes(Key);
	}
	else
	{
		K = Key;
	}
	K.SetNumZeroed(BlockSize); // pad to exactly 64 bytes

	// ipad / opad
	TArray<uint8> IKeyPad, OKeyPad;
	IKeyPad.SetNumUninitialized(BlockSize);
	OKeyPad.SetNumUninitialized(BlockSize);
	for (int32 i = 0; i < BlockSize; ++i)
	{
		IKeyPad[i] = K[i] ^ 0x36u;
		OKeyPad[i] = K[i] ^ 0x5Cu;
	}

	// Inner hash: SHA256(iKeyPad || Message)
	FSHA256Hasher InnerHasher;
	InnerHasher.Update(IKeyPad.GetData(), BlockSize);
	InnerHasher.Update(Message.GetData(), static_cast<uint64>(Message.Num()));
	InnerHasher.Final();
	TArray<uint8> InnerDigest;
	InnerDigest.SetNumUninitialized(32);
	InnerHasher.GetHash(InnerDigest.GetData());

	// Outer hash: SHA256(oKeyPad || InnerDigest)
	FSHA256Hasher OuterHasher;
	OuterHasher.Update(OKeyPad.GetData(), BlockSize);
	OuterHasher.Update(InnerDigest.GetData(), 32);
	OuterHasher.Final();
	TArray<uint8> Result;
	Result.SetNumUninitialized(32);
	OuterHasher.GetHash(Result.GetData());
	return Result;
}

FString FAwsSigV4::ToHex(const TArray<uint8>& Bytes)
{
	FString Out;
	Out.Reserve(Bytes.Num() * 2);
	for (uint8 B : Bytes)
	{
		Out += FString::Printf(TEXT("%02x"), B);
	}
	return Out;
}

TArray<uint8> FAwsSigV4::ToBytes(const FString& Str)
{
	FTCHARToUTF8 Conv(*Str);
	TArray<uint8> Out;
	Out.Append(reinterpret_cast<const uint8*>(Conv.Get()), Conv.Length());
	return Out;
}

// ── Public API ───────────────────────────────────────────────────────────────

bool FAwsSigV4::SignRequest(
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request,
	const TArray<uint8>& BodyBytes,
	const FString& Region,
	const FString& Service)
{
	// Read instance credentials from env vars (set automatically on EC2 by GameLift)
	FString AccessKeyId     = FPlatformMisc::GetEnvironmentVariable(TEXT("AWS_ACCESS_KEY_ID"));
	FString SecretAccessKey = FPlatformMisc::GetEnvironmentVariable(TEXT("AWS_SECRET_ACCESS_KEY"));
	FString SessionToken    = FPlatformMisc::GetEnvironmentVariable(TEXT("AWS_SESSION_TOKEN"));

	if (AccessKeyId.IsEmpty() || SecretAccessKey.IsEmpty())
	{
		UE_LOG(LogTemp, Warning, TEXT("AwsSigV4: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY not set — request unsigned"));
		return false;
	}

	// Timestamps
	FDateTime UtcNow = FDateTime::UtcNow();
	FString DateTimeStr = FString::Printf(TEXT("%04d%02d%02dT%02d%02d%02dZ"),
		UtcNow.GetYear(), UtcNow.GetMonth(), UtcNow.GetDay(),
		UtcNow.GetHour(), UtcNow.GetMinute(), UtcNow.GetSecond());
	FString DateStr = DateTimeStr.Left(8); // "YYYYMMDD"

	// Extract host and path from URL
	FString Url = Request->GetURL();
	FString Host;
	FString PathAndQuery;
	{
		int32 SchemeEnd = Url.Find(TEXT("://"), ESearchCase::CaseSensitive, ESearchDir::FromStart);
		FString AfterScheme = (SchemeEnd != INDEX_NONE) ? Url.Mid(SchemeEnd + 3) : Url;
		int32 SlashPos = AfterScheme.Find(TEXT("/"));
		Host         = (SlashPos != INDEX_NONE) ? AfterScheme.Left(SlashPos) : AfterScheme;
		PathAndQuery = (SlashPos != INDEX_NONE) ? AfterScheme.Mid(SlashPos)  : TEXT("/");
	}
	FString CanonicalUri;
	FString CanonicalQueryString;
	{
		int32 QPos = PathAndQuery.Find(TEXT("?"));
		CanonicalUri         = (QPos != INDEX_NONE) ? PathAndQuery.Left(QPos)    : PathAndQuery;
		CanonicalQueryString = (QPos != INDEX_NONE) ? PathAndQuery.Mid(QPos + 1) : TEXT("");
	}

	// Payload hash
	FString PayloadHash = Sha256Hex(BodyBytes);

	// Signed headers (sorted alphabetically)
	FString SignedHeaders;
	FString CanonicalHeaders;
	if (!SessionToken.IsEmpty())
	{
		CanonicalHeaders = FString::Printf(
			TEXT("content-type:application/json\nhost:%s\nx-amz-date:%s\nx-amz-security-token:%s\n"),
			*Host, *DateTimeStr, *SessionToken);
		SignedHeaders = TEXT("content-type;host;x-amz-date;x-amz-security-token");
	}
	else
	{
		CanonicalHeaders = FString::Printf(
			TEXT("content-type:application/json\nhost:%s\nx-amz-date:%s\n"),
			*Host, *DateTimeStr);
		SignedHeaders = TEXT("content-type;host;x-amz-date");
	}

	// Canonical request
	FString Verb = Request->GetVerb();
	FString CanonicalRequest = FString::Printf(
		TEXT("%s\n%s\n%s\n%s\n%s\n%s"),
		*Verb, *CanonicalUri, *CanonicalQueryString,
		*CanonicalHeaders, *SignedHeaders, *PayloadHash);

	// Credential scope
	FString CredentialScope = FString::Printf(TEXT("%s/%s/%s/aws4_request"),
		*DateStr, *Region, *Service);

	// String to sign
	FString HashedCanonical = Sha256Hex(ToBytes(CanonicalRequest));
	FString StringToSign = FString::Printf(TEXT("AWS4-HMAC-SHA256\n%s\n%s\n%s"),
		*DateTimeStr, *CredentialScope, *HashedCanonical);

	// Signing key: HMAC(HMAC(HMAC(HMAC("AWS4"+secret, date), region), service), "aws4_request")
	TArray<uint8> SigningKey = ToBytes(FString(TEXT("AWS4")) + SecretAccessKey);
	SigningKey = HmacSha256(SigningKey, ToBytes(DateStr));
	SigningKey = HmacSha256(SigningKey, ToBytes(Region));
	SigningKey = HmacSha256(SigningKey, ToBytes(Service));
	SigningKey = HmacSha256(SigningKey, ToBytes(TEXT("aws4_request")));

	FString Signature = ToHex(HmacSha256(SigningKey, ToBytes(StringToSign)));

	// Authorization header
	FString Authorization = FString::Printf(
		TEXT("AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s"),
		*AccessKeyId, *CredentialScope, *SignedHeaders, *Signature);

	// Apply headers
	Request->SetHeader(TEXT("x-amz-date"), DateTimeStr);
	Request->SetHeader(TEXT("Authorization"), Authorization);
	if (!SessionToken.IsEmpty())
	{
		Request->SetHeader(TEXT("x-amz-security-token"), SessionToken);
	}

	return true;
}
