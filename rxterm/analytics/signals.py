"""The signal board: one row per ticker with technicals, fundamentals,
news sentiment, catalyst proximity and composite long/short scores."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from .. import universe
from ..data.catalysts import Catalyst, next_catalyst
from . import indicators as ind


def _f(v) -> float:
    try:
        return float(v) if v is not None else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def build_board(history: dict[str, pd.DataFrame], profiles: dict[str, dict],
                news_sent: dict[str, dict], calendar: list[Catalyst]) -> pd.DataFrame:
    bench = history.get(universe.SECTOR_BENCH)
    bench_3m = ind.pct(bench["Close"], 63) if bench is not None else 0.0
    bench_1m = ind.pct(bench["Close"], 21) if bench is not None else 0.0
    rows = []
    for t, df in history.items():
        sec = universe.get(t)
        if sec is None:
            continue
        c = df["Close"]
        last = float(c.iloc[-1])
        prof = profiles.get(t, {}) or {}
        ns = news_sent.get(t, {})
        cat = next_catalyst(calendar, t, ("PDUFA", "ADCOM", "READOUT"))
        earn = next_catalyst(calendar, t, ("EARNINGS",))
        sma50, sma200 = ind.sma(c, 50), ind.sma(c, 200)
        atr = ind.atr(df)
        target = _f(prof.get("targetMeanPrice"))
        pre = _f(prof.get("preMarketPrice"))
        prev_close = _f(prof.get("regularMarketPreviousClose"))
        rows.append({
            "ticker": t, "name": sec.name, "segment": sec.segment,
            "last": last,
            "chg1d": ind.pct(c, 1), "chg5d": ind.pct(c, 5), "chg1m": ind.pct(c, 21),
            "chg3m": ind.pct(c, 63), "chg6m": ind.pct(c, 126), "ytd": ind.ytd(c),
            "rsi": ind.rsi(c), "sma20": ind.sma(c, 20), "sma50": sma50, "sma200": sma200,
            "dist50": last / sma50 - 1 if sma50 == sma50 else np.nan,
            "dist200": last / sma200 - 1 if sma200 == sma200 else np.nan,
            "hi52": float(c.tail(252).max()), "lo52": float(c.tail(252).min()),
            "off_hi": last / float(c.tail(252).max()) - 1,
            "rv20": ind.realized_vol(c, 20), "atr": atr, "atr_pct": atr / last if last else np.nan,
            "vol_ratio": ind.volume_ratio(df), "dollar_vol": float((df["Close"] * df["Volume"]).tail(20).mean()),
            "rs3m": ind.pct(c, 63) - bench_3m, "rs1m": ind.pct(c, 21) - bench_1m,
            "mcap": _f(prof.get("marketCap")), "fwd_pe": _f(prof.get("forwardPE")), "beta": _f(prof.get("beta")),
            "short_float": _f(prof.get("shortPercentOfFloat")),
            "target": target, "target_upside": target / last - 1 if target == target and last else np.nan,
            "rec": prof.get("recommendationKey") or "", "analysts": prof.get("numberOfAnalystOpinions") or 0,
            "premkt": pre / prev_close - 1 if pre == pre and prev_close == prev_close and prev_close else np.nan,
            "news_score": ns.get("score", 0.0), "news_count": ns.get("count", 0),
            "news_tags": ", ".join(sorted(ns.get("tags", set()))),
            "headline": ns["top"].title if ns.get("top") else "",
            "cat_type": cat.type if cat else "", "cat_days": cat.days_out if cat else np.nan,
            "cat_event": cat.event if cat else "", "cat_date": cat.when if cat else None,
            "earn_days": earn.days_out if earn else np.nan, "earn_date": earn.when if earn else None,
            "spark": ind.sparkline(c.tail(60).tolist(), 24),
        })
    board = pd.DataFrame(rows).set_index("ticker") if rows else pd.DataFrame()
    return score(board) if not board.empty else board


def score(b: pd.DataFrame) -> pd.DataFrame:
    """Composite cross-sectional long/short scores (0–100) from factor z-scores."""
    eq = b[b["segment"] != universe.ETF].copy()
    trend = ((eq["dist50"] > 0).astype(int) + (eq["dist200"] > 0).astype(int)
             + (eq["sma50"] > eq["sma200"]).astype(int) - 1.5) / 1.5
    momentum = 0.5 * ind.zscore(eq["chg3m"]) + 0.5 * ind.zscore(eq["rs3m"])
    short_mom = ind.zscore(eq["chg1m"])
    news = eq["news_score"].clip(-1, 1) * np.minimum(eq["news_count"], 3) / 3 * 2
    upside = ind.zscore(eq["target_upside"].clip(-0.5, 1.5)).fillna(0)
    rsi = eq["rsi"].fillna(50)
    # buy the dip inside an uptrend / sell the rip inside a downtrend
    dip = ((rsi < 38) & (eq["dist200"] > -0.03)).astype(float) * 1.2
    rip = ((rsi > 65) & (eq["dist200"] < 0)).astype(float) * 1.2
    stretched = (rsi > 78).astype(float)
    washed = (rsi < 25).astype(float)
    squeeze = (eq["short_float"].fillna(0) > 0.15).astype(float)

    long_raw = 1.0 * trend + 0.9 * momentum + 0.35 * short_mom + 0.9 * news + 0.4 * upside + dip - 0.8 * stretched
    short_raw = -1.0 * trend - 0.9 * momentum - 0.35 * short_mom - 0.9 * news - 0.3 * upside + rip - 0.8 * washed - 0.6 * squeeze

    eq["f_trend"], eq["f_mom"], eq["f_news"], eq["f_upside"] = trend, momentum, news, upside
    eq["long_score"] = (long_raw.rank(pct=True) * 100).round(0)
    eq["short_score"] = (short_raw.rank(pct=True) * 100).round(0)
    eq["long_raw"], eq["short_raw"] = long_raw, short_raw
    eq["signal"] = np.select(
        [eq["long_score"] >= 85, eq["long_score"] >= 70, eq["short_score"] >= 85, eq["short_score"] >= 70],
        ["STRONG BUY", "BUY", "STRONG SELL", "SELL"], default="NEUTRAL")
    out = b.join(eq[["f_trend", "f_mom", "f_news", "f_upside", "long_score", "short_score",
                     "long_raw", "short_raw", "signal"]])
    out["signal"] = out["signal"].fillna("—")
    return out


def segment_perf(board: pd.DataFrame) -> pd.DataFrame:
    eq = board[board["segment"] != universe.ETF]
    return eq.groupby("segment")[["chg1d", "chg5d", "chg1m", "chg3m", "ytd"]].median().reindex(
        [s for s in universe.SEGMENTS if s in set(eq["segment"])])


def breadth(board: pd.DataFrame) -> dict:
    eq = board[board["segment"] != universe.ETF]
    n = len(eq) or 1
    return {
        "advancers": int((eq["chg1d"] > 0).sum()), "decliners": int((eq["chg1d"] < 0).sum()),
        "above50": float((eq["dist50"] > 0).sum() / n), "above200": float((eq["dist200"] > 0).sum() / n),
        "new_highs": int((eq["off_hi"] > -0.01).sum()), "n": n,
        "median_1d": float(eq["chg1d"].median()),
    }


def as_of(history: dict[str, pd.DataFrame]) -> date | None:
    dates = [df.index[-1].date() for df in history.values() if len(df)]
    return max(dates) if dates else None
