"""Price alerts: `ALRT LLY > 1250` — persisted in ~/.rxterm/alerts.json, checked on every quote refresh."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class Alert:
    ticker: str
    op: str              # ">" (crosses above) or "<" (crosses below)
    level: float
    created: str
    triggered: str = ""  # timestamp when hit; "" while armed

    @property
    def armed(self) -> bool:
        return not self.triggered

    def describe(self) -> str:
        word = "above" if self.op == ">" else "below"
        return f"{self.ticker} {word} {self.level:,.2f}"


class AlertBook:
    def __init__(self, path: Path):
        self.path = path
        self.alerts: list[Alert] = []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.alerts = [Alert(**a) for a in raw]
        except (OSError, ValueError, TypeError):
            self.alerts = []

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps([asdict(a) for a in self.alerts], indent=1), encoding="utf-8")
        except OSError:
            pass

    def add(self, ticker: str, level: float, op: str | None = None, last: float | None = None) -> Alert:
        if op not in (">", "<"):
            op = ">" if last is None or level >= last else "<"
        a = Alert(ticker.upper(), op, float(level), datetime.now().isoformat(timespec="seconds"))
        self.alerts.append(a)
        self.save()
        return a

    def remove(self, ticker: str | None = None) -> int:
        before = len(self.alerts)
        self.alerts = [] if ticker in (None, "ALL") else [a for a in self.alerts if a.ticker != ticker.upper()]
        self.save()
        return before - len(self.alerts)

    def check(self, prices: dict[str, float]) -> list[tuple[Alert, float]]:
        hits = []
        for a in self.alerts:
            px = prices.get(a.ticker)
            if not a.armed or px is None or px != px:
                continue
            if (a.op == ">" and px >= a.level) or (a.op == "<" and px <= a.level):
                a.triggered = datetime.now().isoformat(timespec="seconds")
                hits.append((a, px))
        if hits:
            self.save()
        return hits


def parse(args: list[str]) -> tuple[str, str | None, float] | None:
    """`LLY > 1250`, `LLY < 1100`, `LLY 1250`, `LLY >1250` → (ticker, op, level)."""
    if not args:
        return None
    ticker, rest = args[0], "".join(args[1:]).replace(",", "")
    op = None
    if rest[:1] in "<>":
        op, rest = rest[0], rest[1:]
    try:
        return ticker, op, float(rest)
    except ValueError:
        return None
