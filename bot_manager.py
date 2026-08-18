import asyncio
import logging
from telegram import Update
from managed_bot import ManagedBotHandler
from database import db

logger = logging.getLogger(__name__)


class DynamicBotManager:
    def __init__(self):
        self.running_bots: dict[int, ManagedBotHandler] = {}
        self.start_locks: dict[int, asyncio.Lock] = {}

    def _get_lock(self, bot_id: int) -> asyncio.Lock:
        if bot_id not in self.start_locks:
            self.start_locks[bot_id] = asyncio.Lock()
        return self.start_locks[bot_id]

    async def load_and_start_all(self):
        bots = await db.get_all_active_bots()
        logger.info("🔄 Loading %s managed bots...", len(bots))

        for bot in bots:
            if not bot.get("token"):
                await db.update_bot_status(bot["bot_id"], "failed")
                continue

            asyncio.create_task(
                self.start_bot_instance(
                    int(bot["bot_id"]),
                    bot["token"],
                )
            )

    async def start_bot_instance(self, bot_id: int, token: str) -> bool:
        async with self._get_lock(bot_id):
            if bot_id in self.running_bots:
                handler = self.running_bots[bot_id]
                if handler.app.updater and handler.app.updater.running:
                    return True

            handler = None

            try:
                await db.update_bot_status(bot_id, "starting")

                handler = ManagedBotHandler(bot_id, token)

                # Initialize PTB application.
                await handler.app.initialize()

                # Verify token before registering the bot as online.
                bot_me = await handler.app.bot.get_me()
                username = bot_me.username or str(bot_id)

                # A bot must not keep an old webhook while polling.
                await handler.app.bot.delete_webhook(
                    drop_pending_updates=True
                )

                # Start the application and updater.
                await handler.app.start()

                if not handler.app.updater:
                    raise RuntimeError("Telegram updater is unavailable")

                await handler.app.updater.start_polling(
                    drop_pending_updates=True,
                    allowed_updates=Update.ALL_TYPES,
                    poll_interval=0.5,
                    timeout=30,
                )

                self.running_bots[bot_id] = handler
                await db.update_bot_status(bot_id, "active")

                logger.info(
                    "🟢 Managed bot @%s (%s) is ONLINE",
                    username,
                    bot_id,
                )
                return True

            except Exception as exc:
                logger.exception(
                    "🔴 Failed to start managed bot %s",
                    bot_id,
                )

                await db.update_bot_status(bot_id, "failed")

                if handler is not None:
                    try:
                        if handler.app.updater and handler.app.updater.running:
                            await handler.app.updater.stop()
                    except Exception:
                        pass

                    try:
                        if handler.app.running:
                            await handler.app.stop()
                    except Exception:
                        pass

                    try:
                        await handler.app.shutdown()
                    except Exception:
                        pass

                return False

    async def stop_bot_instance(self, bot_id: int):
        async with self._get_lock(bot_id):
            handler = self.running_bots.pop(bot_id, None)

            if not handler:
                await db.update_bot_status(bot_id, "stopped")
                return

            try:
                if handler.app.updater and handler.app.updater.running:
                    await handler.app.updater.stop()

                if handler.app.running:
                    await handler.app.stop()

                await handler.app.shutdown()
                await db.update_bot_status(bot_id, "stopped")

                logger.info("🛑 Managed bot %s stopped", bot_id)

            except Exception:
                logger.exception(
                    "Error stopping managed bot %s",
                    bot_id,
                )

    async def restart_bot_instance(self, bot_id: int) -> bool:
        bot = await db.get_bot(bot_id)

        if not bot or not bot.get("token"):
            return False

        await self.stop_bot_instance(bot_id)

        return await self.start_bot_instance(
            int(bot["bot_id"]),
            bot["token"],
        )


bot_manager = DynamicBotManager()
