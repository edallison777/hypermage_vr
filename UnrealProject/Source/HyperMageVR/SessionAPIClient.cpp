// Copyright 2026 HyperMage. All Rights Reserved.

#include "SessionAPIClient.h"
#include "AwsSigV4.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonSerializer.h"

// ── Public interface ─────────────────────────────────────────────────────────

bool USessionAPIClient::SendSessionSummary(const FPlayerSessionSummary& Summary)
{
	if (EndpointURL.IsEmpty())
	{
		UE_LOG(LogTemp, Log,
			TEXT("SessionAPIClient (no endpoint): session %s player %s rewards %d — not sent"),
			*Summary.SessionId, *Summary.PlayerId, Summary.Rewards.Num());
		return true; // Treat as ok for local dev — caller should not retry
	}

	// Build JSON body matching the post-session-summary Lambda schema:
	// { "playerId", "sessionId", "rewards": [...], "endTime" }
	TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetStringField(TEXT("playerId"),  Summary.PlayerId);
	Body->SetStringField(TEXT("sessionId"), Summary.SessionId);

	TArray<TSharedPtr<FJsonValue>> RewardsArray;
	for (const FString& RewardId : Summary.Rewards)
	{
		RewardsArray.Add(MakeShared<FJsonValueString>(RewardId));
	}
	Body->SetArrayField(TEXT("rewards"), RewardsArray);

	// ISO-8601 end time
	FString EndTime = Summary.SessionEndTime.ToIso8601();
	Body->SetStringField(TEXT("endTime"), EndTime);

	FString BodyString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&BodyString);
	FJsonSerializer::Serialize(Body, Writer);

	return PostSigned(TEXT("/session-summary"), BodyString);
}

bool USessionAPIClient::SendInteractionEvent(const FInteractionEvent& Event)
{
	if (EndpointURL.IsEmpty())
	{
		UE_LOG(LogTemp, Verbose,
			TEXT("SessionAPIClient (no endpoint): event %s player %s type %s — not sent"),
			*Event.EventId, *Event.PlayerId, *Event.EventType);
		return true;
	}

	// Build JSON body matching the interaction-events table schema
	TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetStringField(TEXT("eventId"),   Event.EventId);
	Body->SetStringField(TEXT("playerId"),  Event.PlayerId);
	Body->SetStringField(TEXT("eventType"), Event.EventType);
	Body->SetStringField(TEXT("timestamp"), Event.Timestamp.ToIso8601());
	Body->SetNumberField(TEXT("ttl"),       static_cast<double>(Event.TTL));

	TSharedRef<FJsonObject> DataObj = MakeShared<FJsonObject>();
	for (const auto& Pair : Event.Data)
	{
		DataObj->SetStringField(Pair.Key, Pair.Value);
	}
	Body->SetObjectField(TEXT("data"), DataObj);

	FString BodyString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&BodyString);
	FJsonSerializer::Serialize(Body, Writer);

	return PostSigned(TEXT("/interaction-events"), BodyString);
}

void USessionAPIClient::SetEndpointURL(const FString& URL)
{
	EndpointURL = URL;
	UE_LOG(LogTemp, Log, TEXT("SessionAPIClient: endpoint set to %s"), *URL);
}

// ── Private helpers ──────────────────────────────────────────────────────────

bool USessionAPIClient::PostSigned(const FString& Path, const FString& JsonBody)
{
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> HttpRequest = FHttpModule::Get().CreateRequest();
	HttpRequest->SetURL(EndpointURL + Path);
	HttpRequest->SetVerb(TEXT("POST"));
	HttpRequest->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
	HttpRequest->SetHeader(TEXT("host"),          FString(TEXT("")) + /* extracted by signer */ TEXT(""));

	// Convert body to bytes for signing
	FTCHARToUTF8 Conv(*JsonBody);
	TArray<uint8> BodyBytes;
	BodyBytes.Append(reinterpret_cast<const uint8*>(Conv.Get()), Conv.Length());
	HttpRequest->SetContent(BodyBytes);

	// Sign with SigV4 using instance IAM role credentials
	if (!FAwsSigV4::SignRequest(HttpRequest, BodyBytes, AwsRegion, TEXT("execute-api")))
	{
		UE_LOG(LogTemp, Warning,
			TEXT("SessionAPIClient: SigV4 signing failed for %s — sending unsigned (will likely get 403)"), *Path);
	}

	// Capture Path by value for the lambda
	FString CapturedPath = Path;
	HttpRequest->OnProcessRequestComplete().BindUObject(this, &USessionAPIClient::OnPostComplete, CapturedPath);
	HttpRequest->ProcessRequest();

	UE_LOG(LogTemp, Log, TEXT("SessionAPIClient: POST %s dispatched (fire-and-forget)"), *Path);
	return true;
}

void USessionAPIClient::OnPostComplete(FHttpRequestPtr /*Request*/, FHttpResponsePtr Response, bool bSuccess, FString Path)
{
	if (!bSuccess || !Response.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("SessionAPIClient: POST %s — network error"), *Path);
		return;
	}

	int32 Code = Response->GetResponseCode();
	if (Code == 200 || Code == 201)
	{
		UE_LOG(LogTemp, Log, TEXT("SessionAPIClient: POST %s — success (%d)"), *Path, Code);
	}
	else
	{
		UE_LOG(LogTemp, Warning, TEXT("SessionAPIClient: POST %s — HTTP %d: %s"),
			*Path, Code, *Response->GetContentAsString());
	}
}
