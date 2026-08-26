"""Premium feature helpers shared by TG-Power admin/managed-bot code."""
from datetime import datetime, timedelta, timezone

PREMIUM_BUTTONS = [
    '⭐ Premium Status','💳 Buy Premium','🎁 Grant Premium','⏳ Premium Days',
    '✏️ Premium Caption','🔘 Premium Buttons','📢 Premium Ads','📊 Premium Stats',
    '👥 Premium Users','⚙️ Premium Settings'
]

def premium_until(days:int):
    return datetime.now(timezone.utc) + timedelta(days=max(1, int(days)))

def is_active(record):
    if not record or not record.get('is_premium'):
        return False
    until = record.get('premium_until')
    if not until:
        return True
    if isinstance(until, datetime) and until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return until > datetime.now(timezone.utc)
