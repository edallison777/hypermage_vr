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

protected:
	UPROPERTY()
	FString EndpointURL;

	UPROPERTY()
	FString AwsRegion = TEXT("eu-west-1");

private:
	/** Dispatch a signed POST and log on completion. Returns true if sent. */
	bool PostSigned(const FString& Path, const FString& JsonBody);

	void OnPostComplete(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bSuccess, FString Path);
};
