from typing import List, Optional, Any
from datetime import datetime
import pymongo
from motor.motor_asyncio import AsyncIOMotorDatabase
from models.flag import FeatureFlag, FlagUpdate, FlagSummary, AuditLog

class AuditRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["audit_logs"]

    async def log(self, entry: AuditLog):
        await self.collection.insert_one(entry.model_dump())

    async def get_history(self, flag_key: str, limit: int = 50) -> List[AuditLog]:
        cursor = self.collection.find({"flag_key": flag_key}).sort("timestamp", pymongo.DESCENDING).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [AuditLog(**doc) for doc in docs]

class FlagRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["feature_flags"]
        self.audit_collection = db["audit_logs"]

    async def setup_indexes(self, flag_ttl_days: int = 90):
        await self.collection.create_index("key", unique=True)
        await self.collection.create_index("tags")
        await self.collection.create_index("enabled")
        await self.collection.create_index([("updated_at", pymongo.DESCENDING)])
        await self.collection.create_index(
            [("updated_at", pymongo.ASCENDING)],
            expireAfterSeconds=flag_ttl_days * 86400,
            name="flag_ttl",
        )
        await self.audit_collection.create_index([("flag_key", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])

    async def create(self, flag: FeatureFlag):
        await self.collection.insert_one(flag.model_dump())

    async def get_by_key(self, key: str) -> Optional[FeatureFlag]:
        doc = await self.collection.find_one({"key": key})
        if doc:
            return FeatureFlag(**doc)
        return None

    async def get_by_id(self, id: str) -> Optional[FeatureFlag]:
        doc = await self.collection.find_one({"id": id})
        if doc:
            return FeatureFlag(**doc)
        return None

    async def delete(self, key: str) -> bool:
        result = await self.collection.delete_one({"key": key})
        return result.deleted_count > 0

    async def update(self, key: str, update_data: FlagUpdate) -> Optional[FeatureFlag]:
        doc = await self.collection.find_one({"key": key})
        if not doc:
            return None
            
        current_flag = FeatureFlag(**doc)
        update_dict = update_data.model_dump(exclude_unset=True)
        
        current_dict = current_flag.model_dump()
        current_dict.update(update_dict)
        current_dict["updated_at"] = datetime.utcnow()
        
        # Pydantic validation
        validated_flag = FeatureFlag(**current_dict)
        
        await self.collection.update_one(
            {"key": key},
            {"$set": validated_flag.model_dump(exclude={"id", "key"})}
        )
        return validated_flag

    async def list_all(self, tags: Optional[List[str]] = None, enabled: Optional[bool] = None, limit: int = 50, skip: int = 0) -> List[FlagSummary]:
        query = {}
        if tags:
            query["tags"] = {"$all": tags}
        if enabled is not None:
            query["enabled"] = enabled
            
        cursor = self.collection.find(query).sort("updated_at", pymongo.DESCENDING).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        
        summaries = []
        for doc in docs:
            summaries.append(FlagSummary(
                id=doc["id"],
                key=doc["key"],
                name=doc["name"],
                description=doc.get("description"),
                enabled=doc["enabled"],
                tags=doc.get("tags", []),
                variant_count=len(doc.get("variants", [])),
                rule_count=len(doc.get("targeting_rules", [])),
                rollout_percentage=doc.get("rollout", {}).get("percentage", 100.0),
                created_at=doc["created_at"],
                updated_at=doc["updated_at"]
            ))
        return summaries

    async def get_many_by_keys(self, keys: List[str]) -> List[FeatureFlag]:
        if not keys:
            return []
        cursor = self.collection.find({"key": {"$in": keys}})
        docs = await cursor.to_list(length=None)
        return [FeatureFlag(**doc) for doc in docs]

    async def get_all_enabled(self) -> List[FeatureFlag]:
        cursor = self.collection.find({"enabled": True})
        docs = await cursor.to_list(length=None)
        return [FeatureFlag(**doc) for doc in docs]

    async def count_all(self) -> int:
        return await self.collection.count_documents({})
