"""Rich-text formatting helpers for the terminal."""

from __future__ import annotations

from rich.text import Text

AMBER = "#ff9e1b"
UP = "#2bd576"
DN = "#ff4d4f"
DIM = "#7d8590"
WHITE = "#e6edf3"
BLUE = "#4ea1ff"
PURPLE = "#b38cff"
CYAN = "#39c5cf"


def nan(x) -> bool:
    return x is None or (isinstance(x, float) and x != x)


def pct(x, digits: int = 1, plus: bool = True, width: int = 0) -> Text:
    if nan(x):
        return Text("—".rjust(width), style=DIM)
    s = f"{x * 100:+.{digits}f}%" if plus else f"{x * 100:.{digits}f}%"
    return Text(s.rjust(width), style=UP if x > 0 else DN if x < 0 else WHITE)


def num(x, digits: int = 2, width: int = 0, style: str = WHITE) -> Text:
    if nan(x):
        return Text("—".rjust(width), style=DIM)
    return Text(f"{x:,.{digits}f}".rjust(width), style=style)


def big(x) -> str:
    if nan(x) or not x:
        return "—"
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(x) >= div:
            return f"{x / div:,.2f}{unit}"
    return f"{x:,.0f}"


def rsi(x) -> Text:
    if nan(x):
        return Text("—", style=DIM)
    style = DN if x >= 70 else UP if x <= 30 else WHITE
    return Text(f"{x:.0f}", style=style)


def signal(s: str) -> Text:
    style = {"STRONG BUY": f"bold {UP}", "BUY": UP, "STRONG SELL": f"bold {DN}", "SELL": DN}.get(s, DIM)
    return Text(s or "—", style=style)


def direction(d: str) -> Text:
    return Text(f" {d} ", style={"LONG": f"bold black on {UP}", "SHORT": f"bold white on {DN}"}.get(
        d, f"bold black on {PURPLE}"))


def tone(t: str) -> Text:
    return Text({"POS": "▲", "NEG": "▼"}.get(t, "•"), style={"POS": UP, "NEG": DN}.get(t, DIM))


def cat_type(t: str) -> Text:
    return Text(t or "", style={"PDUFA": f"bold {DN}", "ADCOM": f"bold {DN}", "READOUT": f"bold {PURPLE}",
                                "TRIAL": PURPLE, "EARNINGS": BLUE}.get(t, DIM))
