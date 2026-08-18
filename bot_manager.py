import asyncio
import logging
from managed_bot import ManagedBotHandler
from database import db

logger = logging.getLogger(__name__)

class DynamicBotManager:
    def __init__(self):
        self.running_bots: dict[int, ManagedBotHandler] = {}

    async def load_and_start_all(self):
        active_bots = await db.get_all_active_bots()
        logger.info(f"Loading {len(active_bots)} active managed bots...")
        for bot in active_bots:
            await self.start_bot_instance(bot["bot_id"], bot["token"])

    async def start_bot_instance(self, bot_id: int, token: str) -> bool:
        if bot_id in self.running_bots:
            return True

        try:
            handler = ManagedBotHandler(bot_id, token)
            await handler.app.initialize()
            
            # WAA HAGAN FIX-KA: Tirtir Webhook-ka Telegram si Polling-ku fariimaha u helo
            await handler.app.bot.delete_webhook(drop_pending_updates=True)
            
            await handler.app.start()
            await handler.app.updater.start_polling(drop_pending_updates=True)
            
            self.running_bots[bot_id] = handler
            logger.info(f"✅ Managed Bot successfully started & listening: {bot_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start managed bot {bot_id}: {e}")
            await db.update_bot_status(bot_id, "failed")
            return False

    async def stop_bot_instance(self, bot_id: int):
        if bot_id in self.running_bots:
            try:
                handler = self.running_bots[bot_id]
                await handler.app.updater.stop()
                await handler.app.stop()
                await handler.app.shutdown()
                del self.running_bots[bot_id]
                logger.info(f"🛑 Managed Bot stopped: {bot_id}")
            except Exception as e:
                logger.error(f"Error stopping bot {bot_id}: {e}")

bot_manager = DynamicBotManager()
