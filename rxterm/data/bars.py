"""Chart timeframes: which bars to fetch for each period button."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .market import MarketData


@dataclass(frozen=True)
class Timeframe:
    code: str
    label: str
    period: str          # provider period
    interval: str        # provider interval
    days: int | None     # slice of the cached 1y daily history (None = fetch)

    @property
    def intraday(self) -> bool:
        return self.interval.endswith("m")


TIMEFRAMES: list[Timeframe] = [
    Timeframe("1D", "1 day · 5-min bars", "1d", "5m", None),
    Timeframe("5D", "5 days · 30-min bars", "5d", "30m", None),
    Timeframe("1M", "1 month · daily", "1mo", "1d", 21),
    Timeframe("3M", "3 months · daily", "3mo", "1d", 63),
    Timeframe("6M", "6 months · daily", "6mo", "1d", 126),
    Timeframe("YTD", "year to date · daily", "ytd", "1d", -1),
    Timeframe("1Y", "1 year · daily", "1y", "1d", 252),
    Timeframe("2Y", "2 years · daily", "2y", "1d", None),
    Timeframe("5Y", "5 years · weekly", "5y", "1wk", None),
    Timeframe("10Y", "10 years · weekly", "10y", "1wk", None),
]
TF = {t.code: t for t in TIMEFRAMES}
ALIASES = {"MAX": "10Y", "1W": "5D", "5Y.": "5Y", "1MO": "1M", "3MO": "3M", "6MO": "6M", "12M": "1Y"}
DIGIT_KEYS = {"1": "1D", "2": "5D", "3": "1M", "4": "3M", "5": "6M", "6": "YTD", "7": "1Y", "8": "2Y",
              "9": "5Y", "0": "10Y"}


def resolve(code: str) -> str | None:
    code = code.upper()
    code = ALIASES.get(code, code)
    return code if code in TF else None


def step(code: str, delta: int) -> str:
    codes = [t.code for t in TIMEFRAMES]
    i = codes.index(code) if code in codes else codes.index("6M")
    return codes[max(0, min(len(codes) - 1, i + delta))]


def from_daily(daily: pd.DataFrame | None, tf: Timeframe) -> pd.DataFrame | None:
    """Slice the already-loaded 1y daily history when it covers the timeframe."""
    if daily is None or tf.days is None:
        return None
    if tf.days == -1:
        return daily[daily.index.year == daily.index[-1].year]
    return daily.tail(tf.days + 1)


def get_bars(md: MarketData, ticker: str, code: str, daily: pd.DataFrame | None = None) -> pd.DataFrame | None:
    tf = TF[code]
    sliced = from_daily(daily, tf)
    if sliced is not None and len(sliced) >= 3:
        return sliced
    return md.bars(ticker, tf.period, tf.interval)
