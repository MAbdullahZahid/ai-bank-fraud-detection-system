"""
Email notifications:
- Welcome email when an admin creates a user
- Transaction result email to the customer (success or blocked-as-fraud)
- Fraud alert email to the bank admin whenever a transaction is blocked

Tries STARTTLS (port 587) first, falls back to SSL (port 465) - some
networks/firewalls block one or the other.

If SMTP isn't configured, every function fails silently (logs to console)
rather than blocking the transaction or user creation.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from app.constants import CURRENCY_SYMBOL

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "AI Bank Fraud Detection")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")


def _send(msg: MIMEMultipart, to_email: str) -> bool:
    """Shared send logic used by every email function below."""
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[EMAIL] SMTP_USER/SMTP_PASSWORD not set in .env - skipping email.")
        return False

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print(f"[EMAIL] Sent to {to_email} (STARTTLS, port {SMTP_PORT})")
        return True
    except Exception as e:
        print(f"[EMAIL] STARTTLS on port {SMTP_PORT} failed: {e}")

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, 465, timeout=15) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print(f"[EMAIL] Sent to {to_email} (SSL, port 465 fallback)")
        return True
    except Exception as e:
        print(f"[EMAIL] SSL fallback also failed: {e}")
        return False


def send_welcome_email(to_email: str, full_name: str, phone_number: str, password: str, balance: float) -> bool:
    """Sent once, when an admin creates a new user."""
    subject = "Your AI Bank Fraud Detection account is ready"
    body = f"""Hi {full_name},

An account has been created for you. Here are your login details:

Phone number (used as your account number): {phone_number}
Password: {password}
Starting balance: {CURRENCY_SYMBOL} {balance:,.2f}

Log in with your phone number and password to send and receive money.
Please keep these details secure.

- {SMTP_FROM_NAME}
"""
    msg = MIMEMultipart()
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    return _send(msg, to_email)


def send_transaction_email(to_email: str, full_name: str, transaction_type: str,
                            amount: float, is_fraud: bool, probability: float) -> bool:
    """Sent to the customer after every transaction - success or blocked."""
    if is_fraud:
        subject = "Transaction blocked - suspicious activity detected"
        body = f"""Hi {full_name},

A {transaction_type} of {CURRENCY_SYMBOL} {amount:,.2f} on your account was flagged as
potentially fraudulent (confidence: {probability * 100:.1f}%) and has been
BLOCKED. No money was moved.

If this was you, please contact support to verify your identity.
If this wasn't you, no action is needed - the transaction did not go through.

- {SMTP_FROM_NAME}
"""
    else:
        subject = "Transaction successful"
        body = f"""Hi {full_name},

Your {transaction_type} of {CURRENCY_SYMBOL} {amount:,.2f} was completed successfully.

- {SMTP_FROM_NAME}
"""

    msg = MIMEMultipart()
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    return _send(msg, to_email)


def send_admin_fraud_alert(user_full_name: str, user_phone: str, transaction_type: str,
                            amount: float, probability: float, transaction_id: int) -> bool:
    """Sent to the bank admin whenever a transaction is flagged as fraud."""
    if not ADMIN_EMAIL:
        print("[EMAIL] ADMIN_EMAIL not set in .env - skipping admin fraud alert.")
        return False

    subject = f"Fraud flagged - Transaction #{transaction_id}"
    body = f"""A transaction was flagged as fraud and blocked.

Customer: {user_full_name} ({user_phone})
Type: {transaction_type}
Amount: {CURRENCY_SYMBOL} {amount:,.2f}
Model confidence: {probability * 100:.2f}%
Transaction ID: {transaction_id}

Review this in the admin portal under Fraud logs.
"""
    msg = MIMEMultipart()
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = ADMIN_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    return _send(msg, ADMIN_EMAIL)

def send_dispute_email(to_email: str, full_name: str, approved: bool,
                        amount: float, transaction_type: str) -> bool:
    """Sent to the customer once an admin resolves their dispute."""
    if approved:
        subject = "Your dispute was approved"
        body = f"""Hi {full_name},

Good news - after review, your disputed {transaction_type} of {CURRENCY_SYMBOL} {amount:,.2f}
has been confirmed as legitimate. The transaction has now been completed
and your balance has been updated.

Thank you for reporting this - it also helps us improve our fraud detection.

- {SMTP_FROM_NAME}
"""
    else:
        subject = "Your dispute was reviewed"
        body = f"""Hi {full_name},

After review, your disputed {transaction_type} of {CURRENCY_SYMBOL} {amount:,.2f} has been
confirmed as correctly flagged. The transaction remains blocked and no
money was moved.

If you believe this is incorrect, please contact support directly.

- {SMTP_FROM_NAME}
"""

    msg = MIMEMultipart()
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    return _send(msg, to_email)