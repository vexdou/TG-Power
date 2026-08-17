import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, Message, CallbackQuery
from pymongo import MongoClient

# ==========================================
# 1. CONFIGURATION & DATABASE SETUP
# ==========================================
API_ID = int(os.environ.get("API_ID", 123456))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI", "YOUR_MONGO_URI")
RENDER_URL = os.environ.get("RENDER_URL", "https://your-app.onrender.com").rstrip('/')

# MongoDB Connection
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["saas_bot_db"]
users_col = db["users"]
bots_col = db["bots"]

# Pyrogram Client
main_app = Client(
    "main_saas_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ==========================================
# 2. MULTI-LANGUAGE TRANSLATIONS DICTIONARY
# ==========================================
TEXTS = {
    "so": {
        "choose_lang": "🌐 **Fadlan dooro luuqadda aad rabto inaad ku isticmaasho bot-ka:**",
        "welcome": (
            "👋 **Kusoo dhawoow SaaS Bot Creation Platform!**\n\n"
            "Nidaamkan wuxuu kuusoo saarayaa bot-yada Telegram-ka si otomaatig ah iyada oo aan koodh la qorayn.\n\n"
            "⚙️ **Waxqabadka Bot-kan:**\n"
            "• Abuuro Bot cusub 1-daqiiqo gudaheed.\n"
            "• Ku maamul dhammaan bot-yadaada hal dashboard.\n"
            "• Mini App foom ah oo kuu fududeynaya magacaabista bot-ka."
        ),
        "btn_create": "➕ Sameey Bot Cusub",
        "btn_mybots": "📦 Bot-yadayda",
        "btn_stats": "📊 Tirokoobka",
        "btn_lang": "🌐 Language / Luuqadda",
        "my_bots_empty": "📦 **Bot-yadaada:**\n\nHada ma haysatid wax bot ah oo firfircoon. Taabo **'➕ Sameey Bot Cusub'** si aad u bilaawdo.",
        "stats": "📊 **Tirokoobka Nidaamka:**\n\n• Isticmaalayaasha: `{users}`\n• Bot-yada Firfircoon: `{bots}`",
        "lang_changed": "✅ Luuqadda waxaa loo beddelayed Soomaali!"
    },
    "en": {
        "choose_lang": "🌐 **Please select your preferred language:**",
        "welcome": (
            "👋 **Welcome to SaaS Bot Creation Platform!**\n\n"
            "This system automatically generates and manages Telegram bots without writing any code.\n\n"
            "⚙️ **Features:**\n"
            "• Create a new Bot in under 1 minute.\n"
            "• Manage all your created bots from a single dashboard.\n"
            "• Interactive Mini App form for seamless bot setup."
        ),
        "btn_create": "➕ Create New Bot",
        "btn_mybots": "📦 My Bots",
        "btn_stats": "📊 Statistics",
        "btn_lang": "🌐 Language / Luuqadda",
        "my_bots_empty": "📦 **Your Bots:**\n\nYou don't have any active bots yet. Tap **'➕ Create New Bot'** to get started.",
        "stats": "📊 **System Statistics:**\n\n• Total Users: `{users}`\n• Active Bots: `{bots}`",
        "lang_changed": "✅ Language successfully set to English!"
    },
    "ar": {
        "choose_lang": "🌐 **الرجاء اختيار اللغة التي تفضلها:**",
        "welcome": (
            "👋 **مرحبًا بك في منصة إنشاء البوتات SaaS!**\n\n"
            "يقوم هذا النظام بإنشاء وإدارة بوتات التليجرام تلقائيًا دون الحاجة لكتابة أي كود.\n\n"
            "⚙️ **المميزات:**\n"
            "• إنشاء بوت جديد في أقل من دقيقة.\n"
            "• إدارة جميع البوتات الخاصة بك من لوحة تحكم واحدة.\n"
            "• تطبيق مصغر (Mini App) لإنشاء البوت بسهولة."
        ),
        "btn_create": "➕ إنشاء بوت جديد",
        "btn_mybots": "📦 بوتاتي",
        "btn_stats": "📊 الإحصائيات",
        "btn_lang": "🌐 اللغة / Language",
        "my_bots_empty": "📦 **بوتاتك:**\n\nليس لديك أي بوت نشط حاليًا. اضغط على **'➕ إنشاء بوت جديد'** للبدء.",
        "stats": "📊 **إحصائيات النظام:**\n\n• إجمالي المستخدمين: `{users}`\n• البوتات النشطة: `{bots}`",
        "lang_changed": "✅ تم تغيير اللغة بنجاح إلى العربية!"
    }
}

# ==========================================
# 3. HELPER FUNCTIONS & KEYBOARDS
# ==========================================
def get_user_lang(user_id: int):
    user = users_col.find_one({"user_id": user_id})
    return user.get("lang") if user else None

def set_user_lang(user_id: int, lang: str):
    users_col.update_one({"user_id": user_id}, {"$set": {"lang": lang, "user_id": user_id}}, upsert=True)

def build_main_keyboard(lang: str):
    t = TEXTS.get(lang, TEXTS["so"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["btn_create"], web_app=WebAppInfo(url=f"{RENDER_URL}/create-app"))],
        [InlineKeyboardButton(t["btn_mybots"], callback_data="my_bots"), InlineKeyboardButton(t["btn_stats"], callback_data="my_stats")],
        [InlineKeyboardButton(t["btn_lang"], callback_data="change_language")]
    ])

def build_lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇸🇴 Soomaali", callback_data="set_lang_so")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")],
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="set_lang_ar")]
    ])

# ==========================================
# 4. BOT HANDLERS
# ==========================================
@main_app.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    current_lang = get_user_lang(user_id)

    # Haddii uu cusub yahay
    if not current_lang:
        await message.reply_text(
            TEXTS["so"]["choose_lang"],
            reply_markup=build_lang_keyboard()
        )
    else:
        t = TEXTS[current_lang]
        await message.reply_text(
            t["welcome"],
            reply_markup=build_main_keyboard(current_lang)
        )

@main_app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    # Doorashada Luuqadda Marka Ugu Horreysa
    if data.startswith("set_lang_"):
        selected_lang = data.split("_")[2]
        set_user_lang(user_id, selected_lang)
        t = TEXTS[selected_lang]
        
        await query.answer(t["lang_changed"])
        await query.message.edit_text(
            t["welcome"],
            reply_markup=build_main_keyboard(selected_lang)
        )

    # Beddelaada Luuqadda (Button-ka 4-aad)
    elif data == "change_language":
        lang = get_user_lang(user_id) or "so"
        await query.message.edit_text(
            TEXTS[lang]["choose_lang"],
            reply_markup=build_lang_keyboard()
        )

    # Liiska Bot-yada Isticmaalaha
    elif data == "my_bots":
        lang = get_user_lang(user_id) or "so"
        t = TEXTS[lang]
        user_bots = list(bots_col.find({"owner_id": user_id}))

        if not user_bots:
            await query.answer()
            await query.message.edit_text(t["my_bots_empty"], reply_markup=build_main_keyboard(lang))
        else:
            msg = "📦 **Your Bots / Bot-yadaada:**\n\n"
            for b in user_bots:
                msg += f"🤖 **{b.get('bot_name')}** — @{b.get('bot_username')}\n"
            
            await query.answer()
            await query.message.edit_text(msg, reply_markup=build_main_keyboard(lang))

    # Tirokoobka (Statistics)
    elif data == "my_stats":
        lang = get_user_lang(user_id) or "so"
        t = TEXTS[lang]
        
        total_users = users_col.count_documents({})
        total_bots = bots_col.count_documents({})

        stats_text = t["stats"].format(users=total_users, bots=total_bots)
        await query.answer()
        await query.message.edit_text(stats_text, reply_markup=build_main_keyboard(lang))

# ==========================================
# 5. EXECUTION ENTRY POINT
# ==========================================
if __name__ == "__main__":
    print("👑 Main SaaS Bot is running...")
    main_app.run()
