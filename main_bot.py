import asyncio
import logging
import os
import time

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButtonRequestManagedBot,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.error import TelegramError, Forbidden, BadRequest

from config import Config
from database import db
from bot_manager import bot_manager


logger = logging.getLogger(__name__)


# ================================================================
# MAIN BOT SETTINGS
# ================================================================

LANGUAGES = {
    "en": {
        "name": "English 🇬🇧",
        "welcome": (
            "🤖 **BOT BUILDER PLATFORM**\n\n"
            "Welcome, {name}! 👋\n\n"
            "Create your own downloader bot directly from Telegram."
        ),
        "help": (
            "ℹ️ **HELP**\n\n"
            "Use **Create New Bot** to create your own managed downloader bot.\n"
            "Use **My Bots** to view your bots.\n"
            "Use **Language** to change the main bot language."
        ),
    },
    "so": {
        "name": "Soomaali 🇸🇴",
        "welcome": (
            "🤖 **BOT BUILDER PLATFORM**\n\n"
            "Soo dhawoow {name}! 👋\n\n"
            "Waxaad Telegram gudaheeda ka abuuri kartaa downloader bot kuu gaar ah."
        ),
        "help": (
            "ℹ️ **CAAWIMAAD**\n\n"
            "Isticmaal **Create New Bot** si aad u abuurto bot-kaaga.\n"
            "Isticmaal **My Bots** si aad u aragto bot-yadaada.\n"
            "Isticmaal **Language** si aad u beddesho luuqadda."
        ),
    },
    "ar": {
        "name": "العربية 🇸🇦",
        "welcome": (
            "🤖 **منصة إنشاء البوتات**\n\n"
            "مرحباً {name}! 👋\n\n"
            "يمكنك إنشاء بوت تحميل خاص بك مباشرة من Telegram."
        ),
        "help": (
            "ℹ️ **المساعدة**\n\n"
            "استخدم Create New Bot لإنشاء البوت.\n"
            "استخدم My Bots لعرض البوتات الخاصة بك.\n"
            "استخدم Language لتغيير اللغة."
        ),
    },
    "es": {
        "name": "Español 🇪🇸",
        "welcome": (
            "🤖 **PLATAFORMA DE BOTS**\n\n"
            "¡Bienvenido {name}! 👋\n\n"
            "Crea tu propio bot descargador desde Telegram."
        ),
        "help": (
            "ℹ️ **AYUDA**\n\n"
            "Usa Create New Bot para crear tu bot.\n"
            "Usa My Bots para ver tus bots.\n"
            "Usa Language para cambiar el idioma."
        ),
    },
}


def is_admin(user_id: int) -> bool:
    return int(user_id) == int(Config.OWNER_ID)


# ================================================================
# MAIN USER KEYBOARD
# ================================================================

def main_keyboard():
    request_id = int(time.time())

    create_button = KeyboardButton(
        text="➕ Create New Bot",
        request_managed_bot=KeyboardButtonRequestManagedBot(
            request_id=request_id,
            suggested_name="My Downloader Bot",
            suggested_username="MyDownloaderBot",
        ),
    )

    return ReplyKeyboardMarkup(
        [
            [create_button],
            [
                KeyboardButton("🤖 My Bots"),
                KeyboardButton("🌐 Language"),
            ],
            [
                KeyboardButton("ℹ️ Help"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def admin_keyboard():
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("📊 Main Statistics"),
                KeyboardButton("🤖 All Bots"),
            ],
            [
                KeyboardButton("👥 All Users"),
                KeyboardButton("📢 Broadcast All Bots"),
            ],
            [
                KeyboardButton("📣 Broadcast One Bot"),
                KeyboardButton("🔐 Force Join"),
            ],
            [
                KeyboardButton("▶️ Start Bot"),
                KeyboardButton("⏹ Stop Bot"),
            ],
            [
                KeyboardButton("🗑 Delete Bot"),
                KeyboardButton("⚙️ Bot Creation"),
            ],
            [
                KeyboardButton("🌐 Language"),
                KeyboardButton("🔙 User Panel"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def language_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "English 🇬🇧",
                    callback_data="main_lang_en",
                ),
                InlineKeyboardButton(
                    "Soomaali 🇸🇴",
                    callback_data="main_lang_so",
                ),
            ],
            [
                InlineKeyboardButton(
                    "العربية 🇸🇦",
                    callback_data="main_lang_ar",
                ),
                InlineKeyboardButton(
                    "Español 🇪🇸",
                    callback_data="main_lang_es",
                ),
            ],
        ]
    )


# ================================================================
# MAIN SaaS BOT
# ================================================================

class MainSaaSBot:

    def __init__(self):

        self.app = (
            Application
            .builder()
            .token(Config.BOT_TOKEN)
            .build()
        )

        self._setup_handlers()

    # ============================================================
    # HANDLERS
    # ============================================================

    def _setup_handlers(self):

        self.app.add_handler(
            CommandHandler(
                "start",
                self.start_command,
            )
        )

        self.app.add_handler(
            CommandHandler(
                "admin",
                self.admin_command,
            )
        )

        self.app.add_handler(
            CommandHandler(
                "language",
                self.language_command,
            )
        )

        self.app.add_handler(
            MessageHandler(
                filters.StatusUpdate.MANAGED_BOT_CREATED,
                self.handle_managed_bot_created,
            )
        )

        self.app.add_handler(
            CallbackQueryHandler(
                self.handle_callback,
            )
        )

        self.app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_text_messages,
            )
        )

        self.app.add_error_handler(
            self.error_handler,
        )

    # ============================================================
    # START
    # ============================================================

    async def start_bot(self):

        try:

            await self.app.initialize()

            await self.app.bot.delete_webhook(
                drop_pending_updates=True,
            )

            await self.app.start()

            if self.app.updater is None:
                raise RuntimeError(
                    "Main bot updater is not available."
                )

            await self.app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
                poll_interval=1.0,
                timeout=30,
            )

            bot_me = await self.app.bot.get_me()

            logger.info(
                f"👑 Main SaaS Bot Online: "
                f"@{bot_me.username}"
            )

        except Exception as e:

            logger.error(
                f"🔴 Main bot startup error: {e}",
                exc_info=True,
            )

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
                exc_info=True,
            )

    # ============================================================
    # LANGUAGE
    # ============================================================

    async def get_language(self, user_id: int) -> str:

        try:

            user = await db.get_main_user(
                user_id
            )

            if user:
                return user.get(
                    "language",
                    "en",
                )

        except Exception as e:

            logger.error(
                f"Language read error: {e}",
                exc_info=True,
            )

        return "en"

    async def set_language(
        self,
        user_id: int,
        language: str,
    ):

        try:

            await db.set_main_user_language(
                user_id,
                language,
            )

        except Exception as e:

            logger.error(
                f"Language save error: {e}",
                exc_info=True,
            )

    async def language_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):

        if not update.effective_user:
            return

        await update.message.reply_text(
            "🌐 **Choose Language / Dooro Luuqada**",
            reply_markup=language_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    # ============================================================
    # START COMMAND
    # ============================================================

    async def start_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):

        if not update.effective_user:
            return

        user = update.effective_user

        try:

            await db.save_main_user(
                user_id=user.id,
                username=user.username or "",
                full_name=user.full_name or "",
            )

        except Exception as e:

            logger.error(
                f"Could not save main user: {e}",
                exc_info=True,
            )

        lang = await self.get_language(
            user.id
        )

        language = LANGUAGES.get(
            lang,
            LANGUAGES["en"],
        )

        await update.message.reply_text(
            language["welcome"].format(
                name=user.first_name or "User"
            ),
            reply_markup=(
                admin_keyboard()
                if is_admin(user.id)
                else main_keyboard()
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    # ============================================================
    # ADMIN COMMAND
    # ============================================================

    async def admin_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):

        if not update.effective_user:
            return

        if not is_admin(
            update.effective_user.id
        ):
            await update.message.reply_text(
                "⛔ You are not authorized."
            )
            return

        await self.show_admin_panel(
            update,
        )

    async def show_admin_panel(
        self,
        update: Update,
    ):

        stats = await self.get_main_stats()

        text = (
            "👑 **MAIN ADMIN PANEL**\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Users: `{stats['users']}`\n"
            f"🤖 Bots: `{stats['bots']}`\n"
            f"🟢 Active: `{stats['active']}`\n"
            f"🔴 Failed: `{stats['failed']}`\n"
            f"📥 Downloads: `{stats['downloads']}`\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Dooro maamulka aad rabto:"
        )

        await update.message.reply_text(
            text,
            reply_markup=admin_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    # ============================================================
    # MAIN STATISTICS
    # ============================================================

    async def get_main_stats(self):

        try:

            users = await db.main_users.count_documents({})

            bots = await db.bots.count_documents({})

            active = await db.bots.count_documents(
                {
                    "status": "active"
                }
            )

            failed = await db.bots.count_documents(
                {
                    "status": "failed"
                }
            )

            downloads = await db.downloads.count_documents({})

            return {
                "users": users,
                "bots": bots,
                "active": active,
                "failed": failed,
                "downloads": downloads,
            }

        except Exception as e:

            logger.error(
                f"Main stats error: {e}",
                exc_info=True,
            )

            return {
                "users": 0,
                "bots": 0,
                "active": 0,
                "failed": 0,
                "downloads": 0,
            }

    async def show_main_stats(
        self,
        update: Update,
    ):

        stats = await self.get_main_stats()

        text = (
            "📊 **MAIN SYSTEM STATISTICS**\n\n"
            f"👥 Main Users: `{stats['users']}`\n"
            f"🤖 Created Bots: `{stats['bots']}`\n"
            f"🟢 Active Bots: `{stats['active']}`\n"
            f"🔴 Failed Bots: `{stats['failed']}`\n"
            f"📥 Total Downloads: `{stats['downloads']}`\n\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
        )

    # ============================================================
    # ALL BOTS
    # ============================================================

    async def show_all_bots(
        self,
        update: Update,
    ):

        try:

            cursor = db.bots.find({})

            bots = await cursor.to_list(
                length=None
            )

        except Exception as e:

            logger.error(
                f"All bots error: {e}",
                exc_info=True,
            )

            await update.message.reply_text(
                "❌ Database error."
            )
            return

        if not bots:

            await update.message.reply_text(
                "🤖 No managed bots have been created yet."
            )
            return

        text = (
            "🤖 **ALL MANAGED BOTS**\n\n"
        )

        buttons = []

        for bot in bots:

            bot_id = bot.get(
                "bot_id"
            )

            username = bot.get(
                "username",
                "N/A",
            )

            status = bot.get(
                "status",
                "unknown",
            )

            emoji = (
                "🟢"
                if status == "active"
                else "🔴"
            )

            text += (
                f"{emoji} @{username}\n"
                f"ID: `{bot_id}`\n"
                f"Owner: `{bot.get('owner_id', 'N/A')}`\n"
                f"Status: `{status}`\n\n"
            )

            buttons.append(
                [
                    InlineKeyboardButton(
                        f"📊 @{username}",
                        callback_data=f"admin_botstats_{bot_id}",
                    ),
                    InlineKeyboardButton(
                        "⚙️ Manage",
                        callback_data=f"admin_manage_{bot_id}",
                    ),
                ]
            )

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    # ============================================================
    # BOT STATS
    # ============================================================

    async def show_bot_stats(
        self,
        query,
        bot_id: int,
    ):

        try:

            bot = await db.get_bot(
                bot_id
            )

            if not bot:
                await query.edit_message_text(
                    "❌ Bot not found."
                )
                return

            stats = await db.get_bot_stats(
                bot_id
            )

            text = (
                "📊 **BOT STATISTICS**\n\n"
                f"🤖 @{bot.get('username', 'N/A')}\n"
                f"🆔 `{bot_id}`\n"
                f"👤 Owner: `{bot.get('owner_id', 'N/A')}`\n"
                f"🟢 Status: `{bot.get('status', 'unknown')}`\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"👥 Users: `{stats['total_users']}`\n"
                f"📥 Downloads: `{stats['total_downloads']}`\n"
                f"🎬 Videos: `{stats['videos']}`\n"
                f"🎵 Audio: `{stats['audio']}`\n"
            )

            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🔙 Back",
                                callback_data="admin_allbots",
                            )
                        ]
                    ]
                ),
            )

        except Exception as e:

            logger.error(
                f"Bot stats error: {e}",
                exc_info=True,
            )

            await query.edit_message_text(
                "❌ Could not load bot statistics."
            )

    # ============================================================
    # BOT MANAGEMENT
    # ============================================================

    async def manage_bot_menu(
        self,
        query,
        bot_id: int,
    ):

        bot = await db.get_bot(
            bot_id
        )

        if not bot:

            await query.edit_message_text(
                "❌ Bot not found."
            )
            return

        username = bot.get(
            "username",
            "N/A",
        )

        status = bot.get(
            "status",
            "unknown",
        )

        buttons = []

        if status == "active":

            buttons.append(
                [
                    InlineKeyboardButton(
                        "⏹ Stop Bot",
                        callback_data=f"admin_stop_{bot_id}",
                    )
                ]
            )

        else:

            buttons.append(
                [
                    InlineKeyboardButton(
                        "▶️ Start Bot",
                        callback_data=f"admin_start_{bot_id}",
                    )
                ]
            )

        buttons.extend(
            [
                [
                    InlineKeyboardButton(
                        "📊 Statistics",
                        callback_data=f"admin_botstats_{bot_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔐 Force Join",
                        callback_data=f"admin_force_{bot_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🗑 Delete Bot",
                        callback_data=f"admin_confirmdelete_{bot_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="admin_allbots",
                    )
                ],
            ]
        )

        await query.edit_message_text(
            (
                "⚙️ **BOT MANAGEMENT**\n\n"
                f"🤖 @{username}\n"
                f"🆔 `{bot_id}`\n"
                f"🟢 Status: `{status}`"
            ),
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    # ============================================================
    # START BOT
    # ============================================================

    async def start_managed_bot(
        self,
        query,
        bot_id: int,
    ):

        bot = await db.get_bot(
            bot_id
        )

        if not bot:

            await query.answer(
                "Bot not found.",
                show_alert=True,
            )
            return

        token = bot.get(
            "token"
        )

        if not token:

            await query.answer(
                "Bot token is missing.",
                show_alert=True,
            )
            return

        await query.answer(
            "Starting bot..."
        )

        started = await bot_manager.start_bot_instance(
            bot_id,
            token,
        )

        if started:

            await db.update_bot_status(
                bot_id,
                "active",
            )

            await query.edit_message_text(
                "🟢 **Bot started successfully.**",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⚙️ Manage",
                                callback_data=f"admin_manage_{bot_id}",
                            )
                        ]
                    ]
                ),
            )

        else:

            await query.edit_message_text(
                "🔴 **Bot could not be started.**\n\n"
                "Check Render logs for the exact error.",
                parse_mode=ParseMode.MARKDOWN,
            )

    # ============================================================
    # STOP BOT
    # ============================================================

    async def stop_managed_bot(
        self,
        query,
        bot_id: int,
    ):

        await query.answer(
            "Stopping..."
        )

        try:

            await bot_manager.stop_bot_instance(
                bot_id
            )

            await db.update_bot_status(
                bot_id,
                "stopped",
            )

            await query.edit_message_text(
                "⏹ **Bot stopped successfully.**",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⚙️ Manage",
                                callback_data=f"admin_manage_{bot_id}",
                            )
                        ]
                    ]
                ),
            )

        except Exception as e:

            logger.error(
                f"Stop bot error: {e}",
                exc_info=True,
            )

            await query.edit_message_text(
                "❌ Failed to stop bot."
            )

    # ============================================================
    # DELETE BOT
    # ============================================================

    async def delete_managed_bot(
        self,
        query,
        bot_id: int,
    ):

        bot = await db.get_bot(
            bot_id
        )

        if not bot:

            await query.answer(
                "Bot not found.",
                show_alert=True,
            )
            return

        try:

            await bot_manager.stop_bot_instance(
                bot_id
            )

        except Exception:
            pass

        try:

            await db.bots.delete_one(
                {
                    "bot_id": bot_id
                }
            )

            await db.users.delete_many(
                {
                    "bot_id": bot_id
                }
            )

            await db.downloads.delete_many(
                {
                    "bot_id": bot_id
                }
            )

            await query.edit_message_text(
                "🗑 **Bot deleted from the SaaS system.**",
                parse_mode=ParseMode.MARKDOWN,
            )

        except Exception as e:

            logger.error(
                f"Delete bot error: {e}",
                exc_info=True,
            )

            await query.edit_message_text(
                "❌ Database error while deleting bot."
            )

    # ============================================================
    # FORCE JOIN
    # ============================================================

    async def show_force_join(
        self,
        update: Update,
    ):

        try:

            bots = await db.bots.find({}).to_list(
                length=None
            )

        except Exception:

            await update.message.reply_text(
                "❌ Database error."
            )
            return

        if not bots:

            await update.message.reply_text(
                "❌ No bots available."
            )
            return

        buttons = []

        for bot in bots:

            buttons.append(
                [
                    InlineKeyboardButton(
                        f"🔐 @{bot.get('username', 'N/A')}",
                        callback_data=f"admin_force_{bot.get('bot_id')}",
                    )
                ]
            )

        await update.message.reply_text(
            "🔐 **FORCE JOIN MANAGEMENT**\n\n"
            "Dooro bot-ka aad rabto inaad Force Join u maamusho:",
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def force_join_menu(
        self,
        query,
        bot_id: int,
    ):

        bot = await db.get_bot(
            bot_id
        )

        if not bot:

            await query.answer(
                "Bot not found.",
                show_alert=True,
            )
            return

        channels = bot.get(
            "force_join_channels",
            []
        )

        text = (
            "🔐 **FORCE JOIN**\n\n"
            f"🤖 @{bot.get('username', 'N/A')}\n\n"
            "Channels:\n"
        )

        if channels:

            for channel in channels:
                text += f"• `{channel}`\n"

        else:

            text += "• None\n"

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "➕ Add Channel",
                            callback_data=f"force_add_{bot_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "➖ Remove Channel",
                            callback_data=f"force_remove_{bot_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data=f"admin_manage_{bot_id}",
                        )
                    ],
                ]
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    # ============================================================
    # FORCE JOIN ADD
    # ============================================================

    async def add_force_join_prompt(
        self,
        query,
        bot_id: int,
        context: ContextTypes.DEFAULT_TYPE,
    ):

        context.user_data["state"] = "force_add"
        context.user_data["force_bot_id"] = bot_id

        await query.edit_message_text(
            "➕ **Add Force Join Channel**\n\n"
            "Ii soo dir channel username-ka.\n\n"
            "Example:\n"
            "`@MyChannel`\n\n"
            "Bot-ka waa inuu channel-ka ku leeyahay "
            "permission ku filan si Force Join u shaqeeyo.",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def save_force_join(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):

        bot_id = context.user_data.get(
            "force_bot_id"
        )

        if not bot_id:
            return

        channel = update.message.text.strip()

        if not channel.startswith("@"):

            await update.message.reply_text(
                "❌ Channel username-ku waa inuu ku bilaabmaa `@`.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        bot = await db.get_bot(
            bot_id
        )

        if not bot:

            await update.message.reply_text(
                "❌ Bot not found."
            )
            context.user_data.clear()
            return

        channels = bot.get(
            "force_join_channels",
            []
        )

        if channel not in channels:

            channels.append(
                channel
            )

        await db.bots.update_one(
            {
                "bot_id": bot_id
            },
            {
                "$set": {
                    "force_join_channels": channels
                }
            }
        )

        context.user_data.clear()

        await update.message.reply_text(
            f"✅ Force Join channel added:\n`{channel}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_keyboard(),
        )

    # ============================================================
    # FORCE JOIN REMOVE
    # ============================================================

    async def remove_force_join_menu(
        self,
        query,
        bot_id: int,
    ):

        bot = await db.get_bot(
            bot_id
        )

        if not bot:

            await query.answer(
                "Bot not found.",
                show_alert=True,
            )
            return

        channels = bot.get(
            "force_join_channels",
            []
        )

        if not channels:

            await query.answer(
                "No channels configured.",
                show_alert=True,
            )
            return

        buttons = []

        for channel in channels:

            buttons.append(
                [
                    InlineKeyboardButton(
                        f"🗑 {channel}",
                        callback_data=(
                            f"force_del_{bot_id}_"
                            f"{channel[1:]}"
                        ),
                    )
                ]
            )

        buttons.append(
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data=f"admin_force_{bot_id}",
                )
            ]
        )

        await query.edit_message_text(
            "➖ **Remove Force Join Channel**",
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def delete_force_join(
        self,
        query,
        bot_id: int,
        channel_name: str,
    ):

        channel = "@" + channel_name

        await db.bots.update_one(
            {
                "bot_id": bot_id
            },
            {
                "$pull": {
                    "force_join_channels": channel
                }
            }
        )

        await query.answer(
            "Channel removed."
        )

        await self.force_join_menu(
            query,
            bot_id,
        )

    # ============================================================
    # BROADCAST ALL BOTS
    # ============================================================

    async def broadcast_all_prompt(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):

        context.user_data["state"] = "broadcast_all"

        await update.message.reply_text(
            "📢 **BROADCAST ALL BOTS**\n\n"
            "Hadda ii soo dir message-ka aad rabto "
            "in loo diro users-ka dhammaan managed bots.\n\n"
            "Text, photo, video, document, audio iwm waa la copy-gareyn karaa.",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def perform_broadcast_all(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):

        context.user_data.clear()

        bots = await db.bots.find(
            {}
        ).to_list(
            length=None
        )

        sent = 0
        failed = 0
        users_seen = set()

        status = await update.message.reply_text(
            "⏳ Broadcast started..."
        )

        for bot in bots:

            bot_id = bot.get(
                "bot_id"
            )

            handler = bot_manager.running_bots.get(
                bot_id
            )

            if not handler:
                continue

            users = await db.get_all_bot_users(
                bot_id
            )

            for user in users:

                user_id = user.get(
                    "user_id"
                )

                if not user_id:
                    continue

                # Prevent duplicate delivery if the same user
                # uses multiple managed bots.
                unique_key = (
                    bot_id,
                    user_id,
                )

                if unique_key in users_seen:
                    continue

                users_seen.add(
                    unique_key
                )

                try:

                    await update.message.copy(
                        chat_id=user_id
                    )

                    sent += 1

                    await asyncio.sleep(
                        0.05
                    )

                except Forbidden:

                    failed += 1

                except TelegramError:

                    failed += 1

                except Exception:

                    failed += 1

        await status.edit_text(
            "📢 **BROADCAST FINISHED**\n\n"
            f"🟢 Sent: `{sent}`\n"
            f"🔴 Failed: `{failed}`",
            parse_mode=ParseMode.MARKDOWN,
        )

    # ============================================================
    # BROADCAST ONE BOT
    # ============================================================

    async def broadcast_one_prompt(
        self,
        update: Update,
    ):

        bots = await db.bots.find(
            {}
        ).to_list(
            length=None
        )

        if not bots:

            await update.message.reply_text(
                "❌ No managed bots."
            )
            return

        buttons = []

        for bot in bots:

            buttons.append(
                [
                    InlineKeyboardButton(
                        f"📣 @{bot.get('username', 'N/A')}",
                        callback_data=(
                            f"broadcast_bot_{bot.get('bot_id')}"
                        ),
                    )
                ]
            )

        await update.message.reply_text(
            "📣 **BROADCAST ONE BOT**\n\n"
            "Dooro bot-ka:",
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def one_bot_broadcast_prompt(
        self,
        query,
        bot_id: int,
        context: ContextTypes.DEFAULT_TYPE,
    ):

        context.user_data["state"] = "broadcast_one"
        context.user_data["broadcast_bot_id"] = bot_id

        await query.edit_message_text(
            "📣 **BROADCAST**\n\n"
            "Hadda ii soo dir message-ka loo dirayo users-ka bot-kan.",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def perform_one_bot_broadcast(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):

        bot_id = context.user_data.get(
            "broadcast_bot_id"
        )

        context.user_data.clear()

        if not bot_id:
            return

        handler = bot_manager.running_bots.get(
            bot_id
        )

        if not handler:

            await update.message.reply_text(
                "❌ Bot-kan hadda online ma aha."
            )
            return

        users = await db.get_all_bot_users(
            bot_id
        )

        status = await update.message.reply_text(
            f"⏳ Broadcasting to {len(users)} users..."
        )

        sent = 0
        failed = 0

        for user in users:

            user_id = user.get(
                "user_id"
            )

            if not user_id:
                continue

            try:

                await update.message.copy(
                    chat_id=user_id
                )

                sent += 1

                await asyncio.sleep(
                    0.05
                )

            except Exception:

                failed += 1

        await status.edit_text(
            "📣 **BROADCAST FINISHED**\n\n"
            f"🟢 Sent: `{sent}`\n"
            f"🔴 Failed: `{failed}`",
            parse_mode=ParseMode.MARKDOWN,
        )

    # ============================================================
    # ALL USERS
    # ============================================================

    async def show_all_users(
        self,
        update: Update,
    ):

        try:

            total_users = await db.main_users.count_documents({})

            bot_users = await db.users.count_documents({})

            unique_bot_users = len(
                await db.users.distinct(
                    "user_id"
                )
            )

            text = (
                "👥 **USER STATISTICS**\n\n"
                f"👤 Main Bot Users: `{total_users}`\n"
                f"👥 Bot User Records: `{bot_users}`\n"
                f"🧑 Unique Managed-Bot Users: `{unique_bot_users}`"
            )

            await update.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
            )

        except Exception as e:

            logger.error(
                f"User stats error: {e}",
                exc_info=True,
            )

            await update.message.reply_text(
                "❌ Database error."
            )

    # ============================================================
    # BOT CREATION SETTING
    # ============================================================

    async def show_bot_creation_setting(
        self,
        update: Update,
    ):

        enabled = await db.get_system_setting(
            "bot_creation_enabled",
            True,
        )

        state = (
            "🟢 ENABLED"
            if enabled
            else "🔴 DISABLED"
        )

        await update.message.reply_text(
            (
                "⚙️ **BOT CREATION SETTING**\n\n"
                f"Status: **{state}**\n\n"
                "Marka Disabled yahay users ma abuuri karaan bots cusub."
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🟢 Enable",
                            callback_data="creation_enable",
                        ),
                        InlineKeyboardButton(
                            "🔴 Disable",
                            callback_data="creation_disable",
                        ),
                    ]
                ]
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    # ============================================================
    # USER BOT CREATION CHECK
    # ============================================================

    async def creation_allowed(
        self,
        user_id: int,
    ) -> bool:

        if is_admin(user_id):
            return True

        return await db.get_system_setting(
            "bot_creation_enabled",
            True,
        )

    # ============================================================
    # MANAGED BOT CREATED
    # ============================================================

    async def get_managed_bot_token(
        self,
        bot_id: int,
    ) -> str | None:

        try:

            token = await self.app.bot.get_managed_bot_token(
                bot_id
            )

            return token

        except Exception as e:

            logger.error(
                f"Managed bot token error: {e}",
                exc_info=True,
            )

            return None

    async def handle_managed_bot_created(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):

        message = update.message

        if not message:
            return

        managed = getattr(
            message,
            "managed_bot_created",
            None,
        )

        if not managed:
            return

        bot_info = getattr(
            managed,
            "bot",
            None,
        )

        if not bot_info:
            return

        owner = update.effective_user

        if not owner:
            return

        # Check creation system switch.
        if not await self.creation_allowed(
            owner.id
        ):

            await message.reply_text(
                "⛔ Bot creation is currently disabled."
            )
            return

        bot_id = bot_info.id
        username = bot_info.username or ""
        first_name = (
            bot_info.first_name
            or "Managed Bot"
        )

        status_msg = await message.reply_text(
            "⏳ **Bot-ka waa la sameeyay!**\n\n"
            "Waxaan helayaa managed token-ka kadibna waan kicinayaa...",
            parse_mode=ParseMode.MARKDOWN,
        )

        token = await self.get_managed_bot_token(
            bot_id
        )

        if not token:

            await status_msg.edit_text(
                "❌ **Token-ka managed bot-ka lama helin.**\n\n"
                "Hubi in main bot-ku yahay Manager Bot oo "
                "Bot Management Mode uu shaqaynayo.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        try:

            await db.add_new_bot(
                owner_id=owner.id,
                token=token,
                bot_id=bot_id,
                username=username,
            )

        except Exception as e:

            logger.error(
                f"Database error saving bot {bot_id}: {e}",
                exc_info=True,
            )

            await status_msg.edit_text(
                "❌ Bot-ka waa la sameeyay laakiin database-ka "
                "laguma kaydin karin.",
            )
            return

        started = await bot_manager.start_bot_instance(
            bot_id,
            token,
        )

        if started:

            await status_msg.edit_text(
                "✅ **BOT-KAA WAA LA KICIYAY!**\n\n"
                f"🤖 Name: **{first_name}**\n"
                f"🔗 Username: **@{username}**\n"
                "🟢 Status: **Active & Online**\n\n"
                f"👉 https://t.me/{username}",
                parse_mode=ParseMode.MARKDOWN,
            )

        else:

            await status_msg.edit_text(
                "⚠️ Bot-ka waa la abuuray laakiin "
                "ma kicin.\n\n"
                "Bot-ka database-ka waa kaydsan yahay; "
                "eeg Render logs.",
            )

    # ============================================================
    # MY BOTS
    # ============================================================

    async def show_my_bots(
        self,
        update: Update,
    ):

        user_id = update.effective_user.id

        try:

            bots = await db.bots.find(
                {
                    "owner_id": user_id
                }
            ).to_list(
                length=None
            )

        except Exception as e:

            logger.error(
                f"My bots error: {e}",
                exc_info=True,
            )

            await update.message.reply_text(
                "❌ Database error."
            )
            return

        if not bots:

            await update.message.reply_text(
                "❌ Weli ma lihid managed bot.\n\n"
                "Taabo ➕ Create New Bot."
            )
            return

        text = (
            "🤖 **MY BOTS**\n\n"
        )

        buttons = []

        for bot in bots:

            username = bot.get(
                "username",
                "N/A",
            )

            status = bot.get(
                "status",
                "unknown",
            )

            text += (
                f"🤖 @{username}\n"
                f"🆔 `{bot.get('bot_id')}`\n"
                f"Status: `{status}`\n\n"
            )

            buttons.append(
                [
                    InlineKeyboardButton(
                        f"📊 @{username}",
                        callback_data=(
                            f"owner_stats_{bot.get('bot_id')}"
                        ),
                    )
                ]
            )

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    # ============================================================
    # TEXT HANDLER
    # ============================================================

    async def handle_text_messages(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):

        if not update.message:
            return

        text = update.message.text

        if not text:
            return

        user_id = update.effective_user.id

        # --------------------------------------------------------
        # ACTIVE STATE HANDLERS
        # --------------------------------------------------------

        state = context.user_data.get(
            "state"
        )

        if is_admin(user_id):

            if state == "broadcast_all":
                await self.perform_broadcast_all(
                    update,
                    context,
                )
                return

            if state == "broadcast_one":
                await self.perform_one_bot_broadcast(
                    update,
                    context,
                )
                return

            if state == "force_add":
                await self.save_force_join(
                    update,
                    context,
                )
                return

        # --------------------------------------------------------
        # USER PANEL
        # --------------------------------------------------------

        if text == "➕ Create New Bot":

            allowed = await self.creation_allowed(
                user_id
            )

            if not allowed:

                await update.message.reply_text(
                    "⛔ Bot creation is temporarily disabled."
                )
                return

            # Native managed bot keyboard button normally
            # triggers the creation flow itself.
            await update.message.reply_text(
                "➕ Taabo button-ka **Create New Bot** "
                "si Telegram kuu furo managed-bot creation.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        if text == "🤖 My Bots":

            await self.show_my_bots(
                update
            )
            return

        if text == "🌐 Language":

            await self.language_command(
                update,
                context,
            )
            return

        if text == "ℹ️ Help":

            lang = await self.get_language(
                user_id
            )

            language = LANGUAGES.get(
                lang,
                LANGUAGES["en"],
            )

            await update.message.reply_text(
                language["help"],
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # --------------------------------------------------------
        # ADMIN PANEL
        # --------------------------------------------------------

        if is_admin(user_id):

            if text == "📊 Main Statistics":

                await self.show_main_stats(
                    update
                )
                return

            if text == "🤖 All Bots":

                await self.show_all_bots(
                    update
                )
                return

            if text == "👥 All Users":

                await self.show_all_users(
                    update
                )
                return

            if text == "📢 Broadcast All Bots":

                await self.broadcast_all_prompt(
                    update,
                    context,
                )
                return

            if text == "📣 Broadcast One Bot":

                await self.broadcast_one_prompt(
                    update
                )
                return

            if text == "🔐 Force Join":

                await self.show_force_join(
                    update
                )
                return

            if text == "⚙️ Bot Creation":

                await self.show_bot_creation_setting(
                    update
                )
                return

            if text == "▶️ Start Bot":

                await self.show_all_bots(
                    update
                )
                return

            if text == "⏹ Stop Bot":

                await self.show_all_bots(
                    update
                )
                return

            if text == "🗑 Delete Bot":

                await self.show_all_bots(
                    update
                )
                return

            if text == "🔙 User Panel":

                await update.message.reply_text(
                    "👤 **USER PANEL**",
                    reply_markup=main_keyboard(),
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

    # ============================================================
    # CALLBACKS
    # ============================================================

    async def handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):

        query = update.callback_query

        if not query:
            return

        try:

            await query.answer()

        except Exception:
            pass

        data = query.data or ""

        user_id = (
            query.from_user.id
        )

        # --------------------------------------------------------
        # LANGUAGE
        # --------------------------------------------------------

        if data.startswith(
            "main_lang_"
        ):

            lang = data.replace(
                "main_lang_",
                "",
            )

            if lang not in LANGUAGES:
                return

            await self.set_language(
                user_id,
                lang,
            )

            await query.edit_message_text(
                f"✅ Language changed to "
                f"**{LANGUAGES[lang]['name']}**",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # --------------------------------------------------------
        # ADMIN SECURITY
        # --------------------------------------------------------

        if data.startswith(
            "admin_"
        ) or data.startswith(
            "force_"
        ) or data.startswith(
            "creation_"
        ) or data.startswith(
            "broadcast_bot_"
        ):

            if not is_admin(user_id):

                await query.answer(
                    "⛔ Admin only.",
                    show_alert=True,
                )
                return

        # --------------------------------------------------------
        # ALL BOTS
        # --------------------------------------------------------

        if data == "admin_allbots":

            try:

                bots = await db.bots.find(
                    {}
                ).to_list(
                    length=None
                )

                if not bots:

                    await query.edit_message_text(
                        "🤖 No managed bots."
                    )
                    return

                buttons = []

                for bot in bots:

                    bot_id = bot.get(
                        "bot_id"
                    )

                    username = bot.get(
                        "username",
                        "N/A",
                    )

                    buttons.append(
                        [
                            InlineKeyboardButton(
                                f"📊 @{username}",
                                callback_data=(
                                    f"admin_botstats_{bot_id}"
                                ),
                            ),
                            InlineKeyboardButton(
                                "⚙️ Manage",
                                callback_data=(
                                    f"admin_manage_{bot_id}"
                                ),
                            ),
                        ]
                    )

                await query.edit_message_text(
                    "🤖 **ALL MANAGED BOTS**",
                    reply_markup=InlineKeyboardMarkup(
                        buttons
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )

            except Exception as e:

                logger.error(
                    f"All bots callback error: {e}",
                    exc_info=True,
                )

            return

        # --------------------------------------------------------
        # BOT STATS
        # --------------------------------------------------------

        if data.startswith(
            "admin_botstats_"
        ):

            bot_id = int(
                data.replace(
                    "admin_botstats_",
                    "",
                )
            )

            await self.show_bot_stats(
                query,
                bot_id,
            )
            return

        if data.startswith(
            "owner_stats_"
        ):

            bot_id = int(
                data.replace(
                    "owner_stats_",
                    "",
                )
            )

            bot = await db.get_bot(
                bot_id
            )

            if not bot:
                return

            if bot.get(
                "owner_id"
            ) != user_id:

                await query.answer(
                    "⛔ This is not your bot.",
                    show_alert=True,
                )
                return

            stats = await db.get_bot_stats(
                bot_id
            )

            await query.edit_message_text(
                "📊 **YOUR BOT STATS**\n\n"
                f"🤖 @{bot.get('username', 'N/A')}\n\n"
                f"👥 Users: `{stats['total_users']}`\n"
                f"📥 Downloads: `{stats['total_downloads']}`\n"
                f"🎬 Videos: `{stats['videos']}`\n"
                f"🎵 Audio: `{stats['audio']}`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # --------------------------------------------------------
        # MANAGE BOT
        # --------------------------------------------------------

        if data.startswith(
            "admin_manage_"
        ):

            bot_id = int(
                data.replace(
                    "admin_manage_",
                    "",
                )
            )

            await self.manage_bot_menu(
                query,
                bot_id,
            )
            return

        # --------------------------------------------------------
        # START
        # --------------------------------------------------------

        if data.startswith(
            "admin_start_"
        ):

            bot_id = int(
                data.replace(
                    "admin_start_",
                    "",
                )
            )

            await self.start_managed_bot(
                query,
                bot_id,
            )
            return

        # --------------------------------------------------------
        # STOP
        # --------------------------------------------------------

        if data.startswith(
            "admin_stop_"
        ):

            bot_id = int(
                data.replace(
                    "admin_stop_",
                    "",
                )
            )

            await self.stop_managed_bot(
                query,
                bot_id,
            )
            return

        # --------------------------------------------------------
        # DELETE CONFIRM
        # --------------------------------------------------------

        if data.startswith(
            "admin_confirmdelete_"
        ):

            bot_id = int(
                data.replace(
                    "admin_confirmdelete_",
                    "",
                )
            )

            await query.edit_message_text(
                "⚠️ **CONFIRM DELETE**\n\n"
                "Tani waxay ka saari doontaa bot-ka SaaS database-ka.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "✅ Yes, Delete",
                                callback_data=(
                                    f"admin_delete_{bot_id}"
                                ),
                            ),
                            InlineKeyboardButton(
                                "❌ Cancel",
                                callback_data=(
                                    f"admin_manage_{bot_id}"
                                ),
                            ),
                        ]
                    ]
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        if data.startswith(
            "admin_delete_"
        ):

            bot_id = int(
                data.replace(
                    "admin_delete_",
                    "",
                )
            )

            await self.delete_managed_bot(
                query,
                bot_id,
            )
            return

        # --------------------------------------------------------
        # FORCE JOIN
        # --------------------------------------------------------

        if data.startswith(
            "admin_force_"
        ):

            bot_id = int(
                data.replace(
                    "admin_force_",
                    "",
                )
            )

            await self.force_join_menu(
                query,
                bot_id,
            )
            return

        if data.startswith(
            "force_add_"
        ):

            bot_id = int(
                data.replace(
                    "force_add_",
                    "",
                )
            )

            await self.add_force_join_prompt(
                query,
                bot_id,
                context,
            )
            return

        if data.startswith(
            "force_remove_"
        ):

            bot_id = int(
                data.replace(
                    "force_remove_",
                    "",
                )
            )

            await self.remove_force_join_menu(
                query,
                bot_id,
            )
            return

        if data.startswith(
            "force_del_"
        ):

            parts = data.split(
                "_",
                3,
            )

            if len(parts) < 4:
                return

            bot_id = int(
                parts[2]
            )

            channel_name = parts[3]

            await self.delete_force_join(
                query,
                bot_id,
                channel_name,
            )
            return

        # --------------------------------------------------------
        # BROADCAST ONE BOT
        # --------------------------------------------------------

        if data.startswith(
            "broadcast_bot_"
        ):

            bot_id = int(
                data.replace(
                    "broadcast_bot_",
                    "",
                )
            )

            await self.one_bot_broadcast_prompt(
                query,
                bot_id,
                context,
            )
            return

        # --------------------------------------------------------
        # CREATION ENABLE/DISABLE
        # --------------------------------------------------------

        if data == "creation_enable":

            await db.set_system_setting(
                "bot_creation_enabled",
                True,
            )

            await query.edit_message_text(
                "🟢 **Bot Creation ENABLED**",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        if data == "creation_disable":

            await db.set_system_setting(
                "bot_creation_enabled",
                False,
            )

            await query.edit_message_text(
                "🔴 **Bot Creation DISABLED**",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

    # ============================================================
    # ERROR HANDLER
    # ============================================================

    async def error_handler(
        self,
        update: object,
        context: ContextTypes.DEFAULT_TYPE,
    ):

        logger.error(
            f"Main Bot Error: {context.error}",
            exc_info=True,
        )


main_bot = MainSaaSBot()
