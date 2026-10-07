"""Custom terminal widgets: braille price chart, scrolling ticker tape, clock."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from .fmt import AMBER, BLUE, DIM, DN, UP, WHITE

# Braille dot bit for (x in 0..1, y in 0..3) inside a 2×4 cell
_BITS = ((0x01, 0x02, 0x04, 0x40), (0x08, 0x10, 0x20, 0x80))


class PriceChart(Widget):
    """High-resolution line chart drawn with Unicode braille (2×4 dots per cell)."""

    DEFAULT_CSS = "PriceChart { height: 1fr; }"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.df: pd.DataFrame | None = None
        self.title = ""

    def set_data(self, df: pd.DataFrame | None, title: str = "") -> None:
        self.df = df
        self.title = title
        self.refresh()

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if self.df is None or len(self.df) < 3 or w < 20 or h < 5:
            return Text("  no chart data", style=DIM)
        axis_w = 10
        cw, ch = w - axis_w, h - 2  # leave room for date axis + title
        close = self.df["Close"].astype(float)
        sma = close.rolling(min(50, max(5, len(close) // 4))).mean()
        lo, hi = float(min(close.min(), sma.min())), float(max(close.max(), sma.max()))
        if hi == lo:
            hi = lo + 1
        px_w, px_h = cw * 2, ch * 4

        def to_px(series: pd.Series) -> list[tuple[int, int]]:
            n = len(series)
            pts = []
            for i, v in enumerate(series):
                if v != v:
                    continue
                x = int(i / max(n - 1, 1) * (px_w - 1))
                y = int((hi - v) / (hi - lo) * (px_h - 1))
                pts.append((x, y))
            return pts

        grid = [[0] * cw for _ in range(ch)]
        owner = [[0] * cw for _ in range(ch)]  # 1 = price, 2 = sma

        def plot(points, who):
            prev = None
            for x, y in points:
                if prev is None:
                    _set(x, y, who)
                else:
                    # connect to the previous point: step across x, filling vertical gaps
                    py = prev[1]
                    for xi in range(prev[0] + 1, x + 1):
                        yi = int(round(prev[1] + (y - prev[1]) * (xi - prev[0]) / (x - prev[0])))
                        for yy in range(min(py, yi), max(py, yi) + 1):
                            _set(xi, yy, who)
                        py = yi
                    if x == prev[0]:
                        for yy in range(min(prev[1], y), max(prev[1], y) + 1):
                            _set(x, yy, who)
                prev = (x, y)

        def _set(x, y, who):
            cx, cy = x // 2, y // 4
            if 0 <= cx < cw and 0 <= cy < ch:
                grid[cy][cx] |= _BITS[x % 2][y % 4]
                if who == 1 or owner[cy][cx] == 0:
                    owner[cy][cx] = who

        plot(to_px(sma), 2)
        plot(to_px(close), 1)
        up = close.iloc[-1] >= close.iloc[0]
        line_col = UP if up else DN

        out = Text()
        chg = close.iloc[-1] / close.iloc[0] - 1
        out.append(f" {self.title}", style=f"bold {AMBER}")
        out.append(f"  last {close.iloc[-1]:,.2f}  ", style=WHITE)
        out.append(f"{chg * 100:+.1f}% over period", style=line_col)
        out.append("   ━ price  ", style=line_col)
        out.append("━ SMA", style=BLUE)
        out.append("\n")
        for r in range(ch):
            for c in range(cw):
                bits = grid[r][c]
                if bits:
                    out.append(chr(0x2800 + bits), style=line_col if owner[r][c] == 1 else BLUE)
                else:
                    out.append("·" if (r % 4 == 0 and c % 6 == 0) else " ", style="#30363d")
            level = hi - (r + 0.5) / ch * (hi - lo)
            if r % 2 == 0 or r == ch - 1:
                out.append(f" {level:>9,.2f}", style=DIM)
            out.append("\n")
        # date axis
        idx = self.df.index
        labels = " " * cw
        n_lab = max(2, cw // 14)
        chars = list(labels)
        for k in range(n_lab):
            pos = int(k / (n_lab - 1) * (cw - 8))
            d = idx[int(k / (n_lab - 1) * (len(idx) - 1))]
            for j, chh in enumerate(f"{d:%d%b%y}"):
                if pos + j < cw:
                    chars[pos + j] = chh
        out.append("".join(chars), style=DIM)
        return out


class TickerTape(Static):
    """Continuously scrolling quote tape."""

    offset: reactive[int] = reactive(0)

    def __init__(self, **kw):
        super().__init__("", **kw)
        self._text = Text(" RXTERM · loading market data… ", style=AMBER)

    def on_mount(self) -> None:
        self.set_interval(0.12, self._tick)

    def set_quotes(self, quotes: list[tuple[str, float, float]]) -> None:
        t = Text()
        for tick, last, chg in quotes:
            t.append(f" {tick} ", style=f"bold {AMBER}")
            t.append(f"{last:,.2f} ", style=WHITE)
            arrow = "▲" if chg >= 0 else "▼"
            t.append(f"{arrow}{abs(chg) * 100:.2f}%", style=UP if chg >= 0 else DN)
            t.append("  │", style="#30363d")
        self._text = t

    def _tick(self) -> None:
        self.offset = (self.offset + 1) % max(len(self._text.plain), 1)

    def render(self) -> Text:
        w = self.size.width or 120
        base = self._text
        if len(base.plain) == 0:
            return base
        reps = (w // max(len(base.plain), 1)) + 2
        full = Text().join([base] * reps)
        return full[self.offset:self.offset + w]


class Clock(Static):
    def __init__(self, tz: ZoneInfo, **kw):
        super().__init__("", **kw)
        self.tz = tz

    def on_mount(self) -> None:
        self.set_interval(1, self._tick)
        self._tick()

    def _tick(self) -> None:
        now = datetime.now(self.tz)
        ny = datetime.now(ZoneInfo("America/New_York"))
        mins = ny.hour * 60 + ny.minute
        if ny.weekday() >= 5:
            state, col = "CLOSED", DIM
        elif 570 <= mins < 960:
            state, col = "MKT OPEN", UP
        elif 240 <= mins < 570:
            state, col = "PRE-MKT", AMBER
        elif 960 <= mins < 1200:
            state, col = "AFTER-HRS", AMBER
        else:
            state, col = "CLOSED", DIM
        t = Text()
        t.append(f"{now:%a %d %b %Y  %H:%M:%S} {now.tzname()} ", style=WHITE)
        t.append(f" {state} ", style=f"bold black on {col}")
        self.update(t)
