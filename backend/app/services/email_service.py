"""
Sends a welcome email with account details when an admin creates a new user.
Uses SMTP credentials from .env - works with Gmail (requires an App Password,
not your regular Gmail password - see README for setup) or any SMTP provider.

If SMTP isn't configured, this fails silently (logs to console) rather than
blocking user creation - a missing email shouldn't stop the admin's workflow.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "AI Bank Fraud Detection")


def send_welcome_email(to_email: str, full_name: str, phone_number: str, password: str, balance: float) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[EMAIL] SMTP_USER/SMTP_PASSWORD not set in .env - skipping welcome email.")
        return False

    subject = "Your AI Bank Fraud Detection account is ready"
    body = f"""Hi {full_name},

An account has been created for you. Here are your login details:

Phone number (used as your account number): {phone_number}
Password: {password}
Starting balance: Rs {balance:,.2f}

Log in with your phone number and password to send and receive money.
Please keep these details secure.

- {SMTP_FROM_NAME}
"""

    msg = MIMEMultipart()
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print(f"[EMAIL] Welcome email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL] Failed to send welcome email to {to_email}: {e}")
        return False
