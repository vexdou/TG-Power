import logging

from motor.motor_asyncio import AsyncIOMotorClient
from config import Config


logger = logging.getLogger(__name__)


class Database:

    def __init__(self):

        self.client = AsyncIOMotorClient(
            Config.MONGO_URI,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000
        )

        self.db = self.client[
            Config.DB_NAME
        ]

        self.bots = self.db["bots"]
        self.users = self.db["bot_users"]
        self.downloads = self.db["downloads"]

    async def init_db(self):

        try:

            # Test MongoDB connection first.
            await self.client.admin.command(
                "ping"
            )

            await self.bots.create_index(
                "bot_id",
                unique=True
            )

            await self.users.create_index(
                [
                    ("bot_id", 1),
                    ("user_id", 1)
                ],
                unique=True
            )

            logger.info(
                "✅ MongoDB Indexes initialized successfully."
            )

        except Exception as e:

            logger.error(
                f"❌ Database initialization error: "
                f"{e}",
                exc_info=True
            )

            # Do not crash the whole application here.
            # The rest of the bot can continue and the
            # next database operation will report its error.

    # ================================================================
    # MANAGED BOTS OPERATIONS
    # ================================================================

    async def add_new_bot(
        self,
        owner_id: int,
        token: str,
        bot_id: int,
        username: str = ""
    ):

        bot_data = {
            "bot_id": bot_id,
            "owner_id": owner_id,
            "token": token,
            "username": username,
            "status": "active",
            "force_join_channels": []
        }

        await self.bots.update_one(
            {
                "bot_id": bot_id
            },
            {
                "$set": bot_data
            },
            upsert=True
        )

    async def get_bot(
        self,
        bot_id: int
    ):

        return await self.bots.find_one(
            {
                "bot_id": bot_id
            }
        )

    async def get_all_active_bots(self):

        cursor = self.bots.find(
            {
                "status": "active"
            }
        )

        return await cursor.to_list(
            length=None
        )

    async def update_bot_status(
        self,
        bot_id: int,
        status: str
    ):

        await self.bots.update_one(
            {
                "bot_id": bot_id
            },
            {
                "$set": {
                    "status": status
                }
            }
        )

    # ================================================================
    # USER MANAGEMENT
    # ================================================================

    async def save_bot_user(
        self,
        bot_id: int,
        user_id: int,
        username: str,
        full_name: str
    ):

        user_data = {
            "bot_id": bot_id,
            "user_id": user_id,
            "username": username,
            "full_name": full_name
        }

        await self.users.update_one(
            {
                "bot_id": bot_id,
                "user_id": user_id
            },
            {
                "$setOnInsert": {
                    "language": Config.DEFAULT_LANG
                },
                "$set": user_data
            },
            upsert=True
        )

    async def get_bot_user(
        self,
        bot_id: int,
        user_id: int
    ):

        return await self.users.find_one(
            {
                "bot_id": bot_id,
                "user_id": user_id
            }
        )

    async def set_user_language(
        self,
        bot_id: int,
        user_id: int,
        lang: str
    ):

        await self.users.update_one(
            {
                "bot_id": bot_id,
                "user_id": user_id
            },
            {
                "$set": {
                    "language": lang
                }
            }
        )

    async def get_all_bot_users(
        self,
        bot_id: int
    ):

        cursor = self.users.find(
            {
                "bot_id": bot_id
            }
        )

        return await cursor.to_list(
            length=None
        )

    # ================================================================
    # DOWNLOAD STATS
    # ================================================================

    async def log_download(
        self,
        bot_id: int,
        user_id: int,
        platform: str,
        media_type: str
    ):

        record = {
            "bot_id": bot_id,
            "user_id": user_id,
            "platform": platform,
            "media_type": media_type
        }

        await self.downloads.insert_one(
            record
        )

    async def get_bot_stats(
        self,
        bot_id: int
    ):

        total_users = (
            await self.users.count_documents(
                {
                    "bot_id": bot_id
                }
            )
        )

        total_downloads = (
            await self.downloads.count_documents(
                {
                    "bot_id": bot_id
                }
            )
        )

        videos = (
            await self.downloads.count_documents(
                {
                    "bot_id": bot_id,
                    "media_type": "video"
                }
            )
        )

        audio = (
            await self.downloads.count_documents(
                {
                    "bot_id": bot_id,
                    "media_type": "audio"
                }
            )
        )

        return {
            "total_users": total_users,
            "total_downloads": total_downloads,
            "videos": videos,
            "audio": audio
        }


db = Database()
