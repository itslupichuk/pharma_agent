"""Preset screens over the signal board."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .. import universe


@dataclass(frozen=True)
class Screen:
    code: str
    title: str
    description: str
    filter: Callable[[pd.DataFrame], pd.Series]
    sort: str
    ascending: bool = False
    columns: tuple[str, ...] = ("last", "chg1d", "chg1m", "chg3m", "rsi", "rv20", "vol_ratio", "signal")


def _eq(b: pd.DataFrame) -> pd.Series:
    return b["segment"] != universe.ETF


SCREENS: dict[str, Screen] = {s.code: s for s in (
    Screen("TOPLONG", "Top Long Setups", "Highest composite long score (trend, momentum, news, upside).",
           lambda b: _eq(b) & (b["long_score"] >= 75), "long_score",
           columns=("last", "chg1d", "chg3m", "rs3m", "rsi", "news_score", "long_score", "signal")),
    Screen("TOPSHORT", "Top Short Setups", "Highest composite short score (downtrend, weak RS, negative news).",
           lambda b: _eq(b) & (b["short_score"] >= 75), "short_score",
           columns=("last", "chg1d", "chg3m", "rs3m", "rsi", "news_score", "short_float", "short_score")),
    Screen("MOMO", "Momentum Leaders", "Above 50/200-DMA, 3M return top quartile, RSI 50–75.",
           lambda b: _eq(b) & (b["dist50"] > 0) & (b["dist200"] > 0) & b["rsi"].between(50, 75)
           & (b["chg3m"] >= b.loc[_eq(b), "chg3m"].quantile(0.75)), "chg3m",
           columns=("last", "chg1d", "chg1m", "chg3m", "rs3m", "rsi", "dist50", "signal")),
    Screen("OVERSOLD", "Oversold Quality", "RSI < 35 on large caps still near/above the 200-DMA — mean-reversion longs.",
           lambda b: _eq(b) & (b["rsi"] < 35) & (b["dist200"] > -0.08)
           & b["segment"].isin([universe.BIG_PHARMA, universe.LARGE_BIO, universe.SPEC]), "rsi", True,
           columns=("last", "chg1d", "chg5d", "chg1m", "rsi", "dist200", "target_upside", "signal")),
    Screen("BREAKOUT", "52-Week High Breakouts", "Within 2% of 52w high on above-average volume.",
           lambda b: _eq(b) & (b["off_hi"] > -0.02) & (b["vol_ratio"] > 1.2), "vol_ratio",
           columns=("last", "chg1d", "chg1m", "off_hi", "vol_ratio", "rsi", "rv20", "signal")),
    Screen("BREAKDOWN", "Breakdowns", "Below 50 & 200-DMA, 1M return < −10% — short candidates.",
           lambda b: _eq(b) & (b["dist50"] < 0) & (b["dist200"] < 0) & (b["chg1m"] < -0.10), "chg1m", True,
           columns=("last", "chg1d", "chg1m", "chg3m", "dist200", "rsi", "short_float", "signal")),
    Screen("CATALYST", "Binary Catalysts ≤ 45d", "PDUFA, AdCom or trial readout inside 45 days.",
           lambda b: _eq(b) & (b["cat_days"] <= 45), "cat_days", True,
           columns=("last", "chg1m", "rv20", "cat_type", "cat_days", "cat_event")),
    Screen("PDUFA", "FDA Decisions ≤ 60d", "PDUFA dates and advisory committees inside 60 days.",
           lambda b: _eq(b) & b["cat_type"].isin(["PDUFA", "ADCOM"]) & (b["cat_days"] <= 60), "cat_days", True,
           columns=("last", "chg1m", "rv20", "cat_type", "cat_days", "cat_event")),
    Screen("EARNINGS", "Earnings ≤ 14d", "Reporting inside two weeks.",
           lambda b: _eq(b) & (b["earn_days"] <= 14), "earn_days", True,
           columns=("last", "chg1d", "chg1m", "rv20", "earn_days", "fwd_pe", "signal")),
    Screen("UNUSUALVOL", "Unusual Volume", "Session volume ≥ 2× the 20-day average.",
           lambda b: _eq(b) & (b["vol_ratio"] >= 2), "vol_ratio",
           columns=("last", "chg1d", "vol_ratio", "dollar_vol", "news_count", "headline")),
    Screen("SQUEEZE", "Short-Squeeze Watch", "Short interest > 15% of float with positive 1M momentum.",
           lambda b: _eq(b) & (b["short_float"] > 0.15) & (b["chg1m"] > 0), "short_float",
           columns=("last", "chg1d", "chg1m", "short_float", "vol_ratio", "rsi", "signal")),
    Screen("NEWSPOS", "Positive Newsflow", "Strongest positive recency-weighted news sentiment.",
           lambda b: _eq(b) & (b["news_score"] > 0.2) & (b["news_count"] > 0), "news_score",
           columns=("last", "chg1d", "news_score", "news_count", "news_tags", "headline")),
    Screen("NEWSNEG", "Negative Newsflow", "Strongest negative recency-weighted news sentiment.",
           lambda b: _eq(b) & (b["news_score"] < -0.2) & (b["news_count"] > 0), "news_score", True,
           columns=("last", "chg1d", "news_score", "news_count", "news_tags", "headline")),
    Screen("VALUE", "Value Pharma", "Forward P/E < 15 with Street upside > 10%.",
           lambda b: _eq(b) & (b["fwd_pe"] < 15) & (b["fwd_pe"] > 0) & (b["target_upside"] > 0.10), "target_upside",
           columns=("last", "chg3m", "fwd_pe", "target", "target_upside", "rec", "signal")),
    Screen("HIGHVOL", "Highest Realized Vol", "Top 20-day realized volatility — premium-rich names.",
           lambda b: _eq(b) & (b["rv20"] > 0), "rv20",
           columns=("last", "chg1d", "chg1m", "rv20", "atr_pct", "cat_type", "cat_days")),
)}


def run(board: pd.DataFrame, code: str, limit: int = 40) -> pd.DataFrame:
    s = SCREENS[code.upper()]
    if board.empty:
        return board
    try:
        mask = s.filter(board).fillna(False).astype(bool)
    except KeyError:
        return board.iloc[0:0]
    return board[mask].sort_values(s.sort, ascending=s.ascending).head(limit)
