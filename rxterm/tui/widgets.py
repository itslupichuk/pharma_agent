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
    """Price chart in the terminal.

    * line mode: high-resolution braille line (2×4 dots per cell)
    * candle mode: one candle per column (█ body, │ wick), bars bucketed to fit the width
    * optional moving average overlay and volume pane
    * compare mode: several tickers normalised to % change from the first bar
    """

    DEFAULT_CSS = "PriceChart { height: 1fr; }"
    COMPARE_COLORS = (AMBER, BLUE, "#b38cff", "#39c5cf", UP, "#f778ba")

    def __init__(self, **kw):
        super().__init__(**kw)
        self.df: pd.DataFrame | None = None
        self.title = ""
        self.mode = "line"          # line | candle
        self.ma = 50                # 0 = off
        self.volume = True
        self.intraday = False
        self.compare: list[tuple[str, pd.Series]] = []

    def set_data(self, df: pd.DataFrame | None, title: str = "", intraday: bool = False) -> None:
        self.df, self.title, self.intraday, self.compare = df, title, intraday, []
        self.refresh()

    def set_compare(self, series: list[tuple[str, pd.Series]], title: str = "") -> None:
        self.compare, self.title, self.df = series, title, None
        self.refresh()

    # ── helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _buckets(df: pd.DataFrame, cols: int) -> pd.DataFrame:
        """Aggregate bars into at most `cols` OHLCV buckets."""
        if len(df) <= cols:
            return df
        groups = (pd.Series(range(len(df))) * cols // len(df)).values
        g = df.groupby(groups)
        out = pd.DataFrame({"Open": g["Open"].first(), "High": g["High"].max(), "Low": g["Low"].min(),
                            "Close": g["Close"].last(), "Volume": g["Volume"].sum()})
        out.index = [df.index[ix[0]] for ix in g.indices.values()]
        return out

    def _axis_labels(self, idx, width: int) -> str:
        chars = [" "] * width
        if len(idx) == 0 or width < 10:
            return "".join(chars)
        if self.intraday:
            one_day = idx[0].date() == idx[-1].date()
            fmt_ = "%H:%M" if one_day else "%a %H:%M"
        else:
            span = (idx[-1] - idx[0]).days
            fmt_ = "%b%y" if span > 900 else "%d%b%y"
        sample = f"{idx[-1]:{fmt_}}"
        n_lab = max(2, width // (len(sample) + 6))
        for k in range(n_lab):
            pos = int(k / (n_lab - 1) * (width - len(sample)))
            d = idx[int(k / (n_lab - 1) * (len(idx) - 1))]
            for j, ch in enumerate(f"{d:{fmt_}}"):
                if 0 <= pos + j < width:
                    chars[pos + j] = ch
        return "".join(chars)

    @staticmethod
    def _braille(series_list, lo, hi, cw, ch):
        """Rasterise [(values, owner_id)] into braille cells → (bits grid, owner grid)."""
        px_w, px_h = cw * 2, ch * 4
        grid = [[0] * cw for _ in range(ch)]
        owner = [[0] * cw for _ in range(ch)]

        def _set(x, y, who):
            cx, cy = x // 2, y // 4
            if 0 <= cx < cw and 0 <= cy < ch:
                grid[cy][cx] |= _BITS[x % 2][y % 4]
                owner[cy][cx] = who

        for values, who in series_list:
            n = len(values)
            prev = None
            for i, v in enumerate(values):
                if v != v:
                    prev = None
                    continue
                x = int(i / max(n - 1, 1) * (px_w - 1))
                y = int((hi - v) / (hi - lo) * (px_h - 1))
                if prev is None:
                    _set(x, y, who)
                else:
                    py = prev[1]
                    if x == prev[0]:
                        for yy in range(min(py, y), max(py, y) + 1):
                            _set(x, yy, who)
                    for xi in range(prev[0] + 1, x + 1):
                        yi = int(round(prev[1] + (y - prev[1]) * (xi - prev[0]) / (x - prev[0])))
                        for yy in range(min(py, yi), max(py, yi) + 1):
                            _set(xi, yy, who)
                        py = yi
                prev = (x, y)
        return grid, owner

    # ── render ─────────────────────────────────────────────────────────
    def render(self) -> Text:
        if self.compare:
            return self._render_compare()
        w, h = self.size.width, self.size.height
        if self.df is None or len(self.df) < 2 or w < 24 or h < 6:
            return Text("  loading chart…" if self.df is None else "  not enough data for this period", style=DIM)
        axis_w = 10
        cw = w - axis_w
        vh = 3 if (self.volume and h >= 14) else 0
        ch = h - 2 - vh - (1 if vh else 0)
        df = self.df.astype(float)
        close = df["Close"]
        ma = close.rolling(self.ma).mean() if self.ma and len(close) > self.ma else None
        lo = float(df["Low"].min() if self.mode == "candle" else close.min())
        hi = float(df["High"].max() if self.mode == "candle" else close.max())
        if ma is not None and ma.notna().any():
            lo, hi = min(lo, float(ma.min())), max(hi, float(ma.max()))
        pad = (hi - lo) * 0.03 or max(hi * 0.01, 0.01)
        lo, hi = lo - pad, hi + pad
        first, last = float(df["Open"].iloc[0] if self.intraday else close.iloc[0]), float(close.iloc[-1])
        up = last >= first
        line_col = UP if up else DN

        out = Text()
        out.append(f" {self.title}", style=f"bold {AMBER}")
        out.append(f"  {last:,.2f} ", style=f"bold {WHITE}")
        out.append(f"{(last / first - 1) * 100:+.2f}%", style=line_col)
        out.append(f"   H {df['High'].max():,.2f}  L {df['Low'].min():,.2f}", style=DIM)
        legend = f"   {'CANDLE' if self.mode == 'candle' else 'LINE'} · MA {self.ma or 'off'} · VOL {'on' if vh else 'off'}"
        out.append(legend, style="#6e7681")
        out.append("\n")

        rows: list[Text] = [Text() for _ in range(ch)]
        if self.mode == "candle":
            bars = self._buckets(df, cw)
            n = len(bars)
            colmap = {int(i * cw / n) if n < cw else i: i for i in range(n)}
            ma_grid = ma_owner = None
            if ma is not None:
                ma_b = ma.groupby((pd.Series(range(len(ma))) * min(cw, len(ma)) // len(ma)).values).last() if len(ma) > cw else ma
                ma_grid, ma_owner = self._braille([(list(ma_b.values), 2)], lo, hi, cw, ch)
            row_h = (hi - lo) / ch
            for r in range(ch):
                top, bot = hi - r * row_h, hi - (r + 1) * row_h
                for c in range(cw):
                    i = colmap.get(c)
                    if i is not None:
                        o, hh, ll, cc = bars["Open"].iloc[i], bars["High"].iloc[i], bars["Low"].iloc[i], bars["Close"].iloc[i]
                        col = UP if cc >= o else DN
                        b_top, b_bot = max(o, cc), min(o, cc)
                        if b_top >= bot and b_bot <= top:
                            rows[r].append("█" if (b_top - b_bot) >= row_h * 0.5 or (b_top >= top or b_bot <= bot) else "▬", style=col)
                            continue
                        if hh >= bot and ll <= top:
                            rows[r].append("│", style=col)
                            continue
                    if ma_grid is not None and ma_grid[r][c]:
                        rows[r].append(chr(0x2800 + ma_grid[r][c]), style=BLUE)
                    else:
                        rows[r].append("·" if (r % 4 == 0 and c % 6 == 0) else " ", style="#30363d")
            vol_cols = {c: bars["Volume"].iloc[i] for c, i in colmap.items()}
            vol_up = {c: bars["Close"].iloc[i] >= bars["Open"].iloc[i] for c, i in colmap.items()}
        else:
            series = [(list(close.values), 1)]
            if ma is not None:
                series.insert(0, (list(ma.values), 2))
            grid, owner = self._braille(series, lo, hi, cw, ch)
            for r in range(ch):
                for c in range(cw):
                    bits = grid[r][c]
                    if bits:
                        rows[r].append(chr(0x2800 + bits), style=line_col if owner[r][c] == 1 else BLUE)
                    else:
                        rows[r].append("·" if (r % 4 == 0 and c % 6 == 0) else " ", style="#30363d")
            vb = self._buckets(df, cw)
            n = len(vb)
            vol_cols = {int(i * cw / n) if n < cw else i: vb["Volume"].iloc[i] for i in range(n)}
            vol_up = {int(i * cw / n) if n < cw else i: vb["Close"].iloc[i] >= vb["Open"].iloc[i] for i in range(n)}

        for r in range(ch):
            out.append_text(rows[r])
            if r % 2 == 0 or r == ch - 1:
                out.append(f" {hi - (r + 0.5) / ch * (hi - lo):>9,.2f}", style=DIM)
            out.append("\n")

        if vh:
            out.append("─" * cw, style="#30363d")
            out.append(" VOLUME".ljust(axis_w), style="#6e7681")
            out.append("\n")
            vmax = max(vol_cols.values()) if vol_cols else 0
            levels = " ▁▂▃▄▅▆▇█"
            for r in range(vh):
                line = Text()
                for c in range(cw):
                    v = vol_cols.get(c)
                    if not v or not vmax:
                        line.append(" ")
                        continue
                    units = v / vmax * vh * 8
                    fill = units - (vh - 1 - r) * 8
                    ch_ = levels[int(max(0, min(8, fill)))]
                    line.append(ch_, style=(UP if vol_up.get(c) else DN) + " dim")
                out.append_text(line)
                if r == 0:
                    out.append(f" {vmax / 1e6:>8,.1f}M" if vmax >= 1e6 else f" {vmax:>9,.0f}", style=DIM)
                out.append("\n")
        out.append(self._axis_labels(df.index, cw), style=DIM)
        return out

    def _render_compare(self) -> Text:
        w, h = self.size.width, self.size.height
        axis_w = 9
        cw, ch = w - axis_w, h - 3
        if cw < 10 or ch < 4:
            return Text("")
        norm = []
        for label, s in self.compare:
            s = s.dropna().astype(float)
            if len(s) >= 2:
                norm.append((label, (s / s.iloc[0] - 1) * 100))
        if not norm:
            return Text("  no data to compare", style=DIM)
        idx = max((s.index for _, s in norm), key=len)
        aligned = [(lab, s.reindex(idx).ffill()) for lab, s in norm]
        lo = min(float(s.min()) for _, s in aligned)
        hi = max(float(s.max()) for _, s in aligned)
        lo, hi = min(lo, 0.0), max(hi, 0.0)
        pad = (hi - lo) * 0.05 or 1
        lo, hi = lo - pad, hi + pad
        zero = [0.0] * len(idx)
        series = [(zero, 99)] + [(list(s.values), k + 1) for k, (_, s) in enumerate(aligned)]
        grid, owner = self._braille(series, lo, hi, cw, ch)
        out = Text()
        out.append(f" {self.title}  ", style=f"bold {AMBER}")
        for k, (lab, s) in enumerate(aligned):
            col = self.COMPARE_COLORS[k % len(self.COMPARE_COLORS)]
            out.append(f"━ {lab} ", style=f"bold {col}")
            out.append(f"{s.iloc[-1]:+.1f}%   ", style=UP if s.iloc[-1] >= 0 else DN)
        out.append("\n")
        for r in range(ch):
            for c in range(cw):
                bits = grid[r][c]
                o = owner[r][c]
                if bits:
                    col = "#30363d" if o == 99 else self.COMPARE_COLORS[(o - 1) % len(self.COMPARE_COLORS)]
                    out.append(chr(0x2800 + bits), style=col)
                else:
                    out.append(" ")
            if r % 2 == 0 or r == ch - 1:
                out.append(f" {hi - (r + 0.5) / ch * (hi - lo):>+7.1f}%", style=DIM)
            out.append("\n")
        out.append(self._axis_labels(idx, cw), style=DIM)
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
