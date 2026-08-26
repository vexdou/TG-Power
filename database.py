from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

import config


client = AsyncIOMotorClient(config.MONGO_URI)
mongo_db: AsyncIOMotorDatabase = client[config.DB_NAME]

users_col = mongo_db["users"]
bots_col = mongo_db["bots"]
bot_users_col = mongo_db["bot_users"]
downloads_col = mongo_db["downloads"]
broadcasts_col = mongo_db["broadcasts"]
settings_col = mongo_db["settings"]
logs_col = mongo_db["logs"]
channels_col = mongo_db["channels"]


def now():
    return datetime.now(timezone.utc)


async def _ensure_index(collection, keys, *, unique=False, name=None):
    """
    Create an index safely.

    MongoDB can already contain an index with the same key pattern but a
    different name/options. Calling create_index() directly in that situation
    raises IndexOptionsConflict (code 85), which was causing the Render crash.

    This function:
      1. Reuses an existing compatible index.
      2. Removes an incompatible index with the same key pattern.
      3. Creates the requested index.
    """
    if isinstance(keys, str):
        normalized_keys = [(keys, ASCENDING)]
    else:
        normalized_keys = list(keys)

    desired_name = name or "_".join(
        f"{field}_{direction}" for field, direction in normalized_keys
    )

    existing_indexes = await collection.list_indexes().to_list(length=None)

    for index in existing_indexes:
        existing_keys = list(index.get("key", {}).items())

        if existing_keys != normalized_keys:
            continue

        existing_name = index.get("name")
        existing_unique = bool(index.get("unique", False))

        # Same key pattern + compatible options: reuse it.
        if existing_unique == unique:
            return existing_name

        # Same key pattern but incompatible options (for example unique=True
        # requested while an old non-unique index exists). Remove the old one.
        if existing_name:
            await collection.drop_index(existing_name)
        break

    kwargs = {"unique": unique, "name": desired_name}
    return await collection.create_index(normalized_keys, **kwargs)


async def init_db():
    """
    Initialize all MongoDB indexes.

    This version is safe to run repeatedly and fixes the common
    IndexOptionsConflict / duplicate-index-name problem caused by an older
    database schema.
    """

    await _ensure_index(
        users_col,
        "user_id",
        unique=True,
        name="user_id_unique",
    )

    await _ensure_index(
        bots_col,
        "username",
        unique=True,
        name="username_unique",
    )

    await _ensure_index(
        bots_col,
        [("owner_id", ASCENDING), ("status", ASCENDING)],
        name="owner_id_1_status_1",
    )

    await _ensure_index(
        bot_users_col,
        [("bot_username", ASCENDING), ("user_id", ASCENDING)],
        unique=True,
        name="bot_username_1_user_id_1_unique",
    )

    await _ensure_index(
        bot_users_col,
        [("bot_username", ASCENDING), ("is_blocked", ASCENDING)],
        name="bot_username_1_is_blocked_1",
    )

    await _ensure_index(
        downloads_col,
        [("bot_username", ASCENDING), ("timestamp", DESCENDING)],
        name="bot_username_1_timestamp_-1",
    )

    await _ensure_index(
        downloads_col,
        "user_id",
        name="user_id_1",
    )

    await _ensure_index(
        broadcasts_col,
        [("bot_username", ASCENDING), ("created_at", DESCENDING)],
        name="bot_username_1_created_at_-1",
    )

    await _ensure_index(
        logs_col,
        "created_at",
        name="created_at_1",
    )

    await _ensure_index(
        channels_col,
        [("bot_username", ASCENDING), ("username", ASCENDING)],
        unique=True,
        name="bot_username_1_username_1_unique",
    )

    await _ensure_index(
        settings_col,
        "key",
        unique=True,
        name="key_unique",
    )


async def add_user(user_id: int, first_name: str = "", username: str = ""):
    await users_col.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "first_name": first_name or "",
                "username": username or "",
                "last_seen": now(),
            },
            "$setOnInsert": {
                "created_at": now(),
                "can_create": True,
                "lang": "so",
            },
        },
        upsert=True,
    )


async def get_user(user_id: int):
    return await users_col.find_one({"user_id": user_id})


async def set_creation_access(user_id: int, allowed: bool):
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"can_create": allowed}},
        upsert=True,
    )


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
    await settings_col.update_one(
        {"key": "bot_creation"},
        {
            "$set": {
                "key": "bot_creation",
                "value": status,
            }
        },
        upsert=True,
    )


async def register_bot(
    owner_id: int,
    bot_token: str,
    bot_name: str,
    bot_username: str,
    bot_id: Optional[int] = None,
):
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
    return await bots_col.find_one(
        {
            "owner_id": owner_id,
            "username": username.lstrip("@"),
        }
    )


async def get_user_bots(owner_id: int, limit: int = 100):
    return (
        await bots_col.find({"owner_id": owner_id})
        .sort("created_at", DESCENDING)
        .to_list(length=limit)
    )


async def get_all_active_bots(limit: int = 2000):
    return await bots_col.find({"status": "active"}).to_list(length=limit)


async def count_user_bots(owner_id: int):
    return await bots_col.count_documents(
        {
            "owner_id": owner_id,
            "status": {"$ne": "deleted"},
        }
    )


async def set_bot_status(username: str, status: str):
    await bots_col.update_one(
        {"username": username.lstrip("@")},
        {"$set": {"status": status}},
    )


async def delete_bot(username: str):
    await bots_col.update_one(
        {"username": username.lstrip("@")},
        {"$set": {"status": "deleted"}},
    )


async def add_bot_user(
    bot_username: str,
    user_id: int,
    first_name: str = "",
    username: str = "",
):
    bot_username = bot_username.lstrip("@")

    existing = await bot_users_col.find_one(
        {
            "bot_username": bot_username,
            "user_id": user_id,
        }
    )

    await bot_users_col.update_one(
        {
            "bot_username": bot_username,
            "user_id": user_id,
        },
        {
            "$set": {
                "first_name": first_name or "",
                "username": username or "",
                "last_seen": now(),
                "is_blocked": False,
            },
            "$setOnInsert": {
                "joined_at": now(),
                "download_count": 0,
            },
        },
        upsert=True,
    )

    if not existing:
        await bots_col.update_one(
            {"username": bot_username},
            {"$inc": {"total_users": 1}},
        )


async def mark_bot_user_blocked(
    bot_username: str,
    user_id: int,
    blocked: bool = True,
):
    await bot_users_col.update_one(
        {
            "bot_username": bot_username.lstrip("@"),
            "user_id": user_id,
        },
        {"$set": {"is_blocked": blocked}},
        upsert=True,
    )


async def get_bot_users(
    bot_username: str,
    skip: int = 0,
    limit: int = 50,
):
    return (
        await bot_users_col.find(
            {
                "bot_username": bot_username.lstrip("@"),
                "is_blocked": {"$ne": True},
            }
        )
        .sort("joined_at", ASCENDING)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )


async def count_bot_users(bot_username: str):
    return await bot_users_col.count_documents(
        {"bot_username": bot_username.lstrip("@")}
    )


async def log_download(
    bot_username: str,
    user_id: int,
    platform: str,
    url: str = "",
):
    bot_username = bot_username.lstrip("@")

    await downloads_col.insert_one(
        {
            "bot_username": bot_username,
            "user_id": user_id,
            "platform": platform,
            "url": url[:500],
            "timestamp": now(),
        }
    )

    await bot_users_col.update_one(
        {
            "bot_username": bot_username,
            "user_id": user_id,
        },
        {"$inc": {"download_count": 1}},
    )

    await bots_col.update_one(
        {"username": bot_username},
        {"$inc": {"total_downloads": 1}},
    )


async def bot_platform_counts(bot_username: str):
    pipeline = [
        {
            "$match": {
                "bot_username": bot_username.lstrip("@"),
            }
        },
        {
            "$group": {
                "_id": "$platform",
                "count": {"$sum": 1},
            }
        },
        {
            "$sort": {
                "count": -1,
            }
        },
    ]

    return await downloads_col.aggregate(pipeline).to_list(length=50)


async def add_broadcast(
    bot_username: str,
    owner_id: int,
    total: int,
):
    doc = {
        "bot_username": bot_username.lstrip("@"),
        "owner_id": owner_id,
        "total": total,
        "sent": 0,
        "failed": 0,
        "created_at": now(),
        "status": "running",
    }

    res = await broadcasts_col.insert_one(doc)
    return res.inserted_id


async def finish_broadcast(
    broadcast_id,
    sent: int,
    failed: int,
):
    await broadcasts_col.update_one(
        {"_id": broadcast_id},
        {
            "$set": {
                "sent": sent,
                "failed": failed,
                "status": "completed",
                "finished_at": now(),
            }
        },
    )


async def log_event(event: str, **data):
    await logs_col.insert_one(
        {
            "event": event,
            "created_at": now(),
            **data,
        }
    )


async def get_channels(bot_username: str):
    return (
        await channels_col.find(
            {"bot_username": bot_username.lstrip("@")}
        )
        .sort("username", ASCENDING)
        .to_list(length=50)
    )


async def add_channel(
    bot_username: str,
    username: str,
    chat_id: Optional[int] = None,
):
    username = username.strip().lstrip("@")
    bot_username = bot_username.lstrip("@")

    await channels_col.update_one(
        {
            "bot_username": bot_username,
            "username": username,
        },
        {
            "$set": {
                "chat_id": chat_id,
                "username": username,
            }
        },
        upsert=True,
    )

    await bots_col.update_one(
        {"username": bot_username},
        {"$addToSet": {"force_join_channels": username}},
    )


async def remove_channel(bot_username: str, username: str):
    username = username.strip().lstrip("@")
    bot_username = bot_username.lstrip("@")

    await channels_col.delete_one(
        {
            "bot_username": bot_username,
            "username": username,
        }
    )

    await bots_col.update_one(
        {"username": bot_username},
        {"$pull": {"force_join_channels": username}},
    )


async def set_premium(
    bot_username: str,
    user_id: int,
    enabled: bool,
):
    await bot_users_col.update_one(
        {
            "bot_username": bot_username.lstrip("@"),
            "user_id": user_id,
        },
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


# ============================================================
# MANAGED-BOT DATABASE FACADE + PREMIUM
# ============================================================

class DatabaseFacade:
    """Small compatibility layer used by managed_bot.py.

    The original downloader system uses function-based database helpers while
    the managed bot handler uses an object API. Keeping the adapter here avoids
    introducing a second database implementation or changing the downloader.
    """

    async def get_bot(self, bot_id):
        key = str(bot_id).lstrip("@").lower()
        try:
            numeric = int(bot_id)
            doc = await bots_col.find_one({"bot_id": numeric})
            if doc:
                return doc
        except Exception:
            pass
        return await bots_col.find_one({"username": key})

    async def get_bot_user(self, bot_id, user_id):
        bot = await self.get_bot(bot_id)
        username = (bot or {}).get("username", str(bot_id).lstrip("@"))
        return await bot_users_col.find_one({"bot_username": username, "user_id": int(user_id)})

    async def save_bot_user(self, bot_id, user_id, username="", full_name=""):
        bot = await self.get_bot(bot_id)
        bot_username = (bot or {}).get("username", str(bot_id).lstrip("@").lower())
        await add_bot_user(bot_username, int(user_id), full_name, username)
        return await self.get_bot_user(bot_id, user_id)

    async def get_all_bot_users(self, bot_id):
        bot = await self.get_bot(bot_id)
        username = (bot or {}).get("username", str(bot_id).lstrip("@").lower())
        return await bot_users_col.find({"bot_username": username}).sort("joined_at", ASCENDING).to_list(length=10000)

    async def set_user_language(self, bot_id, user_id, lang):
        bot = await self.get_bot(bot_id)
        username = (bot or {}).get("username", str(bot_id).lstrip("@").lower())
        await bot_users_col.update_one(
            {"bot_username": username, "user_id": int(user_id)},
            {"$set": {"language": lang, "last_seen": now()}},
            upsert=True,
        )

    async def get_bot_stats(self, bot_id):
        bot = await self.get_bot(bot_id)
        if not bot:
            return {"total_users": 0, "total_downloads": 0}
        username = bot.get("username", "")
        videos = await downloads_col.count_documents({"bot_username": username, "platform": {"$ne": "audio"}})
        return {
            "total_users": await count_bot_users(username),
            "total_downloads": int(bot.get("total_downloads", 0)),
            "videos": videos,
            "audio": await downloads_col.count_documents({"bot_username": username, "platform": "audio"}),
            "photos": await downloads_col.count_documents({"bot_username": username, "platform": "photo"}),
        }

    async def log_download(self, bot_id, user_id, platform, url=""):
        bot = await self.get_bot(bot_id)
        username = (bot or {}).get("username", str(bot_id).lstrip("@"))
        return await log_download(username, int(user_id), platform, url)

    async def is_bot_premium(self, bot_id):
        bot = await self.get_bot(bot_id)
        if not bot:
            return False
        premium = bot.get("premium") or {}
        if not premium.get("is_active"):
            return False
        until = premium.get("until")
        if until and normalize_dt(until) <= now():
            await bots_col.update_one({"_id": bot["_id"]}, {"$set": {"premium.is_active": False}})
            return False
        return True

    async def get_bot_premium_settings(self, bot_id):
        bot = await self.get_bot(bot_id)
        username = (bot or {}).get("username", str(bot_id).lstrip("@"))
        doc = await settings_col.find_one({"key": f"premium:{username}"})
        if doc:
            return doc.get("value", {}) or {}
        return {"start_message": "", "buttons": [], "caption": "", "ads_enabled": False}

    async def update_bot_premium_settings(self, bot_id, settings):
        bot = await self.get_bot(bot_id)
        username = (bot or {}).get("username", str(bot_id).lstrip("@"))
        await settings_col.update_one(
            {"key": f"premium:{username}"},
            {"$set": {"key": f"premium:{username}", "value": settings, "updated_at": now()}},
            upsert=True,
        )

    async def set_bot_premium_setting(self, bot_id, key, value):
        settings = await self.get_bot_premium_settings(bot_id)
        settings[key] = value
        await self.update_bot_premium_settings(bot_id, settings)

    async def activate_premium(self, bot_id, days, plan="admin", stars=0, source="admin"):
        bot = await self.get_bot(bot_id)
        if not bot:
            return None
        current = normalize_dt((bot.get("premium") or {}).get("until"))
        start = current if current and current > now() else now()
        until = start + timedelta(days=int(days))
        await bots_col.update_one(
            {"_id": bot["_id"]},
            {"$set": {"premium": {"is_active": True, "plan": plan, "days": int(days), "stars": int(stars), "source": source, "activated_at": now(), "until": until}}},
        )
        return until

    async def deactivate_premium(self, bot_id):
        bot = await self.get_bot(bot_id)
        if not bot:
            return False
        result = await bots_col.update_one({"_id": bot["_id"]}, {"$set": {"premium.is_active": False, "premium.deactivated_at": now()}})
        return result.modified_count > 0

    async def premium_bots(self):
        return await bots_col.find({"premium.is_active": True, "premium.until": {"$gt": now()}}).to_list(length=5000)

    async def premium_expire(self):
        result = await bots_col.update_many({"premium.is_active": True, "premium.until": {"$lte": now()}}, {"$set": {"premium.is_active": False}})
        return result.modified_count

    async def get_premium_prices(self):
        doc = await settings_col.find_one({"key": "premium_prices"})
        return (doc or {}).get("value", {"1m": 100, "3m": 300, "6m": 600, "1y": 1000})

    async def set_premium_prices(self, prices):
        current = await self.get_premium_prices()
        current.update({k: int(v) for k, v in prices.items() if k in {"1m", "3m", "6m", "1y"} and int(v) > 0})
        await settings_col.update_one({"key": "premium_prices"}, {"$set": {"key": "premium_prices", "value": current, "updated_at": now()}}, upsert=True)
        return current


def normalize_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


# Managed-bot object API. The original module-level Mongo handle remains
# available as mongo_db; all existing helper functions continue unchanged.
db = DatabaseFacade()
