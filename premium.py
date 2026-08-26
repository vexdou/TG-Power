from datetime import timedelta
from database import db, bots_col, downloads_col, bot_users_col, settings_col, now

PLANS = {"1m": (30, "1 Month"), "3m": (90, "3 Months"), "6m": (180, "6 Months"), "1y": (365, "1 Year")}
DEFAULT_PRICES = {"1m": 100, "3m": 300, "6m": 600, "1y": 1000}

async def get_prices():
    return await db.get_premium_prices()

async def premium_status(bot):
    p = (bot or {}).get("premium") or {}
    active = bool(p.get("is_active")) and (not p.get("until") or p["until"] > now())
    return active, p

async def admin_center_text():
    prices = await get_prices()
    bots = await db.premium_bots()
    return ("⭐ PREMIUM ADMIN CENTER\n\n"
            f"Premium bots: {len(bots)}\n"
            f"1 Month: {prices.get('1m', 100)} XTR\n"
            f"3 Months: {prices.get('3m', 300)} XTR\n"
            f"6 Months: {prices.get('6m', 600)} XTR\n"
            f"1 Year: {prices.get('1y', 1000)} XTR\n\n"
            "Use the buttons below to manage Premium.")

async def grant(bot_id, days, admin_id):
    return await db.activate_premium(bot_id, int(days), plan="admin", source=f"admin:{admin_id}")

async def revoke(bot_id):
    return await db.deactivate_premium(bot_id)

async def stats():
    bots = await db.premium_bots()
    bot_ids = [b.get("username") for b in bots]
    downloads = 0
    users = 0
    for name in bot_ids:
        downloads += await downloads_col.count_documents({"bot_username": name})
        users += await bot_users_col.count_documents({"bot_username": name})
    return len(bots), users, downloads
