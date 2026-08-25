import logging
from datetime import datetime, timezone, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, PreCheckoutQueryHandler, MessageHandler, ContextTypes, filters

from config import Config
from database import db
from bot_manager import bot_manager

logger = logging.getLogger(__name__)

PREMIUM_I18N = {
    "en": {
        "no_bots": "⭐ Premium\n\nCreate a downloader bot first, then you can activate Premium with Telegram Stars.",
        "choose_bot": "⭐ PREMIUM\n\nChoose the bot you want to upgrade.\n\nPremium removes system ads, enables priority download processing and unlocks premium customization.",
        "plans": "⭐ PREMIUM PLANS\n\nPremium benefits:\n• 🚫 No system ads\n• ⚡ Priority download processing\n• 🎨 Premium caption and button controls\n• 🛠 Owner/admin customization\n\nChoose a plan:",
        "not_owner": "⛔ This bot does not belong to you.",
        "payment_invalid": "Invalid Premium payment.",
        "payment_failed": "Premium payment could not be verified.",
        "activated": "🎉 PREMIUM ACTIVATED!\n\n🤖 Bot: @{name}\n⭐ Paid: {stars} Telegram Stars\n📅 Plan: {plan}\n⏳ Expires: {until}\n\n🚫 System ads are disabled for this bot.\n⚡ Premium priority processing is enabled.",
        "activation_error": "❌ Payment received, but Premium activation needs administrator attention.",
    },
    "so": {
        "no_bots": "⭐ Premium\n\nMarka hore samee downloader bot, kadib Premium waxaad ku furan kartaa Telegram Stars.",
        "choose_bot": "⭐ PREMIUM\n\nDooro bot-ka aad rabto inaad Premium ka dhigto.\n\nPremium wuxuu ka saaraa ads-ka system-ka, wuxuu siinayaa download priority sare, wuxuuna furayaa habaynta Premium.",
        "plans": "⭐ QORSHEYAASHA PREMIUM\n\nFaa'iidooyinka Premium:\n• 🚫 Ads system-ka ma jiro\n• ⚡ Download xawaare/priority sare\n• 🎨 Caption iyo buttons gaar ah\n• 🛠 Maamul iyo habayn Premium\n\nDooro qorshaha:",
        "not_owner": "⛔ Bot-kan adiga ma lihid.",
        "payment_invalid": "Lacag-bixinta Premium ma saxna.",
        "payment_failed": "Lacag-bixinta Premium lama xaqiijin karin.",
        "activated": "🎉 PREMIUM WAA FURMAY!\n\n🤖 Bot: @{name}\n⭐ La bixiyey: {stars} Telegram Stars\n📅 Qorshe: {plan}\n⏳ Wuxuu dhacayaa: {until}\n\n🚫 Ads-ka system-ka waa laga saaray bot-kan.\n⚡ Download priority sare waa la furay.",
        "activation_error": "❌ Lacagta waa la helay, laakiin Premium wuxuu u baahan yahay in admin uu hubiyo.",
    },
    "ar": {
        "no_bots": "⭐ بريميوم\n\nأنشئ بوت تحميل أولاً، ثم يمكنك تفعيل Premium باستخدام Telegram Stars.",
        "choose_bot": "⭐ PREMIUM\n\nاختر البوت الذي تريد ترقيته.\n\nPremium يزيل إعلانات النظام ويعطي أولوية للتحميل ويفتح التخصيص.",
        "plans": "⭐ خطط PREMIUM\n\nمزايا Premium:\n• 🚫 بدون إعلانات النظام\n• ⚡ أولوية تحميل أعلى\n• 🎨 تخصيص النص والأزرار\n• 🛠 تخصيص من المالك/المسؤول\n\nاختر الخطة:",
        "not_owner": "⛔ هذا البوت ليس ملكك.",
        "payment_invalid": "دفعة Premium غير صالحة.",
        "payment_failed": "تعذر التحقق من دفعة Premium.",
        "activated": "🎉 تم تفعيل PREMIUM!\n\n🤖 البوت: @{name}\n⭐ المدفوع: {stars} Telegram Stars\n📅 الخطة: {plan}\n⏳ الانتهاء: {until}\n\n🚫 تم تعطيل إعلانات النظام لهذا البوت.\n⚡ تم تفعيل أولوية التحميل.",
        "activation_error": "❌ تم استلام الدفعة، لكن تفعيل Premium يحتاج إلى مراجعة المسؤول.",
    },
    "es": {
        "no_bots": "⭐ Premium\n\nPrimero crea un bot descargador y después activa Premium con Telegram Stars.",
        "choose_bot": "⭐ PREMIUM\n\nElige el bot que quieres actualizar.\n\nPremium elimina los anuncios del sistema, activa prioridad de descarga y desbloquea la personalización.",
        "plans": "⭐ PLANES PREMIUM\n\nBeneficios Premium:\n• 🚫 Sin anuncios del sistema\n• ⚡ Prioridad de descarga\n• 🎨 Caption y botones personalizados\n• 🛠 Personalización del propietario/admin\n\nElige un plan:",
        "not_owner": "⛔ Este bot no te pertenece.",
        "payment_invalid": "Pago Premium no válido.",
        "payment_failed": "No se pudo verificar el pago Premium.",
        "activated": "🎉 ¡PREMIUM ACTIVADO!\n\n🤖 Bot: @{name}\n⭐ Pagado: {stars} Telegram Stars\n📅 Plan: {plan}\n⏳ Expira: {until}\n\n🚫 Los anuncios del sistema están desactivados.\n⚡ Prioridad de descarga activada.",
        "activation_error": "❌ El pago fue recibido, pero la activación de Premium necesita revisión del administrador.",
    },
}

async def localized(uid, key, **kwargs):
    try:
        lang = await db.get_main_user_language(uid)
    except Exception:
        lang = "en"
    if lang not in PREMIUM_I18N: 
        lang = "en"
    return PREMIUM_I18N[lang][key].format(**kwargs)

PLANS = {
    "1m": ("1 Month", 30),
    "3m": ("3 Months", 90),
    "6m": ("6 Months", 180),
    "1y": ("1 Year", 365),
}

DEFAULT_PRICES = {
    "1m": 100,
    "3m": 300,
    "6m": 600,
    "1y": 1000
}

def _admins():
    ids = set()
    if getattr(Config, "OWNER_ID", 0):
        ids.add(int(Config.OWNER_ID))
    ids.update(int(x) for x in getattr(Config, "ADMIN_IDS", []) if str(x).isdigit())
    return ids

def _is_admin(uid):
    return int(uid) in _admins()

def owner_plans(bot_id, prices):
    p1m = prices.get("1m", DEFAULT_PRICES["1m"])
    p3m = prices.get("3m", DEFAULT_PRICES["3m"])
    p6m = prices.get("6m", DEFAULT_PRICES["6m"])
    p1y = prices.get("1y", DEFAULT_PRICES["1y"])
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"1 Month — {p1m} ⭐", callback_data=f"prem:buy:{bot_id}:1m"),
            InlineKeyboardButton(f"3 Months — {p3m} ⭐", callback_data=f"prem:buy:{bot_id}:3m")
        ],
        [
            InlineKeyboardButton(f"6 Months — {p6m} ⭐", callback_data=f"prem:buy:{bot_id}:6m"),
            InlineKeyboardButton(f"1 Year — {p1y} ⭐", callback_data=f"prem:buy:{bot_id}:1y")
        ],
    ])

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    bots = await db.get_user_bots(update.effective_user.id)
    if not bots:
        await update.message.reply_text(await localized(update.effective_user.id, "no_bots"))
        return
    rows = []
    for bot in bots:
        bid = bot["bot_id"]
        name = bot.get("username") or str(bid)
        rows.append([InlineKeyboardButton(f"⭐ @{name}", callback_data=f"prem:bot:{bid}")])
    await update.message.reply_text(
        await localized(update.effective_user.id, "choose_bot"),
        reply_markup=InlineKeyboardMarkup(rows),
    )

async def premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not (q.data or "").startswith("prem:"):
        return False

    uid = q.from_user.id
    parts = q.data.split(":")
    
    if len(parts) < 3:
        await q.answer()
        return True
        
    action = parts[1]
    try:
        bot_id = int(parts[2])
    except ValueError:
        await q.answer()
        return True

    bot = await db.get_bot(bot_id)
    
    # Hubinta Milkiilaha Bot-ka
    bot_owner = bot.get("owner_id") if bot else None
    if not bot or (bot_owner is not None and int(bot_owner) != uid):
        await q.answer(await localized(uid, "not_owner"), show_alert=True)
        return True

    # Jawaabta callback query-ga hal jeer oo kaliya halkan ku bixi
    await q.answer()

    if action == "bot":
        prices = await db.get_premium_prices() or {}
        await q.edit_message_text(
            await localized(uid, "plans"),
            reply_markup=owner_plans(bot_id, prices),
        )
        return True

    if action == "buy" and len(parts) >= 4:
        plan = parts[3]
        if plan not in PLANS:
            return True
            
        prices = await db.get_premium_prices() or {}
        stars = int(prices.get(plan, DEFAULT_PRICES.get(plan, 100)))
        title, days = PLANS[plan]
        payload = f"tgpower-premium:{bot_id}:{plan}:{uid}"
        
        await context.bot.send_invoice(
            chat_id=uid,
            title=f"TG-Power Premium — {title}",
            description=f"Premium for @{bot.get('username') or bot_id}. No system ads + priority processing + premium controls.",
            payload=payload,
            currency="XTR",
            prices=[LabeledPrice(label=f"Premium {title}", amount=stars)],
        )
        return True
        
    return True

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.pre_checkout_query
    payload = q.invoice_payload or ""
    if not payload.startswith("tgpower-premium:"):
        await q.answer(ok=False, error_message=await localized(q.from_user.id, "payment_invalid"))
        return
    try:
        _, bot_id, plan, owner_id = payload.split(":")
        bot = await db.get_bot(int(bot_id))
        prices = await db.get_premium_prices() or {}
        
        expected_price = int(prices.get(plan, DEFAULT_PRICES.get(plan, 100)))
        bot_owner = bot.get("owner_id") if bot else None
        
        valid = bot and bot_owner is not None and int(bot_owner) == int(q.from_user.id) == int(owner_id) and plan in PLANS
        valid = valid and int(q.total_amount) == expected_price
        
        await q.answer(ok=bool(valid), error_message=None if valid else await localized(q.from_user.id, "payment_failed"))
    except Exception as e:
        logger.exception("Precheckout error: %s", e)
        await q.answer(ok=False, error_message=await localized(q.from_user.id, "payment_invalid"))

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    payment = update.message.successful_payment
    if not payment:
        return
    payload = payment.invoice_payload or ""
    if not payload.startswith("tgpower-premium:"):
        return
    try:
        _, bot_id_s, plan, owner_id_s = payload.split(":")
        bot_id = int(bot_id_s)
        owner_id = int(owner_id_s)
        if owner_id != update.effective_user.id or plan not in PLANS:
            return
            
        prices = await db.get_premium_prices() or {}
        stars = int(prices.get(plan, DEFAULT_PRICES.get(plan, 100)))
        days = PLANS[plan][1]
        
        until = await db.activate_bot_premium(bot_id, owner_id, plan, days, stars)
        bot = await db.get_bot(bot_id)
        
        if bot and bot.get("status") == "active":
            try:
                await bot_manager.stop_bot_instance(bot_id)
                await bot_manager.start_bot_instance(bot_id, bot.get("token"))
            except Exception:
                logger.exception("Could not restart premium bot %s", bot_id)
                
        until_str = until.strftime("%Y-%m-%d %H:%M UTC") if hasattr(until, "strftime") else str(until)
        
        await update.message.reply_text(
            await localized(
                update.effective_user.id, "activated",
                name=(bot or {}).get("username") or bot_id, stars=stars,
                plan=PLANS[plan][0], until=until_str
            )
        )
    except Exception as exc:
        logger.exception("Premium payment handling failed: %s", exc)
        await update.message.reply_text(await localized(update.effective_user.id, "activation_error"))

async def admin_premium_center(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not _is_admin(update.effective_user.id):
        return
    prices = await db.get_premium_prices() or {}
    p1m = prices.get("1m", DEFAULT_PRICES["1m"])
    p3m = prices.get("3m", DEFAULT_PRICES["3m"])
    p6m = prices.get("6m", DEFAULT_PRICES["6m"])
    p1y = prices.get("1y", DEFAULT_PRICES["1y"])
    
    premium = await db.get_premium_bots() or []
    await update.message.reply_text(
        "⭐ PREMIUM ADMIN CENTER\n\n"
        f"1 Month: {p1m} ⭐\n3 Months: {p3m} ⭐\n6 Months: {p6m} ⭐\n1 Year: {p1y} ⭐\n\n"
        f"⭐ Active premium bots: {len(premium)}\n\n"
        "Use the buttons below to manage prices, premium bots, grants and premium customization.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Prices", callback_data="padmin:prices"), InlineKeyboardButton("⭐ Premium Bots", callback_data="padmin:list")],
            [InlineKeyboardButton("🎁 Grant Premium", callback_data="padmin:grant"), InlineKeyboardButton("✏️ Caption", callback_data="padmin:caption")],
            [InlineKeyboardButton("🔘 Buttons", callback_data="padmin:buttons"), InlineKeyboardButton("📢 Ads", callback_data="padmin:ads")],
            [InlineKeyboardButton("📊 Premium Stats", callback_data="padmin:stats")],
        ]),
    )

async def admin_premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not _is_admin(q.from_user.id) or not (q.data or "").startswith("padmin:"):
        return False
    data = q.data.split(":")
    await q.answer()
    action = data[1] if len(data) > 1 else ""
    if action == "prices":
        prices = await db.get_premium_prices() or {}
        p1m = prices.get("1m", DEFAULT_PRICES["1m"])
        p3m = prices.get("3m", DEFAULT_PRICES["3m"])
        p6m = prices.get("6m", DEFAULT_PRICES["6m"])
        p1y = prices.get("1y", DEFAULT_PRICES["1y"])
        await q.edit_message_text(
            "💰 PREMIUM PRICES\n\n"
            f"1m = {p1m} ⭐\n3m = {p3m} ⭐\n6m = {p6m} ⭐\n1y = {p1y} ⭐\n\n"
            "To change them, use the admin text commands:\n"
            "/setpremium 1m 100\n/setpremium 3m 300\n/setpremium 6m 600\n/setpremium 1y 1000"
        )
    elif action == "list":
        bots = await db.get_premium_bots() or []
        if not bots:
            await q.edit_message_text("⭐ No premium bots yet.")
            return True
        rows=[]
        text="⭐ PREMIUM BOTS\n\n"
        for b in bots[:50]:
            until=(b.get("premium") or {}).get("until")
            name=b.get("username") or b.get("bot_id")
            until_str = until.strftime('%Y-%m-%d') if hasattr(until,'strftime') else str(until)
            text += f"⭐ @{name} — expires {until_str}\n"
            rows.append([InlineKeyboardButton(f"⚙️ @{name}", callback_data=f"padmin:manage:{b['bot_id']}")])
        await q.edit_message_text(text[:4000], reply_markup=InlineKeyboardMarkup(rows))
    elif action == "manage" and len(data) >= 3:
        bid=int(data[2])
        b=await db.get_bot(bid)
        if not b: 
            await q.edit_message_text("❌ Bot not found.")
            return True
        settings=await db.get_bot_premium_settings(bid) or {}
        await q.edit_message_text(
            f"⭐ PREMIUM BOT @{b.get('username') or bid}\n\n"
            f"Caption: {settings.get('caption','Default')}\n"
            f"Buttons: {len(settings.get('buttons',[]))}/10\n"
            f"Custom ad: {'ON' if settings.get('ad_text') else 'OFF'}\n\n"
            "Use /premiumcaption BOT_ID text\nUse /premiumad BOT_ID text\nUse /premiumbutton BOT_ID Label|https://example.com"
        )
    elif action == "stats":
        bots=await db.get_premium_bots() or []
        total_stars=sum(int((b.get('premium') or {}).get('stars',0)) for b in bots)
        await q.edit_message_text(f"📊 PREMIUM STATS\n\nActive premium bots: {len(bots)}\nRecorded Stars: {total_stars} ⭐")
    elif action in {"grant","caption","buttons","ads"}:
        await q.edit_message_text("Use the admin commands shown in Premium Center to configure this feature.\n\n/premiumgrant BOT_ID DAYS\n/premiumcaption BOT_ID text\n/premiumbutton BOT_ID Label|URL\n/premiumad BOT_ID text")
    return True

async def admin_premium_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user or not _is_admin(update.effective_user.id):
        return
    text=update.message.text or ""
    parts=text.split(maxsplit=2)
    cmd=parts[0].lower()
    try:
        if cmd=="/setpremium" and len(parts)>=3:
            plan=parts[1]
            stars=int(parts[2])
            prices=await db.set_premium_prices({plan:stars})
            await update.message.reply_text(f"✅ Premium price updated.\n{plan}: {prices.get(plan, stars)} ⭐")
        elif cmd=="/premiumgrant" and len(parts)>=3:
            bid=int(parts[1])
            days=int(parts[2])
            until=await db.grant_bot_premium(bid,days,update.effective_user.id)
            await update.message.reply_text("✅ Premium granted." if until else "❌ Bot not found.")
        elif cmd=="/premiumcaption" and len(parts)>=3:
            bid=int(parts[1])
            await db.set_bot_premium_setting(bid,"caption",parts[2])
            await update.message.reply_text("✅ Premium caption saved.")
        elif cmd=="/premiumad" and len(parts)>=3:
            bid=int(parts[1])
            await db.set_bot_premium_setting(bid,"ad_text",parts[2])
            await update.message.reply_text("✅ Custom ad saved. It stays disabled while Premium is active.")
        elif cmd=="/premiumbutton" and len(parts)>=3:
            bid=int(parts[1])
            raw=parts[2]
            label,url=raw.split("|",1)
            settings=await db.get_bot_premium_settings(bid) or {}
            buttons=settings.get("buttons",[])
            if len(buttons)>=10: 
                await update.message.reply_text("❌ Maximum 10 buttons.")
                return
            buttons.append({"label":label.strip()[:64],"url":url.strip()[:512]})
            await db.set_bot_premium_setting(bid,"buttons",buttons)
            await update.message.reply_text(f"✅ Button saved ({len(buttons)}/10).")
    except Exception as exc:
        await update.message.reply_text(f"❌ {exc}")

def register_premium_handlers(app):
    app.add_handler(CommandHandler("premium", premium_command), group=0)
    app.add_handler(CommandHandler("premiumadmin", admin_premium_center), group=0)
    app.add_handler(PreCheckoutQueryHandler(precheckout), group=0)
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment), group=0)
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r"^/(setpremium|premiumgrant|premiumcaption|premiumbutton|premiumad)(?:@\w+)?(?:\s|$)"), admin_premium_text), group=0)
    app.add_handler(CallbackQueryHandler(premium_callback, pattern=r"^prem:"), group=0)
    app.add_handler(CallbackQueryHandler(admin_premium_callback, pattern=r"^padmin:"), group=0)
