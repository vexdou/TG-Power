import os
from dotenv import load_dotenv

# Soo rarida variables-ka .env faylka
load_dotenv()

class Config:
    # 1. Main Bot & Admin Config
    BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_MAIN_BOT_TOKEN_HERE")
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # Telegram User ID-gaaga Admin-ka
    
    # 2. MongoDB Database Config
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME = os.getenv("DB_NAME", "tg_power_db")
    
    # 3. Downloader Settings
    DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50")) # 50MB ee Telegram Bot Limit
    
    # 4. System Settings
    DEFAULT_LANG = "en"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
