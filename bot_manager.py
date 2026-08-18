import asyncio
import logging
from telegram import Update
from managed_bot import ManagedBotHandler
from database import db

logger = logging.getLogger(__name__)

class DynamicBotManager:
    def __init__(self):
        self.running_bots: dict[int, ManagedBotHandler] = {}
        self.running_tasks: dict[int, asyncio.Task] = {}

    async def load_and_start_all(self):
        active_bots = await db.get_all_active_bots()
        logger.info(f"🔄 Loading {len(active_bots)} active managed bots...")
        for bot in active_bots:
            asyncio.create_task(self.start_bot_instance(bot["bot_id"], bot["token"]))

    async def start_bot_instance(self, bot_id: int, token: str) -> bool:
        if bot_id in self.running_bots:
            logger.info(f"Bot {bot_id} is already running.")
            return True

        try:
            handler = ManagedBotHandler(bot_id, token)
            
            # 1. Initialize Application
            await handler.app.initialize()
            
            # 2. Verify Bot Token & Connection
            bot_me = await handler.app.bot.get_me()
            logger.info(f"🤖 Managed Bot Authenticated: @{bot_me.username} ({bot_id})")

            # 3. Clean Webhook & Pending Updates
            await handler.app.bot.delete_webhook(drop_pending_updates=True)
            
            # 4. Start Application & Polling with ALL UPDATES allowed
            await handler.app.start()
            await handler.app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
                poll_interval=1.0,
                timeout=30
            )

            self.running_bots[bot_id] = handler
            await db.update_bot_status(bot_id, "active")
            logger.info(f"🟢 Managed Bot @{bot_me.username} is FULLY ONLINE & listening!")
            return True

        except Exception as e:
            logger.error(f"🔴 Failed to start managed bot {bot_id}: {e}", exc_info=True)
            await db.update_bot_status(bot_id, "failed")
            return False

    async def stop_bot_instance(self, bot_id: int):
        if bot_id in self.running_bots:
            try:
                handler = self.running_bots.pop(bot_id)
                if handler.app.updater and handler.app.updater.running:
                    await handler.app.updater.stop()
                if handler.app.running:
                    await handler.app.stop()
                await handler.app.shutdown()
                logger.info(f"🛑 Managed Bot {bot_id} stopped successfully.")
            except Exception as e:
                logger.error(f"Error stopping bot {bot_id}: {e}")

bot_manager = DynamicBotManager()
