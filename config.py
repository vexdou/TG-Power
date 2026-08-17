import os

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
USER_SESSION = os.environ.get("USER_SESSION", "")  # Pyrogram Session String for BotFather Automation
MONGO_URI = os.environ.get("MONGO_URI", "")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
PORT = int(os.environ.get("PORT", 8000))

# Speed & Safety Limits
MAX_CONCURRENT_DOWNLOADS = 2
MAX_FILE_SIZE_MB = 150
