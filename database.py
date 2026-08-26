import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure, DuplicateKeyError

from config import Config

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    return None


class Database:
    """
    MongoDB database layer for TG-Power.

    Includes:
        - Main users
        - Managed bots
        - Managed bot users
        - Downloads
        - Premium subscriptions
        - Premium settings
        - Premium payments
        - Premium statistics
        - Global settings
        - Force join
        - Pending downloads
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

        self.users = self.db.users
        self.bots = self.db.bots
        self.bot_users = self.db.bot_users
        self.downloads = self.db.downloads
        self.broadcasts = self.db.broadcasts
        self.settings = self.db.settings
        self.pending_downloads = self.db.pending_downloads

        # Premium
        self.premium_settings = self.db.premium_settings
        self.premium_payments = self.db.premium_payments

        self._connected = False

    # =========================================================
    # INDEXES
    # =========================================================

    async def _ensure_index(
        self,
        collection,
        keys,
        name,
        unique=False,
        sparse=False,
    ):
        keys = list(keys)

        try:
            indexes = await collection.index_information()
        except Exception:
            logger.exception(
                "Could not read MongoDB indexes for %s",
                collection.name,
            )
            raise

        for existing_name, existing_spec in indexes.items():
            existing_keys = existing_spec.get("key", [])

            if list(existing_keys) != keys:
                continue

            existing_unique = bool(existing_spec.get("unique", False))
            existing_sparse = bool(existing_spec.get("sparse", False))

            if existing_name == "_id_":
                return existing_name

            if (
                (not unique or existing_unique)
                and (not sparse or existing_sparse)
            ):
                return existing_name

            if unique and not existing_unique:
                try:
                    await collection.drop_index(existing_name)

                    return await collection.create_index(
                        keys,
                        unique=True,
                        sparse=sparse,
                        name=name,
                    )
                except Exception:
                    logger.exception(
                        "Could not migrate index %s on %s",
                        existing_name,
                        collection.name,
                    )

                    try:
                        return await collection.create_index(
                            keys,
                            unique=False,
                            sparse=existing_sparse,
                            name=existing_name,
                        )
                    except Exception:
                        pass

        try:
            return await collection.create_index(
                keys,
                unique=unique,
                sparse=sparse,
                name=name,
            )
        except OperationFailure as exc:
            if getattr(exc, "code", None) == 85:
                indexes_after = await collection.index_information()

                for current_name, current_spec in indexes_after.items():
                    if list(current_spec.get("key", [])) == keys:
                        return current_name

            raise

    # =========================================================
    # CONNECTION
    # =========================================================

    async def connect(self):
        try:
            await self.client.admin.command("ping")
            await self.init_db()

            self._connected = True

            logger.info("✅ MongoDB connected successfully")

        except Exception:
            self._connected = False
            logger.exception("❌ MongoDB connection failed")
            raise

    async def close(self):
        try:
            self.client.close()
            self._connected = False
            logger.info("🔌 MongoDB connection closed")
        except Exception:
            logger.exception("Database close error")

    # =========================================================
    # INIT
    # =========================================================

    async def init_db(self):

        # Main users
        await self._ensure_index(
            self.users,
            [("user_id", ASCENDING)],
            "user_id_unique",
            unique=True,
        )

        # Bots
        await self._ensure_index(
            self.bots,
            [("bot_id", ASCENDING)],
            "bot_id_unique",
            unique=True,
        )

        await self._ensure_index(
            self.bots,
            [("owner_id", ASCENDING)],
            "owner_id_index",
        )

        await self._ensure_index(
            self.bots,
            [("username", ASCENDING)],
            "username_unique",
            unique=True,
            sparse=True,
        )

        await self._ensure_index(
            self.bots,
            [("status", ASCENDING)],
            "status_index",
        )

        await self._ensure_index(
            self.bots,
            [("premium.is_active", ASCENDING)],
            "premium_active_index",
        )

        await self._ensure_index(
            self.bots,
            [("premium.until", ASCENDING)],
            "premium_until_index",
        )

        await self._ensure_index(
            self.bots,
            [("premium.plan", ASCENDING)],
            "premium_plan_index",
        )

        # Bot users
        await self._ensure_index(
            self.bot_users,
            [
                ("bot_id", ASCENDING),
                ("user_id", ASCENDING),
            ],
            "bot_user_unique",
            unique=True,
        )

        await self._ensure_index(
            self.bot_users,
            [("bot_id", ASCENDING)],
            "bot_users_bot_id",
        )

        # Downloads
        await self._ensure_index(
            self.downloads,
            [
                ("bot_id", ASCENDING),
                ("timestamp", DESCENDING),
            ],
            "downloads_bot_timestamp",
        )

        await self._ensure_index(
            self.downloads,
            [("user_id", ASCENDING)],
            "downloads_user_id",
        )

        # Pending
        await self._ensure_index(
            self.pending_downloads,
            [("created_at", DESCENDING)],
            "pending_created_at",
        )

        # Premium settings
        await self._ensure_index(
            self.premium_settings,
            [("bot_id", ASCENDING)],
            "premium_settings_bot_unique",
            unique=True,
        )

        # Premium payments
        await self._ensure_index(
            self.premium_payments,
            [("telegram_payment_charge_id", ASCENDING)],
            "telegram_charge_unique",
            unique=True,
            sparse=True,
        )

        await self._ensure_index(
            self.premium_payments,
            [
                ("bot_id", ASCENDING),
                ("created_at", DESCENDING),
            ],
            "premium_payments_bot_date",
        )

        await self._ensure_index(
            self.premium_payments,
            [("user_id", ASCENDING)],
            "premium_payments_user",
        )

        # =====================================================
        # PLATFORM SETTINGS
        # =====================================================

        existing = await self.settings.find_one(
            {"_id": "platform_config"}
        )

        defaults = {
            "force_join_channels": [],
            "maintenance_mode": False,
            "bot_creation_enabled": True,
            "max_video_seconds": 600,
            "max_file_mb": 50,
        }

        if not existing:
            defaults["created_at"] = utcnow()

            await self.settings.insert_one(
                {
                    "_id": "platform_config",
                    **defaults,
                }
            )
        else:
            missing = {}

            for key, value in defaults.items():
                if key not in existing:
                    missing[key] = value

            if missing:
                await self.settings.update_one(
                    {"_id": "platform_config"},
                    {"$set": missing},
                )

        # =====================================================
        # PREMIUM PRICES
        # =====================================================

        premium_prices = await self.settings.find_one(
            {"_id": "premium_prices"}
        )

        if not premium_prices:
            await self.settings.insert_one(
                {
                    "_id": "premium_prices",
                    "prices": {
                        "1m": 100,
                        "3m": 300,
                        "6m": 600,
                        "1y": 1000,
                    },
                    "updated_at": utcnow(),
                }
            )

        # =====================================================
        # PREMIUM SYSTEM CONFIG
        # =====================================================

        premium_config = await self.settings.find_one(
            {"_id": "premium_config"}
        )

        if not premium_config:
            await self.settings.insert_one(
                {
                    "_id": "premium_config",
                    "enabled": True,
                    "currency": "XTR",
                    "max_custom_buttons": 10,
                    "priority_enabled": True,
                    "ads_disabled": True,
                    "custom_caption_enabled": True,
                    "custom_buttons_enabled": True,
                    "created_at": utcnow(),
                    "updated_at": utcnow(),
                }
            )

    # =========================================================
    # PREMIUM PRICES
    # =========================================================

    async def get_premium_prices(self) -> dict:
        cfg = await self.settings.find_one(
            {"_id": "premium_prices"}
        )

        default = {
            "1m": 100,
            "3m": 300,
            "6m": 600,
            "1y": 1000,
        }

        if not cfg:
            return default

        prices = cfg.get("prices", {})

        result = {}

        for plan, value in default.items():
            try:
                result[plan] = int(prices.get(plan, value))
            except Exception:
                result[plan] = value

        return result

    async def set_premium_prices(self, new_prices: dict) -> dict:
        current = await self.get_premium_prices()

        for plan, value in new_prices.items():
            if plan not in {"1m", "3m", "6m", "1y"}:
                continue

            try:
                value = int(value)
            except Exception:
                continue

            if value < 1:
                continue

            current[plan] = value

        await self.settings.update_one(
            {"_id": "premium_prices"},
            {
                "$set": {
                    "prices": current,
                    "updated_at": utcnow(),
                }
            },
            upsert=True,
        )

        return current

    # =========================================================
    # PREMIUM CONFIG
    # =========================================================

    async def get_premium_config(self) -> dict:
        cfg = await self.settings.find_one(
            {"_id": "premium_config"}
        )

        if not cfg:
            return {
                "enabled": True,
                "currency": "XTR",
                "max_custom_buttons": 10,
                "priority_enabled": True,
                "ads_disabled": True,
                "custom_caption_enabled": True,
                "custom_buttons_enabled": True,
            }

        return cfg

    async def set_premium_config(self, key: str, value):
        await self.settings.update_one(
            {"_id": "premium_config"},
            {
                "$set": {
                    key: value,
                    "updated_at": utcnow(),
                }
            },
            upsert=True,
        )

        return value

    async def is_premium_enabled(self) -> bool:
        cfg = await self.get_premium_config()
        return bool(cfg.get("enabled", True))

    # =========================================================
    # PREMIUM ACTIVATION
    # =========================================================

    async def activate_bot_premium(
        self,
        bot_id: int | str,
        owner_id: int | str,
        plan: str,
        days: int,
        stars: int,
        payment_id: str = "",
        source: str = "telegram_stars",
    ):
        bid = int(bot_id)
        owner = int(owner_id)

        now = utcnow()

        bot = await self.get_bot(bid)

        if not bot:
            return None

        existing_premium = bot.get("premium") or {}

        current_until = normalize_datetime(
            existing_premium.get("until")
        )

        if current_until and current_until > now:
            start_date = current_until
        else:
            start_date = now

        until = start_date + timedelta(days=int(days))

        premium_data = {
            "is_active": True,
            "plan": str(plan),
            "stars": int(stars),
            "activated_at": now,
            "until": until,
            "activated_by": owner,
            "source": source,
            "payment_id": payment_id or "",
            "updated_at": now,
        }

        await self.bots.update_one(
            {"bot_id": bid},
            {
                "$set": {
                    "premium": premium_data,
                    "updated_at": now,
                }
            },
        )

        return until

    async def grant_bot_premium(
        self,
        bot_id: int | str,
        days: int,
        admin_id: int | str,
    ):
        bot = await self.get_bot(int(bot_id))

        if not bot:
            return None

        owner_id = bot.get("owner_id", admin_id)

        return await self.activate_bot_premium(
            bot_id=int(bot_id),
            owner_id=int(owner_id),
            plan="grant",
            days=int(days),
            stars=0,
            source="admin_grant",
        )

    async def deactivate_bot_premium(
        self,
        bot_id: int | str,
    ) -> bool:
        result = await self.bots.update_one(
            {"bot_id": int(bot_id)},
            {
                "$set": {
                    "premium.is_active": False,
                    "premium.deactivated_at": utcnow(),
                }
            },
        )

        return result.modified_count > 0

    async def expire_premium_bots(self) -> int:
        now = utcnow()

        result = await self.bots.update_many(
            {
                "premium.is_active": True,
                "premium.until": {
                    "$lte": now,
                },
            },
            {
                "$set": {
                    "premium.is_active": False,
                    "premium.expired_at": now,
                }
            },
        )

        return result.modified_count

    async def get_premium_bots(self, include_expired=False):
        now = utcnow()

        if include_expired:
            cursor = self.bots.find(
                {
                    "premium": {
                        "$exists": True,
                    }
                }
            )
        else:
            cursor = self.bots.find(
                {
                    "premium.is_active": True,
                    "premium.until": {
                        "$gt": now,
                    },
                }
            )

        cursor = cursor.sort(
            "premium.until",
            ASCENDING,
        )

        return await cursor.to_list(length=5000)

    async def is_bot_premium(self, bot_id: int | str) -> bool:
        bot = await self.get_bot(int(bot_id))

        if not bot:
            return False

        premium = bot.get("premium") or {}

        if not premium.get("is_active"):
            return False

        until = normalize_datetime(
            premium.get("until")
        )

        if not until:
            return False

        if until <= utcnow():
            await self.deactivate_bot_premium(bot_id)
            return False

        return True

    async def get_bot_premium(self, bot_id: int | str) -> dict:
        bot = await self.get_bot(bot_id)

        if not bot:
            return {}

        premium = bot.get("premium") or {}

        until = normalize_datetime(
            premium.get("until")
        )

        active = bool(
            premium.get("is_active")
            and until
            and until > utcnow()
        )

        premium["is_active"] = active

        return premium

    async def get_premium_remaining_days(
        self,
        bot_id: int | str,
    ) -> int:
        premium = await self.get_bot_premium(bot_id)

        until = normalize_datetime(
            premium.get("until")
        )

        if not until:
            return 0

        seconds = (until - utcnow()).total_seconds()

        if seconds <= 0:
            return 0

        return max(
            1,
            int(seconds / 86400),
        )

    # =========================================================
    # PREMIUM PAYMENT RECORDS
    # =========================================================

    async def payment_exists(
        self,
        telegram_payment_charge_id: str,
    ) -> bool:
        if not telegram_payment_charge_id:
            return False

        doc = await self.premium_payments.find_one(
            {
                "telegram_payment_charge_id":
                    telegram_payment_charge_id
            }
        )

        return doc is not None

    async def save_premium_payment(
        self,
        user_id: int,
        bot_id: int,
        plan: str,
        stars: int,
        telegram_payment_charge_id: str = "",
        provider_payment_charge_id: str = "",
        invoice_payload: str = "",
    ) -> bool:

        document = {
            "user_id": int(user_id),
            "bot_id": int(bot_id),
            "plan": str(plan),
            "stars": int(stars),
            "telegram_payment_charge_id":
                telegram_payment_charge_id or "",
            "provider_payment_charge_id":
                provider_payment_charge_id or "",
            "invoice_payload":
                invoice_payload or "",
            "created_at": utcnow(),
        }

        try:
            await self.premium_payments.insert_one(
                document
            )
            return True

        except DuplicateKeyError:
            return False

    async def get_bot_payments(
        self,
        bot_id: int | str,
        limit: int = 100,
    ):
        cursor = (
            self.premium_payments
            .find({"bot_id": int(bot_id)})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )

        return await cursor.to_list(length=limit)

    async def get_all_premium_payments(
        self,
        limit: int = 1000,
    ):
        cursor = (
            self.premium_payments
            .find({})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )

        return await cursor.to_list(length=limit)

    async def get_premium_stats(self):
        total_payments = await self.premium_payments.count_documents({})

        total_stars_result = await self.premium_payments.aggregate(
            [
                {
                    "$group": {
                        "_id": None,
                        "total": {
                            "$sum": "$stars"
                        },
                    }
                }
            ]
        ).to_list(length=1)

        total_stars = (
            int(total_stars_result[0]["total"])
            if total_stars_result
            else 0
        )

        active_bots = await self.bots.count_documents(
            {
                "premium.is_active": True,
                "premium.until": {
                    "$gt": utcnow()
                },
            }
        )

        return {
            "payments": total_payments,
            "stars": total_stars,
            "active_bots": active_bots,
        }

    # =========================================================
    # PREMIUM SETTINGS PER BOT
    # =========================================================

    async def get_bot_premium_settings(
        self,
        bot_id: int | str,
    ) -> dict:
        doc = await self.premium_settings.find_one(
            {"bot_id": int(bot_id)}
        )

        if not doc:
            return {
                "caption": "",
                "buttons": [],
                "ad_text": "",
                "ad_enabled": False,
                "priority": True,
            }

        return doc.get(
            "settings",
            {},
        )

    async def set_bot_premium_setting(
        self,
        bot_id: int | str,
        key: str,
        value,
    ):
        bid = int(bot_id)

        await self.premium_settings.update_one(
            {"bot_id": bid},
            {
                "$set": {
                    f"settings.{key}": value,
                    "updated_at": utcnow(),
                },
                "$setOnInsert": {
                    "bot_id": bid,
                    "created_at": utcnow(),
                },
            },
            upsert=True,
        )

        return value

    async def delete_bot_premium_setting(
        self,
        bot_id: int | str,
        key: str,
    ):
        await self.premium_settings.update_one(
            {"bot_id": int(bot_id)},
            {
                "$unset": {
                    f"settings.{key}": ""
                },
                "$set": {
                    "updated_at": utcnow()
                },
            },
        )

    async def clear_bot_premium_settings(
        self,
        bot_id: int | str,
    ):
        await self.premium_settings.update_one(
            {"bot_id": int(bot_id)},
            {
                "$set": {
                    "settings": {},
                    "updated_at": utcnow(),
                }
            },
            upsert=True,
        )

    # =========================================================
    # MAIN USERS
    # =========================================================

    async def save_main_user(
        self,
        user_id: int,
        username: str = "",
        full_name: str = "",
    ):
        uid = int(user_id)
        now = utcnow()

        await self.users.update_one(
            {"user_id": uid},
            {
                "$set": {
                    "username": username or "",
                    "full_name": full_name or "",
                    "last_seen": now,
                },
                "$setOnInsert": {
                    "user_id": uid,
                    "language": "en",
                    "is_banned": False,
                    "created_at": now,
                },
            },
            upsert=True,
        )

        return await self.get_main_user(uid)

    async def get_main_user(self, user_id: int):
        return await self.users.find_one(
            {"user_id": int(user_id)}
        )

    async def get_main_user_language(
        self,
        user_id: int,
    ) -> str:
        user = await self.get_main_user(user_id)

        if not user:
            return "en"

        return user.get(
            "language",
            "en",
        )

    async def set_main_user_language(
        self,
        user_id: int,
        language: str,
    ):
        uid = int(user_id)
        now = utcnow()

        await self.users.update_one(
            {"user_id": uid},
            {
                "$set": {
                    "language": language,
                    "last_seen": now,
                },
                "$setOnInsert": {
                    "user_id": uid,
                    "is_banned": False,
                    "created_at": now,
                },
            },
            upsert=True,
        )

    async def get_all_main_users(self):
        return await self.users.find({}).to_list(
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
        uid = int(user_id)

        await self.users.update_one(
            {"user_id": uid},
            {
                "$set": {
                    "is_banned": bool(banned)
                },
                "$setOnInsert": {
                    "user_id": uid,
                    "created_at": utcnow(),
                },
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
        bid = int(bot_id)
        owner = int(owner_id)

        existing = await self.bots.find_one(
            {"bot_id": bid}
        )

        now = utcnow()

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

        premium = (
            existing.get(
                "premium",
                {},
            )
            if existing
            else {}
        )

        bot_doc = {
            "bot_id": bid,
            "owner_id": owner,
            "title": title or "",
            "username": username or "",
            "token": token or "",
            "status": status,
            "created_at": created_at,
            "updated_at": now,
            "force_join_channels":
                force_join_channels,
            "premium": premium,
        }

        await self.bots.update_one(
            {"bot_id": bid},
            {"$set": bot_doc},
            upsert=True,
        )

        return await self.get_bot(bid)

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

        return await cursor.to_list(length=100)

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
                    "status_updated_at": utcnow(),
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
                    "updated_at": utcnow(),
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
                    "updated_at": utcnow(),
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

        await self.premium_settings.delete_one(
            {"bot_id": bid}
        )

        await self.premium_payments.delete_many(
            {"bot_id": bid}
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
                {"bot_id": int(query)}
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
    # BOT USERS
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

        now = utcnow()

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

        await self.bot_users.update_one(
            {
                "bot_id": bid,
                "user_id": uid,
            },
            {
                "$set": {
                    "language": language,
                    "last_seen": utcnow(),
                },
                "$setOnInsert": {
                    "bot_id": bid,
                    "user_id": uid,
                    "username": "",
                    "full_name": "",
                    "created_at": utcnow(),
                },
            },
            upsert=True,
        )

    async def get_all_bot_users(
        self,
        bot_id: int | str,
    ):
        return await self.bot_users.find(
            {"bot_id": int(bot_id)}
        ).to_list(length=None)

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
            "timestamp": utcnow(),
        }

        result = await self.downloads.insert_one(
            document
        )

        return result.inserted_id

    async def count_downloads(self):
        return await self.downloads.count_documents({})

    async def count_successful_downloads(self):
        return await self.downloads.count_documents(
            {"status": "success"}
        )

    async def get_bot_downloads(
        self,
        bot_id: int | str,
        limit: int = 100,
    ):
        cursor = (
            self.downloads
            .find({"bot_id": int(bot_id)})
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )

        return await cursor.to_list(
            length=limit
        )

    async def get_bot_stats(
        self,
        bot_id: int | str,
    ):
        bid = int(bot_id)

        total_users = await self.bot_users.count_documents(
            {"bot_id": bid}
        )

        total_downloads = await self.downloads.count_documents(
            {"bot_id": bid}
        )

        videos = await self.downloads.count_documents(
            {
                "bot_id": bid,
                "media_type": "video",
            }
        )

        audio = await self.downloads.count_documents(
            {
                "bot_id": bid,
                "media_type": "audio",
            }
        )

        photos = await self.downloads.count_documents(
            {
                "bot_id": bid,
                "media_type": "photo",
            }
        )

        successful = await self.downloads.count_documents(
            {
                "bot_id": bid,
                "status": "success",
            }
        )

        failed = await self.downloads.count_documents(
            {
                "bot_id": bid,
                "status": "failed",
            }
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
        return {
            "users":
                await self.users.count_documents({}),

            "bots":
                await self.bots.count_documents({}),

            "active_bots":
                await self.bots.count_documents(
                    {"status": "active"}
                ),

            "starting_bots":
                await self.bots.count_documents(
                    {"status": "starting"}
                ),

            "failed_bots":
                await self.bots.count_documents(
                    {"status": "failed"}
                ),

            "bot_users":
                await self.bot_users.count_documents({}),

            "downloads":
                await self.downloads.count_documents({}),

            "successful_downloads":
                await self.downloads.count_documents(
                    {"status": "success"}
                ),
        }

    # =========================================================
    # SYSTEM SETTINGS
    # =========================================================

    async def get_system_setting(
        self,
        key: str,
        default=None,
    ):
        cfg = await self.settings.find_one(
            {"_id": "platform_config"}
        )

        return (
            cfg.get(key, default)
            if cfg
            else default
        )

    async def set_system_setting(
        self,
        key: str,
        value,
    ):
        await self.settings.update_one(
            {"_id": "platform_config"},
            {
                "$set": {
                    key: value,
                    "updated_at": utcnow(),
                }
            },
            upsert=True,
        )

        return value

    async def is_bot_creation_enabled(self):
        return bool(
            await self.get_system_setting(
                "bot_creation_enabled",
                True,
            )
        )

    async def set_bot_creation_enabled(
        self,
        status: bool,
    ):
        return await self.set_system_setting(
            "bot_creation_enabled",
            bool(status),
        )

    async def is_maintenance_mode(self):
        return bool(
            await self.get_system_setting(
                "maintenance_mode",
                False,
            )
        )

    async def set_maintenance_mode(
        self,
        status: bool,
    ):
        return await self.set_system_setting(
            "maintenance_mode",
            bool(status),
        )

    # =========================================================
    # FORCE JOIN
    # =========================================================

    async def get_global_force_join_channels(self):
        cfg = await self.settings.find_one(
            {"_id": "platform_config"}
        )

        return (
            cfg.get("force_join_channels", [])
            if cfg
            else []
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
            {"_id": "platform_config"},
            {
                "$addToSet": {
                    "force_join_channels": channel
                }
            },
            upsert=True,
        )

        return (
            True,
            await self.get_global_force_join_channels(),
        )

    async def remove_global_force_join_channel(
        self,
        channel: str,
    ):
        await self.settings.update_one(
            {"_id": "platform_config"},
            {
                "$pull": {
                    "force_join_channels": channel
                }
            },
        )

        return await self.get_global_force_join_channels()

    async def clear_global_force_join_channels(self):
        await self.settings.update_one(
            {"_id": "platform_config"},
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
            "created_at": utcnow(),
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
            {"_id": pending_id}
        )

    async def delete_pending_download(
        self,
        pending_id,
    ):
        await self.pending_downloads.delete_one(
            {"_id": pending_id}
        )


db = Database()
