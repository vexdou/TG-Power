"""Compatibility creator helper.

Managed-bot creation is handled by Telegram's official managed-bot update in
bot.py. This helper exists so legacy imports do not crash the application.
"""
async def create_bot_via_botfather(*args, **kwargs):
    raise RuntimeError('Use Telegram Managed Bot creation from the Create New Bot button.')
