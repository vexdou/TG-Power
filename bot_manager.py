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
            active_bots = await db.get_all_active_bots()

            logger.info(
                f"🔄 Loading {len(active_bots)} active managed bots..."
            )

            tasks = []

            for bot in active_bots:
                bot_id = bot.get("bot_id")
                token = bot.get("token")

                if not bot_id or not token:
                    logger.error(
                        f"⚠️ Invalid managed bot record: {bot}"
                    )
                    continue

                tasks.append(
                    asyncio.create_task(
                        self.start_bot_instance(
                            bot_id,
                            token
                        )
                    )
                )

            if tasks:
                results = await asyncio.gather(
                    *tasks,
                    return_exceptions=True
                )

                for index, result in enumerate(results):

                    if isinstance(result, Exception):
                        logger.error(
                            f"🔴 Managed bot startup task failed: {result}",
                            exc_info=True
                        )

        except Exception as e:
            logger.error(
                f"🔴 Failed loading managed bots: {e}",
                exc_info=True
            )

    async def start_bot_instance(
        self,
        bot_id: int,
        token: str
    ) -> bool:

        if bot_id in self.running_bots:
            logger.info(
                f"Bot {bot_id} already running."
            )
            return True

        if bot_id in self.starting_bots:
            logger.info(
                f"Bot {bot_id} is already starting."
            )
            return False

        self.starting_bots.add(bot_id)

        handler = None

        try:

            handler = ManagedBotHandler(
                bot_id,
                token
            )

            # ------------------------------------------------------
            # INITIALIZE APPLICATION
            # ------------------------------------------------------

            await handler.app.initialize()

            # ------------------------------------------------------
            # VERIFY TOKEN
            # ------------------------------------------------------

            bot_me = await handler.app.bot.get_me()

            logger.info(
                f"🤖 Authenticated Bot: "
                f"@{bot_me.username} ({bot_id})"
            )

            # ------------------------------------------------------
            # CLEAR WEBHOOK
            # ------------------------------------------------------

            await handler.app.bot.delete_webhook(
                drop_pending_updates=True
            )

            # ------------------------------------------------------
            # START APPLICATION
            # ------------------------------------------------------

            await handler.app.start()

            # ------------------------------------------------------
            # START POLLING
            # ------------------------------------------------------

            if handler.app.updater is None:
                raise RuntimeError(
                    "Telegram updater is not available."
                )

            await handler.app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
                poll_interval=1.0,
                timeout=30
            )

            # ------------------------------------------------------
            # STORE ONLY AFTER FULL SUCCESS
            # ------------------------------------------------------

            self.running_bots[bot_id] = handler

            await db.update_bot_status(
                bot_id,
                "active"
            )

            logger.info(
                f"🟢 Managed Bot @{bot_me.username} "
                f"is fully ONLINE!"
            )

            return True

        except Exception as e:

            logger.error(
                f"🔴 Failed to start managed bot "
                f"{bot_id}: {e}",
                exc_info=True
            )

            # ------------------------------------------------------
            # CLEANUP PARTIALLY STARTED APPLICATION
            # ------------------------------------------------------

            if handler is not None:

                try:
                    if (
                        handler.app.updater
                        and handler.app.updater.running
                    ):
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
                await db.update_bot_status(
                    bot_id,
                    "failed"
                )
            except Exception as db_error:
                logger.error(
                    f"Could not update bot {bot_id} "
                    f"status: {db_error}"
                )

            return False

        finally:
            self.starting_bots.discard(bot_id)

    async def stop_bot_instance(
        self,
        bot_id: int
    ):

        handler = self.running_bots.get(
            bot_id
        )

        if not handler:
            return

        try:

            self.running_bots.pop(
                bot_id,
                None
            )

            if (
                handler.app.updater
                and handler.app.updater.running
            ):
                await handler.app.updater.stop()

            if handler.app.running:
                await handler.app.stop()

            await handler.app.shutdown()

            await db.update_bot_status(
                bot_id,
                "stopped"
            )

            logger.info(
                f"🛑 Managed Bot {bot_id} stopped."
            )

        except Exception as e:

            logger.error(
                f"Error stopping bot {bot_id}: {e}",
                exc_info=True
            )


bot_manager = DynamicBotManager()
