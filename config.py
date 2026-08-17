import os
from typing import List

def _csv_ints(value: str) -> List[int]:
    result = []
    for item in (value or "").split(","):
        item = item.strip()
        if item:
            try:
                result.append(int(item))
            except ValueError:
                pass
    return result

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
USER_SESSION = os.getenv("USER_SESSION", "")
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = os.getenv("DB_NAME", "telegram_saas_platform")
ADMIN_IDS = _csv_ints(os.getenv("ADMIN_IDS", ""))

PORT = int(os.getenv("PORT", "10000"))
RENDER_URL = os.getenv("RENDER_URL", "").rstrip("/")

MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "150"))
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "900"))
MAX_BOTS_PER_USER = int(os.getenv("MAX_BOTS_PER_USER", "5"))
MAX_BROADCAST_WORKERS = int(os.getenv("MAX_BROADCAST_WORKERS", "5"))
BROADCAST_DELAY = float(os.getenv("BROADCAST_DELAY", "0.08"))

# Only allow BotFather automation when explicitly enabled.
ENABLE_BOTFATHER_AUTOMATION = os.getenv("ENABLE_BOTFATHER_AUTOMATION", "true").lower() == "true"

if not MONGO_URI:
    raise RuntimeError("MONGO_URI is required")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")
if not API_ID or not API_HASH:
    raise RuntimeError("API_ID and API_HASH are required")
