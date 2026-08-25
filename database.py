import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(Config.MONGO_URI)
        self.db = self.client[Config.DB_NAME]

        self.users = self.db.users
        self.bots = self.db.bots
        self.bot_users = self.db.bot_users
        self.downloads = self.db.downloads
        self.broadcasts = self.db.broadcasts
        self.settings = self.db.settings
        self.pending_downloads = self.db.pending_downloads

    async def init_db(self):
        await self.users.create_index("user_id", unique=True)
        await self.bots.create_index("bot_id", unique=True)
        await self.bots.create_index("owner_id")
        await self.bots.create_index("username", unique=True)
        await self.bot_users.create_index(
            [("bot_id", 1), ("user_id", 1)], unique=True
        )
        await self.downloads.create_index([("bot_id", 1), ("timestamp", -1)])

        if not await self.settings.find_one({"_id": "platform_config"}):
            await self.settings.insert_one({
                "_id": "platform_config",
                "force_join_channels": [],
                "maintenance_mode": False,
                "bot_creation_enabled": True,
            })

    # ---------------- MAIN BOT USERS ----------------

    async def save_main_user(self, user_id: int, username: str = "", full_name: str = ""):
        user_id = int(user_id)
        user = await self.users.find_one({"user_id": user_id})
        if user:
            update = {}
            if username and user.get("username") != username:
                update["username"] = username
            if full_name and user.get("full_name") != full_name:
                update["full_name"] = full_name
            if update:
                await self.users.update_one({"user_id": user_id}, {"$set": update})
            return user

        user_doc = {
            "user_id": user_id,
            "username": username or "",
            "full_name": full_name or "",
            "language": "en",
            "is_banned": False,
            "created_at": datetime.now(timezone.utc),
        }
        await self.users.insert_one(user_doc)
        return user_doc

    async def get_main_user_language(self, user_id: int) -> str:
        user = await self.users.find_one({"user_id": int(user_id)})
        if user and user.get("language"):
            return user["language"]
        return "en"

    async def set_main_user_language(self, user_id: int, language: str):
        await self.users.update_one(
            {"user_id": int(user_id)},
            {"$set": {"language": language}},
            upsert=True,
        )

    async def get_all_main_users(self):
        cursor = self.users.find()
        return await cursor.to_list(length=10000)

    # ---------------- MANAGED BOTS ----------------

    async def save_bot(
        self,
        bot_id: int | str,
        owner_id: int | str,
        token: str,
        username: str,
        title: str,
    ):
        bot_id = int(bot_id)
        owner_id = int(owner_id)
        existing = await self.bots.find_one({"bot_id": bot_id})
        created_at = (
            existing.get("created_at")
            if existing
            else datetime.now(timezone.utc)
        )

        bot_doc = {
            "bot_id": bot_id,
            "owner_id": owner_id,
            "title": title or "",
            "username": username or "",
            "token": token,
            "status": existing.get("status", "starting") if existing else "starting",
            "created_at": created_at,
            "force_join_channels": existing.get("force_join_channels", []) if existing else [],
        }

        await self.bots.update_one(
            {"bot_id": bot_id},
            {"$set": bot_doc},
            upsert=True,
        )

    async def get_bot(self, bot_id: int | str):
        return await self.bots.find_one({"bot_id": int(bot_id)})

    async def get_user_bots(self, owner_id: int | str):
        cursor = self.bots.find({"owner_id": int(owner_id)}).sort("created_at", -1)
        return await cursor.to_list(length=100)

    async def get_all_bots(self):
        cursor = self.bots.find()
        return await cursor.to_list(length=1000)

    async def get_all_active_bots(self):
        cursor = self.bots.find(
            {"status": {"$in": ["active", "starting", "failed"]}}
        )
        return await cursor.to_list(length=1000)

    async def delete_bot(self, bot_id: int | str):
        bid = int(bot_id)
        await self.bots.delete_one({"bot_id": bid})
        await self.bot_users.delete_many({"bot_id": bid})
        await self.downloads.delete_many({"bot_id": bid})

    async def update_bot_status(self, bot_id: int | str, status: str):
        await self.bots.update_one(
            {"bot_id": int(bot_id)},
            {"$set": {
                "status": status,
                "status_updated_at": datetime.now(timezone.utc),
            }},
        )

    async def search_bots(self, query: str):
        query = str(query).strip().lstrip("@")
        if query.isdigit():
            cursor = self.bots.find({"bot_id": int(query)})
        else:
            cursor = self.bots.find({"username": {"$regex": query, "$options": "i"}})
        return await cursor.to_list(length=30)

    # ---------------- SETTINGS & FORCE JOIN ----------------

    async def is_bot_creation_enabled(self) -> bool:
        cfg = await self.settings.find_one({"_id": "platform_config"})
        return cfg.get("bot_creation_enabled", True) if cfg else True

    async def set_bot_creation_enabled(self, status: bool):
        await self.settings.update_one(
            {"_id": "platform_config"},
            {"$set": {"bot_creation_enabled": status}},
            upsert=True,
        )

    async def get_global_force_join_channels(self):
        cfg = await self.settings.find_one({"_id": "platform_config"})
        return cfg.get("force_join_channels", []) if cfg else []

    async def add_global_force_join_channel(self, channel: str):
        channels = await self.get_global_force_join_channels()
        if channel in channels or len(channels) >= 5:
            return False, channels
        await self.settings.update_one(
            {"_id": "platform_config"},
            {"$addToSet": {"force_join_channels": channel}},
            upsert=True,
        )
        new_channels = await self.get_global_force_join_channels()
        return True, new_channels

    async def remove_global_force_join_channel(self, channel: str):
        await self.settings.update_one(
            {"_id": "platform_config"},
            {"$pull": {"force_join_channels": channel}},
        )

    async def clear_global_force_join_channels(self):
        await self.settings.update_one(
            {"_id": "platform_config"},
            {"$set": {"force_join_channels": []}},
            upsert=True,
        )

    async def get_system_setting(self, key: str, default=None):
        cfg = await self.settings.find_one({"_id": "platform_config"})
        return cfg.get(key, default) if cfg else default

    async def set_system_setting(self, key: str, value):
        await self.settings.update_one(
            {"_id": "platform_config"},
            {"$set": {key: value}},
            upsert=True,
        )

    # ---------------- MANAGED BOT USERS ----------------

    async def save_bot_user(
        self,
        bot_id: int | str,
        user_id: int | str,
        username: str = "",
        full_name: str = "",
    ):
        bid = int(bot_id)
        uid = int(user_id)
        now = datetime.now(timezone.utc)

        await self.bot_users.update_one(
            {"bot_id": bid, "user_id": uid},
            {
                "$set": {
                    "username": username or "",
                    "full_name": full_name or "",
                    "last_seen": now,
                },
                "$setOnInsert": {
                    "bot_id": bid,
                    "user_id": uid,
                    "language": "en",
                    "created_at": now,
                },
            },
            upsert=True,
        )

    async def get_all_bot_users(self, bot_id: int | str):
        cursor = self.bot_users.find(
            {"bot_id": int(bot_id)}, {"user_id": 1}
        )
        return await cursor.to_list(length=None)

    # ---------------- STATS ----------------

    async def get_bot_stats(self, bot_id: int | str):
        bid = int(bot_id)
        total_users = await self.bot_users.count_documents({"bot_id": bid})
        total_downloads = await self.downloads.count_documents({"bot_id": bid})
        videos = await self.downloads.count_documents({"bot_id": bid, "media_type": "video"})
        audio = await self.downloads.count_documents({"bot_id": bid, "media_type": "audio"})
        photos = await self.downloads.count_documents({"bot_id": bid, "media_type": "photo"})

        return {
            "total_users": total_users,
            "total_downloads": total_downloads,
            "videos": videos,
            "audio": audio,
            "photos": photos,
        }

    async def get_global_stats(self):
        users = await self.users.count_documents({})
        bots = await self.bots.count_documents({})
        active_bots = await self.bots.count_documents({"status": "active"})
        failed_bots = await self.bots.count_documents({"status": "failed"})
        bot_users = await self.bot_users.count_documents({})
        downloads = await self.downloads.count_documents({})

        return {
            "users": users,
            "bots": bots,
            "active_bots": active_bots,
            "failed_bots": failed_bots,
            "bot_users": bot_users,
            "downloads": downloads,
        }

    async def count_downloads(self):
        return await self.downloads.count_documents({})

    async def count_successful_downloads(self):
        return await self.downloads.count_documents({"status": "success"})


db = Database()
