import os


def _int(name, default=0):
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
API_ID = _int("API_ID")
API_HASH = os.getenv("API_HASH", "").strip()
MONGO_URI = os.getenv("MONGO_URI", "").strip()
DB_NAME = os.getenv("DB_NAME", "tg_power")
OWNER_ID = _int("OWNER_ID")
ADMIN_IDS = set()
for raw in os.getenv("ADMIN_IDS", "").replace(";", ",").split(","):
    raw = raw.strip()
    if raw:
        try:
            ADMIN_IDS.add(int(raw))
        except ValueError:
            pass
if OWNER_ID:
    ADMIN_IDS.add(OWNER_ID)

MAX_BOTS_PER_USER = _int("MAX_BOTS_PER_USER", 5)
MAX_FILE_SIZE_MB = _int("MAX_FILE_SIZE_MB", 2000)
MAX_VIDEO_DURATION_SECONDS = _int("MAX_VIDEO_DURATION_SECONDS", 1800)
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
PORT = _int("PORT", 10000)
USER_SESSION = os.getenv("USER_SESSION", "").strip()
ENABLE_BOTFATHER_AUTOMATION = os.getenv("ENABLE_BOTFATHER_AUTOMATION", "true").lower() in {"1", "true", "yes", "on"}

# Backwards-compatible Config namespace used by downloader.py.
class Config:
    BOT_TOKEN = BOT_TOKEN
    API_ID = API_ID
    API_HASH = API_HASH
    MONGO_URI = MONGO_URI
    DB_NAME = DB_NAME
    OWNER_ID = OWNER_ID
    ADMIN_IDS = ADMIN_IDS
    MAX_BOTS_PER_USER = MAX_BOTS_PER_USER
    MAX_FILE_SIZE_MB = MAX_FILE_SIZE_MB
    MAX_VIDEO_DURATION_SECONDS = MAX_VIDEO_DURATION_SECONDS
    DOWNLOAD_DIR = DOWNLOAD_DIR
    USER_SESSION = USER_SESSION
    ENABLE_BOTFATHER_AUTOMATION = ENABLE_BOTFATHER_AUTOMATION
