"""Email delivery over SMTP (Gmail App Password or any other SMTP server)."""
import os
import smtplib
from email.message import EmailMessage


def mail_settings() -> dict | None:
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    to = os.getenv("MAIL_TO")
    if not (user and password and to):
        return None
    return {
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": user,
        "password": password,
        "sender": os.getenv("MAIL_FROM", user),
        "recipients": [addr.strip() for addr in to.split(",") if addr.strip()],
    }


def send_email(subject: str, text: str, html: str, settings: dict) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings["sender"]
    msg["To"] = ", ".join(settings["recipients"])
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(settings["host"], settings["port"], timeout=30) as smtp:
        smtp.starttls()
        smtp.login(settings["user"], settings["password"])
        smtp.send_message(msg)
