import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME: str = os.getenv("DB_NAME", "tg_power_saas")
    
    # Telegram API Credentials (bot_creator uses this to talk with BotFather)
    API_ID: int = int(os.getenv("API_ID", "0"))
    API_HASH: str = os.getenv("API_HASH", "")
    BOTFATHER_SESSION: str = os.getenv("BOTFATHER_SESSION", "botfather_creator")
    
    # Main Admin Telegram User IDs
    ADMIN_IDS: list[int] = [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
    ]
    
    # System limits
    MAX_BOTS_PER_USER: int = int(os.getenv("MAX_BOTS_PER_USER", "3"))
    MAX_CONCURRENT_DOWNLOADS: int = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "5"))
    DEFAULT_DOWNLOAD_LIMIT: int = int(os.getenv("DEFAULT_DOWNLOAD_LIMIT", "50"))
