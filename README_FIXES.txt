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
