import asyncio
import logging

from telegram import Update
from managed_bot import ManagedBotHandler
from database import db

logger = logging.getLogger(__name__)


class DynamicBotManager:
    def __init__(self):
        self.running_bots: dict[int, ManagedBotHandler] = {}
        self.starting_bots: set[int] = set()

    async def load_and_start_all(self):
        try:
            bots = await db.get_all_bots()
            active_bots = [b for b in bots if b.get("status") == "active"]

            logger.info(
                "🔄 Loading %s active managed bots...",
                len(active_bots),
            )

            tasks = []
            for bot in active_bots:
                bot_id = bot.get("bot_id")
                token = bot.get("token")

                if not bot_id or not token:
                    logger.error("⚠️ Invalid managed bot record: %s", bot)
                    continue

                tasks.append(
                    asyncio.create_task(
                        self.start_bot_instance(bot_id, token)
                    )
                )

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        except Exception:
            logger.exception("🔴 Failed loading managed bots")

    async def start_bot_instance(self, bot_id: int, token: str) -> bool:
        if bot_id in self.running_bots:
            return True

        if bot_id in self.starting_bots:
            return False

        self.starting_bots.add(bot_id)
        handler = None

        try:
            handler = ManagedBotHandler(bot_id, token)

            await handler.app.initialize()
            bot_me = await handler.app.bot.get_me()

            await handler.app.bot.delete_webhook(drop_pending_updates=True)
            await handler.app.start()

            if handler.app.updater is None:
                raise RuntimeError("Telegram updater is not available.")

            await handler.app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
                poll_interval=1.0,
                timeout=30,
            )

            self.running_bots[bot_id] = handler
            await db.update_bot_status(bot_id, "active")

            logger.info(
                "🟢 Managed Bot @%s (%s) is fully ONLINE!",
                bot_me.username,
                bot_id,
            )
            return True

        except Exception as e:
            logger.exception("🔴 Failed to start managed bot %s", bot_id)

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

            try:
                await db.update_bot_status(bot_id, "failed", str(e))
            except Exception:
                logger.exception("Could not update bot %s status", bot_id)

            return False

        finally:
            self.starting_bots.discard(bot_id)

    async def stop_bot_instance(self, bot_id: int):
        handler = self.running_bots.pop(bot_id, None)
        if not handler:
            return

        try:
            if handler.app.updater and handler.app.updater.running:
                await handler.app.updater.stop()
            if handler.app.running:
                await handler.app.stop()
            await handler.app.shutdown()
            await db.update_bot_status(bot_id, "stopped")
            logger.info("🛑 Managed Bot %s stopped.", bot_id)
        except Exception:
            logger.exception("Error stopping bot %s", bot_id)


bot_manager = DynamicBotManager()
