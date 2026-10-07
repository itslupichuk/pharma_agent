"""Technical indicators on daily OHLCV frames."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def pct(close: pd.Series, n: int) -> float:
    if len(close) <= n:
        return float("nan")
    return float(close.iloc[-1] / close.iloc[-1 - n] - 1)


def ytd(close: pd.Series) -> float:
    this_year = close[close.index.year == close.index[-1].year]
    prior = close[close.index.year < close.index[-1].year]
    base = prior.iloc[-1] if len(prior) else this_year.iloc[0]
    return float(close.iloc[-1] / base - 1)


def sma(close: pd.Series, n: int) -> float:
    return float(close.tail(n).mean()) if len(close) >= n else float("nan")


def rsi(close: pd.Series, n: int = 14) -> float:
    if len(close) < n + 1:
        return float("nan")
    delta = close.diff().dropna()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] > 0 else float("inf")
    return float(100 - 100 / (1 + rs))


def atr(df: pd.DataFrame, n: int = 14) -> float:
    if len(df) < n + 1:
        return float("nan")
    prev = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - prev).abs(), (df["Low"] - prev).abs()], axis=1).max(axis=1)
    return float(tr.tail(n).mean())


def realized_vol(close: pd.Series, n: int = 20) -> float:
    r = np.log(close).diff().dropna().tail(n)
    return float(r.std() * math.sqrt(252)) if len(r) >= max(5, n // 2) else float("nan")


def volume_ratio(df: pd.DataFrame, n: int = 20) -> float:
    v = df["Volume"]
    if len(v) < n + 1:
        return float("nan")
    base = v.iloc[-n - 1:-1].mean()
    return float(v.iloc[-1] / base) if base > 0 else float("nan")


def max_drawdown(close: pd.Series) -> float:
    peak = close.cummax()
    return float((close / peak - 1).min())


def zscore(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    sd = s.std()
    if not sd or np.isnan(sd):
        return s * 0
    return ((s - s.mean()) / sd).clip(-3, 3).fillna(0)


def sparkline(values, width: int = 20) -> str:
    """Unicode block sparkline."""
    blocks = "▁▂▃▄▅▆▇█"
    vals = [float(v) for v in values if v == v]
    if not vals:
        return ""
    if len(vals) > width:
        step = len(vals) / width
        vals = [vals[int(i * step)] for i in range(width)]
    lo, hi = min(vals), max(vals)
    rng = hi - lo or 1
    return "".join(blocks[min(7, int((v - lo) / rng * 7.999))] for v in vals)
