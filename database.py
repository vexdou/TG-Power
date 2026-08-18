import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(Config.MONGO_URI)
        self.db = self.client[Config.DB_NAME]
        
        # Collections
        self.users = self.db.users
        self.bots = self.db.bots
        self.bot_users = self.db.bot_users
        self.downloads = self.db.downloads
        self.broadcasts = self.db.broadcasts
        self.settings = self.db.settings
        self.channels = self.db.channels

    async def init_db(self):
        # Create Indexes for fast querying
        await self.users.create_index("user_id", unique=True)
        await self.bots.create_index("bot_id", unique=True)
        await self.bots.create_index("owner_id")
        await self.bots.create_index("username", unique=True)
        await self.bot_users.create_index([("bot_id", 1), ("user_id", 1)], unique=True)
        await self.downloads.create_index([("bot_id", 1), ("timestamp", -1)])

    # Main Bot User Operations
    async def get_or_create_user(self, user_id: int, username: str = None, full_name: str = None):
        user = await self.users.find_one({"user_id": user_id})
        if not user:
            user = {
                "user_id": user_id,
                "username": username,
                "full_name": full_name,
                "can_create_bots": True,
                "is_blocked": False,
                "created_at": datetime.now(timezone.utc)
            }
            await self.users.insert_one(user)
        return user

    # Managed Bot Operations
    async def add_bot(self, bot_id: int, owner_id: int, name: str, username: str, token: str):
        bot_doc = {
            "bot_id": bot_id,
            "owner_id": owner_id,
            "name": name,
            "username": username,
            "token": token,
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "force_join_channels": [],
            "settings": {
                "download_limit": Config.DEFAULT_DOWNLOAD_LIMIT,
                "allow_audio": True
            }
        }
        await self.bots.insert_one(bot_doc)

    async def get_user_bots(self, owner_id: int):
        cursor = self.bots.find({"owner_id": owner_id})
        return await cursor.to_list(length=100)

    async def get_all_active_bots(self):
        cursor = self.bots.find({"status": "active"})
        return await cursor.to_list(length=1000)

    async def get_bot(self, bot_id: int):
        return await self.bots.find_one({"bot_id": bot_id})

    async def update_bot_status(self, bot_id: int, status: str):
        await self.bots.update_one({"bot_id": bot_id}, {"$set": {"status": status}})

    async def delete_bot(self, bot_id: int):
        await self.bots.delete_one({"bot_id": bot_id})
        await self.bot_users.delete_many({"bot_id": bot_id})
        await self.downloads.delete_many({"bot_id": bot_id})

    # Stats Operations
    async def log_download(self, bot_id: int, user_id: int, platform: str, media_type: str):
        await self.downloads.insert_one({
            "bot_id": bot_id,
            "user_id": user_id,
            "platform": platform,
            "media_type": media_type,
            "timestamp": datetime.now(timezone.utc)
        })

    async def get_bot_stats(self, bot_id: int):
        total_users = await self.bot_users.count_documents({"bot_id": bot_id})
        total_downloads = await self.downloads.count_documents({"bot_id": bot_id})
        videos = await self.downloads.count_documents({"bot_id": bot_id, "media_type": "video"})
        audio = await self.downloads.count_documents({"bot_id": bot_id, "media_type": "audio"})
        return {
            "total_users": total_users,
            "total_downloads": total_downloads,
            "videos": videos,
            "audio": audio
        }

db = Database()
