"""Turn the signal board into concrete, risk-tiered trade ideas.

CONSERVATIVE  large/liquid names, defined-risk vertical spreads 30–60 DTE
              (or shares), 2-ATR stops, ~2R targets.
AGGRESSIVE    SMID/high-vol names and binary catalysts, outright calls/puts
              2–6 weeks out, or long straddles into binary events with no
              directional edge.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .. import universe
from ..data.market import MarketData, OptionChain

CONSERVATIVE, AGGRESSIVE = "CONSERVATIVE", "AGGRESSIVE"


@dataclass
class Leg:
    action: str      # BUY / SELL
    kind: str        # CALL / PUT / SHARES
    strike: float | None
    expiry: date | None
    price: float     # per-share premium (mid) or share price

    def label(self) -> str:
        if self.kind == "SHARES":
            return f"{self.action} shares @ {self.price:,.2f}"
        return f"{self.action} {self.expiry:%d%b%y}".upper() + f" {self.strike:g} {self.kind} @ {self.price:,.2f}"


@dataclass
class TradeIdea:
    ticker: str
    name: str
    segment: str
    tier: str
    direction: str            # LONG / SHORT / LONG VOL
    structure: str            # e.g. "Bull Call Spread"
    legs: list[Leg]
    spot: float
    entry: float              # underlying reference level
    target: float
    stop: float
    horizon: str
    conviction: int           # 1–5
    score: float
    net_premium: float | None = None     # debit (+) per share for option structures
    max_gain: float | None = None
    max_loss: float | None = None
    breakeven: float | None = None
    breakeven_low: float | None = None
    basis: str = "underlying"     # entry/target/stop quoted on the underlying or on the option premium
    iv: float | None = None
    rv: float | None = None
    drivers: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    catalyst: str = ""
    headline: str = ""
    thesis: str = ""

    @property
    def rr(self) -> float:
        risk = abs(self.entry - self.stop)
        return abs(self.target - self.entry) / risk if risk else float("nan")

    @property
    def trade_line(self) -> str:
        return " / ".join(l.label() for l in self.legs)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rr"] = round(self.rr, 2) if self.rr == self.rr else None
        d["trade_line"] = self.trade_line
        return d


# ── option helpers ─────────────────────────────────────────────────────

def _mid(row) -> float:
    bid, ask, last = float(row["bid"]), float(row["ask"]), float(row["last"])
    if bid > 0 and ask > 0 and ask >= bid:
        return round((bid + ask) / 2, 2)
    return round(last, 2)


def _nearest(df: pd.DataFrame, strike: float) -> pd.Series | None:
    if df is None or df.empty:
        return None
    liquid = df[(df["openInterest"] > 0) | (df["volume"] > 0)]
    pool = liquid if len(liquid) >= 3 else df
    return pool.iloc[(pool["strike"] - strike).abs().argsort().iloc[0]]


def pick_expiry(md: MarketData, ticker: str, target_dte: int, min_date: date | None = None) -> date | None:
    exps = md.expiries(ticker)
    if not exps:
        return None
    today = date.today()
    cands = [e for e in exps if (e - today).days >= 7 and (min_date is None or e >= min_date)]
    if not cands:
        cands = [e for e in exps if e > today]
    return min(cands, key=lambda e: abs((e - today).days - target_dte)) if cands else None


def atm_iv(chain: OptionChain) -> float | None:
    vals = []
    for df in (chain.calls, chain.puts):
        row = _nearest(df, chain.spot)
        if row is not None and row["iv"] == row["iv"] and 0.02 < row["iv"] < 5:
            vals.append(float(row["iv"]))
    return float(np.mean(vals)) if vals else None


def options_flow(chain: OptionChain) -> dict:
    cv, pv = chain.calls["volume"].sum(), chain.puts["volume"].sum()
    coi, poi = chain.calls["openInterest"].sum(), chain.puts["openInterest"].sum()
    return {"pc_vol": float(pv / cv) if cv else float("nan"), "pc_oi": float(poi / coi) if coi else float("nan"),
            "vol_oi": float((cv + pv) / (coi + poi)) if (coi + poi) else float("nan")}


# ── structuring ────────────────────────────────────────────────────────

def _levels(row: pd.Series, direction: str, tier: str) -> tuple[float, float, float]:
    spot, atr = float(row["last"]), float(row["atr"]) if row["atr"] == row["atr"] else float(row["last"]) * 0.03
    k_stop, r_mult = (2.0, 2.0) if tier == CONSERVATIVE else (1.75, 2.5)
    if direction == "LONG":
        stop = spot - k_stop * atr
        target = spot + r_mult * (spot - stop)
        tgt = row.get("target")
        if tier == CONSERVATIVE and tgt == tgt and tgt and spot < tgt < target:
            target = max(tgt, spot + 1.5 * (spot - stop))
    else:
        stop = spot + k_stop * atr
        target = max(spot - r_mult * (stop - spot), spot * 0.4)
    return spot, round(target, 2), round(stop, 2)


def structure_trade(md: MarketData, row: pd.Series, direction: str, tier: str, binary_vol: bool = False) -> dict:
    """Pick concrete option legs. Falls back to shares when chains are unavailable."""
    t = row.name
    spot, target, stop = _levels(row, "SHORT" if direction == "SHORT" else "LONG", tier)
    out = {"spot": spot, "entry": round(spot, 2), "target": target, "stop": stop}

    cat_date = row.get("cat_date")
    min_exp = cat_date + timedelta(days=3) if (isinstance(cat_date, date) and tier == AGGRESSIVE
                                               and row.get("cat_days", 999) <= 45) else None
    target_dte = 45 if tier == CONSERVATIVE else 30
    exp = pick_expiry(md, t, target_dte, min_exp)
    chain = md.option_chain(t, exp) if exp else None
    if chain is None or chain.calls.empty or chain.puts.empty:
        return _shares(out, direction)

    iv = atm_iv(chain)
    out["iv"] = iv
    out["flow"] = options_flow(chain)
    horizon = f"{chain.dte} days (exp {chain.expiry:%d %b})"

    if direction == "LONG VOL" or binary_vol:
        c = _nearest(chain.calls, spot)
        p = _nearest(chain.puts, float(c["strike"])) if c is not None else None
        if not (_usable(c, spot, spot, 0.06) and _usable(p, spot, spot, 0.06)):
            return _shares(out, "LONG")
        cm, pm = _mid(c), _mid(p)
        debit = cm + pm
        k = float(c["strike"])
        out.update(structure="Long Straddle", direction="LONG VOL",
                   legs=[Leg("BUY", "CALL", k, chain.expiry, cm), Leg("BUY", "PUT", k, chain.expiry, pm)],
                   net_premium=round(debit, 2), max_loss=round(debit, 2), max_gain=None,
                   breakeven=round(k + debit, 2), breakeven_low=round(k - debit, 2), horizon=horizon,
                   basis="premium", entry=round(debit, 2), target=round(debit * 1.6, 2), stop=round(debit * 0.5, 2),
                   implied_move=debit / spot if spot else None)
        return out

    if tier == CONSERVATIVE:
        if direction == "LONG":
            lo = _nearest(chain.calls, spot)
            if not _usable(lo, spot, spot, 0.06):
                return _shares(out, direction)
            hi = _nearest(chain.calls[chain.calls["strike"] > float(lo["strike"])], target)
            if hi is None or _mid(lo) - _mid(hi) <= 0:
                return _outright(out, chain, "CALL", spot, horizon)
            debit = round(max(_mid(lo) - _mid(hi), 0.01), 2)
            width = float(hi["strike"] - lo["strike"])
            out.update(structure="Bull Call Spread",
                       legs=[Leg("BUY", "CALL", float(lo["strike"]), chain.expiry, _mid(lo)),
                             Leg("SELL", "CALL", float(hi["strike"]), chain.expiry, _mid(hi))],
                       net_premium=debit, max_loss=debit, max_gain=round(width - debit, 2),
                       breakeven=round(float(lo["strike"]) + debit, 2), horizon=horizon)
        else:
            hi = _nearest(chain.puts, spot)
            if not _usable(hi, spot, spot, 0.06):
                return _shares(out, direction)
            lo = _nearest(chain.puts[chain.puts["strike"] < float(hi["strike"])], target)
            if lo is None or _mid(hi) - _mid(lo) <= 0:
                return _outright(out, chain, "PUT", spot, horizon)
            debit = round(max(_mid(hi) - _mid(lo), 0.01), 2)
            width = float(hi["strike"] - lo["strike"])
            out.update(structure="Bear Put Spread",
                       legs=[Leg("BUY", "PUT", float(hi["strike"]), chain.expiry, _mid(hi)),
                             Leg("SELL", "PUT", float(lo["strike"]), chain.expiry, _mid(lo))],
                       net_premium=debit, max_loss=debit, max_gain=round(width - debit, 2),
                       breakeven=round(float(hi["strike"]) - debit, 2), horizon=horizon)
        return out

    return _outright(out, chain, "CALL" if direction == "LONG" else "PUT", spot, horizon)


def _shares(out: dict, direction: str) -> dict:
    out.update(structure="Shares" if direction != "SHORT" else "Short Shares",
               legs=[Leg("BUY" if direction != "SHORT" else "SELL SHORT", "SHARES", None, None, round(out["spot"], 2))],
               horizon="2–6 weeks", net_premium=None, max_gain=None, max_loss=None, breakeven=None)
    return out


def _usable(row, spot: float, want: float, tol: float = 0.12) -> bool:
    """Strike close enough to what we asked for, with a real two-sided price."""
    return row is not None and abs(float(row["strike"]) - want) <= tol * spot and _mid(row) >= 0.05


def _outright(out: dict, chain: OptionChain, kind: str, spot: float, horizon: str) -> dict:
    df = chain.calls if kind == "CALL" else chain.puts
    otm = spot * (1.04 if kind == "CALL" else 0.96)
    row = _nearest(df, otm)
    if not _usable(row, spot, otm):
        return _shares(out, "LONG" if kind == "CALL" else "SHORT")
    prem = _mid(row)
    k = float(row["strike"])
    out.update(structure=f"Long {kind.title()}", legs=[Leg("BUY", kind, k, chain.expiry, prem)],
               net_premium=prem, max_loss=prem, max_gain=None,
               breakeven=round(k + prem if kind == "CALL" else k - prem, 2), horizon=horizon)
    return out


# ── idea selection ─────────────────────────────────────────────────────

def _fmt_pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def drivers_for(row: pd.Series, direction: str) -> list[str]:
    d: list[str] = []
    if row["chg3m"] == row["chg3m"]:
        d.append(f"3M {_fmt_pct(row['chg3m'])} vs XBI {_fmt_pct(row['chg3m'] - row['rs3m'])} (RS {_fmt_pct(row['rs3m'])})")
    if row["dist50"] == row["dist50"] and row["dist200"] == row["dist200"]:
        pos50 = "above" if row["dist50"] > 0 else "below"
        pos200 = "above" if row["dist200"] > 0 else "below"
        d.append(f"Trading {pos50} 50-DMA ({_fmt_pct(row['dist50'])}) and {pos200} 200-DMA ({_fmt_pct(row['dist200'])})")
    if row["rsi"] == row["rsi"]:
        tag = " — oversold" if row["rsi"] < 32 else " — overbought" if row["rsi"] > 70 else ""
        d.append(f"RSI(14) {row['rsi']:.0f}{tag}")
    if row.get("news_count", 0):
        tone = "positive" if row["news_score"] > 0.15 else "negative" if row["news_score"] < -0.15 else "mixed"
        d.append(f"Newsflow {tone} ({int(row['news_count'])} items, score {row['news_score']:+.2f})"
                 + (f": “{row['headline'][:90]}”" if row.get("headline") else ""))
    if row["target_upside"] == row["target_upside"]:
        d.append(f"Street target ${row['target']:,.2f} ({_fmt_pct(row['target_upside'])}, {row['rec'].replace('_', ' ')})")
    if row["vol_ratio"] == row["vol_ratio"] and row["vol_ratio"] >= 1.5:
        d.append(f"Volume {row['vol_ratio']:.1f}× 20-day average")
    if row["short_float"] == row["short_float"] and row["short_float"] > 0.10:
        d.append(f"Short interest {row['short_float'] * 100:.1f}% of float")
    if row.get("cat_type"):
        d.append(f"{row['cat_type']} in {int(row['cat_days'])}d: {row['cat_event'][:90]}")
    if row["earn_days"] == row["earn_days"] and row["earn_days"] <= 30:
        d.append(f"Earnings in {int(row['earn_days'])}d ({row['earn_date']:%b %d})")
    return d


def risks_for(row: pd.Series, direction: str, tier: str, structure: str) -> list[str]:
    r: list[str] = []
    if row.get("cat_type") and row["cat_days"] <= 60:
        r.append(f"Binary {row['cat_type']} event in {int(row['cat_days'])}d can gap the stock through stops")
    if row["earn_days"] == row["earn_days"] and row["earn_days"] <= 30:
        r.append(f"Earnings on {row['earn_date']:%b %d} inside the trade window")
    if direction == "SHORT" and row["short_float"] == row["short_float"] and row["short_float"] > 0.08:
        r.append(f"Crowded short ({row['short_float'] * 100:.0f}% SI) — squeeze risk on any good news")
    if direction == "SHORT":
        r.append("M&A optionality: biopharma takeouts typically carry 40–100% premiums")
    if direction == "LONG" and row["segment"] in (universe.BIG_PHARMA, universe.SPEC):
        r.append("Drug-pricing policy (MFN / IRA negotiation / tariffs) headline risk")
    if direction == "LONG" and row["segment"] == universe.MID_BIO:
        r.append("Dilution risk — SMID biotechs frequently raise equity into strength")
    if "Long" in structure and tier == AGGRESSIVE:
        r.append("Long premium decays daily; IV crush after the catalyst")
    if row["rv20"] == row["rv20"] and row["rv20"] > 0.6:
        r.append(f"High realized vol ({row['rv20'] * 100:.0f}%) — size accordingly")
    r.append("Sector beta: XBI/IBB macro and rate sensitivity")
    return r[:4]


def _conviction(score: float, news_count: int, has_cat: bool) -> int:
    c = 1 + int(score >= 70) + int(score >= 82) + int(score >= 92)
    c += int(news_count > 0 and score >= 75)
    return max(1, min(5, c))


def _pick(df: pd.DataFrame, col: str, n: int, taken: set[str]) -> list[str]:
    picks = []
    for t in df.sort_values(col, ascending=False).index:
        if t not in taken:
            picks.append(t)
            taken.add(t)
        if len(picks) >= n:
            break
    return picks


def generate(board: pd.DataFrame, md: MarketData, n_each: int = 3) -> list[TradeIdea]:
    eq = board[(board["segment"] != universe.ETF) & board["long_score"].notna()].copy()
    if eq.empty:
        return []
    mcap = eq["mcap"].fillna(0)
    big = eq["segment"].isin([universe.BIG_PHARMA, universe.LARGE_BIO, universe.SPEC])
    cons_pool = eq[big & ((mcap >= 10e9) | (mcap == 0)) & (eq["dollar_vol"] >= 40e6) & (eq["rv20"].fillna(1) < 0.50)]
    aggr_pool = eq[(eq["dollar_vol"] >= 8e6) & ((eq["rv20"].fillna(0) >= 0.35) | (eq["cat_days"].fillna(999) <= 45)
                                                 | (eq["segment"] == universe.MID_BIO))]

    taken: set[str] = set()
    specs: list[tuple[str, str, str, bool]] = []   # (ticker, tier, direction, binary_vol)

    # Conservative: 2 longs + 1 short (if a real short setup exists, else 3 longs)
    c_short = cons_pool[cons_pool["short_score"] >= 80]
    n_short = 1 if len(c_short) else 0
    for t in _pick(cons_pool, "long_raw", n_each - n_short, taken):
        specs.append((t, CONSERVATIVE, "LONG", False))
    for t in _pick(c_short, "short_raw", n_short, taken):
        specs.append((t, CONSERVATIVE, "SHORT", False))

    # Aggressive: best directional long, best directional short, best binary-catalyst vol play
    a_pool = aggr_pool[~aggr_pool.index.isin(taken)]
    binary = a_pool[(a_pool["cat_days"] <= 45) & a_pool["cat_type"].isin(["PDUFA", "ADCOM", "READOUT"])
                    & ((a_pool["mcap"].fillna(0) < 25e9))]
    for t in _pick(a_pool, "long_raw", 1, taken):
        specs.append((t, AGGRESSIVE, "LONG", False))
    a_short = a_pool[(a_pool["short_score"] >= 80) & ~a_pool.index.isin(taken)]
    for t in _pick(a_short, "short_raw", 1, taken):
        specs.append((t, AGGRESSIVE, "SHORT", False))
    if len(binary[~binary.index.isin(taken)]):
        b = binary[~binary.index.isin(taken)].copy()
        b["prio"] = -b["cat_days"] + 30 * (b["cat_type"] != "READOUT")
        for t in _pick(b, "prio", 1, taken):
            row = eq.loc[t]
            edge = max(row["long_score"], row["short_score"])
            if edge >= 85:
                specs.append((t, AGGRESSIVE, "LONG" if row["long_score"] >= row["short_score"] else "SHORT", False))
            else:
                specs.append((t, AGGRESSIVE, "LONG VOL", True))
    while sum(1 for s in specs if s[1] == AGGRESSIVE) < n_each:
        extra = _pick(a_pool, "long_raw", 1, taken)
        if not extra:
            break
        specs.append((extra[0], AGGRESSIVE, "LONG", False))

    ideas = []
    for t, tier, direction, binary_vol in specs:
        row = eq.loc[t]
        s = structure_trade(md, row, direction, tier, binary_vol)
        direction = s.pop("direction", direction)
        score = float(row["long_score"] if direction == "LONG" else row["short_score"] if direction == "SHORT"
                      else max(row["long_score"], row["short_score"]))
        cat = f"{row['cat_type']} {row['cat_date']:%b %d}: {row['cat_event']}" if row.get("cat_type") else (
            f"Earnings {row['earn_date']:%b %d}" if row["earn_days"] == row["earn_days"] and row["earn_days"] <= 45 else "")
        idea = TradeIdea(
            ticker=t, name=row["name"], segment=row["segment"], tier=tier, direction=direction,
            structure=s["structure"], legs=s["legs"], spot=s["spot"], entry=s["entry"], target=s["target"],
            stop=s["stop"], horizon=s["horizon"], conviction=_conviction(score, int(row["news_count"]), bool(cat)),
            score=score, net_premium=s.get("net_premium"), max_gain=s.get("max_gain"), max_loss=s.get("max_loss"),
            breakeven=s.get("breakeven"), breakeven_low=s.get("breakeven_low"), basis=s.get("basis", "underlying"),
            iv=s.get("iv"), rv=float(row["rv20"]) if row["rv20"] == row["rv20"] else None,
            drivers=drivers_for(row, direction), catalyst=cat,
        )
        if s.get("flow") and s["flow"]["pc_vol"] == s["flow"]["pc_vol"]:
            f = s["flow"]
            idea.drivers.append(f"Options: ATM IV {idea.iv * 100:.0f}% vs RV {idea.rv * 100:.0f}%, put/call vol {f['pc_vol']:.2f}"
                                if idea.iv and idea.rv else f"Options put/call volume {f['pc_vol']:.2f}")
        if s.get("implied_move"):
            idea.drivers.append(f"Straddle prices a ±{s['implied_move'] * 100:.1f}% move through expiry")
        idea.risks = risks_for(row, direction, tier, idea.structure)
        ideas.append(idea)
    return ideas
