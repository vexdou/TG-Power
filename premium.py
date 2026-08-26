import logging
from datetime import datetime, timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
)
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import Config
from database import db
from bot_manager import bot_manager

logger = logging.getLogger(__name__)


# ============================================================
# PREMIUM CONFIG
# ============================================================

PLANS = {
    "1m": {
        "name": "1 Month",
        "days": 30,
    },
    "3m": {
        "name": "3 Months",
        "days": 90,
    },
    "6m": {
        "name": "6 Months",
        "days": 180,
    },
    "1y": {
        "name": "1 Year",
        "days": 365,
    },
}

DEFAULT_PRICES = {
    "1m": 100,
    "3m": 300,
    "6m": 600,
    "1y": 1000,
}


# ============================================================
# TRANSLATIONS
# ============================================================

PREMIUM_I18N = {
    "en": {
        "no_bots":
            "⭐ PREMIUM\n\n"
            "You don't have a downloader bot yet.\n\n"
            "Create a bot first, then activate Premium "
            "with Telegram Stars.",

        "choose_bot":
            "⭐ PREMIUM\n\n"
            "Choose the downloader bot you want to upgrade.",

        "plans":
            "⭐ PREMIUM PLANS\n\n"
            "Premium includes:\n"
            "• 🚫 System ads disabled\n"
            "• ⚡ Priority downloads\n"
            "• 🎨 Premium captions\n"
            "• 🔘 Premium custom buttons\n"
            "• 🛠 Premium customization\n"
            "• 📊 Premium statistics\n"
            "• ♾️ Subscription extension\n\n"
            "Choose your plan:",

        "not_owner":
            "⛔ This bot does not belong to you.",

        "invalid_plan":
            "❌ Invalid Premium plan.",

        "payment_invalid":
            "❌ Invalid Premium payment.",

        "payment_failed":
            "❌ Premium payment could not be verified.",

        "premium_disabled":
            "❌ Premium purchases are currently disabled.",

        "invoice_error":
            "❌ Could not create the Premium invoice.",

        "activated":
            "🎉 PREMIUM ACTIVATED!\n\n"
            "🤖 Bot: @{name}\n"
            "⭐ Paid: {stars} Telegram Stars\n"
            "📅 Plan: {plan}\n"
            "⏳ Expires: {until}\n\n"
            "🚫 System ads: OFF\n"
            "⚡ Priority processing: ON\n"
            "🎨 Premium customization: ON",

        "already_processed":
            "✅ This Premium payment has already been processed.",

        "activation_error":
            "❌ Payment received, but Premium activation failed. "
            "Please contact the administrator.",

        "bot_not_found":
            "❌ Bot not found.",

        "premium_status":
            "⭐ PREMIUM STATUS\n\n"
            "🤖 Bot: @{name}\n"
            "📦 Plan: {plan}\n"
            "⏳ Expires: {until}\n"
            "📅 Remaining: {days} day(s)\n"
            "🚫 Ads: OFF\n"
            "⚡ Priority: ON",
    },

    "so": {
        "no_bots":
            "⭐ PREMIUM\n\n"
            "Weli ma lihid downloader bot.\n\n"
            "Marka hore samee bot, kadib Premium "
            "waxaad ku furan kartaa Telegram Stars.",

        "choose_bot":
            "⭐ PREMIUM\n\n"
            "Dooro downloader bot-ka aad rabto inaad Premium ka dhigto.",

        "plans":
            "⭐ QORSHEYAASHA PREMIUM\n\n"
            "Premium wuxuu leeyahay:\n"
            "• 🚫 Ads-ka system-ka waa dansan yihiin\n"
            "• ⚡ Download priority sare\n"
            "• 🎨 Caption gaar ah\n"
            "• 🔘 Buttons gaar ah\n"
            "• 🛠 Premium customization\n"
            "• 📊 Premium statistics\n"
            "• ♾️ Waqtiga Premium waa la kordhin karaa\n\n"
            "Dooro qorshaha:",

        "not_owner":
            "⛔ Bot-kan adiga ma lihid.",

        "invalid_plan":
            "❌ Qorshaha Premium ma saxna.",

        "payment_invalid":
            "❌ Lacag-bixinta Premium ma saxna.",

        "payment_failed":
            "❌ Lacag-bixinta Premium lama xaqiijin karin.",

        "premium_disabled":
            "❌ Premium purchase-ka hadda waa dansan yahay.",

        "invoice_error":
            "❌ Lama abuuri karin Premium invoice.",

        "activated":
            "🎉 PREMIUM WAA FURMAY!\n\n"
            "🤖 Bot: @{name}\n"
            "⭐ La bixiyey: {stars} Telegram Stars\n"
            "📅 Qorshe: {plan}\n"
            "⏳ Wuxuu dhacayaa: {until}\n\n"
            "🚫 Ads: DANSAN\n"
            "⚡ Priority: FURAN\n"
            "🎨 Premium customization: FURAN",

        "already_processed":
            "✅ Lacag-bixintan Premium hore ayaa loo farsameeyey.",

        "activation_error":
            "❌ Lacagta waa la helay, laakiin Premium lama furi karin. "
            "La xiriir maamulka.",

        "bot_not_found":
            "❌ Bot-ka lama helin.",

        "premium_status":
            "⭐ XAAALADDA PREMIUM\n\n"
            "🤖 Bot: @{name}\n"
            "📦 Qorshe: {plan}\n"
            "⏳ Dhacaya: {until}\n"
            "📅 Maalmaha haray: {days}\n"
            "🚫 Ads: DANSAN\n"
            "⚡ Priority: FURAN",
    },

    "ar": {
        "no_bots":
            "⭐ PREMIUM\n\n"
            "ليس لديك بوت تحميل بعد.\n\n"
            "أنشئ بوت أولاً ثم فعّل Premium باستخدام Telegram Stars.",

        "choose_bot":
            "⭐ PREMIUM\n\n"
            "اختر بوت التحميل الذي تريد ترقيته.",

        "plans":
            "⭐ خطط PREMIUM\n\n"
            "مزايا Premium:\n"
            "• 🚫 بدون إعلانات النظام\n"
            "• ⚡ أولوية التحميل\n"
            "• 🎨 نصوص مخصصة\n"
            "• 🔘 أزرار مخصصة\n"
            "• 🛠 تخصيص Premium\n"
            "• 📊 إحصائيات Premium\n"
            "• ♾️ تمديد الاشتراك\n\n"
            "اختر الخطة:",

        "not_owner":
            "⛔ هذا البوت ليس ملكك.",

        "invalid_plan":
            "❌ خطة Premium غير صالحة.",

        "payment_invalid":
            "❌ دفعة Premium غير صالحة.",

        "payment_failed":
            "❌ تعذر التحقق من دفعة Premium.",

        "premium_disabled":
            "❌ شراء Premium معطل حالياً.",

        "invoice_error":
            "❌ تعذر إنشاء فاتورة Premium.",

        "activated":
            "🎉 تم تفعيل PREMIUM!\n\n"
            "🤖 البوت: @{name}\n"
            "⭐ المدفوع: {stars} Telegram Stars\n"
            "📅 الخطة: {plan}\n"
            "⏳ الانتهاء: {until}\n\n"
            "🚫 الإعلانات: متوقفة\n"
            "⚡ أولوية التحميل: مفعلة\n"
            "🎨 التخصيص: مفعل",

        "already_processed":
            "✅ تمت معالجة دفعة Premium هذه مسبقاً.",

        "activation_error":
            "❌ تم استلام الدفع، لكن تعذر تفعيل Premium.",

        "bot_not_found":
            "❌ لم يتم العثور على البوت.",

        "premium_status":
            "⭐ حالة PREMIUM\n\n"
            "🤖 البوت: @{name}\n"
            "📦 الخطة: {plan}\n"
            "⏳ الانتهاء: {until}\n"
            "📅 الأيام المتبقية: {days}\n"
            "🚫 الإعلانات: متوقفة\n"
            "⚡ الأولوية: مفعلة",
    },

    "es": {
        "no_bots":
            "⭐ PREMIUM\n\n"
            "Todavía no tienes un bot descargador.\n\n"
            "Crea uno primero y después activa Premium con Telegram Stars.",

        "choose_bot":
            "⭐ PREMIUM\n\n"
            "Elige el bot descargador que quieres actualizar.",

        "plans":
            "⭐ PLANES PREMIUM\n\n"
            "Premium incluye:\n"
            "• 🚫 Sin anuncios del sistema\n"
            "• ⚡ Prioridad de descarga\n"
            "• 🎨 Captions personalizados\n"
            "• 🔘 Botones personalizados\n"
            "• 🛠 Personalización Premium\n"
            "• 📊 Estadísticas Premium\n"
            "• ♾️ Extensión de suscripción\n\n"
            "Elige un plan:",

        "not_owner":
            "⛔ Este bot no te pertenece.",

        "invalid_plan":
            "❌ Plan Premium no válido.",

        "payment_invalid":
            "❌ Pago Premium no válido.",

        "payment_failed":
            "❌ No se pudo verificar el pago Premium.",

        "premium_disabled":
            "❌ Las compras Premium están desactivadas.",

        "invoice_error":
            "❌ No se pudo crear la factura Premium.",

        "activated":
            "🎉 ¡PREMIUM ACTIVADO!\n\n"
            "🤖 Bot: @{name}\n"
            "⭐ Pagado: {stars} Telegram Stars\n"
            "📅 Plan: {plan}\n"
            "⏳ Expira: {until}\n\n"
            "🚫 Anuncios: OFF\n"
            "⚡ Prioridad: ON\n"
            "🎨 Personalización: ON",

        "already_processed":
            "✅ Este pago Premium ya fue procesado.",

        "activation_error":
            "❌ El pago fue recibido, pero no se pudo activar Premium.",

        "bot_not_found":
            "❌ Bot no encontrado.",

        "premium_status":
            "⭐ ESTADO PREMIUM\n\n"
            "🤖 Bot: @{name}\n"
            "📦 Plan: {plan}\n"
            "⏳ Expira: {until}\n"
            "📅 Días restantes: {days}\n"
            "🚫 Anuncios: OFF\n"
            "⚡ Prioridad: ON",
    },
}


# ============================================================
# HELPERS
# ============================================================

async def localized(
    user_id: int,
    key: str,
    **kwargs,
):
    try:
        lang = await db.get_main_user_language(
            user_id
        )
    except Exception:
        lang = "en"

    if lang not in PREMIUM_I18N:
        lang = "en"

    text = PREMIUM_I18N[lang].get(
        key,
        PREMIUM_I18N["en"].get(
            key,
            key,
        ),
    )

    try:
        return text.format(**kwargs)
    except Exception:
        return text


def _admins():
    ids = set()

    owner_id = getattr(
        Config,
        "OWNER_ID",
        0,
    )

    if owner_id:
        try:
            ids.add(int(owner_id))
        except Exception:
            pass

    for value in getattr(
        Config,
        "ADMIN_IDS",
        [],
    ):
        try:
            ids.add(int(value))
        except Exception:
            pass

    return ids


def _is_admin(user_id: int) -> bool:
    return int(user_id) in _admins()


def _plan_name(plan: str) -> str:
    return PLANS.get(
        plan,
        {}
    ).get(
        "name",
        plan,
    )


def _safe_until(value):
    if not value:
        return "N/A"

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(
            timezone.utc
        ).strftime(
            "%Y-%m-%d %H:%M UTC"
        )

    return str(value)


def owner_plans(
    bot_id: int,
    prices: dict,
):
    prices = prices or {}

    p1m = int(
        prices.get(
            "1m",
            DEFAULT_PRICES["1m"],
        )
    )

    p3m = int(
        prices.get(
            "3m",
            DEFAULT_PRICES["3m"],
        )
    )

    p6m = int(
        prices.get(
            "6m",
            DEFAULT_PRICES["6m"],
        )
    )

    p1y = int(
        prices.get(
            "1y",
            DEFAULT_PRICES["1y"],
        )
    )

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"1 Month — {p1m} ⭐",
                    callback_data=f"prem:buy:{bot_id}:1m",
                ),
                InlineKeyboardButton(
                    f"3 Months — {p3m} ⭐",
                    callback_data=f"prem:buy:{bot_id}:3m",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"6 Months — {p6m} ⭐",
                    callback_data=f"prem:buy:{bot_id}:6m",
                ),
                InlineKeyboardButton(
                    f"1 Year — {p1y} ⭐",
                    callback_data=f"prem:buy:{bot_id}:1y",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data=f"prem:bot:{bot_id}",
                ),
            ],
        ]
    )


def bot_list_keyboard(bots):
    rows = []

    for bot in bots:
        bid = int(bot["bot_id"])
        username = (
            bot.get("username")
            or str(bid)
        )

        rows.append(
            [
                InlineKeyboardButton(
                    f"⭐ @{username}",
                    callback_data=f"prem:bot:{bid}",
                )
            ]
        )

    return InlineKeyboardMarkup(rows)


# ============================================================
# /premium
# ============================================================

async def premium_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_user or not update.message:
        return

    uid = update.effective_user.id

    if not await db.is_premium_enabled():
        await update.message.reply_text(
            await localized(
                uid,
                "premium_disabled",
            )
        )
        return

    await db.expire_premium_bots()

    bots = await db.get_user_bots(uid)

    if not bots:
        await update.message.reply_text(
            await localized(
                uid,
                "no_bots",
            )
        )
        return

    await update.message.reply_text(
        await localized(
            uid,
            "choose_bot",
        ),
        reply_markup=bot_list_keyboard(
            bots
        ),
    )


# ============================================================
# PREMIUM STATUS
# ============================================================

async def premium_status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_user or not update.message:
        return

    uid = update.effective_user.id

    bots = await db.get_user_bots(uid)

    if not bots:
        await update.message.reply_text(
            await localized(
                uid,
                "no_bots",
            )
        )
        return

    await db.expire_premium_bots()

    rows = []

    for bot in bots:
        bid = int(bot["bot_id"])
        name = (
            bot.get("username")
            or str(bid)
        )

        premium = await db.get_bot_premium(
            bid
        )

        if premium.get("is_active"):
            rows.append(
                [
                    InlineKeyboardButton(
                        f"⭐ @{name}",
                        callback_data=f"prem:status:{bid}",
                    )
                ]
            )

    if not rows:
        await update.message.reply_text(
            "⭐ PREMIUM STATUS\n\n"
            "No active Premium subscription."
        )
        return

    await update.message.reply_text(
        "⭐ PREMIUM STATUS\n\n"
        "Choose a bot:",
        reply_markup=InlineKeyboardMarkup(
            rows
        ),
    )


# ============================================================
# PREMIUM CALLBACK
# ============================================================

async def premium_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    q = update.callback_query

    if not q:
        return False

    data = q.data or ""

    if not data.startswith("prem:"):
        return False

    parts = data.split(":")

    if len(parts) < 3:
        await q.answer()
        return True

    action = parts[1]

    try:
        bot_id = int(parts[2])
    except Exception:
        await q.answer(
            "❌ Invalid bot.",
            show_alert=True,
        )
        return True

    uid = q.from_user.id

    bot = await db.get_bot(bot_id)

    if not bot:
        await q.answer(
            await localized(
                uid,
                "bot_not_found",
            ),
            show_alert=True,
        )
        return True

    owner_id = bot.get("owner_id")

    if owner_id is None or int(owner_id) != uid:
        await q.answer(
            await localized(
                uid,
                "not_owner",
            ),
            show_alert=True,
        )
        return True

    # --------------------------------------------------------
    # SELECT BOT
    # --------------------------------------------------------

    if action == "bot":
        await q.answer()

        prices = await db.get_premium_prices()

        premium = await db.get_bot_premium(
            bot_id
        )

        username = (
            bot.get("username")
            or str(bot_id)
        )

        if premium.get("is_active"):
            remaining = (
                await db.get_premium_remaining_days(
                    bot_id
                )
            )

            until = _safe_until(
                premium.get("until")
            )

            text = await localized(
                uid,
                "premium_status",
                name=username,
                plan=_plan_name(
                    premium.get(
                        "plan",
                        "",
                    )
                ),
                until=until,
                days=remaining,
            )

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "♻️ Extend Premium",
                            callback_data=f"prem:plans:{bot_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="prem:back",
                        )
                    ],
                ]
            )

            await q.edit_message_text(
                text,
                reply_markup=keyboard,
            )

        else:
            await q.edit_message_text(
                await localized(
                    uid,
                    "plans",
                ),
                reply_markup=owner_plans(
                    bot_id,
                    prices,
                ),
            )

        return True

    # --------------------------------------------------------
    # SHOW PLANS
    # --------------------------------------------------------

    if action == "plans":
        await q.answer()

        prices = await db.get_premium_prices()

        await q.edit_message_text(
            await localized(
                uid,
                "plans",
            ),
            reply_markup=owner_plans(
                bot_id,
                prices,
            ),
        )

        return True

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    if action == "status":
        await q.answer()

        premium = await db.get_bot_premium(
            bot_id
        )

        if not premium.get("is_active"):
            await q.edit_message_text(
                "⭐ PREMIUM\n\n"
                "❌ Premium is not active.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⭐ Buy Premium",
                                callback_data=f"prem:plans:{bot_id}",
                            )
                        ]
                    ]
                ),
            )
            return True

        name = (
            bot.get("username")
            or str(bot_id)
        )

        await q.edit_message_text(
            await localized(
                uid,
                "premium_status",
                name=name,
                plan=_plan_name(
                    premium.get(
                        "plan",
                        "",
                    )
                ),
                until=_safe_until(
                    premium.get("until")
                ),
                days=await db.get_premium_remaining_days(
                    bot_id
                ),
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "♻️ Extend",
                            callback_data=f"prem:plans:{bot_id}",
                        )
                    ]
                ]
            ),
        )

        return True

    # --------------------------------------------------------
    # BACK
    # --------------------------------------------------------

    if action == "back":
        bots = await db.get_user_bots(uid)

        if not bots:
            await q.edit_message_text(
                await localized(
                    uid,
                    "no_bots",
                )
            )
            return True

        await q.answer()

        await q.edit_message_text(
            await localized(
                uid,
                "choose_bot",
            ),
            reply_markup=bot_list_keyboard(
                bots
            ),
        )

        return True

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    if action == "buy":
        if len(parts) < 4:
            await q.answer(
                await localized(
                    uid,
                    "invalid_plan",
                ),
                show_alert=True,
            )
            return True

        plan = parts[3]

        if plan not in PLANS:
            await q.answer(
                await localized(
                    uid,
                    "invalid_plan",
                ),
                show_alert=True,
            )
            return True

        if not await db.is_premium_enabled():
            await q.answer(
                await localized(
                    uid,
                    "premium_disabled",
                ),
                show_alert=True,
            )
            return True

        prices = await db.get_premium_prices()

        try:
            stars = int(
                prices.get(
                    plan,
                    DEFAULT_PRICES[plan],
                )
            )
        except Exception:
            stars = DEFAULT_PRICES[plan]

        if stars <= 0:
            await q.answer(
                await localized(
                    uid,
                    "invalid_plan",
                ),
                show_alert=True,
            )
            return True

        title = PLANS[plan]["name"]

        payload = (
            f"tgpower-premium:"
            f"{bot_id}:"
            f"{plan}:"
            f"{uid}"
        )

        await q.answer()

        try:
            await context.bot.send_invoice(
                chat_id=uid,
                title=f"TG-Power Premium — {title}",
                description=(
                    f"Premium subscription for "
                    f"@{bot.get('username') or bot_id}. "
                    f"System ads disabled, priority downloads "
                    f"and premium customization."
                ),
                payload=payload,
                currency="XTR",
                prices=[
                    LabeledPrice(
                        label=f"Premium {title}",
                        amount=stars,
                    )
                ],
            )

        except Exception:
            logger.exception(
                "Premium invoice creation failed"
            )

            await context.bot.send_message(
                chat_id=uid,
                text=await localized(
                    uid,
                    "invoice_error",
                ),
            )

        return True

    return True


# ============================================================
# PRECHECKOUT
# ============================================================

async def precheckout(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    q = update.pre_checkout_query

    if not q:
        return

    payload = q.invoice_payload or ""

    if not payload.startswith(
        "tgpower-premium:"
    ):
        await q.answer(
            ok=False,
            error_message=(
                "Invalid Premium payment."
            ),
        )
        return

    try:
        parts = payload.split(":")

        if len(parts) != 4:
            raise ValueError(
                "Invalid Premium payload"
            )

        _, bot_id_s, plan, owner_id_s = parts

        bot_id = int(bot_id_s)
        owner_id = int(owner_id_s)

        if plan not in PLANS:
            raise ValueError(
                "Invalid plan"
            )

        bot = await db.get_bot(
            bot_id
        )

        if not bot:
            raise ValueError(
                "Bot not found"
            )

        bot_owner = bot.get(
            "owner_id"
        )

        if bot_owner is None:
            raise ValueError(
                "Bot owner missing"
            )

        if int(bot_owner) != int(
            q.from_user.id
        ):
            raise ValueError(
                "Wrong owner"
            )

        if int(owner_id) != int(
            q.from_user.id
        ):
            raise ValueError(
                "Wrong payer"
            )

        prices = await db.get_premium_prices()

        expected_price = int(
            prices.get(
                plan,
                DEFAULT_PRICES[plan],
            )
        )

        if int(q.total_amount) != expected_price:
            raise ValueError(
                "Wrong payment amount"
            )

        if not await db.is_premium_enabled():
            raise ValueError(
                "Premium disabled"
            )

        await q.answer(
            ok=True
        )

    except Exception as exc:
        logger.warning(
            "Premium precheckout rejected: %s",
            exc,
        )

        await q.answer(
            ok=False,
            error_message=(
                "Premium payment could not be verified."
            ),
        )


# ============================================================
# SUCCESSFUL PAYMENT
# ============================================================

async def successful_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if (
        not update.message
        or not update.effective_user
    ):
        return

    payment = (
        update.message.successful_payment
    )

    if not payment:
        return

    payload = (
        payment.invoice_payload
        or ""
    )

    if not payload.startswith(
        "tgpower-premium:"
    ):
        return

    uid = update.effective_user.id

    try:
        parts = payload.split(":")

        if len(parts) != 4:
            raise ValueError(
                "Invalid payment payload"
            )

        _, bot_id_s, plan, owner_id_s = parts

        bot_id = int(bot_id_s)
        owner_id = int(owner_id_s)

        if plan not in PLANS:
            raise ValueError(
                "Invalid plan"
            )

        if owner_id != uid:
            raise ValueError(
                "Payment owner mismatch"
            )

        bot = await db.get_bot(
            bot_id
        )

        if not bot:
            await update.message.reply_text(
                await localized(
                    uid,
                    "bot_not_found",
                )
            )
            return

        if int(
            bot.get("owner_id", 0)
        ) != uid:
            raise ValueError(
                "Bot ownership mismatch"
            )

        charge_id = (
            getattr(
                payment,
                "telegram_payment_charge_id",
                "",
            )
            or ""
        )

        provider_charge_id = (
            getattr(
                payment,
                "provider_payment_charge_id",
                "",
            )
            or ""
        )

        # ----------------------------------------------------
        # IDEMPOTENCY
        # ----------------------------------------------------

        if charge_id and await db.payment_exists(
            charge_id
        ):
            await update.message.reply_text(
                await localized(
                    uid,
                    "already_processed",
                )
            )
            return

        prices = await db.get_premium_prices()

        stars = int(
            prices.get(
                plan,
                DEFAULT_PRICES[plan],
            )
        )

        actual_stars = int(
            payment.total_amount
        )

        if actual_stars != stars:
            logger.error(
                "Premium amount mismatch. "
                "Expected=%s Actual=%s",
                stars,
                actual_stars,
            )

            raise ValueError(
                "Payment amount mismatch"
            )

        days = PLANS[plan]["days"]

        # ----------------------------------------------------
        # SAVE PAYMENT FIRST
        # ----------------------------------------------------

        saved = await db.save_premium_payment(
            user_id=uid,
            bot_id=bot_id,
            plan=plan,
            stars=stars,
            telegram_payment_charge_id=charge_id,
            provider_payment_charge_id=provider_charge_id,
            invoice_payload=payload,
        )

        if not saved:
            await update.message.reply_text(
                await localized(
                    uid,
                    "already_processed",
                )
            )
            return

        # ----------------------------------------------------
        # ACTIVATE / EXTEND PREMIUM
        # ----------------------------------------------------

        until = await db.activate_bot_premium(
            bot_id=bot_id,
            owner_id=uid,
            plan=plan,
            days=days,
            stars=stars,
            payment_id=charge_id,
            source="telegram_stars",
        )

        if not until:
            raise RuntimeError(
                "Premium activation returned None"
            )

        # ----------------------------------------------------
        # RESTART BOT
        # ----------------------------------------------------

        try:
            status = bot.get(
                "status"
            )

            if status in {
                "active",
                "starting",
                "failed",
            }:
                token = bot.get(
                    "token"
                )

                if token:
                    try:
                        await bot_manager.stop_bot_instance(
                            bot_id
                        )
                    except Exception:
                        logger.warning(
                            "Could not stop bot %s",
                            bot_id,
                            exc_info=True,
                        )

                    try:
                        await bot_manager.start_bot_instance(
                            bot_id,
                            token,
                        )
                    except Exception:
                        logger.warning(
                            "Could not restart bot %s",
                            bot_id,
                            exc_info=True,
                        )

        except Exception:
            logger.exception(
                "Premium bot restart error"
            )

        # ----------------------------------------------------
        # SUCCESS MESSAGE
        # ----------------------------------------------------

        username = (
            bot.get("username")
            or str(bot_id)
        )

        await update.message.reply_text(
            await localized(
                uid,
                "activated",
                name=username,
                stars=stars,
                plan=PLANS[plan]["name"],
                until=_safe_until(
                    until
                ),
            )
        )

    except Exception as exc:
        logger.exception(
            "Premium successful payment failed: %s",
            exc,
        )

        await update.message.reply_text(
            await localized(
                uid,
                "activation_error",
            )
        )


# ============================================================
# ADMIN PREMIUM CENTER
# ============================================================

async def admin_premium_center(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if (
        not update.message
        or not update.effective_user
        or not _is_admin(
            update.effective_user.id
        )
    ):
        return

    await db.expire_premium_bots()

    prices = await db.get_premium_prices()
    stats = await db.get_premium_stats()

    await update.message.reply_text(
        "⭐ PREMIUM ADMIN CENTER\n\n"
        f"💰 1 Month: {prices['1m']} ⭐\n"
        f"💰 3 Months: {prices['3m']} ⭐\n"
        f"💰 6 Months: {prices['6m']} ⭐\n"
        f"💰 1 Year: {prices['1y']} ⭐\n\n"
        f"⭐ Active Bots: {stats['active_bots']}\n"
        f"💳 Payments: {stats['payments']}\n"
        f"⭐ Total Stars: {stats['stars']}\n\n"
        "Premium management:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "💰 Prices",
                        callback_data="padmin:prices",
                    ),
                    InlineKeyboardButton(
                        "⭐ Premium Bots",
                        callback_data="padmin:list",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🎁 Grant Premium",
                        callback_data="padmin:grant",
                    ),
                    InlineKeyboardButton(
                        "📊 Statistics",
                        callback_data="padmin:stats",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "✏️ Caption",
                        callback_data="padmin:caption",
                    ),
                    InlineKeyboardButton(
                        "🔘 Buttons",
                        callback_data="padmin:buttons",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "📢 Ads",
                        callback_data="padmin:ads",
                    ),
                    InlineKeyboardButton(
                        "⚙️ Settings",
                        callback_data="padmin:settings",
                    ),
                ],
            ]
        ),
    )


# ============================================================
# ADMIN CALLBACK
# ============================================================

async def admin_premium_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    q = update.callback_query

    if not q:
        return False

    data_raw = q.data or ""

    if not data_raw.startswith(
        "padmin:"
    ):
        return False

    if not _is_admin(
        q.from_user.id
    ):
        await q.answer(
            "⛔ Admin only.",
            show_alert=True,
        )
        return True

    data = data_raw.split(":")

    action = (
        data[1]
        if len(data) > 1
        else ""
    )

    await q.answer()

    # --------------------------------------------------------
    # PRICES
    # --------------------------------------------------------

    if action == "prices":
        prices = await db.get_premium_prices()

        await q.edit_message_text(
            "💰 PREMIUM PRICES\n\n"
            f"1 Month = {prices['1m']} ⭐\n"
            f"3 Months = {prices['3m']} ⭐\n"
            f"6 Months = {prices['6m']} ⭐\n"
            f"1 Year = {prices['1y']} ⭐\n\n"
            "Commands:\n"
            "/setpremium 1m 100\n"
            "/setpremium 3m 300\n"
            "/setpremium 6m 600\n"
            "/setpremium 1y 1000",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="padmin:home",
                        )
                    ]
                ]
            ),
        )

        return True

    # --------------------------------------------------------
    # PREMIUM BOT LIST
    # --------------------------------------------------------

    if action == "list":
        await db.expire_premium_bots()

        bots = await db.get_premium_bots()

        if not bots:
            await q.edit_message_text(
                "⭐ PREMIUM BOTS\n\n"
                "No active Premium bots.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🔙 Back",
                                callback_data="padmin:home",
                            )
                        ]
                    ]
                ),
            )
            return True

        rows = []
        text = "⭐ PREMIUM BOTS\n\n"

        for bot in bots[:50]:
            bid = int(
                bot["bot_id"]
            )

            name = (
                bot.get("username")
                or str(bid)
            )

            premium = (
                bot.get("premium")
                or {}
            )

            until = _safe_until(
                premium.get(
                    "until"
                )
            )

            text += (
                f"⭐ @{name}\n"
                f"🆔 {bid}\n"
                f"📅 {until}\n\n"
            )

            rows.append(
                [
                    InlineKeyboardButton(
                        f"⚙️ @{name}",
                        callback_data=f"padmin:manage:{bid}",
                    )
                ]
            )

        rows.append(
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="padmin:home",
                )
            ]
        )

        await q.edit_message_text(
            text[:4000],
            reply_markup=InlineKeyboardMarkup(
                rows
            ),
        )

        return True

    # --------------------------------------------------------
    # MANAGE BOT
    # --------------------------------------------------------

    if action == "manage" and len(data) >= 3:
        try:
            bid = int(data[2])
        except Exception:
            await q.edit_message_text(
                "❌ Invalid bot ID."
            )
            return True

        bot = await db.get_bot(
            bid
        )

        if not bot:
            await q.edit_message_text(
                "❌ Bot not found."
            )
            return True

        settings = (
            await db.get_bot_premium_settings(
                bid
            )
        )

        premium = (
            await db.get_bot_premium(
                bid
            )
        )

        name = (
            bot.get("username")
            or str(bid)
        )

        buttons = settings.get(
            "buttons",
            [],
        )

        caption = settings.get(
            "caption",
            "",
        )

        ad_text = settings.get(
            "ad_text",
            "",
        )

        await q.edit_message_text(
            f"⭐ PREMIUM BOT\n\n"
            f"🤖 @{name}\n"
            f"🆔 {bid}\n\n"
            f"📦 Plan: {_plan_name(premium.get('plan', ''))}\n"
            f"⏳ Expires: {_safe_until(premium.get('until'))}\n"
            f"🔘 Buttons: {len(buttons)}/10\n"
            f"✏️ Caption: {'ON' if caption else 'DEFAULT'}\n"
            f"📢 Custom ad: {'ON' if ad_text else 'OFF'}\n\n"
            f"/premiumgrant {bid} DAYS\n"
            f"/premiumcaption {bid} TEXT\n"
            f"/premiumbutton {bid} Label|URL\n"
            f"/premiumad {bid} TEXT\n"
            f"/premiumclearbuttons {bid}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Premium Bots",
                            callback_data="padmin:list",
                        )
                    ]
                ]
            ),
        )

        return True

    # --------------------------------------------------------
    # STATS
    # --------------------------------------------------------

    if action == "stats":
        await db.expire_premium_bots()

        stats = await db.get_premium_stats()

        payments = (
            await db.get_all_premium_payments(
                limit=10
            )
        )

        plan_counts = {
            "1m": 0,
            "3m": 0,
            "6m": 0,
            "1y": 0,
        }

        for payment in payments:
            plan = payment.get(
                "plan"
            )

            if plan in plan_counts:
                plan_counts[plan] += 1

        await q.edit_message_text(
            "📊 PREMIUM STATISTICS\n\n"
            f"⭐ Active bots: {stats['active_bots']}\n"
            f"💳 Payments: {stats['payments']}\n"
            f"⭐ Stars recorded: {stats['stars']}\n\n"
            "Recent plan distribution:\n"
            f"• 1 Month: {plan_counts['1m']}\n"
            f"• 3 Months: {plan_counts['3m']}\n"
            f"• 6 Months: {plan_counts['6m']}\n"
            f"• 1 Year: {plan_counts['1y']}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="padmin:home",
                        )
                    ]
                ]
            ),
        )

        return True

    # --------------------------------------------------------
    # SETTINGS
    # --------------------------------------------------------

    if action == "settings":
        cfg = await db.get_premium_config()

        await q.edit_message_text(
            "⚙️ PREMIUM SETTINGS\n\n"
            f"Premium enabled: "
            f"{'YES' if cfg.get('enabled', True) else 'NO'}\n"
            f"Ads disabled: "
            f"{'YES' if cfg.get('ads_disabled', True) else 'NO'}\n"
            f"Priority: "
            f"{'YES' if cfg.get('priority_enabled', True) else 'NO'}\n"
            f"Custom caption: "
            f"{'YES' if cfg.get('custom_caption_enabled', True) else 'NO'}\n"
            f"Custom buttons: "
            f"{'YES' if cfg.get('custom_buttons_enabled', True) else 'NO'}\n"
            f"Max buttons: "
            f"{cfg.get('max_custom_buttons', 10)}\n\n"
            "Commands:\n"
            "/premiumenable\n"
            "/premiumdisable",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="padmin:home",
                        )
                    ]
                ]
            ),
        )

        return True

    # --------------------------------------------------------
    # COMMAND HELP
    # --------------------------------------------------------

    if action in {
        "grant",
        "caption",
        "buttons",
        "ads",
    }:
        await q.edit_message_text(
            "🛠 PREMIUM ADMIN TOOLS\n\n"
            "🎁 Grant:\n"
            "/premiumgrant BOT_ID DAYS\n\n"
            "✏️ Caption:\n"
            "/premiumcaption BOT_ID TEXT\n\n"
            "🔘 Button:\n"
            "/premiumbutton BOT_ID Label|URL\n\n"
            "📢 Custom ad:\n"
            "/premiumad BOT_ID TEXT\n\n"
            "🗑 Clear buttons:\n"
            "/premiumclearbuttons BOT_ID\n\n"
            "🗑 Clear settings:\n"
            "/premiumclear BOT_ID",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="padmin:home",
                        )
                    ]
                ]
            ),
        )

        return True

    # --------------------------------------------------------
    # HOME
    # --------------------------------------------------------

    if action == "home":
        prices = await db.get_premium_prices()
        stats = await db.get_premium_stats()

        await q.edit_message_text(
            "⭐ PREMIUM ADMIN CENTER\n\n"
            f"1 Month: {prices['1m']} ⭐\n"
            f"3 Months: {prices['3m']} ⭐\n"
            f"6 Months: {prices['6m']} ⭐\n"
            f"1 Year: {prices['1y']} ⭐\n\n"
            f"Active bots: {stats['active_bots']}\n"
            f"Payments: {stats['payments']}\n"
            f"Stars: {stats['stars']}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "💰 Prices",
                            callback_data="padmin:prices",
                        ),
                        InlineKeyboardButton(
                            "⭐ Bots",
                            callback_data="padmin:list",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "📊 Stats",
                            callback_data="padmin:stats",
                        ),
                        InlineKeyboardButton(
                            "⚙️ Settings",
                            callback_data="padmin:settings",
                        ),
                    ],
                ]
            ),
        )

        return True

    return True


# ============================================================
# ADMIN TEXT COMMANDS
# ============================================================

async def admin_premium_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if (
        not update.message
        or not update.effective_user
        or not _is_admin(
            update.effective_user.id
        )
    ):
        return

    text = (
        update.message.text
        or ""
    ).strip()

    if not text:
        return

    parts = text.split(
        maxsplit=2
    )

    command = (
        parts[0]
        .split("@")[0]
        .lower()
    )

    try:

        # ----------------------------------------------------
        # SET PRICE
        # ----------------------------------------------------

        if command == "/setpremium":
            if len(parts) < 3:
                await update.message.reply_text(
                    "Usage:\n"
                    "/setpremium 1m 100"
                )
                return

            plan = parts[1].lower()

            if plan not in PLANS:
                await update.message.reply_text(
                    "❌ Valid plans: 1m, 3m, 6m, 1y"
                )
                return

            stars = int(
                parts[2]
            )

            if stars <= 0:
                raise ValueError(
                    "Price must be greater than 0."
                )

            prices = (
                await db.set_premium_prices(
                    {
                        plan: stars
                    }
                )
            )

            await update.message.reply_text(
                "✅ PREMIUM PRICE UPDATED\n\n"
                f"{plan} = {prices[plan]} ⭐"
            )

            return

        # ----------------------------------------------------
        # GRANT
        # ----------------------------------------------------

        if command == "/premiumgrant":
            if len(parts) < 3:
                await update.message.reply_text(
                    "Usage:\n"
                    "/premiumgrant BOT_ID DAYS"
                )
                return

            bot_id = int(
                parts[1]
            )

            days = int(
                parts[2]
            )

            if days <= 0:
                raise ValueError(
                    "Days must be greater than 0."
                )

            until = (
                await db.grant_bot_premium(
                    bot_id,
                    days,
                    update.effective_user.id,
                )
            )

            if not until:
                await update.message.reply_text(
                    "❌ Bot not found."
                )
                return

            await update.message.reply_text(
                "🎁 PREMIUM GRANTED\n\n"
                f"🤖 Bot: {bot_id}\n"
                f"📅 Added: {days} day(s)\n"
                f"⏳ Expires: {_safe_until(until)}"
            )

            return

        # ----------------------------------------------------
        # CAPTION
        # ----------------------------------------------------

        if command == "/premiumcaption":
            if len(parts) < 3:
                await update.message.reply_text(
                    "Usage:\n"
                    "/premiumcaption BOT_ID TEXT"
                )
                return

            bot_id = int(
                parts[1]
            )

            caption = parts[2].strip()

            bot = await db.get_bot(
                bot_id
            )

            if not bot:
                await update.message.reply_text(
                    "❌ Bot not found."
                )
                return

            if not await db.is_bot_premium(
                bot_id
            ):
                await update.message.reply_text(
                    "❌ This bot does not have active Premium."
                )
                return

            await db.set_bot_premium_setting(
                bot_id,
                "caption",
                caption[:4000],
            )

            await update.message.reply_text(
                "✅ Premium caption saved."
            )

            return

        # ----------------------------------------------------
        # BUTTON
        # ----------------------------------------------------

        if command == "/premiumbutton":
            if len(parts) < 3:
                await update.message.reply_text(
                    "Usage:\n"
                    "/premiumbutton BOT_ID Label|URL"
                )
                return

            bot_id = int(
                parts[1]
            )

            raw = parts[2].strip()

            if "|" not in raw:
                await update.message.reply_text(
                    "❌ Format:\n"
                    "Label|https://example.com"
                )
                return

            label, url = raw.split(
                "|",
                1,
            )

            label = label.strip()
            url = url.strip()

            if not label:
                raise ValueError(
                    "Button label is empty."
                )

            if not (
                url.startswith(
                    "https://"
                )
                or url.startswith(
                    "http://"
                )
                or url.startswith(
                    "tg://"
                )
            ):
                raise ValueError(
                    "URL must start with http://, https:// or tg://"
                )

            bot = await db.get_bot(
                bot_id
            )

            if not bot:
                await update.message.reply_text(
                    "❌ Bot not found."
                )
                return

            if not await db.is_bot_premium(
                bot_id
            ):
                await update.message.reply_text(
                    "❌ This bot does not have active Premium."
                )
                return

            settings = (
                await db.get_bot_premium_settings(
                    bot_id
                )
            )

            buttons = list(
                settings.get(
                    "buttons",
                    [],
                )
            )

            cfg = (
                await db.get_premium_config()
            )

            max_buttons = int(
                cfg.get(
                    "max_custom_buttons",
                    10,
                )
            )

            if len(buttons) >= max_buttons:
                await update.message.reply_text(
                    f"❌ Maximum {max_buttons} buttons."
                )
                return

            buttons.append(
                {
                    "label": label[:64],
                    "url": url[:512],
                }
            )

            await db.set_bot_premium_setting(
                bot_id,
                "buttons",
                buttons,
            )

            await update.message.reply_text(
                f"✅ Premium button saved.\n"
                f"Buttons: {len(buttons)}/{max_buttons}"
            )

            return

        # ----------------------------------------------------
        # CUSTOM AD
        # ----------------------------------------------------

        if command == "/premiumad":
            if len(parts) < 3:
                await update.message.reply_text(
                    "Usage:\n"
                    "/premiumad BOT_ID TEXT"
                )
                return

            bot_id = int(
                parts[1]
            )

            ad_text = parts[2].strip()

            bot = await db.get_bot(
                bot_id
            )

            if not bot:
                await update.message.reply_text(
                    "❌ Bot not found."
                )
                return

            await db.set_bot_premium_setting(
                bot_id,
                "ad_text",
                ad_text[:2000],
            )

            await db.set_bot_premium_setting(
                bot_id,
                "ad_enabled",
                False,
            )

            await update.message.reply_text(
                "✅ Custom ad saved.\n"
                "ℹ️ System ads remain disabled while Premium is active."
            )

            return

        # ----------------------------------------------------
        # CLEAR BUTTONS
        # ----------------------------------------------------

        if command == "/premiumclearbuttons":
            if len(parts) < 2:
                await update.message.reply_text(
                    "Usage:\n"
                    "/premiumclearbuttons BOT_ID"
                )
                return

            bot_id = int(
                parts[1]
            )

            bot = await db.get_bot(
                bot_id
            )

            if not bot:
                await update.message.reply_text(
                    "❌ Bot not found."
                )
                return

            await db.set_bot_premium_setting(
                bot_id,
                "buttons",
                [],
            )

            await update.message.reply_text(
                "✅ All Premium buttons removed."
            )

            return

        # ----------------------------------------------------
        # CLEAR SETTINGS
        # ----------------------------------------------------

        if command == "/premiumclear":
            if len(parts) < 2:
                await update.message.reply_text(
                    "Usage:\n"
                    "/premiumclear BOT_ID"
                )
                return

            bot_id = int(
                parts[1]
            )

            bot = await db.get_bot(
                bot_id
            )

            if not bot:
                await update.message.reply_text(
                    "❌ Bot not found."
                )
                return

            await db.clear_bot_premium_settings(
                bot_id
            )

            await update.message.reply_text(
                "✅ Premium customization cleared."
            )

            return

        # ----------------------------------------------------
        # ENABLE PREMIUM
        # ----------------------------------------------------

        if command == "/premiumenable":
            await db.set_premium_config(
                "enabled",
                True,
            )

            await update.message.reply_text(
                "✅ Premium purchases enabled."
            )

            return

        # ----------------------------------------------------
        # DISABLE PREMIUM
        # ----------------------------------------------------

        if command == "/premiumdisable":
            await db.set_premium_config(
                "enabled",
                False,
            )

            await update.message.reply_text(
                "🔴 Premium purchases disabled."
            )

            return

        # ----------------------------------------------------
        # EXPIRE NOW
        # ----------------------------------------------------

        if command == "/premiumexpire":
            count = (
                await db.expire_premium_bots()
            )

            await update.message.reply_text(
                f"✅ Expiration check completed.\n"
                f"Expired: {count}"
            )

            return

    except Exception as exc:
        logger.exception(
            "Premium admin command failed"
        )

        await update.message.reply_text(
            f"❌ {exc}"
        )


# ============================================================
# PREMIUM EXPIRATION JOB
# ============================================================

async def premium_expiration_job(
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        count = (
            await db.expire_premium_bots()
        )

        if count:
            logger.info(
                "⭐ Expired %s Premium bot(s)",
                count,
            )

    except Exception:
        logger.exception(
            "Premium expiration job failed"
        )


# ============================================================
# REGISTER HANDLERS
# ============================================================

def register_premium_handlers(app):

    app.add_handler(
        CommandHandler(
            "premium",
            premium_command,
        ),
        group=0,
    )

    app.add_handler(
        CommandHandler(
            "premiumstatus",
            premium_status_command,
        ),
        group=0,
    )

    app.add_handler(
        CommandHandler(
            "premiumadmin",
            admin_premium_center,
        ),
        group=0,
    )

    app.add_handler(
        PreCheckoutQueryHandler(
            precheckout,
        ),
        group=0,
    )

    app.add_handler(
        MessageHandler(
            filters.SUCCESSFUL_PAYMENT,
            successful_payment,
        ),
        group=0,
    )

    app.add_handler(
        MessageHandler(
            filters.COMMAND
            & filters.Regex(
                r"^/(setpremium|premiumgrant|premiumcaption|premiumbutton|premiumad|premiumclearbuttons|premiumclear|premiumenable|premiumdisable|premiumexpire)(?:@\w+)?(?:\s|$)"
            ),
            admin_premium_text,
        ),
        group=0,
    )

    app.add_handler(
        CallbackQueryHandler(
            premium_callback,
            pattern=r"^prem:",
        ),
        group=0,
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_premium_callback,
            pattern=r"^padmin:",
        ),
        group=0,
    )

    # Automatic Premium expiration.
    if getattr(
        app,
        "job_queue",
        None,
    ):
        app.job_queue.run_repeating(
            premium_expiration_job,
            interval=3600,
            first=30,
            name="premium_expiration",
)
