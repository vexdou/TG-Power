import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_MAIN_BOT_TOKEN_HERE")

    try:
        OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
    except ValueError:
        OWNER_ID = 0

    ADMIN_IDS = [
        int(x.strip())
        for x in os.getenv("ADMIN_IDS", "").split(",")
        if x.strip().isdigit()
    ]

    try:
        API_ID = int(os.getenv("API_ID", "0") or "0")
    except ValueError:
        API_ID = 0

    API_HASH = os.getenv("API_HASH", "")
    BOTFATHER_SESSION = os.getenv("BOTFATHER_SESSION") or os.getenv("USER_SESSION", "botfather_session")

    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME = os.getenv("DB_NAME", "tg_power_db")

    DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    MAX_VIDEO_DURATION_SECONDS = int(os.getenv("MAX_VIDEO_DURATION_SECONDS", "600"))

    DEFAULT_LANG = "en"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
