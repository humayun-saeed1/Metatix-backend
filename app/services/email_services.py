import requests
from app.core.config import settings

def send_reset_password_email(email_to: str, reset_token: str):
    reset_link = f"https://metatix-frontend.vercel.app/reset-password?token={reset_token}"
    subject = "Reset Your Metatix Password"
    html = f"""
    <html>
      <body style="font-family: 'Lato', sans-serif; color: #2D2D2D; line-height: 1.6;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #f0f0f0; border-radius: 15px;">
          <h2 style="color: #6E39CB; font-size: 24px; margin-bottom: 20px;">Password Reset Request</h2>
          <p>Hello,</p>
          <p>We received a request to reset the password for your Metatix account. Click the button below to choose a new one:</p>
          <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_link}" style="background-color: #6E39CB; color: white; padding: 12px 25px; text-decoration: none; font-weight: bold; border-radius: 8px; display: inline-block;">Reset Password</a>
          </div>
          <p style="font-size: 12px; color: #9ca3af;">If you didn't request this, you can safely ignore this email. This link will expire in 15 minutes.</p>
          <hr style="border: none; border-top: 1px solid #f0f0f0; margin: 20px 0;">
          <p style="font-size: 10px; color: #9ca3af; text-align: center; text-transform: uppercase; letter-spacing: 1px;">Metatix Ticketing Solutions</p>
        </div>
      </body>
    </html>
    """
    return _send_email(email_to, subject, html)

def send_welcome_email(email_to: str, name: str):
    subject = "Welcome to Metatix!"
    html = f"""
    <div style="font-family: 'Lato', sans-serif; padding: 20px; border: 1px solid #f0f0f0; border-radius: 15px; max-width: 600px; margin: auto;">
        <h2 style="color: #6E39CB;">Welcome to Metatix, {name}! 🎟️</h2>
        <p>Your account is officially active. Whether you are looking to discover exclusive local events or host your own, you are in the right place.</p>
        <p>Log in now to browse upcoming drops.</p>
    </div>
    """
    _send_email(email_to, subject, html)

def send_ticket_email(email_to: str, name: str, event_title: str, quantity: int):
    subject = f"Your Tickets for {event_title} are Confirmed!"
    html = f"""
    <div style="font-family: 'Lato', sans-serif; padding: 20px; border: 1px solid #f0f0f0; border-radius: 15px; max-width: 600px; margin: auto;">
        <h2 style="color: #10B981;">Payment Successful! 🎉</h2>
        <p>Hey {name},</p>
        <p>You have successfully purchased <strong>{quantity} ticket(s)</strong> for <strong>{event_title}</strong>.</p>
        <p>You can view your QR codes anytime in the 'My Tickets' section of your dashboard.</p>
    </div>
    """
    _send_email(email_to, subject, html)

def send_cancellation_email(email_to: str, event_title: str):
    subject = f"Event Cancelled: {event_title}"
    html = f"""
    <div style="font-family: 'Lato', sans-serif; padding: 20px; border: 1px solid #f0f0f0; border-radius: 15px; max-width: 600px; margin: auto;">
        <h2 style="color: #EF4444;">Event Cancellation Notice</h2>
        <p>We are writing to inform you that <strong>{event_title}</strong> has been cancelled by the organizer.</p>
        <p>Any payments made have been flagged for a full refund. We apologize for the inconvenience.</p>
    </div>
    """
    _send_email(email_to, subject, html)

def _send_email(email_to: str, subject: str, html_content: str):
    """
    Helper to send email via Resend API
    """
    try:
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Note: If they don't have a verified domain on Resend, 
        # 'from' MUST be 'onboarding@resend.dev'. 
        # Otherwise, they can use their own MAIL_FROM.
        # We'll try to use their MAIL_FROM but fall back or recommend onboarding if it fails.
        payload = {
            "from": f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>",
            "to": [email_to],
            "subject": subject,
            "html": html_content
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code in [200, 201]:
            return True
        else:
            print(f"🚨 Resend API Error ({response.status_code}): {response.text}")
            return False
            
    except Exception as e:
        print(f"🚨 Email Sending Failed (Resend): {e}")
        return False