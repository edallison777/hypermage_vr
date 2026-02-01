// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "UObject/NoExportTypes.h"
#include "SessionManager.h"
#include "SessionAPIClient.generated.h"

/**
 * Session API Client (Stub Interface)
 * Actual Session API implementation is in Task 15.4
 * This provides a stub for Task 13.3
 */
UCLASS()
class HYPERMAGEVR_API USessionAPIClient : public UObject
{
	GENERATED_BODY()

public:
	/**
	 * Send player session summary to Session API
	 * @param Summary The session summary
	 * @return True if successful
	 */
	UFUNCTION(BlueprintCallable, Category = "Session API")
	bool SendSessionSummary(const FPlayerSessionSummary& Summary);

	/**
	 * Send interaction event to Session API
	 * @param Event The interaction event
	 * @return True if successful
	 */
	UFUNCTION(BlueprintCallable, Category = "Session API")
	bool SendInteractionEvent(const FInteractionEvent& Event);

	/**
	 * Set API endpoint URL
	 * @param URL The API endpoint URL
	 */
	UFUNCTION(BlueprintCallable, Category = "Session API")
	void SetEndpointURL(const FString& URL);

	/**
	 * Get API endpoint URL
	 * @return The API endpoint URL
	 */
	UFUNCTION(BlueprintCallable, Category = "Session API")
	FString GetEndpointURL() const { return EndpointURL; }

protected:
	// API endpoint URL
	UPROPERTY()
	FString EndpointURL;

	// Mock mode flag
	bool bMockMode = true;
};
