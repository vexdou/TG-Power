import logging
import time
import json
import httpx

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from config import Config
from database import db
from bot_manager import bot_manager


logger = logging.getLogger(__name__)


def main_keyboard():

    return {
        "keyboard": [
            [
                {
                    "text": "➕ Create New Bot",
                    "request_managed_bot": {
                        "request_id": int(time.time()),
                        "suggested_name": "My Downloader Bot",
                        "suggested_username": "MyDownloaderBot"
                    }
                }
            ],
            [
                {
                    "text": "🤖 My Bots"
                },
                {
                    "text": "ℹ️ Help"
                }
            ]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


class MainSaaSBot:

    def __init__(self):

        self.app = (
            Application
            .builder()
            .token(Config.BOT_TOKEN)
            .build()
        )

        self._setup_handlers()

    def _setup_handlers(self):

        self.app.add_handler(
            CommandHandler(
                "start",
                self.start_command
            )
        )

        self.app.add_handler(
            MessageHandler(
                filters.StatusUpdate.MANAGED_BOT_CREATED,
                self.handle_managed_bot_created
            )
        )

        self.app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_text_messages
            )
        )

        self.app.add_error_handler(
            self.error_handler
        )

    async def start_bot(self):

        try:

            await self.app.initialize()

            await self.app.bot.delete_webhook(
                drop_pending_updates=True
            )

            await self.app.start()

            if self.app.updater is None:
                raise RuntimeError(
                    "Main bot updater is not available."
                )

            await self.app.updater.start_polling(
                drop_pending_updates=True
            )

            bot_me = await self.app.bot.get_me()

            logger.info(
                f"👑 Main Managed SaaS Bot Online: "
                f"@{bot_me.username}"
            )

        except Exception as e:

            logger.error(
                f"🔴 Main bot startup error: {e}",
                exc_info=True
            )

            # Make sure a partially started application
            # does not remain in a broken state.

            try:
                if (
                    self.app.updater
                    and self.app.updater.running
                ):
                    await self.app.updater.stop()
            except Exception:
                pass

            try:
                if self.app.running:
                    await self.app.stop()
            except Exception:
                pass

            try:
                await self.app.shutdown()
            except Exception:
                pass

            raise

    async def stop_bot(self):

        try:

            if (
                self.app.updater
                and self.app.updater.running
            ):
                await self.app.updater.stop()

            if self.app.running:
                await self.app.stop()

            await self.app.shutdown()

            logger.info(
                "🛑 Main SaaS Bot stopped."
            )

        except Exception as e:

            logger.error(
                f"Main bot shutdown error: {e}",
                exc_info=True
            )

    async def get_managed_bot_token(
        self,
        bot_id: int
    ) -> str | None:

        """
        Kuxirida Telegram API si loogu soo saaro
        Managed Bot Token.
        """

        url = (
            f"https://api.telegram.org/"
            f"bot{Config.BOT_TOKEN}/"
            f"getManagedBotToken"
        )

        try:

            async with httpx.AsyncClient(
                timeout=10.0
            ) as client:

                response = await client.post(
                    url,
                    json={
                        "user_id": bot_id
                    }
                )

                response.raise_for_status()

                res = response.json()

                if res.get("ok"):

                    return res.get(
                        "result"
                    )

                logger.error(
                    f"Telegram managed token API "
                    f"returned error: {res}"
                )

        except httpx.HTTPError as e:

            logger.error(
                f"HTTP error fetching managed "
                f"bot token: {e}"
            )

        except Exception as e:

            logger.error(
                f"Error fetching managed bot token: "
                f"{e}",
                exc_info=True
            )

        return None

    async def start_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        user = update.effective_user

        text = (
            f"🤖 **BOT BUILDER PLATFORM**\n\n"
            f"Soo dhawoow **{user.first_name}** 👋\n\n"
            f"Waxaad halkan ka abuuri kartaa "
            f"downloader bot kuu gaar ah oo toos u "
            f"shaqeeya iyadoon loo baahnayn Token.\n\n"
            f"Taabo **➕ Create New Bot** si aad "
            f"Telegram gudaheeda uga abuurto."
        )

        # Keep the original native managed-bot
        # keyboard structure.
        #
        # Telegram's managed-bot keyboard is not
        # represented by the normal PTB ReplyKeyboardMarkup,
        # therefore send it as the API payload.

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=json.dumps(
                main_keyboard()
            ),
            parse_mode="Markdown"
        )

    async def handle_managed_bot_created(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        message = update.message

        if not message:
            return

        managed = getattr(
            message,
            "managed_bot_created",
            None
        )

        if not managed:
            return

        bot_info = getattr(
            managed,
            "bot",
            None
        )

        if not bot_info:
            return

        bot_id = bot_info.id
        username = bot_info.username or ""
        first_name = (
            bot_info.first_name
            or "Managed Bot"
        )

        owner_id = (
            update.effective_user.id
        )

        status_msg = await message.reply_text(
            "⏳ **Bot-ka waa la sameeyay! "
            "Waxaan helayaa Token-ka oo kicinayaa...**",
            parse_mode="Markdown"
        )

        # ----------------------------------------------------------
        # 1. GET MANAGED BOT TOKEN
        # ----------------------------------------------------------

        token = await self.get_managed_bot_token(
            bot_id
        )

        if not token:

            await status_msg.edit_text(
                "❌ **Cilad:** Token-ka bot-ka "
                "ma soo bixin.\n\n"
                "Hubi in Manager Bot-kaagu leeyahay "
                "Bot Management Mode."
            )

            return

        # ----------------------------------------------------------
        # 2. SAVE BOT
        # ----------------------------------------------------------

        try:

            await db.add_new_bot(
                owner_id=owner_id,
                token=token,
                bot_id=bot_id,
                username=username
            )

        except Exception as e:

            logger.error(
                f"Database error saving bot "
                f"{bot_id}: {e}",
                exc_info=True
            )

            await status_msg.edit_text(
                "❌ Bot-ka waa la abuuray laakiin "
                "database-ka laguma kaydin karin."
            )

            return

        # ----------------------------------------------------------
        # 3. START MANAGED BOT
        # ----------------------------------------------------------

        started = await bot_manager.start_bot_instance(
            bot_id,
            token
        )

        if started:

            await status_msg.edit_text(
                f"✅ **BOT-KAA TIKTOK/YT/IG "
                f"DOWNLOADER WAA LA KICIYAY!**\n\n"
                f"🤖 Name: **{first_name}**\n"
                f"🔗 Username: **@{username}**\n"
                f"🟢 Status: **Active & Online**\n\n"
                f"👉 Taabo halkan si aad u gasho: "
                f"https://t.me/{username}",
                parse_mode="Markdown"
            )

        else:

            await status_msg.edit_text(
                "❌ Bot-ka waa la abuuray "
                "laakiin waa kici waayay. "
                "Fadlan eeg system logs."
            )

    async def handle_text_messages(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        if not update.message:
            return

        text = update.message.text

        if not text:
            return

        user_id = (
            update.effective_user.id
        )

        if text == "🤖 My Bots":

            try:

                cursor = db.bots.find(
                    {
                        "owner_id": user_id
                    }
                )

                user_bots = await cursor.to_list(
                    length=None
                )

            except Exception as e:

                logger.error(
                    f"My Bots database error: {e}",
                    exc_info=True
                )

                await update.message.reply_text(
                    "❌ Database error. "
                    "Fadlan mar kale isku day."
                )

                return

            if not user_bots:

                await update.message.reply_text(
                    "❌ Weli ma lihid managed bot. "
                    "Taabo **➕ Create New Bot**.",
                    parse_mode="Markdown"
                )

                return

            msg = (
                "🤖 **BOT-YADAADA ACTIVE-KA AH:**\n\n"
            )

            for bot in user_bots:

                msg += (
                    f"• **Name:** "
                    f"@{bot.get('username', 'N/A')}\n"
                    f"  `ID: {bot.get('bot_id', 'N/A')}` "
                    f"| Status: "
                    f"`{bot.get('status', 'unknown')}`\n\n"
                )

            await update.message.reply_text(
                msg,
                parse_mode="Markdown"
            )

        elif text == "ℹ️ Help":

            await update.message.reply_text(
                "ℹ️ **BOT BUILDER HELP**\n\n"
                "Taabo **➕ Create New Bot** si "
                "Telegram toos kuugu muujiyo bogga "
                "abuurista bot-ka iyadoon BotFather "
                "lagu wareegayn.",
                parse_mode="Markdown"
            )

    async def error_handler(
        self,
        update: object,
        context: ContextTypes.DEFAULT_TYPE
    ):

        logger.error(
            f"Main Bot Error: {context.error}",
            exc_info=True
        )


main_bot = MainSaaSBot()
