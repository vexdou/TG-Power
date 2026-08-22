from datetime import datetime, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
import config

client = AsyncIOMotorClient(config.MONGO_URI)
db: AsyncIOMotorDatabase = client[config.DB_NAME]

users_col = db["users"]
bots_col = db["bots"]
bot_users_col = db["bot_users"]
downloads_col = db["downloads"]
broadcasts_col = db["broadcasts"]
settings_col = db["settings"]
logs_col = db["logs"]
channels_col = db["channels"]

def now():
    return datetime.now(timezone.utc)

async def init_db():
    await users_col.create_index("user_id", unique=True)
    await bots_col.create_index("username", unique=True)
    await bots_col.create_index([("owner_id", ASCENDING), ("status", ASCENDING)])
    await bot_users_col.create_index([("bot_username", ASCENDING), ("user_id", ASCENDING)], unique=True)
    await bot_users_col.create_index([("bot_username", ASCENDING), ("is_blocked", ASCENDING)])
    await downloads_col.create_index([("bot_username", ASCENDING), ("timestamp", DESCENDING)])
    await downloads_col.create_index("user_id")
    await broadcasts_col.create_index([("bot_username", ASCENDING), ("created_at", DESCENDING)])
    await logs_col.create_index("created_at")
    await channels_col.create_index([("bot_username", ASCENDING), ("username", ASCENDING)], unique=True)
    await settings_col.create_index("key", unique=True)

async def add_user(user_id: int, first_name: str = "", username: str = ""):
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"first_name": first_name or "", "username": username or "", "last_seen": now()},
         "$setOnInsert": {"created_at": now(), "can_create": True, "lang": "so"}},
        upsert=True,
    )

async def get_user(user_id: int):
    return await users_col.find_one({"user_id": user_id})

async def set_creation_access(user_id: int, allowed: bool):
    await users_col.update_one({"user_id": user_id}, {"$set": {"can_create": allowed}}, upsert=True)

async def can_create_bot(user_id: int):
    if user_id in config.ADMIN_IDS:
        return True
    global_setting = await settings_col.find_one({"key": "bot_creation"})
    if global_setting and not global_setting.get("value", True):
        return False
    user = await get_user(user_id)
    return bool(user and user.get("can_create", False))

async def is_bot_creation_enabled():
    doc = await settings_col.find_one({"key": "bot_creation"})
    return True if not doc else bool(doc.get("value", True))

async def toggle_bot_creation(status: bool):
    await settings_col.update_one({"key": "bot_creation"}, {"$set": {"key": "bot_creation", "value": status}}, upsert=True)

async def register_bot(owner_id: int, bot_token: str, bot_name: str, bot_username: str, bot_id: Optional[int] = None):
    doc = {
        "owner_id": owner_id,
        "token": bot_token,
        "name": bot_name,
        "username": bot_username.lstrip("@"),
        "bot_id": bot_id,
        "status": "active",
        "force_join_channels": [],
        "total_users": 0,
        "total_downloads": 0,
        "created_at": now(),
    }
    await bots_col.insert_one(doc)
    return doc

async def get_bot_by_username(username: str):
    return await bots_col.find_one({"username": username.lstrip("@")})

async def get_bot_by_owner(owner_id: int, username: str):
    return await bots_col.find_one({"owner_id": owner_id, "username": username.lstrip("@")})

async def get_user_bots(owner_id: int, limit: int = 100):
    return await bots_col.find({"owner_id": owner_id}).sort("created_at", DESCENDING).to_list(length=limit)

async def get_all_active_bots(limit: int = 2000):
    return await bots_col.find({"status": "active"}).to_list(length=limit)

async def count_user_bots(owner_id: int):
    return await bots_col.count_documents({"owner_id": owner_id, "status": {"$ne": "deleted"}})

async def set_bot_status(username: str, status: str):
    await bots_col.update_one({"username": username.lstrip("@")}, {"$set": {"status": status}})

async def delete_bot(username: str):
    await bots_col.update_one({"username": username.lstrip("@")}, {"$set": {"status": "deleted"}})

async def add_bot_user(bot_username: str, user_id: int, first_name: str = "", username: str = ""):
    existing = await bot_users_col.find_one({"bot_username": bot_username.lstrip("@"), "user_id": user_id})
    await bot_users_col.update_one(
        {"bot_username": bot_username.lstrip("@"), "user_id": user_id},
        {"$set": {"first_name": first_name or "", "username": username or "", "last_seen": now(), "is_blocked": False},
         "$setOnInsert": {"joined_at": now(), "download_count": 0}},
        upsert=True,
    )
    if not existing:
        await bots_col.update_one({"username": bot_username.lstrip("@")}, {"$inc": {"total_users": 1}})

async def mark_bot_user_blocked(bot_username: str, user_id: int, blocked: bool = True):
    await bot_users_col.update_one(
        {"bot_username": bot_username.lstrip("@"), "user_id": user_id},
        {"$set": {"is_blocked": blocked}},
        upsert=True,
    )

async def get_bot_users(bot_username: str, skip: int = 0, limit: int = 50):
    return await bot_users_col.find(
        {"bot_username": bot_username.lstrip("@"), "is_blocked": {"$ne": True}}
    ).sort("joined_at", ASCENDING).skip(skip).limit(limit).to_list(length=limit)

async def count_bot_users(bot_username: str):
    return await bot_users_col.count_documents({"bot_username": bot_username.lstrip("@")})

async def log_download(bot_username: str, user_id: int, platform: str, url: str = ""):
    await downloads_col.insert_one({
        "bot_username": bot_username.lstrip("@"),
        "user_id": user_id,
        "platform": platform,
        "url": url[:500],
        "timestamp": now(),
    })
    await bot_users_col.update_one(
        {"bot_username": bot_username.lstrip("@"), "user_id": user_id},
        {"$inc": {"download_count": 1}}
    )
    await bots_col.update_one({"username": bot_username.lstrip("@")}, {"$inc": {"total_downloads": 1}})

async def bot_platform_counts(bot_username: str):
    pipeline = [
        {"$match": {"bot_username": bot_username.lstrip("@")}},
        {"$group": {"_id": "$platform", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    return await downloads_col.aggregate(pipeline).to_list(length=50)

async def add_broadcast(bot_username: str, owner_id: int, total: int):
    doc = {"bot_username": bot_username.lstrip("@"), "owner_id": owner_id, "total": total,
           "sent": 0, "failed": 0, "created_at": now(), "status": "running"}
    res = await broadcasts_col.insert_one(doc)
    return res.inserted_id

async def finish_broadcast(broadcast_id, sent: int, failed: int):
    await broadcasts_col.update_one(
        {"_id": broadcast_id},
        {"$set": {"sent": sent, "failed": failed, "status": "completed", "finished_at": now()}}
    )

async def log_event(event: str, **data):
    await logs_col.insert_one({"event": event, "created_at": now(), **data})

async def get_channels(bot_username: str):
    return await channels_col.find({"bot_username": bot_username.lstrip("@")}).sort("username", ASCENDING).to_list(length=50)

async def add_channel(bot_username: str, username: str, chat_id: Optional[int] = None):
    username = username.strip().lstrip("@")
    await channels_col.update_one(
        {"bot_username": bot_username.lstrip("@"), "username": username},
        {"$set": {"chat_id": chat_id, "username": username}},
        upsert=True,
    )
    await bots_col.update_one(
        {"username": bot_username.lstrip("@")},
        {"$addToSet": {"force_join_channels": username}}
    )

async def remove_channel(bot_username: str, username: str):
    username = username.strip().lstrip("@")
    await channels_col.delete_one({"bot_username": bot_username.lstrip("@"), "username": username})
    await bots_col.update_one(
        {"username": bot_username.lstrip("@")},
        {"$pull": {"force_join_channels": username}}
    )

async def set_premium(bot_username: str, user_id: int, enabled: bool):
    await bot_users_col.update_one(
        {"bot_username": bot_username.lstrip("@"), "user_id": user_id},
        {"$set": {"premium": enabled}},
        upsert=True,
    )

async def get_main_stats():
    return {
        "users": await users_col.count_documents({}),
        "bots": await bots_col.count_documents({"status": "active"}),
        "downloads": await downloads_col.count_documents({}),
        "owners": await bots_col.distinct("owner_id"),
    }
