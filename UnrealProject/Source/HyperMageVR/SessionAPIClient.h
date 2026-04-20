// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "UObject/NoExportTypes.h"
#include "Http.h"
#include "SessionManager.h"
#include "SessionAPIClient.generated.h"

/**
 * Session API Client
 * Posts session summaries and interaction events to the Session API.
 *
 * When EndpointURL is empty the client logs but does not transmit (safe for local testing).
 * When EndpointURL is set, requests are signed with SigV4 using instance credentials
 * (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN env vars set by GameLift).
 *
 * Failed requests (5xx or network error) are retried up to MaxRetries times with
 * exponential back-off (1 s, 2 s, 4 s). Client errors (4xx) are not retried.
 */
UCLASS()
class HYPERMAGEVR_API USessionAPIClient : public UObject
{
	GENERATED_BODY()

public:
	/**
	 * Send player session summary to Session API (fire-and-forget, async).
	 * @return true if the HTTP request was dispatched (or mock-logged)
	 */
	UFUNCTION(BlueprintCallable, Category = "Session API")
	bool SendSessionSummary(const FPlayerSessionSummary& Summary);

	/**
	 * Send an interaction event to Session API (fire-and-forget, async).
	 * @return true if dispatched (or mock-logged)
	 */
	UFUNCTION(BlueprintCallable, Category = "Session API")
	bool SendInteractionEvent(const FInteractionEvent& Event);

	/** Set the Session API base URL. Passing a non-empty URL disables mock mode. */
	UFUNCTION(BlueprintCallable, Category = "Session API")
	void SetEndpointURL(const FString& URL);

	UFUNCTION(BlueprintCallable, Category = "Session API")
	FString GetEndpointURL() const { return EndpointURL; }

	/** AWS region for SigV4 signing (default: eu-west-1). */
	UFUNCTION(BlueprintCallable, Category = "Session API")
	void SetAwsRegion(const FString& Region) { AwsRegion = Region; }

	/** Maximum number of retry attempts on 5xx / network error (1 s → 2 s → 4 s back-off). */
	static constexpr int32 MaxRetries = 3;

protected:
	UPROPERTY()
	FString EndpointURL;

	UPROPERTY()
	FString AwsRegion = TEXT("eu-west-1");

private:
	/** Dispatch a signed POST; retries on transient failure up to MaxRetries. */
	bool PostSigned(const FString& Path, const FString& JsonBody, int32 Attempt = 0);

	void OnPostComplete(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bSuccess,
	                    FString Path, FString Body, int32 Attempt);
};
