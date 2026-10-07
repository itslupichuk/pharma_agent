"""Runtime configuration, read from the environment (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    home: Path = field(default_factory=lambda: Path(os.getenv("RXTERM_HOME", "~/.rxterm")).expanduser())
    tz_name: str = field(default_factory=lambda: os.getenv("RXTERM_TZ", "America/New_York"))
    demo: bool = field(default_factory=lambda: _flag("RXTERM_DEMO"))

    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("RXTERM_MODEL", "claude-opus-5-5"))

    email_to: str = field(default_factory=lambda: os.getenv("RXTERM_EMAIL_TO", ""))
    email_from: str = field(default_factory=lambda: os.getenv("RXTERM_EMAIL_FROM", "") or os.getenv("RXTERM_SMTP_USER", ""))
    smtp_host: str = field(default_factory=lambda: os.getenv("RXTERM_SMTP_HOST", "smtp.gmail.com"))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("RXTERM_SMTP_PORT", "587")))
    smtp_user: str = field(default_factory=lambda: os.getenv("RXTERM_SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("RXTERM_SMTP_PASSWORD", ""))

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.tz_name)

    @property
    def cache_path(self) -> Path:
        return self.home / "cache.db"

    @property
    def catalysts_path(self) -> Path:
        return self.home / "catalysts.yaml"

    @property
    def watchlist_path(self) -> Path:
        return self.home / "watchlist.txt"

    def ensure_home(self) -> Path:
        self.home.mkdir(parents=True, exist_ok=True)
        return self.home


settings = Settings()
