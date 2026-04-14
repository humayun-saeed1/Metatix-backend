from twilio.rest import Client
from app.core.config import settings

def _get_twilio_client():
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

def send_welcome_sms(phone_number: str, name: str):
    if not phone_number: return
    try:
        if not settings.TWILIO_ACCOUNT_SID or "AC" not in settings.TWILIO_ACCOUNT_SID:
            return  # SMS disabled or tier expired
        client = _get_twilio_client()
        client.messages.create(
            body=f"👋 Welcome to Metatix, {name}! Your account is live. Ready to find your next favorite event?",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )
    except Exception as e:
        # Silenced as per user request (Free tier expired)
        print(f"ℹ️ Twilio SMS skipped/failed: {e}")

def send_ticket_sms(phone_number: str, event_title: str, quantity: int):
    if not phone_number: return
    try:
        if not settings.TWILIO_ACCOUNT_SID or "AC" not in settings.TWILIO_ACCOUNT_SID:
            return
        client = _get_twilio_client()
        client.messages.create(
            body=f"🎟️ METATIX VIP: You're going to {event_title}! Your {quantity} ticket(s) are locked in. Check your email for details.",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )
    except Exception as e:
        print(f"ℹ️ Twilio SMS skipped/failed: {e}")

def send_cancellation_sms(phone_number: str, event_title: str):
    if not phone_number: return
    try:
        if not settings.TWILIO_ACCOUNT_SID or "AC" not in settings.TWILIO_ACCOUNT_SID:
            return
        client = _get_twilio_client()
        client.messages.create(
            body=f"⚠️ METATIX UPDATE: Unfortunately, {event_title} has been cancelled by the organizer. A full refund is being processed.",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )
    except Exception as e:
        print(f"ℹ️ Twilio SMS skipped/failed: {e}")