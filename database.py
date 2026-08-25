import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

from config import Config


logger = logging.getLogger(__name__)


class Database:
    """
    MongoDB database layer for TG-Power.

    Supports:
    - Main bot users
    - Managed bots
    - Managed bot users
    - Downloads
    - Global settings
    - Statistics
    - Force-join channels
    - Bot lifecycle/status
    """

    def __init__(self):
        self.client = AsyncIOMotorClient(
            Config.MONGO_URI,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=30000,
            retryWrites=True,
        )

        self.db = self.client[Config.DB_NAME]

        # Collections
        self.users = self.db.users
        self.bots = self.db.bots
        self.bot_users = self.db.bot_users
        self.downloads = self.db.downloads
        self.broadcasts = self.db.broadcasts
        self.settings = self.db.settings
        self.pending_downloads = self.db.pending_downloads

        self._connected = False

    # =========================================================
    # CONNECTION
    # =========================================================

    async def connect(self):
        """
        Connect to MongoDB and initialize indexes/settings.

        main.py calls:
            await db.connect()
        """

        try:
            # Force an actual connection check.
            await self.client.admin.command("ping")

            await self.init_db()

            self._connected = True

            logger.info("✅ MongoDB connected successfully")

        except Exception:
            self._connected = False

            logger.exception(
                "❌ MongoDB connection failed"
            )

            raise

    async def close(self):
        """
        Safely close MongoDB connection.

        main.py calls:
            await db.close()
        """

        try:
            self.client.close()
            self._connected = False

            logger.info(
                "🔌 MongoDB connection closed"
            )

        except Exception:
            logger.exception(
                "Database close error"
            )

    async def init_db(self):
        """
        Create indexes and default platform configuration.
        """

        # Main users
        await self.users.create_index(
            [("user_id", ASCENDING)],
            unique=True,
            name="user_id_unique",
        )

        # Managed bots
        await self.bots.create_index(
            [("bot_id", ASCENDING)],
            unique=True,
            name="bot_id_unique",
        )

        await self.bots.create_index(
            [("owner_id", ASCENDING)],
            name="owner_id_index",
        )

        await self.bots.create_index(
            [("username", ASCENDING)],
            unique=True,
            sparse=True,
            name="username_unique",
        )

        await self.bots.create_index(
            [("status", ASCENDING)],
            name="status_index",
        )

        # Managed bot users
        await self.bot_users.create_index(
            [
                ("bot_id", ASCENDING),
                ("user_id", ASCENDING),
            ],
            unique=True,
            name="bot_user_unique",
        )

        await self.bot_users.create_index(
            [("bot_id", ASCENDING)],
            name="bot_users_bot_id",
        )

        # Downloads
        await self.downloads.create_index(
            [
                ("bot_id", ASCENDING),
                ("timestamp", DESCENDING),
            ],
            name="downloads_bot_timestamp",
        )

        await self.downloads.create_index(
            [("user_id", ASCENDING)],
            name="downloads_user_id",
        )

        # Settings
        await self.settings.create_index(
            [("_id", ASCENDING)],
            unique=True,
            name="settings_id",
        )

        # Pending downloads
        await self.pending_downloads.create_index(
            [("created_at", DESCENDING)],
            name="pending_created_at",
        )

        # Default configuration
        existing = await self.settings.find_one(
            {"_id": "platform_config"}
        )

        if not existing:
            await self.settings.insert_one(
                {
                    "_id": "platform_config",
                    "force_join_channels": [],
                    "maintenance_mode": False,
                    "bot_creation_enabled": True,
                    "max_video_seconds": 600,
                    "max_file_mb": 50,
                    "created_at": datetime.now(timezone.utc),
                }
            )
        else:
            # Add missing settings without overwriting
            # existing admin configuration.
            await self.settings.update_one(
                {"_id": "platform_config"},
                {
                    "$setOnInsert": {
                        "force_join_channels": [],
                        "maintenance_mode": False,
                        "bot_creation_enabled": True,
                    }
                },
                upsert=True,
            )

    # =========================================================
    # MAIN BOT USERS
    # =========================================================

    async def save_main_user(
        self,
        user_id: int,
        username: str = "",
        full_name: str = "",
    ):
        user_id = int(user_id)

        now = datetime.now(timezone.utc)

        await self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "username": username or "",
                    "full_name": full_name or "",
                    "last_seen": now,
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "language": "en",
                    "is_banned": False,
                    "created_at": now,
                },
            },
            upsert=True,
        )

        return await self.users.find_one(
            {"user_id": user_id}
        )

    async def get_main_user(
        self,
        user_id: int,
    ):
        return await self.users.find_one(
            {"user_id": int(user_id)}
        )

    async def get_main_user_language(
        self,
        user_id: int,
    ) -> str:

        user = await self.users.find_one(
            {"user_id": int(user_id)}
        )

        if user:
            return user.get(
                "language",
                "en",
            )

        return "en"

    async def set_main_user_language(
        self,
        user_id: int,
        language: str,
    ):

        await self.users.update_one(
            {"user_id": int(user_id)},
            {
                "$set": {
                    "language": language,
                    "last_seen": datetime.now(
                        timezone.utc
                    ),
                },
                "$setOnInsert": {
                    "user_id": int(user_id),
                    "is_banned": False,
                    "created_at": datetime.now(
                        timezone.utc
                    ),
                },
            },
            upsert=True,
        )

    async def get_all_main_users(self):

        cursor = self.users.find({})

        return await cursor.to_list(
            length=10000
        )

    async def is_main_user_banned(
        self,
        user_id: int,
    ) -> bool:

        user = await self.users.find_one(
            {"user_id": int(user_id)},
            {"is_banned": 1},
        )

        return bool(
            user and user.get("is_banned", False)
        )

    async def set_main_user_banned(
        self,
        user_id: int,
        banned: bool,
    ):

        await self.users.update_one(
            {"user_id": int(user_id)},
            {
                "$set": {
                    "is_banned": bool(banned)
                }
            },
            upsert=True,
        )

    # =========================================================
    # MANAGED BOTS
    # =========================================================

    async def save_bot(
        self,
        bot_id: int | str,
        owner_id: int | str,
        token: str,
        username: str,
        title: str,
    ):
        """
        Save/update a managed bot.

        This is the method main_bot.py uses after
        Telegram creates a managed bot.
        """

        bot_id = int(bot_id)
        owner_id = int(owner_id)

        existing = await self.bots.find_one(
            {"bot_id": bot_id}
        )

        now = datetime.now(timezone.utc)

        created_at = (
            existing.get("created_at")
            if existing
            else now
        )

        status = (
            existing.get("status", "starting")
            if existing
            else "starting"
        )

        force_join_channels = (
            existing.get(
                "force_join_channels",
                [],
            )
            if existing
            else []
        )

        bot_doc = {
            "bot_id": bot_id,
            "owner_id": owner_id,
            "title": title or "",
            "username": username or "",
            "token": token or "",
            "status": status,
            "created_at": created_at,
            "updated_at": now,
            "force_join_channels": force_join_channels,
        }

        await self.bots.update_one(
            {"bot_id": bot_id},
            {"$set": bot_doc},
            upsert=True,
        )

        logger.info(
            "🤖 Managed bot saved: @%s (%s)",
            username,
            bot_id,
        )

        return await self.get_bot(bot_id)

    async def get_bot(
        self,
        bot_id: int | str,
    ):

        return await self.bots.find_one(
            {"bot_id": int(bot_id)}
        )

    async def get_user_bots(
        self,
        owner_id: int | str,
    ):

        cursor = (
            self.bots
            .find({"owner_id": int(owner_id)})
            .sort("created_at", DESCENDING)
        )

        return await cursor.to_list(
            length=100
        )

    async def get_all_bots(self):

        cursor = self.bots.find(
            {}
        ).sort(
            "created_at",
            DESCENDING,
        )

        return await cursor.to_list(
            length=1000
        )

    async def get_all_active_bots(self):

        cursor = self.bots.find(
            {
                "status": {
                    "$in": [
                        "active",
                        "starting",
                        "failed",
                    ]
                }
            }
        )

        return await cursor.to_list(
            length=1000
        )

    async def update_bot_status(
        self,
        bot_id: int | str,
        status: str,
    ):

        result = await self.bots.update_one(
            {"bot_id": int(bot_id)},
            {
                "$set": {
                    "status": status,
                    "status_updated_at": datetime.now(
                        timezone.utc
                    ),
                }
            },
        )

        return result.modified_count > 0

    async def update_bot_token(
        self,
        bot_id: int | str,
        token: str,
    ):

        await self.bots.update_one(
            {"bot_id": int(bot_id)},
            {
                "$set": {
                    "token": token,
                    "updated_at": datetime.now(
                        timezone.utc
                    ),
                }
            },
        )

    async def update_bot_username(
        self,
        bot_id: int | str,
        username: str,
    ):

        await self.bots.update_one(
            {"bot_id": int(bot_id)},
            {
                "$set": {
                    "username": username,
                    "updated_at": datetime.now(
                        timezone.utc
                    ),
                }
            },
        )

    async def delete_bot(
        self,
        bot_id: int | str,
    ):

        bid = int(bot_id)

        await self.bots.delete_one(
            {"bot_id": bid}
        )

        await self.bot_users.delete_many(
            {"bot_id": bid}
        )

        await self.downloads.delete_many(
            {"bot_id": bid}
        )

        await self.pending_downloads.delete_many(
            {"bot_id": bid}
        )

        logger.info(
            "🗑️ Managed bot deleted: %s",
            bid,
        )

    async def search_bots(
        self,
        query: str,
    ):

        query = (
            str(query)
            .strip()
            .lstrip("@")
        )

        if not query:
            return []

        if query.isdigit():

            cursor = self.bots.find(
                {
                    "bot_id": int(query)
                }
            )

        else:

            cursor = self.bots.find(
                {
                    "username": {
                        "$regex": query,
                        "$options": "i",
                    }
                }
            )

        return await cursor.to_list(
            length=30
        )

    # =========================================================
    # MANAGED BOT USERS
    # =========================================================

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
            {
                "bot_id": bid,
                "user_id": uid,
            },
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

        return await self.get_bot_user(
            bid,
            uid,
        )

    async def get_bot_user(
        self,
        bot_id: int | str,
        user_id: int | str,
    ):

        return await self.bot_users.find_one(
            {
                "bot_id": int(bot_id),
                "user_id": int(user_id),
            }
        )

    async def set_user_language(
        self,
        bot_id: int | str,
        user_id: int | str,
        language: str,
    ):

        bid = int(bot_id)
        uid = int(user_id)

        now = datetime.now(timezone.utc)

        await self.bot_users.update_one(
            {
                "bot_id": bid,
                "user_id": uid,
            },
            {
                "$set": {
                    "language": language,
                    "last_seen": now,
                },
                "$setOnInsert": {
                    "bot_id": bid,
                    "user_id": uid,
                    "username": "",
                    "full_name": "",
                    "created_at": now,
                },
            },
            upsert=True,
        )

    async def get_all_bot_users(
        self,
        bot_id: int | str,
    ):

        cursor = self.bot_users.find(
            {
                "bot_id": int(bot_id)
            }
        )

        return await cursor.to_list(
            length=None
        )

    async def delete_bot_user(
        self,
        bot_id: int | str,
        user_id: int | str,
    ):

        await self.bot_users.delete_one(
            {
                "bot_id": int(bot_id),
                "user_id": int(user_id),
            }
        )

    # =========================================================
    # DOWNLOADS
    # =========================================================

    async def log_download(
        self,
        bot_id: int | str,
        user_id: int | str,
        platform: str = "general",
        media_type: str = "video",
        status: str = "success",
        url: str = "",
        title: str = "",
        file_size: int = 0,
    ):

        document = {
            "bot_id": int(bot_id),
            "user_id": int(user_id),
            "platform": platform or "general",
            "media_type": media_type or "video",
            "status": status or "success",
            "url": url or "",
            "title": title or "",
            "file_size": int(file_size or 0),
            "timestamp": datetime.now(
                timezone.utc
            ),
        }

        result = await self.downloads.insert_one(
            document
        )

        return result.inserted_id

    async def count_downloads(self):

        return await self.downloads.count_documents({})

    async def count_successful_downloads(self):

        return await self.downloads.count_documents(
            {
                "status": "success"
            }
        )

    async def get_bot_downloads(
        self,
        bot_id: int | str,
        limit: int = 100,
    ):

        cursor = (
            self.downloads
            .find(
                {
                    "bot_id": int(bot_id)
                }
            )
            .sort(
                "timestamp",
                DESCENDING,
            )
            .limit(limit)
        )

        return await cursor.to_list(
            length=limit
        )

    # =========================================================
    # BOT STATISTICS
    # =========================================================

    async def get_bot_stats(
        self,
        bot_id: int | str,
    ):

        bid = int(bot_id)

        total_users = (
            await self.bot_users.count_documents(
                {"bot_id": bid}
            )
        )

        total_downloads = (
            await self.downloads.count_documents(
                {"bot_id": bid}
            )
        )

        videos = (
            await self.downloads.count_documents(
                {
                    "bot_id": bid,
                    "media_type": "video",
                }
            )
        )

        audio = (
            await self.downloads.count_documents(
                {
                    "bot_id": bid,
                    "media_type": "audio",
                }
            )
        )

        photos = (
            await self.downloads.count_documents(
                {
                    "bot_id": bid,
                    "media_type": "photo",
                }
            )
        )

        successful = (
            await self.downloads.count_documents(
                {
                    "bot_id": bid,
                    "status": "success",
                }
            )
        )

        failed = (
            await self.downloads.count_documents(
                {
                    "bot_id": bid,
                    "status": "failed",
                }
            )
        )

        return {
            "total_users": total_users,
            "total_downloads": total_downloads,
            "videos": videos,
            "audio": audio,
            "photos": photos,
            "successful": successful,
            "failed": failed,
        }

    async def get_global_stats(self):

        users = await self.users.count_documents({})

        bots = await self.bots.count_documents({})

        active_bots = await self.bots.count_documents(
            {"status": "active"}
        )

        starting_bots = await self.bots.count_documents(
            {"status": "starting"}
        )

        failed_bots = await self.bots.count_documents(
            {"status": "failed"}
        )

        bot_users = await self.bot_users.count_documents(
            {}
        )

        downloads = await self.downloads.count_documents(
            {}
        )

        successful_downloads = (
            await self.downloads.count_documents(
                {"status": "success"}
            )
        )

        return {
            "users": users,
            "bots": bots,
            "active_bots": active_bots,
            "starting_bots": starting_bots,
            "failed_bots": failed_bots,
            "bot_users": bot_users,
            "downloads": downloads,
            "successful_downloads": successful_downloads,
        }

    # =========================================================
    # GLOBAL SETTINGS
    # =========================================================

    async def get_system_setting(
        self,
        key: str,
        default=None,
    ):

        cfg = await self.settings.find_one(
            {
                "_id": "platform_config"
            }
        )

        if not cfg:
            return default

        return cfg.get(
            key,
            default,
        )

    async def set_system_setting(
        self,
        key: str,
        value,
    ):

        await self.settings.update_one(
            {
                "_id": "platform_config"
            },
            {
                "$set": {
                    key: value
                }
            },
            upsert=True,
        )

        return value

    async def is_bot_creation_enabled(self) -> bool:

        value = await self.get_system_setting(
            "bot_creation_enabled",
            True,
        )

        return bool(value)

    async def set_bot_creation_enabled(
        self,
        status: bool,
    ):

        await self.set_system_setting(
            "bot_creation_enabled",
            bool(status),
        )

    async def is_maintenance_mode(self) -> bool:

        value = await self.get_system_setting(
            "maintenance_mode",
            False,
        )

        return bool(value)

    async def set_maintenance_mode(
        self,
        status: bool,
    ):

        await self.set_system_setting(
            "maintenance_mode",
            bool(status),
        )

    # =========================================================
    # FORCE JOIN CHANNELS
    # =========================================================

    async def get_global_force_join_channels(self):

        cfg = await self.settings.find_one(
            {
                "_id": "platform_config"
            }
        )

        if not cfg:
            return []

        return cfg.get(
            "force_join_channels",
            [],
        )

    async def add_global_force_join_channel(
        self,
        channel: str,
    ):

        channel = str(channel).strip()

        if not channel:
            return (
                False,
                await self.get_global_force_join_channels(),
            )

        channels = (
            await self.get_global_force_join_channels()
        )

        if channel in channels:
            return False, channels

        if len(channels) >= 5:
            return False, channels

        await self.settings.update_one(
            {
                "_id": "platform_config"
            },
            {
                "$addToSet": {
                    "force_join_channels": channel
                }
            },
            upsert=True,
        )

        new_channels = (
            await self.get_global_force_join_channels()
        )

        return True, new_channels

    async def remove_global_force_join_channel(
        self,
        channel: str,
    ):

        await self.settings.update_one(
            {
                "_id": "platform_config"
            },
            {
                "$pull": {
                    "force_join_channels": channel
                }
            },
        )

        return await self.get_global_force_join_channels()

    async def clear_global_force_join_channels(self):

        await self.settings.update_one(
            {
                "_id": "platform_config"
            },
            {
                "$set": {
                    "force_join_channels": []
                }
            },
            upsert=True,
        )

    # =========================================================
    # PENDING DOWNLOADS
    # =========================================================

    async def save_pending_download(
        self,
        bot_id: int | str,
        user_id: int | str,
        url: str,
        data: dict | None = None,
    ):

        document = {
            "bot_id": int(bot_id),
            "user_id": int(user_id),
            "url": url,
            "data": data or {},
            "created_at": datetime.now(
                timezone.utc
            ),
        }

        result = await self.pending_downloads.insert_one(
            document
        )

        return result.inserted_id

    async def get_pending_download(
        self,
        pending_id,
    ):

        return await self.pending_downloads.find_one(
            {
                "_id": pending_id
            }
        )

    async def delete_pending_download(
        self,
        pending_id,
    ):

        await self.pending_downloads.delete_one(
            {
                "_id": pending_id
            }
        )


# =============================================================
# SINGLE DATABASE INSTANCE
# =============================================================

db = Database()
