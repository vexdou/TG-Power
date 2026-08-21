TG-Power — CENTRAL FORCE JOIN + 50-BUTTON ADMIN PANEL
=======================================================

What changed in this package
----------------------------
1. Force Join is GLOBAL for every managed downloader bot.
2. Membership is checked ONLY with the MAIN controller bot token.
3. Managed downloader bots do NOT need to be admins in Force Join channels.
4. The MAIN bot must be administrator/owner of every Force Join channel.
5. Admin can configure up to 5 channels.
6. Admin can verify Main Bot access, remove one channel, or clear all channels.
7. Pending links are stored per managed bot/user. After the user joins and presses I Joined, the old pending URL is downloaded automatically; the user does not resend it.
8. The Force Join prompt is deleted after a successful check before the media is sent.
9. Admin panel now has exactly 50 management buttons.
10. Broadcast All targets all saved managed bots; Broadcast Bot lets the admin select one bot.

IMPORTANT: Telegram permission
------------------------------
For each Force Join channel, add the MAIN bot (the BOT_TOKEN in Render) as an
administrator. The downloader/managed bots do not need channel admin access.
Use @ChannelUsername or a valid Telegram channel identifier.

Admin panel highlights
----------------------
Dashboard, All Bots, Search, Users, Bot Users, Bot Owners, Downloads, Download
Stats, Failed/Recent Downloads, Broadcast All/Bot/Preview, Global Force Join,
Force Join verification, Bot Creation, Start/Stop/Restart/Delete, Health, Errors,
Reload, Maintenance, System Settings, Max Video, Max File, Default Language,
User/Bot Export, cleanup tools, DB/queue/uptime/security/status tools, platform
stats, settings reset, backup information, capacity, notifications, and more.

Render
------
Keep these environment variables configured:
BOT_TOKEN, OWNER_ID, ADMIN_IDS, MONGO_URI, DB_NAME, API_ID/API_HASH if BotFather
automation is used. For YouTube cloud restrictions, configure the existing
YouTube authentication variables supported by downloader.py when necessary.

Files added/changed
-------------------
force_join.py
main_bot.py
managed_bot.py
database.py

The rest of the package is included so you can replace the project files together.

PREMIUM + DOWNLOADER FIXES
==========================

Downloader:
- Pinterest/TikTok format selection now falls back to yt-dlp's generic best format instead of requiring MP4 video+M4A audio formats that may not exist.
- YouTube uses Deno/EJS when available and multiple player clients. Render/cloud IP blocking cannot be bypassed by code alone; valid YouTube cookies or a PO token may still be required when YouTube challenges the server.
- Premium bots use a dedicated higher-concurrency download pool.

Telegram Stars Premium:
- /premium lets a bot owner choose one of their bots and pay with Telegram Stars (XTR).
- Default prices: 1 month 100 ⭐, 3 months 300 ⭐, 6 months 600 ⭐, 1 year 1000 ⭐.
- Payment is verified in pre-checkout and activated only after successful payment.
- Premium removes system/custom ads, enables premium priority processing, and supports premium caption/buttons.
- Up to 10 custom premium URL buttons per bot.
- Admin commands: /setpremium PLAN STARS, /premiumgrant BOT_ID DAYS, /premiumcaption BOT_ID TEXT, /premiumbutton BOT_ID LABEL|URL, /premiumad BOT_ID TEXT.
- Premium management is also exposed through the main admin panel's Premium Center buttons.

LANGUAGE UPDATE
- Main bot language is stored per Telegram user in MongoDB.
- Supported main-bot languages: English, Somali, Arabic, Spanish.
- The selected language persists across /start and future sessions.
- Main user keyboard and user-facing welcome/help/id/authorization/bot-creation messages are localized.
- Premium purchase messages are localized too.
- Admin panel remains in English for stable administration controls.
