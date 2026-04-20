// Copyright 2026 HyperMage. All Rights Reserved.

#include "SessionAPIClient.h"
#include "AwsSigV4.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/TSTicker.h"

// ── Public interface ─────────────────────────────────────────────────────────

bool USessionAPIClient::SendSessionSummary(const FPlayerSessionSummary& Summary)
{
	if (EndpointURL.IsEmpty())
	{
		UE_LOG(LogTemp, Log,
			TEXT("SessionAPIClient (no endpoint): session %s player %s rewards %d — not sent"),
			*Summary.SessionId, *Summary.PlayerId, Summary.Rewards.Num());
		return true;
	}

	TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetStringField(TEXT("playerId"),  Summary.PlayerId);
	Body->SetStringField(TEXT("sessionId"), Summary.SessionId);

	TArray<TSharedPtr<FJsonValue>> RewardsArray;
	for (const FString& RewardId : Summary.Rewards)
	{
		RewardsArray.Add(MakeShared<FJsonValueString>(RewardId));
	}
	Body->SetArrayField(TEXT("rewards"), RewardsArray);
	Body->SetStringField(TEXT("endTime"), Summary.SessionEndTime.ToIso8601());

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

bool USessionAPIClient::PostSigned(const FString& Path, const FString& JsonBody, int32 Attempt)
{
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> HttpRequest = FHttpModule::Get().CreateRequest();
	HttpRequest->SetURL(EndpointURL + Path);
	HttpRequest->SetVerb(TEXT("POST"));
	HttpRequest->SetHeader(TEXT("Content-Type"), TEXT("application/json"));

	FTCHARToUTF8 Conv(*JsonBody);
	TArray<uint8> BodyBytes;
	BodyBytes.Append(reinterpret_cast<const uint8*>(Conv.Get()), Conv.Length());
	HttpRequest->SetContent(BodyBytes);

	if (!FAwsSigV4::SignRequest(HttpRequest, BodyBytes, AwsRegion, TEXT("execute-api")))
	{
		UE_LOG(LogTemp, Warning,
			TEXT("SessionAPIClient: SigV4 signing failed for %s — sending unsigned (will likely get 403)"), *Path);
	}

	FString CapturedPath = Path;
	FString CapturedBody = JsonBody;
	HttpRequest->OnProcessRequestComplete().BindUObject(
		this, &USessionAPIClient::OnPostComplete, CapturedPath, CapturedBody, Attempt);
	HttpRequest->ProcessRequest();

	if (Attempt == 0)
	{
		UE_LOG(LogTemp, Log, TEXT("SessionAPIClient: POST %s dispatched"), *Path);
	}
	else
	{
		UE_LOG(LogTemp, Log, TEXT("SessionAPIClient: POST %s retry attempt %d/%d"), *Path, Attempt, MaxRetries);
	}
	return true;
}

void USessionAPIClient::OnPostComplete(FHttpRequestPtr /*Request*/, FHttpResponsePtr Response,
                                        bool bSuccess, FString Path, FString Body, int32 Attempt)
{
	bool bShouldRetry = false;

	if (!bSuccess || !Response.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("SessionAPIClient: POST %s — network error (attempt %d)"), *Path, Attempt + 1);
		bShouldRetry = true;
	}
	else
	{
		int32 Code = Response->GetResponseCode();
		if (Code == 200 || Code == 201)
		{
			UE_LOG(LogTemp, Log, TEXT("SessionAPIClient: POST %s — success (%d)"), *Path, Code);
			return;
		}
		else if (Code >= 500)
		{
			UE_LOG(LogTemp, Warning, TEXT("SessionAPIClient: POST %s — server error %d (attempt %d)"),
				*Path, Code, Attempt + 1);
			bShouldRetry = true;
		}
		else
		{
			UE_LOG(LogTemp, Warning, TEXT("SessionAPIClient: POST %s — HTTP %d: %s"),
				*Path, Code, *Response->GetContentAsString());
		}
	}

	if (bShouldRetry && Attempt < MaxRetries)
	{
		const float Delay = static_cast<float>(1 << Attempt); // 1 s, 2 s, 4 s
		UE_LOG(LogTemp, Log, TEXT("SessionAPIClient: Retrying POST %s in %.0fs (%d/%d)"),
			*Path, Delay, Attempt + 1, MaxRetries);

		FString CapturedPath = Path;
		FString CapturedBody = Body;
		const int32 NextAttempt = Attempt + 1;

		FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateWeakLambda(this, [this, CapturedPath, CapturedBody, NextAttempt](float) -> bool
			{
				PostSigned(CapturedPath, CapturedBody, NextAttempt);
				return false; // fire once then remove
			}),
			Delay
		);
	}
	else if (bShouldRetry)
	{
		UE_LOG(LogTemp, Error, TEXT("SessionAPIClient: POST %s — giving up after %d retries"), *Path, MaxRetries);
	}
}
