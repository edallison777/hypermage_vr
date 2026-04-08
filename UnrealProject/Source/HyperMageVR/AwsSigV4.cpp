// Copyright 2026 HyperMage. All Rights Reserved.

#include "AwsSigV4.h"
#include "Misc/DateTime.h"
// No OpenSSL or FSHA256Hasher — SHA-256 is implemented below to avoid
// the ossl_typ.h 'UI' typedef conflict with UE5 Slate headers.

// ── Self-contained SHA-256 (FIPS 180-4) ──────────────────────────────────────

namespace
{
	FORCEINLINE uint32 RR32(uint32 V, int N) { return (V >> N) | (V << (32 - N)); }

	static const uint32 SHA256K[64] = {
		0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,
		0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
		0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,
		0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
		0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,
		0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
		0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,
		0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
		0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,
		0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
		0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,
		0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
		0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,
		0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
		0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,
		0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u
	};

	static void SHA256Block(uint32 H[8], const uint8* B)
	{
		uint32 W[64];
		for (int i = 0; i < 16; ++i)
			W[i] = (uint32(B[i*4])<<24)|(uint32(B[i*4+1])<<16)|(uint32(B[i*4+2])<<8)|uint32(B[i*4+3]);
		for (int i = 16; i < 64; ++i)
		{
			uint32 s0 = RR32(W[i-15],7)^RR32(W[i-15],18)^(W[i-15]>>3);
			uint32 s1 = RR32(W[i-2],17)^RR32(W[i-2],19) ^(W[i-2]>>10);
			W[i] = W[i-16]+s0+W[i-7]+s1;
		}
		uint32 a=H[0],b=H[1],c=H[2],d=H[3],e=H[4],f=H[5],g=H[6],h=H[7];
		for (int i = 0; i < 64; ++i)
		{
			uint32 S1  = RR32(e,6)^RR32(e,11)^RR32(e,25);
			uint32 ch  = (e&f)^(~e&g);
			uint32 t1  = h+S1+ch+SHA256K[i]+W[i];
			uint32 S0  = RR32(a,2)^RR32(a,13)^RR32(a,22);
			uint32 maj = (a&b)^(a&c)^(b&c);
			uint32 t2  = S0+maj;
			h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
		}
		H[0]+=a; H[1]+=b; H[2]+=c; H[3]+=d;
		H[4]+=e; H[5]+=f; H[6]+=g; H[7]+=h;
	}

	static void ComputeSHA256(const uint8* Data, int32 Len, uint8 Out[32])
	{
		uint32 H[8] = {
			0x6a09e667u,0xbb67ae85u,0x3c6ef372u,0xa54ff53au,
			0x510e527fu,0x9b05688cu,0x1f83d9abu,0x5be0cd19u
		};
		// Pad: append 0x80, zeros, 64-bit big-endian bit length
		int32 PadLen = ((Len + 8) / 64 + 1) * 64;
		TArray<uint8> Msg;
		Msg.SetNumZeroed(PadLen);
		FMemory::Memcpy(Msg.GetData(), Data, Len);
		Msg[Len] = 0x80u;
		uint64 Bits = uint64(Len) * 8;
		for (int i = 0; i < 8; ++i)
			Msg[PadLen-8+i] = uint8(Bits >> (56-i*8));
		for (int32 Off = 0; Off < PadLen; Off += 64)
			SHA256Block(H, Msg.GetData()+Off);
		for (int i = 0; i < 8; ++i)
		{
			Out[i*4+0]=uint8(H[i]>>24); Out[i*4+1]=uint8(H[i]>>16);
			Out[i*4+2]=uint8(H[i]>> 8); Out[i*4+3]=uint8(H[i]);
		}
	}
} // anonymous namespace

// ── Crypto primitives ────────────────────────────────────────────────────────

TArray<uint8> FAwsSigV4::Sha256Bytes(const TArray<uint8>& Data)
{
	TArray<uint8> Out;
	Out.SetNumUninitialized(32);
	ComputeSHA256(Data.GetData(), Data.Num(), Out.GetData());
	return Out;
}

FString FAwsSigV4::Sha256Hex(const TArray<uint8>& Data)
{
	return ToHex(Sha256Bytes(Data));
}

TArray<uint8> FAwsSigV4::HmacSha256(const TArray<uint8>& Key, const TArray<uint8>& Message)
{
	constexpr int32 BlockSize = 64;

	// Normalise key
	TArray<uint8> K;
	if (Key.Num() > BlockSize) K = Sha256Bytes(Key); else K = Key;
	K.SetNumZeroed(BlockSize);

	TArray<uint8> IKeyPad, OKeyPad;
	IKeyPad.SetNumUninitialized(BlockSize);
	OKeyPad.SetNumUninitialized(BlockSize);
	for (int32 i = 0; i < BlockSize; ++i)
	{
		IKeyPad[i] = K[i] ^ 0x36u;
		OKeyPad[i] = K[i] ^ 0x5Cu;
	}

	// Inner: SHA256(iKeyPad || Message)
	TArray<uint8> Inner;
	Inner.Append(IKeyPad);
	Inner.Append(Message);
	TArray<uint8> InnerDigest = Sha256Bytes(Inner);

	// Outer: SHA256(oKeyPad || InnerDigest)
	TArray<uint8> Outer;
	Outer.Append(OKeyPad);
	Outer.Append(InnerDigest);
	return Sha256Bytes(Outer);
}

FString FAwsSigV4::ToHex(const TArray<uint8>& Bytes)
{
	FString Out;
	Out.Reserve(Bytes.Num() * 2);
	for (uint8 B : Bytes)
		Out += FString::Printf(TEXT("%02x"), B);
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
	FString AccessKeyId     = FPlatformMisc::GetEnvironmentVariable(TEXT("AWS_ACCESS_KEY_ID"));
	FString SecretAccessKey = FPlatformMisc::GetEnvironmentVariable(TEXT("AWS_SECRET_ACCESS_KEY"));
	FString SessionToken    = FPlatformMisc::GetEnvironmentVariable(TEXT("AWS_SESSION_TOKEN"));

	if (AccessKeyId.IsEmpty() || SecretAccessKey.IsEmpty())
	{
		UE_LOG(LogTemp, Warning, TEXT("AwsSigV4: credentials not set — request unsigned"));
		return false;
	}

	FDateTime UtcNow = FDateTime::UtcNow();
	FString DateTimeStr = FString::Printf(TEXT("%04d%02d%02dT%02d%02d%02dZ"),
		UtcNow.GetYear(), UtcNow.GetMonth(), UtcNow.GetDay(),
		UtcNow.GetHour(), UtcNow.GetMinute(), UtcNow.GetSecond());
	FString DateStr = DateTimeStr.Left(8);

	// Extract host and path
	FString Url = Request->GetURL();
	FString Host, PathAndQuery;
	{
		int32 SchemeEnd = Url.Find(TEXT("://"), ESearchCase::CaseSensitive, ESearchDir::FromStart);
		FString After = (SchemeEnd != INDEX_NONE) ? Url.Mid(SchemeEnd + 3) : Url;
		int32 Slash = After.Find(TEXT("/"));
		Host         = (Slash != INDEX_NONE) ? After.Left(Slash) : After;
		PathAndQuery = (Slash != INDEX_NONE) ? After.Mid(Slash)  : TEXT("/");
	}
	FString CanonUri, CanonQuery;
	{
		int32 Q = PathAndQuery.Find(TEXT("?"));
		CanonUri   = (Q != INDEX_NONE) ? PathAndQuery.Left(Q)    : PathAndQuery;
		CanonQuery = (Q != INDEX_NONE) ? PathAndQuery.Mid(Q + 1) : TEXT("");
	}

	FString PayloadHash = Sha256Hex(BodyBytes);

	FString SignedHeaders, CanonHeaders;
	if (!SessionToken.IsEmpty())
	{
		CanonHeaders  = FString::Printf(TEXT("content-type:application/json\nhost:%s\nx-amz-date:%s\nx-amz-security-token:%s\n"),
			*Host, *DateTimeStr, *SessionToken);
		SignedHeaders = TEXT("content-type;host;x-amz-date;x-amz-security-token");
	}
	else
	{
		CanonHeaders  = FString::Printf(TEXT("content-type:application/json\nhost:%s\nx-amz-date:%s\n"),
			*Host, *DateTimeStr);
		SignedHeaders = TEXT("content-type;host;x-amz-date");
	}

	FString CanonRequest = FString::Printf(TEXT("%s\n%s\n%s\n%s\n%s\n%s"),
		*Request->GetVerb(), *CanonUri, *CanonQuery,
		*CanonHeaders, *SignedHeaders, *PayloadHash);

	FString CredScope = FString::Printf(TEXT("%s/%s/%s/aws4_request"), *DateStr, *Region, *Service);
	FString StringToSign = FString::Printf(TEXT("AWS4-HMAC-SHA256\n%s\n%s\n%s"),
		*DateTimeStr, *CredScope, *Sha256Hex(ToBytes(CanonRequest)));

	TArray<uint8> SignKey = ToBytes(FString(TEXT("AWS4")) + SecretAccessKey);
	SignKey = HmacSha256(SignKey, ToBytes(DateStr));
	SignKey = HmacSha256(SignKey, ToBytes(Region));
	SignKey = HmacSha256(SignKey, ToBytes(Service));
	SignKey = HmacSha256(SignKey, ToBytes(TEXT("aws4_request")));

	FString Sig = ToHex(HmacSha256(SignKey, ToBytes(StringToSign)));

	Request->SetHeader(TEXT("x-amz-date"), DateTimeStr);
	Request->SetHeader(TEXT("Authorization"),
		FString::Printf(TEXT("AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s"),
			*AccessKeyId, *CredScope, *SignedHeaders, *Sig));
	if (!SessionToken.IsEmpty())
		Request->SetHeader(TEXT("x-amz-security-token"), SessionToken);

	return true;
}
