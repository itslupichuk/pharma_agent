"""Market data providers.

`MarketData` is the interface the rest of RXTERM depends on. `YahooMarketData`
is the default (free, ~15 min delayed); `DemoMarketData` generates a
deterministic synthetic market so the terminal and brief work fully offline.
A paid feed (Polygon, Tradier, IBKR…) can be added by implementing the same
five methods.
"""

from __future__ import annotations

import hashlib
import logging
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Protocol

import numpy as np
import pandas as pd

from ..cache import Cache

log = logging.getLogger(__name__)

HISTORY_TTL = 10 * 60          # daily bars refresh every 10 minutes
PROFILE_TTL = 12 * 3600        # fundamentals / calendar twice a day
OPTIONS_TTL = 15 * 60

PROFILE_FIELDS = (
    "shortName", "marketCap", "trailingPE", "forwardPE", "beta", "shortPercentOfFloat",
    "sharesShort", "shortRatio", "targetMeanPrice", "targetHighPrice", "targetLowPrice",
    "recommendationKey", "numberOfAnalystOpinions", "preMarketPrice", "preMarketChangePercent",
    "regularMarketPreviousClose", "totalCash", "totalDebt", "totalRevenue", "revenueGrowth",
    "grossMargins", "profitMargins", "freeCashflow", "enterpriseValue", "averageVolume",
    "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "dividendYield", "heldPercentInstitutions",
    "longBusinessSummary", "fullTimeEmployees", "website",
)


@dataclass
class OptionChain:
    ticker: str
    expiry: date
    spot: float
    calls: pd.DataFrame   # strike, bid, ask, last, volume, openInterest, iv
    puts: pd.DataFrame

    @property
    def dte(self) -> int:
        return max((self.expiry - date.today()).days, 0)


class MarketData(Protocol):
    name: str

    def history(self, tickers: Iterable[str], period: str = "1y") -> dict[str, pd.DataFrame]: ...
    def profile(self, ticker: str) -> dict: ...
    def profiles(self, tickers: Iterable[str]) -> dict[str, dict]: ...
    def expiries(self, ticker: str) -> list[date]: ...
    def option_chain(self, ticker: str, expiry: date) -> OptionChain | None: ...


def _norm_chain(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["strike", "bid", "ask", "last", "volume", "openInterest", "iv"])
    out = pd.DataFrame({
        "strike": df["strike"].astype(float),
        "bid": df.get("bid", 0).astype(float),
        "ask": df.get("ask", 0).astype(float),
        "last": df.get("lastPrice", 0).astype(float),
        "volume": df.get("volume", 0).fillna(0).astype(float),
        "openInterest": df.get("openInterest", 0).fillna(0).astype(float),
        "iv": df.get("impliedVolatility", np.nan).astype(float),
    })
    return out.sort_values("strike").reset_index(drop=True)


class YahooMarketData:
    """Yahoo Finance via yfinance. Delayed, unofficial, but free and broad."""

    name = "Yahoo Finance (delayed)"

    def __init__(self, cache: Cache):
        self.cache = cache
        import yfinance as yf  # imported lazily: slow import, unused in demo mode

        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
        self._yf = yf

    # ── prices ─────────────────────────────────────────────────────────
    def history(self, tickers: Iterable[str], period: str = "1y") -> dict[str, pd.DataFrame]:
        tickers = sorted({t.upper() for t in tickers})
        key = f"hist:{period}:{hashlib.md5(','.join(tickers).encode()).hexdigest()}"

        def fetch() -> dict[str, pd.DataFrame]:
            raw = self._yf.download(
                tickers, period=period, interval="1d", group_by="ticker",
                auto_adjust=True, progress=False, threads=True,
            )
            out: dict[str, pd.DataFrame] = {}
            for t in tickers:
                try:
                    df = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
                except KeyError:
                    continue
                df = df.dropna(subset=["Close"])
                if len(df) >= 30:
                    df.index = pd.to_datetime(df.index).tz_localize(None)
                    out[t] = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
            return out or None

        return self.cache.memo(key, HISTORY_TTL, fetch) or {}

    # ── fundamentals / calendar ────────────────────────────────────────
    def profile(self, ticker: str) -> dict:
        ticker = ticker.upper()

        def fetch() -> dict:
            tk = self._yf.Ticker(ticker)
            prof: dict = {}
            try:
                info = tk.info or {}
                prof = {k: info.get(k) for k in PROFILE_FIELDS}
            except Exception as exc:  # 429s / missing fields are common
                log.debug("info failed for %s: %s", ticker, exc)
            try:
                cal = tk.calendar or {}
                ed = cal.get("Earnings Date")
                if isinstance(ed, list) and ed:
                    prof["earningsDate"] = ed[0]
                elif isinstance(ed, (date, datetime)):
                    prof["earningsDate"] = ed
                prof["epsEstimate"] = cal.get("Earnings Average")
                prof["revenueEstimate"] = cal.get("Revenue Average")
            except Exception as exc:
                log.debug("calendar failed for %s: %s", ticker, exc)
            return prof or None

        return self.cache.memo(f"profile:{ticker}", PROFILE_TTL, fetch) or {}

    def profiles(self, tickers: Iterable[str]) -> dict[str, dict]:
        tickers = list(tickers)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(self.profile, tickers))
        return dict(zip(tickers, results))

    # ── options ────────────────────────────────────────────────────────
    def expiries(self, ticker: str) -> list[date]:
        def fetch():
            try:
                return [date.fromisoformat(d) for d in self._yf.Ticker(ticker).options]
            except Exception as exc:
                log.debug("expiries failed for %s: %s", ticker, exc)
                return None

        return self.cache.memo(f"exp:{ticker}", OPTIONS_TTL, fetch) or []

    def option_chain(self, ticker: str, expiry: date) -> OptionChain | None:
        def fetch():
            try:
                tk = self._yf.Ticker(ticker)
                ch = tk.option_chain(expiry.isoformat())
                spot = float(ch.underlying.get("regularMarketPrice") or 0) if getattr(ch, "underlying", None) else 0.0
                if not spot:
                    spot = float(tk.fast_info["lastPrice"])
                return OptionChain(ticker, expiry, spot, _norm_chain(ch.calls), _norm_chain(ch.puts))
            except Exception as exc:
                log.debug("chain failed for %s %s: %s", ticker, expiry, exc)
                return None

        return self.cache.memo(f"chain:{ticker}:{expiry}", OPTIONS_TTL, fetch)


# ── Demo provider ──────────────────────────────────────────────────────

def _seed(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:8], 16)


def _bs_price(spot: float, strike: float, t: float, vol: float, call: bool, r: float = 0.04) -> float:
    if t <= 0 or vol <= 0:
        return max(0.0, (spot - strike) if call else (strike - spot))
    d1 = (math.log(spot / strike) + (r + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    n = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))  # noqa: E731
    if call:
        return spot * n(d1) - strike * math.exp(-r * t) * n(d2)
    return strike * math.exp(-r * t) * n(-d2) - spot * n(-d1)


class DemoMarketData:
    """Deterministic synthetic market (seeded per ticker and per day)."""

    name = "DEMO (synthetic data)"

    _BASE = {"Big Pharma": (180, 0.24), "Large-Cap Biotech": (210, 0.38), "SMID Biotech": (38, 0.65),
             "Specialty & Generics": (24, 0.36), "ETF": (120, 0.22)}

    def __init__(self, cache: Cache | None = None):
        from .. import universe

        self._u = universe
        self._day = date.today().isoformat()

    def _params(self, ticker: str) -> tuple[float, float]:
        sec = self._u.get(ticker)
        base, vol = self._BASE.get(sec.segment if sec else "SMID Biotech", (50, 0.5))
        rng = np.random.default_rng(_seed(ticker))
        return base * float(rng.uniform(0.3, 2.5)), vol * float(rng.uniform(0.7, 1.4))

    def history(self, tickers: Iterable[str], period: str = "1y") -> dict[str, pd.DataFrame]:
        want = {"1mo": 22, "3mo": 64, "6mo": 128, "1y": 252, "2y": 504}.get(period, 252)
        days = 504  # always simulate the same path, then slice, so every period agrees on the last price
        idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
        out = {}
        for t in tickers:
            t = t.upper()
            price0, vol = self._params(t)
            rng = np.random.default_rng(_seed(t, self._day))
            drift = rng.normal(0.0003, 0.0007)
            rets = rng.normal(drift, vol / math.sqrt(252), days)
            # occasional catalyst gaps for biotech names
            gaps = rng.random(days) < (0.012 if vol > 0.5 else 0.003)
            rets[gaps] += rng.normal(0, vol * 0.35, gaps.sum())
            close = price0 * np.exp(np.cumsum(rets))
            spread = np.abs(rng.normal(0, vol / math.sqrt(252) * 0.6, days))
            high = close * (1 + spread)
            low = close * (1 - spread)
            open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.003, days))
            volume = rng.lognormal(math.log(1.5e6 if price0 > 80 else 3e6), 0.45, days)
            volume[gaps] *= 4
            out[t] = pd.DataFrame({"Open": open_, "High": np.maximum(high, open_), "Low": np.minimum(low, open_),
                                   "Close": close, "Volume": volume}, index=idx).tail(want)
        return out

    def profile(self, ticker: str) -> dict:
        t = ticker.upper()
        rng = np.random.default_rng(_seed(t, "profile"))
        price, _ = self._params(t)
        sec = self._u.get(t)
        seg = sec.segment if sec else ""
        shares = {"Big Pharma": 2.0e9, "Large-Cap Biotech": 2.0e8, "SMID Biotech": 6.0e7,
                  "Specialty & Generics": 4.0e8}.get(seg, 1e8) * rng.uniform(0.5, 2)
        days_to_earn = int(rng.integers(3, 80))
        return {
            "shortName": sec.name if sec else t,
            "marketCap": price * shares,
            "trailingPE": float(rng.uniform(12, 45)) if seg in ("Big Pharma", "Specialty & Generics") else None,
            "forwardPE": float(rng.uniform(9, 30)) if seg != "SMID Biotech" else None,
            "beta": float(rng.uniform(0.3, 1.8)),
            "shortPercentOfFloat": float(rng.uniform(0.005, 0.25 if seg == "SMID Biotech" else 0.05)),
            "targetMeanPrice": price * float(rng.uniform(0.85, 1.6)),
            "recommendationKey": str(rng.choice(["strong_buy", "buy", "buy", "hold"])),
            "numberOfAnalystOpinions": int(rng.integers(4, 30)),
            "totalCash": shares * price * float(rng.uniform(0.03, 0.4)),
            "revenueGrowth": float(rng.uniform(-0.1, 0.4)),
            "earningsDate": date.today() + timedelta(days=days_to_earn),
            "longBusinessSummary": f"{sec.name if sec else t} is a {seg.lower()} company (synthetic demo profile).",
        }

    def profiles(self, tickers: Iterable[str]) -> dict[str, dict]:
        return {t: self.profile(t) for t in tickers}

    def expiries(self, ticker: str) -> list[date]:
        today = date.today()
        fridays = [today + timedelta(days=(4 - today.weekday()) % 7 + 7 * k) for k in range(0, 9)]
        monthlies = [today + timedelta(days=30 * k) for k in (3, 4, 6, 9)]
        return sorted({d for d in fridays + monthlies if d > today})

    def option_chain(self, ticker: str, expiry: date) -> OptionChain | None:
        hist = self.history([ticker], "3mo").get(ticker.upper())
        if hist is None:
            return None
        spot = float(hist["Close"].iloc[-1])
        _, vol = self._params(ticker)
        t = max((expiry - date.today()).days, 1) / 365
        rng = np.random.default_rng(_seed(ticker, str(expiry)))
        step = 0.5 if spot < 25 else 1 if spot < 60 else 2.5 if spot < 150 else 5 if spot < 500 else 10
        strikes = np.arange(round(spot * 0.6 / step) * step, spot * 1.4 + step, step)

        def side(call: bool) -> pd.DataFrame:
            rows = []
            for k in strikes:
                iv = vol * (1 + 0.25 * abs(math.log(k / spot))) * rng.uniform(0.95, 1.08)
                mid = _bs_price(spot, k, t, iv, call)
                sprd = max(0.05, mid * 0.04)
                oi = float(rng.lognormal(6, 1.2) * math.exp(-8 * abs(math.log(k / spot))))
                rows.append({"strike": k, "bid": max(mid - sprd / 2, 0), "ask": mid + sprd / 2, "last": mid,
                             "volume": float(int(oi * rng.uniform(0.02, 0.6))), "openInterest": float(int(oi)), "iv": iv})
            return pd.DataFrame(rows)

        return OptionChain(ticker.upper(), expiry, spot, side(True), side(False))


def make_market(cache: Cache, demo: bool) -> MarketData:
    return DemoMarketData(cache) if demo else YahooMarketData(cache)
