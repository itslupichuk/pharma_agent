"""SMTP delivery for the morning brief."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from ..config import Settings


class EmailNotConfigured(RuntimeError):
    pass


def send_email(cfg: Settings, subject: str, html: str, text: str, to: str | None = None) -> str:
    recipient = to or cfg.email_to
    if not (recipient and cfg.smtp_user and cfg.smtp_password):
        raise EmailNotConfigured(
            "Set RXTERM_EMAIL_TO, RXTERM_SMTP_USER and RXTERM_SMTP_PASSWORD (Gmail: an App Password).")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"RXTERM <{cfg.email_from or cfg.smtp_user}>"
    msg["To"] = recipient
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    ctx = ssl.create_default_context()
    if cfg.smtp_port == 465:
        with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=ctx, timeout=30) as s:
            s.login(cfg.smtp_user, cfg.smtp_password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(cfg.smtp_user, cfg.smtp_password)
            s.send_message(msg)
    return recipient
