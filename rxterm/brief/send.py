"""SMTP delivery for the morning brief."""

from __future__ import annotations

import logging
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage

from ..config import Settings

log = logging.getLogger(__name__)


class EmailNotConfigured(RuntimeError):
    pass


class EmailSendFailed(RuntimeError):
    pass


def _clean_secret(value: str) -> str:
    # Gmail shows App Passwords as "abcd efgh ijkl mnop"; copies often carry spaces,
    # non-breaking spaces or a trailing newline. None of those are part of the password.
    return re.sub(r"[\s  -​  　﻿]", "", value or "")


def _diagnose(user: str, password: str, host: str) -> list[str]:
    notes = []
    if "@" not in user:
        notes.append("RXTERM_SMTP_USER should be your full Gmail address (name@gmail.com).")
    if "gmail" in host and len(password) != 16:
        notes.append(f"RXTERM_SMTP_PASSWORD is {len(password)} characters after removing spaces; "
                     "Gmail App Passwords are exactly 16 letters. Create one at https://myaccount.google.com/apppasswords "
                     "(your normal Google password will not work).")
    if not password.isascii():
        notes.append("RXTERM_SMTP_PASSWORD contains non-ASCII characters — re-type it rather than copy/paste.")
    return notes


def _send(host: str, port: int, user: str, password: str, msg: EmailMessage) -> None:
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.ehlo()
            s.login(user, password)
            s.send_message(msg)


def send_email(cfg: Settings, subject: str, html: str, text: str, to: str | None = None) -> str:
    user = (cfg.smtp_user or "").strip()
    password = _clean_secret(cfg.smtp_password)
    recipient = (to or cfg.email_to or user).strip()
    if not (recipient and user and password):
        raise EmailNotConfigured(
            "Set RXTERM_SMTP_USER and RXTERM_SMTP_PASSWORD (Gmail: an App Password); RXTERM_EMAIL_TO is optional.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"RXTERM <{(cfg.email_from or user).strip()}>"
    msg["To"] = recipient
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    # Try the configured port first, then the other standard submission port.
    ports = [cfg.smtp_port] + [p for p in (587, 465) if p != cfg.smtp_port]
    errors = []
    for port in ports:
        try:
            _send(cfg.smtp_host, port, user, password, msg)
            return recipient
        except smtplib.SMTPAuthenticationError as exc:
            detail = exc.smtp_error.decode(errors="replace") if isinstance(exc.smtp_error, bytes) else str(exc.smtp_error)
            errors.append(f"port {port}: login rejected ({exc.smtp_code}) {detail.strip()}")
            break  # wrong credentials won't work on another port either
        except (smtplib.SMTPException, OSError) as exc:
            errors.append(f"port {port}: {type(exc).__name__}: {exc}")

    hints = _diagnose(user, password, cfg.smtp_host)
    report = "E-mail not sent.\n  " + "\n  ".join(errors)
    if hints:
        report += "\nLikely cause:\n  " + "\n  ".join(hints)
    print(report, file=sys.stderr)
    raise EmailSendFailed(report)
