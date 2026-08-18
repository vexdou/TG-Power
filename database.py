import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

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
        await self.bot_users.create_index([("bot_id", 1), ("user_id", 1)], unique=True)
        await self.downloads.create_index([("bot_id", 1), ("timestamp", -1)])
        
        # Initialize default platform settings
        if not await self.settings.find_one({"_id": "platform_config"}):
            await self.settings.insert_one({
                "_id": "platform_config",
                "force_join_channels": [],
                "maintenance_mode": False
            })

    # Main Bot User Operations
    async def get_or_create_user(self, user_id: int, username: str = None, full_name: str = None):
        user = await self.users.find_one({"user_id": user_id})
        if not user:
            user = {
                "user_id": user_id,
                "username": username,
                "full_name": full_name,
                "language": None,
                "is_banned": False,
                "created_at": datetime.now(timezone.utc)
            }
            await self.users.insert_one(user)
        return user

    async def set_main_user_language(self, user_id: int, language: str):
        await self.users.update_one({"user_id": user_id}, {"$set": {"language": language}})

    async def ban_unban_user(self, user_id: int, ban_status: bool):
        await self.users.update_one({"user_id": user_id}, {"$set": {"is_banned": ban_status}})

    # Settings & Force Join
    async def get_platform_settings(self):
        return await self.settings.find_one({"_id": "platform_config"})

    async def add_force_join_channel(self, channel: str):
        await self.settings.update_one(
            {"_id": "platform_config"},
            {"$addToSet": {"force_join_channels": channel}}
        )

    async def remove_force_join_channel(self, channel: str):
        await self.settings.update_one(
            {"_id": "platform_config"},
            {"$pull": {"force_join_channels": channel}}
        )

    # Scalable Cursor for 1,000,000+ Users Broadcast
    async def get_all_main_users_cursor(self):
        return self.users.find({"is_banned": False}, {"user_id": 1})

    # Platform Global Stats
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
            "total_bot_users": total_bot_users
        }

    # Managed Bot Operations
    async def save_managed_bot(self, bot_id: int, owner_id: int, username: str, name: str, token: str):
        bot_doc = {
            "bot_id": bot_id,
            "owner_id": owner_id,
            "name": name,
            "username": username,
            "token": token,
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "force_join_channels": [],
            "settings": {"download_limit": Config.DEFAULT_DOWNLOAD_LIMIT, "allow_audio": True}
        }
        await self.bots.update_one({"bot_id": bot_id}, {"$set": bot_doc}, upsert=True)

    async def get_user_bots(self, owner_id: int):
        cursor = self.bots.find({"owner_id": owner_id})
        return await cursor.to_list(length=100)

    async def get_all_active_bots(self):
        cursor = self.bots.find({"status": "active"})
        return await cursor.to_list(length=1000)

    async def delete_bot(self, bot_id: int):
        await self.bots.delete_one({"bot_id": bot_id})
        await self.bot_users.delete_many({"bot_id": bot_id})

    async def update_bot_status(self, bot_id: int, status: str):
        await self.bots.update_one({"bot_id": bot_id}, {"$set": {"status": status}})

db = Database()
