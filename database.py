from motor.motor_asyncio import AsyncIOMotorClient
import config

client = AsyncIOMotorClient(config.MONGO_URI)
db = client['telegram_saas_platform']

users_col = db['users']
bots_col = db['bots']
bot_users_col = db['bot_users']
downloads_col = db['downloads']
settings_col = db['settings']
logs_col = db['logs']

async def init_db():
    # Create indexes for fast searches
    await users_col.create_index("user_id", unique=True)
    await bots_col.create_index("username", unique=True)
    await bot_users_col.create_index([("bot_username", 1), ("user_id", 1)], unique=True)
    await downloads_col.create_index("timestamp")

async def add_user(user_id, name, username):
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"name": name, "username": username, "can_create": True}},
        upsert=True
    )

async def register_bot(owner_id, bot_token, bot_name, bot_username):
    bot_data = {
        "owner_id": owner_id,
        "token": bot_token,
        "name": bot_name,
        "username": bot_username,
        "status": "active",
        "force_join_channels": [],
        "total_downloads": 0,
        "total_users": 0
    }
    await bots_col.insert_one(bot_data)

async def get_all_active_bots():
    return await bots_col.find({"status": "active"}).to_list(length=2000)

async def get_user_bots(owner_id):
    return await bots_col.find({"owner_id": owner_id}).to_list(length=100)

async def get_bot_by_username(username):
    return await bots_col.find_one({"username": username})

async def add_bot_user(bot_username, user_id, first_name):
    res = await bot_users_col.update_one(
        {"bot_username": bot_username, "user_id": user_id},
        {"$set": {"first_name": first_name, "is_blocked": False}},
        upsert=True
    )
    if res.upserted_id:
        await bots_col.update_one({"username": bot_username}, {"$inc": {"total_users": 1}})

async def log_download(bot_username, user_id, platform):
    await downloads_col.insert_one({"bot_username": bot_username, "user_id": user_id, "platform": platform})
    await bots_col.update_one({"username": bot_username}, {"$inc": {"total_downloads": 1}})

async def is_bot_creation_enabled():
    setting = await settings_col.find_one({"key": "bot_creation"})
    return setting.get("value", True) if setting else True

async def toggle_bot_creation(status: bool):
    await settings_col.update_one({"key": "bot_creation"}, {"$set": {"value": status}}, upsert=True)
