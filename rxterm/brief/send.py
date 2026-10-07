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
    elif "gmail" in host and not password.isalpha():
        notes.append("RXTERM_SMTP_PASSWORD contains digits or symbols; Gmail App Passwords are 16 letters only, "
                     "so this looks like your regular Google password. Create an App Password at "
                     "https://myaccount.google.com/apppasswords and paste that instead.")
    if not password.isascii():
        notes.append("RXTERM_SMTP_PASSWORD contains non-ASCII characters — re-type it rather than copy/paste.")
    return notes


def _login(s: smtplib.SMTP, user: str, password: str) -> None:
    # Gmail drops the connection on a bad AUTH PLAIN but answers AUTH LOGIN with a real
    # 535 reason, so prefer LOGIN when offered.
    if "LOGIN" in s.esmtp_features.get("auth", "").upper().split():
        s.user, s.password = user, password
        s.auth("LOGIN", s.auth_login, initial_response_ok=False)
    else:
        s.login(user, password)


def _send(host: str, port: int, user: str, password: str, msg: EmailMessage) -> None:
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            _login(s, user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.ehlo()
            _login(s, user, password)
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
            if "gmail" in cfg.smtp_host:
                errors.append("Gmail says the address/App Password pair is wrong. Make sure the App Password was created "
                              f"while signed in as {user} (check the avatar on myaccount.google.com/apppasswords), "
                              "then copy-paste it into the RXTERM_SMTP_PASSWORD secret.")
            break  # wrong credentials won't work on another port either
        except (smtplib.SMTPException, OSError) as exc:
            errors.append(f"port {port}: {type(exc).__name__}: {exc}")

    hints = _diagnose(user, password, cfg.smtp_host)
    report = "E-mail not sent.\n  " + "\n  ".join(errors)
    if hints:
        report += "\nLikely cause:\n  " + "\n  ".join(hints)
    print(report, file=sys.stderr)
    raise EmailSendFailed(report)


def probe(cfg: Settings) -> list[str]:
    """Step through the SMTP handshake and report each server reply (never the credentials)."""
    user = (cfg.smtp_user or "").strip()
    password = _clean_secret(cfg.smtp_password)
    local, _, domain = user.partition("@")
    out = [f"user: {local[:2]}…@{domain or '?'} ({len(user)} chars) · "
           f"password: {len(password)} chars, ascii={password.isascii()}, alnum={password.isalnum()}"]
    for port in (587, 465):
        try:
            if port == 465:
                s = smtplib.SMTP_SSL(cfg.smtp_host, port, context=ssl.create_default_context(), timeout=20)
            else:
                s = smtplib.SMTP(cfg.smtp_host, port, timeout=20)
            code, banner = s.ehlo()
            out.append(f"[{port}] EHLO {code}")
            if port == 587:
                code, resp = s.starttls(context=ssl.create_default_context())
                out.append(f"[{port}] STARTTLS {code}")
                s.ehlo()
            out.append(f"[{port}] AUTH offered: {s.esmtp_features.get('auth', '').strip()}")
            for mech, fn in (("LOGIN", s.auth_login), ("PLAIN", s.auth_plain)):
                s.user, s.password = user, password
                try:
                    code, resp = s.auth(mech, fn, initial_response_ok=(mech == "PLAIN"))
                    out.append(f"[{port}] AUTH {mech} → {code} OK")
                    s.quit()
                    return out
                except smtplib.SMTPAuthenticationError as exc:
                    msg = exc.smtp_error.decode(errors="replace") if isinstance(exc.smtp_error, bytes) else str(exc.smtp_error)
                    out.append(f"[{port}] AUTH {mech} → {exc.smtp_code} {msg.strip()[:200]}")
                except smtplib.SMTPServerDisconnected as exc:
                    out.append(f"[{port}] AUTH {mech} → server disconnected ({exc})")
                    break
        except (smtplib.SMTPException, OSError) as exc:
            out.append(f"[{port}] {type(exc).__name__}: {exc}")
    return out
