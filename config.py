import os

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN','')
    BOT2_TOKEN = os.getenv('BOT2_TOKEN','')
    API_ID = int(os.getenv('API_ID','0') or 0)
    API_HASH = os.getenv('API_HASH','')
    PHONE = os.getenv('PHONE','')
    MONGO_URI = os.getenv('MONGO_URI', os.getenv('MONGO_URI_1','mongodb://localhost:27017/tgpower'))
    DB_NAME = os.getenv('DB_NAME','tgpower')
    OWNER_ID = int(os.getenv('OWNER_ID','0') or 0)
    ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS','').split(',') if x.strip().isdigit()]
    if OWNER_ID and OWNER_ID not in ADMIN_IDS: ADMIN_IDS.append(OWNER_ID)
    MAX_BOTS_PER_USER = int(os.getenv('MAX_BOTS_PER_USER','5'))
    MAX_VIDEO_DURATION_SECONDS = int(os.getenv('MAX_VIDEO_DURATION_SECONDS', str(int(os.getenv('MAX_YOUTUBE_DURATION','600')))))
    MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB','2000'))
    MAX_CONCURRENT_DOWNLOADS = int(os.getenv('MAX_CONCURRENT_DOWNLOADS','10'))
    PREMIUM_PRICE_STARS = int(os.getenv('PREMIUM_PRICE_STARS','250'))

BOT_TOKEN = Config.BOT_TOKEN
BOT2_TOKEN = Config.BOT2_TOKEN
API_ID = Config.API_ID
API_HASH = Config.API_HASH
MONGO_URI = Config.MONGO_URI
DB_NAME = Config.DB_NAME
ADMIN_IDS = Config.ADMIN_IDS
MAX_BOTS_PER_USER = Config.MAX_BOTS_PER_USER
