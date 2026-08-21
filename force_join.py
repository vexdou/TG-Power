import asyncio
import logging
from telegram import Bot
from telegram.error import TelegramError
from config import Config

logger = logging.getLogger(__name__)


class MainBotForceJoinChecker:
    """Central Force-Join checker. Membership is ALWAYS checked with the MAIN bot token."""

    def __init__(self):
        self.bot = None
        self._lock = asyncio.Lock()

    async def start(self):
        async with self._lock:
            if self.bot is not None:
                return
            self.bot = Bot(token=Config.BOT_TOKEN)
            await self.bot.initialize()
            me = await self.bot.get_me()
            logger.info("🔐 Central Force-Join checker online as @%s", me.username)

    async def stop(self):
        async with self._lock:
            if self.bot is not None:
                try:
                    await self.bot.shutdown()
                finally:
                    self.bot = None

    async def _ensure(self):
        if self.bot is None:
            await self.start()

    async def check_user(self, user_id: int, channels: list[str]) -> tuple[bool, str | None]:
        await self._ensure()
        for channel in channels:
            try:
                member = await self.bot.get_chat_member(chat_id=channel, user_id=user_id)
                status = getattr(member, "status", "")
                if status in {"left", "kicked"}:
                    return False, channel
                if status == "restricted" and not getattr(member, "is_member", False):
                    return False, channel
            except TelegramError as exc:
                logger.warning("Central Force-Join check failed for user %s / %s: %s", user_id, channel, exc)
                return False, channel
            except Exception as exc:
                logger.exception("Unexpected central Force-Join error: %s", exc)
                return False, channel
        return True, None

    async def verify_admin_channels(self, channels: list[str]) -> list[dict]:
        await self._ensure()
        me = await self.bot.get_me()
        result = []
        for channel in channels:
            row = {"channel": channel, "ok": False, "status": "unknown", "error": None}
            try:
                member = await self.bot.get_chat_member(channel, me.id)
                row["status"] = getattr(member, "status", "unknown")
                row["ok"] = row["status"] in {"administrator", "creator"}
                if not row["ok"]:
                    row["error"] = "Main bot must be administrator/owner of this channel."
            except Exception as exc:
                row["error"] = str(exc)
            result.append(row)
        return result


force_join_checker = MainBotForceJoinChecker()
