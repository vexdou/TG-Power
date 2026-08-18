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
            })

    # ---------------- MAIN BOT ----------------

    async def get_or_create_user(
        self, user_id: int, username: str = None, full_name: str = None
    ):
        user = await self.users.find_one({"user_id": user_id})

        if user:
            update = {}
            if username is not None and user.get("username") != username:
                update["username"] = username
            if full_name is not None and user.get("full_name") != full_name:
                update["full_name"] = full_name
            if update:
                await self.users.update_one(
                    {"user_id": user_id}, {"$set": update}
                )
                user.update(update)
            return user

        user = {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "language": None,
            "is_banned": False,
            "created_at": datetime.now(timezone.utc),
        }
        await self.users.insert_one(user)
        return user

    async def set_main_user_language(self, user_id: int, language: str):
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"language": language}},
            upsert=True,
        )

    async def ban_unban_user(self, user_id: int, ban_status: bool):
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_banned": ban_status}},
        )

    async def get_platform_settings(self):
        return await self.settings.find_one({"_id": "platform_config"})

    async def add_force_join_channel(self, channel: str):
        await self.settings.update_one(
            {"_id": "platform_config"},
            {"$addToSet": {"force_join_channels": channel}},
            upsert=True,
        )

    async def remove_force_join_channel(self, channel: str):
        await self.settings.update_one(
            {"_id": "platform_config"},
            {"$pull": {"force_join_channels": channel}},
        )

    async def get_all_main_users_cursor(self):
        return self.users.find({"is_banned": False}, {"user_id": 1})

    # ---------------- MANAGED BOTS ----------------

    async def save_managed_bot(
        self,
        bot_id: int,
        owner_id: int,
        username: str,
        name: str,
        token: str,
    ):
        existing = await self.bots.find_one({"bot_id": bot_id})
        created_at = (
            existing.get("created_at")
            if existing
            else datetime.now(timezone.utc)
        )

        bot_doc = {
            "bot_id": bot_id,
            "owner_id": owner_id,
            "name": name,
            "username": username,
            "token": token,
            "status": "starting",
            "created_at": created_at,
            "force_join_channels": existing.get("force_join_channels", [])
            if existing else [],
            "settings": existing.get(
                "settings",
                {
                    "download_limit": getattr(
                        Config, "DEFAULT_DOWNLOAD_LIMIT", 10
                    ),
                    "allow_audio": True,
                },
            ) if existing else {
                "download_limit": getattr(
                    Config, "DEFAULT_DOWNLOAD_LIMIT", 10
                ),
                "allow_audio": True,
            },
        }

        await self.bots.update_one(
            {"bot_id": bot_id},
            {"$set": bot_doc},
            upsert=True,
        )

    async def get_bot(self, bot_id: int):
        return await self.bots.find_one({"bot_id": bot_id})

    async def get_user_bots(self, owner_id: int):
        cursor = self.bots.find(
            {"owner_id": owner_id}
        ).sort("created_at", -1)
        return await cursor.to_list(length=100)

    async def get_all_active_bots(self):
        cursor = self.bots.find(
            {"status": {"$in": ["active", "starting", "failed"]}}
        )
        return await cursor.to_list(length=1000)

    async def delete_bot(self, bot_id: int):
        await self.bots.delete_one({"bot_id": bot_id})
        await self.bot_users.delete_many({"bot_id": bot_id})
        await self.downloads.delete_many({"bot_id": bot_id})

    async def update_bot_status(self, bot_id: int, status: str):
        await self.bots.update_one(
            {"bot_id": bot_id},
            {"$set": {
                "status": status,
                "status_updated_at": datetime.now(timezone.utc),
            }},
        )

    # ---------------- MANAGED BOT USERS ----------------

    async def save_bot_user(
        self,
        bot_id: int,
        user_id: int,
        username: str = "",
        full_name: str = "",
    ):
        now = datetime.now(timezone.utc)

        await self.bot_users.update_one(
            {"bot_id": bot_id, "user_id": user_id},
            {
                "$set": {
                    "username": username or "",
                    "full_name": full_name or "",
                    "last_seen": now,
                },
                "$setOnInsert": {
                    "bot_id": bot_id,
                    "user_id": user_id,
                    "language": "en",
                    "created_at": now,
                },
            },
            upsert=True,
        )

    async def set_user_language(
        self, bot_id: int, user_id: int, language: str
    ):
        await self.bot_users.update_one(
            {"bot_id": bot_id, "user_id": user_id},
            {"$set": {"language": language}},
            upsert=True,
        )

    async def get_bot_user(self, bot_id: int, user_id: int):
        return await self.bot_users.find_one(
            {"bot_id": bot_id, "user_id": user_id}
        )

    async def get_all_bot_users(self, bot_id: int):
        cursor = self.bot_users.find(
            {"bot_id": bot_id}, {"user_id": 1}
        )
        return await cursor.to_list(length=None)

    # ---------------- DOWNLOADS / STATS ----------------

    async def log_download(
        self,
        bot_id: int,
        user_id: int,
        platform: str,
        media_type: str,
    ):
        await self.downloads.insert_one({
            "bot_id": bot_id,
            "user_id": user_id,
            "platform": platform,
            "media_type": media_type,
            "timestamp": datetime.now(timezone.utc),
        })

    async def get_bot_stats(self, bot_id: int):
        total_users = await self.bot_users.count_documents(
            {"bot_id": bot_id}
        )
        total_downloads = await self.downloads.count_documents(
            {"bot_id": bot_id}
        )

        return {
            "total_users": total_users,
            "total_downloads": total_downloads,
        }

    async def get_global_platform_stats(self):
        total_main_users = await self.users.count_documents({})
        total_created_bots = await self.bots.count_documents({})
        active_bots = await self.bots.count_documents({"status": "active"})
        total_downloads = await self.downloads.count_documents({})
        total_bot_users = await self.bot_users.count_documents({})

        return {
            "total_main_users": total_main_users,
            "total_created_bots": total_created_bots,
            "active_bots": active_bots,
            "total_downloads": total_downloads,
            "total_bot_users": total_bot_users,
        }


db = Database()
