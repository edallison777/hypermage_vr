// Copyright 2026 HyperMage. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "UObject/NoExportTypes.h"
#include "RewardSystem.generated.h"

/**
 * Reward catalog entry
 */
USTRUCT(BlueprintType)
struct FRewardCatalogEntry
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly)
	FString Id;

	UPROPERTY(BlueprintReadOnly)
	FString Name;

	UPROPERTY(BlueprintReadOnly)
	FString Description;

	UPROPERTY(BlueprintReadOnly)
	FString Category;

	FRewardCatalogEntry()
	{
	}
};

/**
 * Reward catalog
 */
USTRUCT(BlueprintType)
struct FRewardCatalog
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly)
	FString Version;

	UPROPERTY(BlueprintReadOnly)
	FString LastUpdated;

	UPROPERTY(BlueprintReadOnly)
	TArray<FRewardCatalogEntry> Rewards;

	FRewardCatalog()
	{
	}
};

/**
 * Reward grant result
 */
USTRUCT(BlueprintType)
struct FRewardGrantResult
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly)
	bool bSuccess;

	UPROPERTY(BlueprintReadOnly)
	FString ErrorCode;

	UPROPERTY(BlueprintReadOnly)
	FString ErrorMessage;

	UPROPERTY(BlueprintReadOnly)
	FString RewardId;

	FRewardGrantResult()
		: bSuccess(false)
	{
	}

	static FRewardGrantResult Success(const FString& InRewardId)
	{
		FRewardGrantResult Result;
		Result.bSuccess = true;
		Result.RewardId = InRewardId;
		return Result;
	}

	static FRewardGrantResult Failure(const FString& InErrorCode, const FString& InErrorMessage, const FString& InRewardId = TEXT(""))
	{
		FRewardGrantResult Result;
		Result.bSuccess = false;
		Result.ErrorCode = InErrorCode;
		Result.ErrorMessage = InErrorMessage;
		Result.RewardId = InRewardId;
		return Result;
	}
};

/**
 * Reward System
 * Implements reward granting with catalog validation (Requirement 5.2, 5.3, 15.1-15.5)
 */
UCLASS()
class HYPERMAGEVR_API URewardSystem : public UObject
{
	GENERATED_BODY()

public:
	/**
	 * Initialize the reward system
	 * Loads the rewards catalog from JSON
	 * @return True if successful
	 */
	UFUNCTION(BlueprintCallable, Category = "Rewards")
	bool Initialize();

	/**
	 * Validate a reward ID against the catalog
	 * @param RewardId The reward ID to validate
	 * @return True if valid
	 */
	UFUNCTION(BlueprintCallable, Category = "Rewards")
	bool IsValidRewardId(const FString& RewardId) const;

	/**
	 * Grant a reward (with validation)
	 * @param PlayerId The player ID
	 * @param RewardId The reward ID
	 * @return The grant result
	 */
	UFUNCTION(BlueprintCallable, Category = "Rewards")
	FRewardGrantResult GrantReward(const FString& PlayerId, const FString& RewardId);

	/**
	 * Get all rewards for a player
	 * @param PlayerId The player ID
	 * @return Array of reward IDs
	 */
	UFUNCTION(BlueprintCallable, Category = "Rewards")
	TArray<FString> GetPlayerRewards(const FString& PlayerId) const;

	/**
	 * Check if player has a specific reward
	 * @param PlayerId The player ID
	 * @param RewardId The reward ID
	 * @return True if player has the reward
	 */
	UFUNCTION(BlueprintCallable, Category = "Rewards")
	bool HasReward(const FString& PlayerId, const FString& RewardId) const;

	/**
	 * Get the reward catalog
	 * @return The reward catalog
	 */
	UFUNCTION(BlueprintCallable, Category = "Rewards")
	const FRewardCatalog& GetCatalog() const { return Catalog; }

	/**
	 * Get catalog loading status
	 * @return True if catalog is loaded
	 */
	UFUNCTION(BlueprintCallable, Category = "Rewards")
	bool IsCatalogLoaded() const { return bCatalogLoaded; }

protected:
	// Reward catalog
	UPROPERTY()
	FRewardCatalog Catalog;

	// Player rewards (PlayerId -> Set of RewardIds)
	// In production, this would be stored in DynamoDB PlayerRewards table
	UPROPERTY()
	TMap<FString, TArray<FString>> PlayerRewards;

	// Catalog loading status
	bool bCatalogLoaded = false;

	// Load catalog from JSON file
	bool LoadCatalogFromFile(const FString& FilePath);

	// Parse catalog JSON
	bool ParseCatalogJson(const FString& JsonString);
};
