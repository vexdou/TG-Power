import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

from config import Config

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.client = None
        self.db = None
        self.bots = None
        self.users = None
        self.downloads = None
        self.main_users = None
        self.system_settings = None
        self.pending_downloads = None

    @staticmethod
    def now():
        return datetime.now(timezone.utc)

    async def connect(self):
        if not Config.MONGO_URI:
            raise RuntimeError("MONGO_URI is not configured.")

        self.client = AsyncIOMotorClient(
            Config.MONGO_URI,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=30000,
            maxPoolSize=100,
            minPoolSize=5,
            retryWrites=True,
        )
        await self.client.admin.command("ping")

        self.db = self.client[Config.DB_NAME]
        self.bots = self.db.bots
        self.users = self.db.bot_users
        self.downloads = self.db.downloads
        self.main_users = self.db.main_users
        self.system_settings = self.db.system_settings
        self.pending_downloads = self.db.pending_downloads

        await self.create_indexes()
        logger.info("🟢 MongoDB connected successfully.")

    async def close(self):
        if self.client:
            self.client.close()
            logger.info("🔴 MongoDB connection closed.")

    async def create_indexes(self):
        await self.bots.create_index([("bot_id", ASCENDING)], unique=True)
        await self.bots.create_index([("owner_id", ASCENDING)])
        await self.bots.create_index([("status", ASCENDING)])
        await self.bots.create_index([("created_at", DESCENDING)])
        await self.users.create_index(
            [("bot_id", ASCENDING), ("user_id", ASCENDING)],
            unique=True,
        )
        await self.users.create_index([("bot_id", ASCENDING)])
        await self.downloads.create_index([("bot_id", ASCENDING)])
        await self.downloads.create_index([("created_at", DESCENDING)])
        await self.main_users.create_index([("user_id", ASCENDING)], unique=True)
        await self.system_settings.create_index([("key", ASCENDING)], unique=True)
        await self.pending_downloads.create_index(
            [("bot_id", ASCENDING), ("user_id", ASCENDING)],
            unique=True,
        )

    # ---------- Main controller users ----------
    async def save_main_user(self, user_id: int, username="", full_name=""):
        now = self.now()
        await self.main_users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "username": username or "",
                    "full_name": full_name or "",
                    "last_seen": now,
                },
                "$setOnInsert": {"user_id": user_id, "language": "en", "created_at": now},
            },
            upsert=True,
        )

    async def get_main_user(self, user_id: int):
        return await self.main_users.find_one({"user_id": user_id})

    async def set_main_user_language(self, user_id: int, language: str):
        if language not in {"en", "so", "ar", "es"}:
            language = "en"
        await self.main_users.update_one(
            {"user_id": user_id},
            {
                "$set": {"language": language, "last_seen": self.now()},
                "$setOnInsert": {"user_id": user_id, "created_at": self.now()},
            },
            upsert=True,
        )

    async def get_main_user_language(self, user_id: int):
        user = await self.get_main_user(user_id)
        return (user or {}).get("language", "en")

    async def get_all_main_users(self):
        return await self.main_users.find({}).to_list(length=None)

    async def count_main_users(self):
        return await self.main_users.count_documents({})

    # ---------- System settings ----------
    async def set_system_setting(self, key: str, value: Any):
        await self.system_settings.update_one(
            {"key": key},
            {
                "$set": {"value": value, "updated_at": self.now()},
                "$setOnInsert": {"key": key, "created_at": self.now()},
            },
            upsert=True,
        )

    async def get_system_setting(self, key: str, default=None):
        row = await self.system_settings.find_one({"key": key})
        return row.get("value", default) if row else default

    async def delete_system_setting(self, key: str):
        await self.system_settings.delete_one({"key": key})

    # ---------- Bots ----------
    async def add_new_bot(self, owner_id: int, token: str, bot_id: int, username=""):
        now = self.now()
        await self.bots.update_one(
            {"bot_id": bot_id},
            {
                "$set": {
                    "owner_id": owner_id,
                    "token": token,
                    "username": username or "",
                    "status": "starting",
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "bot_id": bot_id,
                    "force_join_channels": [],
                    "created_at": now,
                    "last_started_at": None,
                    "last_stopped_at": None,
                    "last_error": None,
                },
            },
            upsert=True,
        )

    async def get_bot(self, bot_id: int):
        return await self.bots.find_one({"bot_id": bot_id})

    async def get_user_bots(self, owner_id: int):
        return await self.bots.find({"owner_id": owner_id}).sort("created_at", DESCENDING).to_list(length=None)

    async def get_all_bots(self):
        return await self.bots.find({}).sort("created_at", DESCENDING).to_list(length=None)

    async def count_bots(self):
        return await self.bots.count_documents({})

    async def count_active_bots(self):
        return await self.bots.count_documents({"status": "active"})

    async def count_failed_bots(self):
        return await self.bots.count_documents({"status": "failed"})

    async def update_bot_status(self, bot_id: int, status: str, error: Optional[str] = None):
        update = {"$set": {"status": status, "updated_at": self.now()}}
        if status == "active":
            update["$set"]["last_started_at"] = self.now()
            update["$set"]["last_error"] = None
        elif status in {"stopped", "inactive"}:
            update["$set"]["last_stopped_at"] = self.now()
        elif status == "failed":
            update["$set"]["last_error"] = error or "Unknown error"
        await self.bots.update_one({"bot_id": bot_id}, update)

    async def delete_bot(self, bot_id: int):
        await self.bots.delete_one({"bot_id": bot_id})
        await self.users.delete_many({"bot_id": bot_id})
        await self.downloads.delete_many({"bot_id": bot_id})
        await self.pending_downloads.delete_many({"bot_id": bot_id})

    async def search_bots(self, text: str):
        text = (text or "").strip().lstrip("@")
        if not text:
            return []
        query = {"username": {"$regex": text, "$options": "i"}}
        if text.isdigit():
            query = {"$or": [query, {"bot_id": int(text)}]}
        return await self.bots.find(query).sort("created_at", DESCENDING).to_list(length=None)

    # ---------- Bot users ----------
    async def save_bot_user(self, bot_id: int, user_id: int, username="", first_name="", language="en"):
        now = self.now()
        await self.users.update_one(
            {"bot_id": bot_id, "user_id": user_id},
            {
                "$set": {
                    "username": username or "",
                    "first_name": first_name or "",
                    "language": language or "en",
                    "last_seen": now,
                },
                "$setOnInsert": {
                    "bot_id": bot_id,
                    "user_id": user_id,
                    "created_at": now,
                    "downloads_count": 0,
                },
            },
            upsert=True,
        )

    async def get_bot_user(self, bot_id: int, user_id: int):
        return await self.users.find_one({"bot_id": bot_id, "user_id": user_id})

    async def get_all_bot_users(self, bot_id: int):
        return await self.users.find({"bot_id": bot_id}).to_list(length=None)

    async def count_bot_users(self, bot_id: int):
        return await self.users.count_documents({"bot_id": bot_id})

    async def count_all_bot_users(self):
        return await self.users.count_documents({})

    async def update_bot_user_language(self, bot_id: int, user_id: int, language: str):
        await self.users.update_one(
            {"bot_id": bot_id, "user_id": user_id},
            {"$set": {"language": language, "last_seen": self.now()}},
        )

    async def increment_user_downloads(self, bot_id: int, user_id: int):
        await self.users.update_one(
            {"bot_id": bot_id, "user_id": user_id},
            {"$inc": {"downloads_count": 1}, "$set": {"last_seen": self.now()}},
            upsert=True,
        )

    # ---------- Downloads ----------
    async def add_download(self, bot_id: int, user_id: int, url="", platform="", media_type="video", status="success", file_size=0):
        result = await self.downloads.insert_one({
            "bot_id": bot_id,
            "user_id": user_id,
            "url": url or "",
            "platform": platform or "",
            "media_type": media_type or "video",
            "status": status or "success",
            "file_size": file_size or 0,
            "created_at": self.now(),
        })
        if status == "success":
            await self.increment_user_downloads(bot_id, user_id)
        return result

    async def count_downloads(self, bot_id: Optional[int] = None):
        return await self.downloads.count_documents({"bot_id": bot_id} if bot_id is not None else {})

    async def count_successful_downloads(self, bot_id: Optional[int] = None):
        query = {"status": "success"}
        if bot_id is not None:
            query["bot_id"] = bot_id
        return await self.downloads.count_documents(query)

    async def get_bot_stats(self, bot_id: int):
        base = {"bot_id": bot_id}
        return {
            "total_users": await self.users.count_documents(base),
            "total_downloads": await self.downloads.count_documents(base),
            "videos": await self.downloads.count_documents({**base, "media_type": "video"}),
            "audio": await self.downloads.count_documents({**base, "media_type": "audio"}),
            "photos": await self.downloads.count_documents({**base, "media_type": "photo"}),
            "successful": await self.downloads.count_documents({**base, "status": "success"}),
            "failed": await self.downloads.count_documents({**base, "status": "failed"}),
        }

    async def get_global_stats(self):
        return {
            "users": await self.count_main_users(),
            "bots": await self.count_bots(),
            "active_bots": await self.count_active_bots(),
            "failed_bots": await self.count_failed_bots(),
            "bot_users": await self.count_all_bot_users(),
            "downloads": await self.count_downloads(),
            "successful_downloads": await self.count_successful_downloads(),
        }

    # ---------- Global Force Join (applies to EVERY managed bot) ----------
    async def get_global_force_join_channels(self):
        value = await self.get_system_setting("global_force_join_channels", [])
        return value if isinstance(value, list) else []

    async def set_global_force_join_channels(self, channels: List[str]):
        cleaned = []
        for channel in channels[:5]:
            value = str(channel).strip()
            if not value:
                continue
            if not value.startswith("@") and not value.startswith("-100"):
                value = "@" + value
            if value not in cleaned:
                cleaned.append(value)
        await self.set_system_setting("global_force_join_channels", cleaned)
        return cleaned

    async def add_global_force_join_channel(self, channel: str):
        channels = await self.get_global_force_join_channels()
        if len(channels) >= 5:
            return False, channels
        value = str(channel).strip()
        if not value:
            return False, channels
        if not value.startswith("@") and not value.startswith("-100"):
            value = "@" + value
        if value in channels:
            return False, channels
        channels.append(value)
        return True, await self.set_global_force_join_channels(channels)

    async def remove_global_force_join_channel(self, index: int):
        channels = await self.get_global_force_join_channels()
        if 0 <= index < len(channels):
            channels.pop(index)
            await self.set_global_force_join_channels(channels)
            return True
        return False

    async def clear_global_force_join_channels(self):
        await self.set_global_force_join_channels([])

    # Legacy per-bot methods kept for compatibility with old data.
    async def get_force_join_channels(self, bot_id: int):
        bot = await self.get_bot(bot_id)
        value = (bot or {}).get("force_join_channels", [])
        return value if isinstance(value, list) else []

    async def add_force_join_channel(self, bot_id: int, channel: str):
        channel = channel.strip()
        if not channel:
            return False
        if not channel.startswith("@"):
            channel = "@" + channel
        result = await self.bots.update_one(
            {"bot_id": bot_id},
            {"$addToSet": {"force_join_channels": channel}, "$set": {"updated_at": self.now()}},
        )
        return result.modified_count > 0

    async def remove_force_join_channel(self, bot_id: int, channel: str):
        if not channel.startswith("@"):
            channel = "@" + channel
        result = await self.bots.update_one(
            {"bot_id": bot_id},
            {"$pull": {"force_join_channels": channel}, "$set": {"updated_at": self.now()}},
        )
        return result.modified_count > 0

    # ---------- Pending downloads for force-join flow ----------
    async def set_pending_download(self, bot_id: int, user_id: int, url: str):
        await self.pending_downloads.update_one(
            {"bot_id": bot_id, "user_id": user_id},
            {"$set": {"url": url, "created_at": self.now()}},
            upsert=True,
        )

    async def get_pending_download(self, bot_id: int, user_id: int):
        return await self.pending_downloads.find_one({"bot_id": bot_id, "user_id": user_id})

    async def clear_pending_download(self, bot_id: int, user_id: int):
        await self.pending_downloads.delete_one({"bot_id": bot_id, "user_id": user_id})

    # ---------- Creation/settings ----------
    async def is_bot_creation_enabled(self):
        return bool(await self.get_system_setting("bot_creation_enabled", True))

    async def set_bot_creation_enabled(self, enabled: bool):
        await self.set_system_setting("bot_creation_enabled", bool(enabled))

    async def count_user_bots(self, owner_id: int):
        return await self.bots.count_documents({"owner_id": owner_id})

    async def can_create_bot(self, owner_id: int, max_bots=5):
        return await self.is_bot_creation_enabled() and (await self.count_user_bots(owner_id)) < max_bots

    async def remove_old_downloads(self, before_date):
        result = await self.downloads.delete_many({"created_at": {"$lt": before_date}})
        return result.deleted_count


db = Database()
