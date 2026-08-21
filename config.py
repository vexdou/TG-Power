import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_MAIN_BOT_TOKEN_HERE")

    # OWNER_ID is the primary admin. ADMIN_IDS can contain more admins.
    # Example in Render:
    # OWNER_ID=123456789
    # ADMIN_IDS=123456789,987654321
    try:
        OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
    except ValueError:
        OWNER_ID = 0

    ADMIN_IDS = [
        int(x.strip())
        for x in os.getenv("ADMIN_IDS", "").split(",")
        if x.strip().isdigit()
    ]

    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME = os.getenv("DB_NAME", "tg_power_db")

    DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    MAX_VIDEO_DURATION_SECONDS = int(
        os.getenv("MAX_VIDEO_DURATION_SECONDS", "600")
    )

    DEFAULT_LANG = "en"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
