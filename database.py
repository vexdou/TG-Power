# ================================================================
# DATABASE.PY
# MongoDB Database Layer for TG-Power SaaS
# ================================================================

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

from config import Config


logger = logging.getLogger(__name__)


# ================================================================
# DATABASE CLASS
# ================================================================

class Database:

    def __init__(self):

        self.client = None
        self.db = None

        # Collections
        self.bots = None
        self.users = None
        self.downloads = None

        # Main SaaS bot collections
        self.main_users = None
        self.system_settings = None

    # ============================================================
    # CONNECT
    # ============================================================

    async def connect(self):

        try:

            if not Config.MONGO_URI:
                raise RuntimeError(
                    "MONGO_URI is not configured."
                )

            self.client = AsyncIOMotorClient(
                Config.MONGO_URI,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
                socketTimeoutMS=30000,
                maxPoolSize=100,
                minPoolSize=5,
                retryWrites=True,
            )

            # Force connection check
            await self.client.admin.command(
                "ping"
            )

            database_name = getattr(
                Config,
                "MONGO_DB_NAME",
                None,
            )

            if not database_name:

                database_name = getattr(
                    Config,
                    "DB_NAME",
                    "tg_power",
                )

            self.db = self.client[
                database_name
            ]

            # ====================================================
            # COLLECTIONS
            # ====================================================

            self.bots = self.db.bots
            self.users = self.db.bot_users
            self.downloads = self.db.downloads

            self.main_users = (
                self.db.main_users
            )

            self.system_settings = (
                self.db.system_settings
            )

            await self.create_indexes()

            logger.info(
                "🟢 MongoDB connected successfully."
            )

        except Exception as e:

            logger.error(
                f"🔴 MongoDB connection error: {e}",
                exc_info=True,
            )

            raise

    # ============================================================
    # DISCONNECT
    # ============================================================

    async def close(self):

        try:

            if self.client:

                self.client.close()

                logger.info(
                    "🔴 MongoDB connection closed."
                )

        except Exception as e:

            logger.error(
                f"MongoDB close error: {e}",
                exc_info=True,
            )

    # ============================================================
    # INDEXES
    # ============================================================

    async def create_indexes(self):

        try:

            # ----------------------------------------------------
            # BOTS
            # ----------------------------------------------------

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
                [("status", ASCENDING)],
                name="status_index",
            )

            await self.bots.create_index(
                [("created_at", DESCENDING)],
                name="created_at_index",
            )

            # ----------------------------------------------------
            # BOT USERS
            # ----------------------------------------------------

            await self.users.create_index(
                [
                    ("bot_id", ASCENDING),
                    ("user_id", ASCENDING),
                ],
                unique=True,
                name="bot_user_unique",
            )

            await self.users.create_index(
                [("bot_id", ASCENDING)],
                name="bot_users_bot_id",
            )

            await self.users.create_index(
                [("user_id", ASCENDING)],
                name="bot_users_user_id",
            )

            # ----------------------------------------------------
            # DOWNLOADS
            # ----------------------------------------------------

            await self.downloads.create_index(
                [("bot_id", ASCENDING)],
                name="downloads_bot_id",
            )

            await self.downloads.create_index(
                [("user_id", ASCENDING)],
                name="downloads_user_id",
            )

            await self.downloads.create_index(
                [("created_at", DESCENDING)],
                name="downloads_created_at",
            )

            # ----------------------------------------------------
            # MAIN USERS
            # ----------------------------------------------------

            await self.main_users.create_index(
                [("user_id", ASCENDING)],
                unique=True,
                name="main_user_unique",
            )

            await self.main_users.create_index(
                [("username", ASCENDING)],
                name="main_username_index",
            )

            # ----------------------------------------------------
            # SYSTEM SETTINGS
            # ----------------------------------------------------

            await self.system_settings.create_index(
                [("key", ASCENDING)],
                unique=True,
                name="system_setting_unique",
            )

            logger.info(
                "🟢 MongoDB indexes created."
            )

        except Exception as e:

            logger.error(
                f"Index creation error: {e}",
                exc_info=True,
            )

    # ============================================================
    # TIME
    # ============================================================

    @staticmethod
    def now():

        return datetime.now(
            timezone.utc
        )

    # ============================================================
    # MAIN USERS
    # ============================================================

    async def save_main_user(
        self,
        user_id: int,
        username: str = "",
        full_name: str = "",
    ):

        now = self.now()

        await self.main_users.update_one(
            {
                "user_id": user_id
            },
            {
                "$set": {
                    "username": username or "",
                    "full_name": full_name or "",
                    "last_seen": now,
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "language": "en",
                    "created_at": now,
                },
            },
            upsert=True,
        )

    async def get_main_user(
        self,
        user_id: int,
    ) -> Optional[Dict[str, Any]]:

        return await self.main_users.find_one(
            {
                "user_id": user_id
            }
        )

    async def set_main_user_language(
        self,
        user_id: int,
        language: str,
    ):

        allowed = {
            "en",
            "so",
            "ar",
            "es",
        }

        if language not in allowed:
            language = "en"

        await self.main_users.update_one(
            {
                "user_id": user_id
            },
            {
                "$set": {
                    "language": language,
                    "last_seen": self.now(),
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "created_at": self.now(),
                },
            },
            upsert=True,
        )

    async def get_main_user_language(
        self,
        user_id: int,
    ) -> str:

        user = await self.get_main_user(
            user_id
        )

        if not user:
            return "en"

        return user.get(
            "language",
            "en",
        )

    async def get_all_main_users(
        self,
    ) -> List[Dict[str, Any]]:

        cursor = self.main_users.find({})

        return await cursor.to_list(
            length=None
        )

    async def count_main_users(
        self,
    ) -> int:

        return await self.main_users.count_documents(
            {}
        )

    # ============================================================
    # SYSTEM SETTINGS
    # ============================================================

    async def set_system_setting(
        self,
        key: str,
        value: Any,
    ):

        await self.system_settings.update_one(
            {
                "key": key
            },
            {
                "$set": {
                    "value": value,
                    "updated_at": self.now(),
                },
                "$setOnInsert": {
                    "key": key,
                    "created_at": self.now(),
                },
            },
            upsert=True,
        )

    async def get_system_setting(
        self,
        key: str,
        default: Any = None,
    ):

        setting = await self.system_settings.find_one(
            {
                "key": key
            }
        )

        if not setting:
            return default

        return setting.get(
            "value",
            default,
        )

    async def delete_system_setting(
        self,
        key: str,
    ):

        await self.system_settings.delete_one(
            {
                "key": key
            }
        )

    # ============================================================
    # NEW BOT
    # ============================================================

    async def add_new_bot(
        self,
        owner_id: int,
        token: str,
        bot_id: int,
        username: str = "",
    ):

        now = self.now()

        document = {
            "owner_id": owner_id,
            "bot_id": bot_id,
            "token": token,
            "username": username or "",
            "status": "starting",
            "force_join_channels": [],
            "created_at": now,
            "updated_at": now,
            "last_started_at": None,
            "last_stopped_at": None,
            "last_error": None,
        }

        result = await self.bots.update_one(
            {
                "bot_id": bot_id
            },
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

        return result

    async def get_bot(
        self,
        bot_id: int,
    ) -> Optional[Dict[str, Any]]:

        return await self.bots.find_one(
            {
                "bot_id": bot_id
            }
        )

    async def get_bot_by_username(
        self,
        username: str,
    ) -> Optional[Dict[str, Any]]:

        username = username.lstrip("@")

        return await self.bots.find_one(
            {
                "username": username
            }
        )

    async def get_user_bots(
        self,
        owner_id: int,
    ) -> List[Dict[str, Any]]:

        cursor = self.bots.find(
            {
                "owner_id": owner_id
            }
        ).sort(
            "created_at",
            DESCENDING,
        )

        return await cursor.to_list(
            length=None
        )

    async def get_all_bots(
        self,
    ) -> List[Dict[str, Any]]:

        cursor = self.bots.find({}).sort(
            "created_at",
            DESCENDING,
        )

        return await cursor.to_list(
            length=None
        )

    async def count_bots(
        self,
    ) -> int:

        return await self.bots.count_documents(
            {}
        )

    async def count_active_bots(
        self,
    ) -> int:

        return await self.bots.count_documents(
            {
                "status": "active"
            }
        )

    async def count_failed_bots(
        self,
    ) -> int:

        return await self.bots.count_documents(
            {
                "status": "failed"
            }
        )

    # ============================================================
    # BOT STATUS
    # ============================================================

    async def update_bot_status(
        self,
        bot_id: int,
        status: str,
        error: Optional[str] = None,
    ):

        now = self.now()

        update = {
            "$set": {
                "status": status,
                "updated_at": now,
            }
        }

        if status == "active":

            update["$set"][
                "last_started_at"
            ] = now

            update["$set"][
                "last_error"
            ] = None

        elif status in {
            "stopped",
            "inactive",
        }:

            update["$set"][
                "last_stopped_at"
            ] = now

        elif status == "failed":

            update["$set"][
                "last_error"
            ] = error or "Unknown error"

        await self.bots.update_one(
            {
                "bot_id": bot_id
            },
            update,
        )

    async def set_bot_error(
        self,
        bot_id: int,
        error: str,
    ):

        await self.update_bot_status(
            bot_id,
            "failed",
            error,
        )

    # ============================================================
    # DELETE BOT
    # ============================================================

    async def delete_bot(
        self,
        bot_id: int,
    ):

        await self.bots.delete_one(
            {
                "bot_id": bot_id
            }
        )

        await self.users.delete_many(
            {
                "bot_id": bot_id
            }
        )

        await self.downloads.delete_many(
            {
                "bot_id": bot_id
            }
        )

    # ============================================================
    # BOT USERS
    # ============================================================

    async def save_bot_user(
        self,
        bot_id: int,
        user_id: int,
        username: str = "",
        first_name: str = "",
        language: str = "en",
    ):

        now = self.now()

        await self.users.update_one(
            {
                "bot_id": bot_id,
                "user_id": user_id,
            },
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

    async def get_bot_user(
        self,
        bot_id: int,
        user_id: int,
    ) -> Optional[Dict[str, Any]]:

        return await self.users.find_one(
            {
                "bot_id": bot_id,
                "user_id": user_id,
            }
        )

    async def get_all_bot_users(
        self,
        bot_id: int,
    ) -> List[Dict[str, Any]]:

        cursor = self.users.find(
            {
                "bot_id": bot_id
            }
        )

        return await cursor.to_list(
            length=None
        )

    async def count_bot_users(
        self,
        bot_id: int,
    ) -> int:

        return await self.users.count_documents(
            {
                "bot_id": bot_id
            }
        )

    async def count_all_bot_users(
        self,
    ) -> int:

        return await self.users.count_documents(
            {}
        )

    async def update_bot_user_language(
        self,
        bot_id: int,
        user_id: int,
        language: str,
    ):

        await self.users.update_one(
            {
                "bot_id": bot_id,
                "user_id": user_id,
            },
            {
                "$set": {
                    "language": language,
                    "last_seen": self.now(),
                }
            },
        )

    async def increment_user_downloads(
        self,
        bot_id: int,
        user_id: int,
    ):

        await self.users.update_one(
            {
                "bot_id": bot_id,
                "user_id": user_id,
            },
            {
                "$inc": {
                    "downloads_count": 1
                },
                "$set": {
                    "last_seen": self.now(),
                },
            },
            upsert=True,
        )

    # ============================================================
    # DOWNLOAD RECORD
    # ============================================================

    async def add_download(
        self,
        bot_id: int,
        user_id: int,
        url: str = "",
        platform: str = "",
        media_type: str = "video",
        status: str = "success",
        file_size: int = 0,
    ):

        document = {
            "bot_id": bot_id,
            "user_id": user_id,
            "url": url or "",
            "platform": platform or "",
            "media_type": media_type or "video",
            "status": status or "success",
            "file_size": file_size or 0,
            "created_at": self.now(),
        }

        result = await self.downloads.insert_one(
            document
        )

        await self.increment_user_downloads(
            bot_id,
            user_id,
        )

        return result

    async def count_downloads(
        self,
        bot_id: Optional[int] = None,
    ) -> int:

        query = {}

        if bot_id is not None:
            query["bot_id"] = bot_id

        return await self.downloads.count_documents(
            query
        )

    async def count_successful_downloads(
        self,
        bot_id: Optional[int] = None,
    ):

        query = {
            "status": "success"
        }

        if bot_id is not None:
            query["bot_id"] = bot_id

        return await self.downloads.count_documents(
            query
        )

    # ============================================================
    # BOT STATISTICS
    # ============================================================

    async def get_bot_stats(
        self,
        bot_id: int,
    ) -> Dict[str, int]:

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
                    "media_type": "video",
                }
            )
        )

        audio = (
            await self.downloads.count_documents(
                {
                    "bot_id": bot_id,
                    "media_type": "audio",
                }
            )
        )

        photos = (
            await self.downloads.count_documents(
                {
                    "bot_id": bot_id,
                    "media_type": "photo",
                }
            )
        )

        successful = (
            await self.downloads.count_documents(
                {
                    "bot_id": bot_id,
                    "status": "success",
                }
            )
        )

        failed = (
            await self.downloads.count_documents(
                {
                    "bot_id": bot_id,
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

    # ============================================================
    # GLOBAL STATISTICS
    # ============================================================

    async def get_global_stats(
        self,
    ) -> Dict[str, int]:

        return {
            "users": await self.count_main_users(),
            "bots": await self.count_bots(),
            "active_bots": (
                await self.count_active_bots()
            ),
            "failed_bots": (
                await self.count_failed_bots()
            ),
            "bot_users": (
                await self.count_all_bot_users()
            ),
            "downloads": (
                await self.count_downloads()
            ),
            "successful_downloads": (
                await self.count_successful_downloads()
            ),
        }

    # ============================================================
    # FORCE JOIN
    # ============================================================

    async def get_force_join_channels(
        self,
        bot_id: int,
    ) -> List[str]:

        bot = await self.get_bot(
            bot_id
        )

        if not bot:
            return []

        channels = bot.get(
            "force_join_channels",
            [],
        )

        if not isinstance(
            channels,
            list,
        ):
            return []

        return channels

    async def add_force_join_channel(
        self,
        bot_id: int,
        channel: str,
    ):

        channel = channel.strip()

        if not channel:
            return False

        if not channel.startswith("@"):
            channel = "@" + channel

        result = await self.bots.update_one(
            {
                "bot_id": bot_id
            },
            {
                "$addToSet": {
                    "force_join_channels": channel
                },
                "$set": {
                    "updated_at": self.now()
                },
            },
        )

        return result.modified_count > 0

    async def remove_force_join_channel(
        self,
        bot_id: int,
        channel: str,
    ):

        channel = channel.strip()

        if not channel.startswith("@"):
            channel = "@" + channel

        result = await self.bots.update_one(
            {
                "bot_id": bot_id
            },
            {
                "$pull": {
                    "force_join_channels": channel
                },
                "$set": {
                    "updated_at": self.now()
                },
            },
        )

        return result.modified_count > 0

    async def clear_force_join_channels(
        self,
        bot_id: int,
    ):

        await self.bots.update_one(
            {
                "bot_id": bot_id
            },
            {
                "$set": {
                    "force_join_channels": [],
                    "updated_at": self.now(),
                }
            },
        )

    async def set_force_join_channels(
        self,
        bot_id: int,
        channels: List[str],
    ):

        cleaned = []

        for channel in channels:

            channel = str(
                channel
            ).strip()

            if not channel:
                continue

            if not channel.startswith("@"):
                channel = "@" + channel

            if channel not in cleaned:
                cleaned.append(
                    channel
                )

        await self.bots.update_one(
            {
                "bot_id": bot_id
            },
            {
                "$set": {
                    "force_join_channels": cleaned,
                    "updated_at": self.now(),
                }
            },
        )

    # ============================================================
    # OWNER / BOT ACCESS
    # ============================================================

    async def is_bot_owner(
        self,
        bot_id: int,
        user_id: int,
    ) -> bool:

        bot = await self.get_bot(
            bot_id
        )

        if not bot:
            return False

        return (
            int(bot.get("owner_id", 0))
            == int(user_id)
        )

    # ============================================================
    # BOT CREATION
    # ============================================================

    async def is_bot_creation_enabled(
        self,
    ) -> bool:

        return await self.get_system_setting(
            "bot_creation_enabled",
            True,
        )

    async def set_bot_creation_enabled(
        self,
        enabled: bool,
    ):

        await self.set_system_setting(
            "bot_creation_enabled",
            bool(enabled),
        )

    # ============================================================
    # BOT LIMIT
    # ============================================================

    async def count_user_bots(
        self,
        owner_id: int,
    ) -> int:

        return await self.bots.count_documents(
            {
                "owner_id": owner_id
            }
        )

    async def can_create_bot(
        self,
        owner_id: int,
        max_bots: int = 5,
    ) -> bool:

        enabled = (
            await self.is_bot_creation_enabled()
        )

        if not enabled:
            return False

        count = await self.count_user_bots(
            owner_id
        )

        return count < max_bots

    # ============================================================
    # SEARCH
    # ============================================================

    async def search_bots(
        self,
        text: str,
    ) -> List[Dict[str, Any]]:

        text = text.strip()

        if not text:
            return []

        regex = {
            "$regex": text,
            "$options": "i",
        }

        cursor = self.bots.find(
            {
                "$or": [
                    {
                        "username": regex
                    },
                    {
                        "bot_id": (
                            int(text)
                            if text.isdigit()
                            else -1
                        )
                    },
                ]
            }
        )

        return await cursor.to_list(
            length=None
        )

    # ============================================================
    # CLEANUP
    # ============================================================

    async def remove_old_downloads(
        self,
        before_date,
    ):

        result = await self.downloads.delete_many(
            {
                "created_at": {
                    "$lt": before_date
                }
            }
        )

        return result.deleted_count


# ================================================================
# GLOBAL DATABASE INSTANCE
# ================================================================

db = Database()
