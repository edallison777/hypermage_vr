// Copyright 2026 HyperMage. All Rights Reserved.

#include "RewardSystem.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonReader.h"
#include "Dom/JsonObject.h"

bool URewardSystem::Initialize()
{
	// Load rewards catalog from JSON file
	// In production, this would be loaded from S3 or bundled with the game
	FString CatalogPath = FPaths::ProjectDir() / TEXT("../Specs/examples/rewards_catalog.json");
	
	if (!LoadCatalogFromFile(CatalogPath))
	{
		UE_LOG(LogTemp, Error, TEXT("RewardSystem: Failed to load rewards catalog from %s"), *CatalogPath);
		return false;
	}

	UE_LOG(LogTemp, Log, TEXT("RewardSystem: Initialized with %d rewards"), Catalog.Rewards.Num());
	return true;
}

bool URewardSystem::IsValidRewardId(const FString& RewardId) const
{
	if (!bCatalogLoaded)
	{
		return false;
	}

	// Check if reward ID exists in catalog
	for (const FRewardCatalogEntry& Entry : Catalog.Rewards)
	{
		if (Entry.Id == RewardId)
		{
			return true;
		}
	}

	return false;
}

FRewardGrantResult URewardSystem::GrantReward(const FString& PlayerId, const FString& RewardId)
{
	// Validate inputs
	if (PlayerId.IsEmpty())
	{
		return FRewardGrantResult::Failure(TEXT("INVALID_PLAYER_ID"), TEXT("Player ID is empty"));
	}

	if (RewardId.IsEmpty())
	{
		return FRewardGrantResult::Failure(TEXT("INVALID_REWARD_ID"), TEXT("Reward ID is empty"));
	}

	// Check if catalog is loaded (Requirement 15.5)
	if (!bCatalogLoaded)
	{
		UE_LOG(LogTemp, Error, TEXT("RewardSystem: Cannot grant reward - catalog not loaded"));
		return FRewardGrantResult::Failure(
			TEXT("REWARD_CATALOG_NOT_FOUND"),
			TEXT("Rewards catalog is not loaded"),
			RewardId
		);
	}

	// Validate reward ID against catalog (Requirement 5.3, 15.2, 15.3)
	if (!IsValidRewardId(RewardId))
	{
		UE_LOG(LogTemp, Warning, TEXT("RewardSystem: Invalid reward ID: %s"), *RewardId);
		return FRewardGrantResult::Failure(
			TEXT("INVALID_REWARD_ID"),
			FString::Printf(TEXT("Reward ID '%s' not found in catalog"), *RewardId),
			RewardId
		);
	}

	// Get or create player rewards array
	TArray<FString>& Rewards = PlayerRewards.FindOrAdd(PlayerId);

	// Check if reward already granted
	if (Rewards.Contains(RewardId))
	{
		UE_LOG(LogTemp, Warning, TEXT("RewardSystem: Reward '%s' already granted to player %s"), 
			*RewardId, *PlayerId);
		return FRewardGrantResult::Failure(
			TEXT("REWARD_ALREADY_GRANTED"),
			FString::Printf(TEXT("Reward '%s' already granted"), *RewardId),
			RewardId
		);
	}

	// Grant reward (store as boolean flag with string identifier)
	// Requirement 5.2, 15.4: Store as boolean flag with string identifier
	Rewards.Add(RewardId);

	UE_LOG(LogTemp, Log, TEXT("RewardSystem: Granted reward '%s' to player %s (total: %d)"),
		*RewardId, *PlayerId, Rewards.Num());

	// In production, this would:
	// 1. Store in DynamoDB PlayerRewards table (no TTL - persistent)
	// 2. Partition key = PlayerId, Sort key = RewardId
	// 3. Value = true (boolean flag)

	return FRewardGrantResult::Success(RewardId);
}

TArray<FString> URewardSystem::GetPlayerRewards(const FString& PlayerId) const
{
	const TArray<FString>* Rewards = PlayerRewards.Find(PlayerId);
	if (Rewards)
	{
		return *Rewards;
	}
	return TArray<FString>();
}

bool URewardSystem::HasReward(const FString& PlayerId, const FString& RewardId) const
{
	const TArray<FString>* Rewards = PlayerRewards.Find(PlayerId);
	if (Rewards)
	{
		return Rewards->Contains(RewardId);
	}
	return false;
}

bool URewardSystem::LoadCatalogFromFile(const FString& FilePath)
{
	// Read JSON file
	FString JsonString;
	if (!FFileHelper::LoadFileToString(JsonString, *FilePath))
	{
		UE_LOG(LogTemp, Error, TEXT("RewardSystem: Failed to read file: %s"), *FilePath);
		return false;
	}

	// Parse JSON
	if (!ParseCatalogJson(JsonString))
	{
		UE_LOG(LogTemp, Error, TEXT("RewardSystem: Failed to parse JSON from: %s"), *FilePath);
		return false;
	}

	bCatalogLoaded = true;
	return true;
}

bool URewardSystem::ParseCatalogJson(const FString& JsonString)
{
	// Create JSON reader
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonString);

	// Parse JSON
	TSharedPtr<FJsonObject> JsonObject;
	if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
	{
		UE_LOG(LogTemp, Error, TEXT("RewardSystem: Failed to deserialize JSON"));
		return false;
	}

	// Parse version
	if (JsonObject->HasField(TEXT("version")))
	{
		Catalog.Version = JsonObject->GetStringField(TEXT("version"));
	}

	// Parse lastUpdated
	if (JsonObject->HasField(TEXT("lastUpdated")))
	{
		Catalog.LastUpdated = JsonObject->GetStringField(TEXT("lastUpdated"));
	}

	// Parse rewards array
	if (!JsonObject->HasField(TEXT("rewards")))
	{
		UE_LOG(LogTemp, Error, TEXT("RewardSystem: JSON missing 'rewards' field"));
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* RewardsArray;
	if (!JsonObject->TryGetArrayField(TEXT("rewards"), RewardsArray))
	{
		UE_LOG(LogTemp, Error, TEXT("RewardSystem: Failed to parse 'rewards' array"));
		return false;
	}

	// Parse each reward entry
	Catalog.Rewards.Empty();
	for (const TSharedPtr<FJsonValue>& RewardValue : *RewardsArray)
	{
		const TSharedPtr<FJsonObject>* RewardObject;
		if (!RewardValue->TryGetObject(RewardObject))
		{
			continue;
		}

		FRewardCatalogEntry Entry;
		Entry.Id = (*RewardObject)->GetStringField(TEXT("id"));
		Entry.Name = (*RewardObject)->GetStringField(TEXT("name"));
		Entry.Description = (*RewardObject)->GetStringField(TEXT("description"));
		
		if ((*RewardObject)->HasField(TEXT("category")))
		{
			Entry.Category = (*RewardObject)->GetStringField(TEXT("category"));
		}

		Catalog.Rewards.Add(Entry);
	}

	UE_LOG(LogTemp, Log, TEXT("RewardSystem: Parsed %d rewards from catalog (version: %s)"),
		Catalog.Rewards.Num(), *Catalog.Version);

	return true;
}
