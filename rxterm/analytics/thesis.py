"""Thesis writing: Claude (when ANTHROPIC_API_KEY is set) or the built-in rules writer.

The Claude writer receives only the data RXTERM computed — signals, levels,
headlines, catalysts — and returns structured JSON: a market take, a one-line
headline + thesis + risks per idea, and short takes on the top stories.
Any API failure silently falls back to the rules writer, so the brief always ships.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from .ideas import AGGRESSIVE, CONSERVATIVE, TradeIdea

if TYPE_CHECKING:
    from ..engine import Snapshot

log = logging.getLogger(__name__)


def _p(x: float | None, digits: int = 1) -> str:
    return "n/a" if x is None or x != x else f"{x * 100:+.{digits}f}%"


# ── Rules-based writer ─────────────────────────────────────────────────

def rules_thesis(idea: TradeIdea, row) -> tuple[str, str]:
    t = idea.ticker
    trend_up = row["dist50"] > 0 and row["dist200"] > 0
    trend_dn = row["dist50"] < 0 and row["dist200"] < 0
    parts: list[str] = []
    if idea.direction == "LONG":
        if trend_up:
            setup = f"{t} is in a confirmed uptrend, holding above its 50- and 200-day averages"
        elif row["rsi"] < 38:
            setup = f"{t} has pulled back to oversold (RSI {row['rsi']:.0f}) while the longer-term trend is intact"
        else:
            setup = f"{t} is turning higher with improving relative strength"
        parts.append(f"{setup}; shares are {_p(row['chg3m'])} over 3M ({row['rs3m'] * 100:+.1f} pts vs XBI).")
        headline = f"{t}: {'trend continuation' if trend_up else 'mean-reversion'} long"
    elif idea.direction == "SHORT":
        setup = (f"{t} is in a persistent downtrend below its 50- and 200-day averages" if trend_dn
                 else f"{t} is losing momentum and lagging the group")
        parts.append(f"{setup}; shares are {_p(row['chg3m'])} over 3M ({row['rs3m'] * 100:+.1f} pts vs XBI).")
        headline = f"{t}: relative-weakness short"
    else:
        parts.append(f"{t} faces a binary {row['cat_type']} event in {int(row['cat_days'])} days "
                     f"({row['cat_event'][:80]}) without a clear directional edge in our signals.")
        headline = f"{t}: long volatility into {row['cat_type']}"

    if row.get("news_count", 0):
        tone = "supportive" if row["news_score"] > 0.15 else "negative" if row["news_score"] < -0.15 else "mixed"
        parts.append(f"Newsflow is {tone}" + (f" — latest: “{row['headline'][:100]}”." if row.get("headline") else "."))
    if row["target_upside"] == row["target_upside"] and idea.direction == "LONG" and row["target_upside"] > 0.05:
        parts.append(f"The Street's ${row['target']:,.0f} mean target implies {_p(row['target_upside'], 0)} upside.")
    if idea.catalyst and idea.direction != "LONG VOL":
        parts.append(f"Next catalyst: {idea.catalyst[:100]}.")

    if idea.structure in ("Bull Call Spread", "Bear Put Spread"):
        parts.append(f"We express it through a defined-risk {idea.structure.lower()} for {idea.net_premium:.2f} "
                     f"(max gain {idea.max_gain:.2f}, {idea.max_gain / idea.max_loss:.1f}:1), breakeven {idea.breakeven:,.2f}.")
    elif idea.structure.startswith("Long ") and idea.structure != "Long Straddle":
        parts.append(f"Outright {idea.legs[0].kind.lower()}s at {idea.legs[0].strike:g} for {idea.net_premium:.2f} "
                     f"give convex exposure; breakeven {idea.breakeven:,.2f}.")
    elif idea.structure == "Long Straddle":
        parts.append(f"The {idea.legs[0].strike:g} straddle costs {idea.net_premium:.2f} "
                     f"(breakevens {idea.breakeven_low:,.2f} / {idea.breakeven:,.2f}); biotech binary events "
                     f"frequently move more than options imply.")
    if idea.basis == "underlying":
        parts.append(f"Risk is managed against the underlying: target {idea.target:,.2f}, stop {idea.stop:,.2f} on a closing basis.")
    else:
        parts.append(f"Take profits at {idea.target:.2f} premium; cut at {idea.stop:.2f}.")
    return headline, " ".join(parts)


def rules_market_take(snap: "Snapshot") -> str:
    b = snap.board
    br = snap.breadth
    def chg(t, col="chg1d"):
        return b.loc[t, col] if t in b.index else float("nan")
    lead = b[b["segment"] != "ETF"].sort_values("chg1d", ascending=False)
    ups = ", ".join(f"{t} {_p(r.chg1d)}" for t, r in lead.head(3).iterrows())
    downs = ", ".join(f"{t} {_p(r.chg1d)}" for t, r in lead.tail(3).iloc[::-1].iterrows())
    xbi, spy, xph = chg("XBI"), chg("SPY"), chg("XPH")
    rel = "outperformed" if xbi > spy else "lagged"
    tone = "risk-on" if br["above50"] > 0.6 else "defensive" if br["above50"] < 0.4 else "mixed"
    neg = [i for i in snap.top_news[:8] if i.sentiment < -0.3]
    pos = [i for i in snap.top_news[:8] if i.sentiment > 0.3]
    txt = (f"Biotech {rel} the tape last session: XBI {_p(xbi)} vs SPY {_p(spy)}, with pharma (XPH) {_p(xph)}. "
           f"Breadth across our {br['n']}-name coverage was {br['advancers']}/{br['decliners']} up/down, and "
           f"{br['above50'] * 100:.0f}% of names sit above their 50-day — a {tone} backdrop. "
           f"Leaders: {ups}. Laggards: {downs}.")
    if pos:
        txt += f" Constructive headlines: {pos[0].title[:110]}."
    if neg:
        txt += f" On the tape for risk: {neg[0].title[:110]}."
    near = [c for c in snap.calendar if c.type in ("PDUFA", "ADCOM") and 0 <= c.days_out <= 14]
    if near:
        txt += " FDA calendar next 2 weeks: " + "; ".join(f"{c.ticker} {c.type} {c.when:%b %d}" for c in near[:4]) + "."
    return txt


# ── Claude writer ──────────────────────────────────────────────────────

SYSTEM = """You are the senior biopharma equity analyst and derivatives strategist on a top-tier \
healthcare hedge fund desk. Each morning you write the RXTERM pharma brief that portfolio managers \
read before the open.

Write like a sell-side morning note: dense, specific, numerate, no filler, no hype. Lead with what \
matters for P&L. Use tickers. Express conviction plainly and name what would make you wrong.

Ground every number, date and event in the data supplied. You may draw on well-established \
background about a company's marketed drugs, pipeline and competitive landscape, but never invent \
prices, dates, trial results or events that are not in the data. If the data is thin, say less."""

SCHEMA = {
    "type": "object",
    "properties": {
        "market_take": {"type": "string", "description": "4–6 sentence lead paragraph on the sector setup today."},
        "ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "headline": {"type": "string", "description": "≤ 12 words, desk-style, e.g. 'LLY: buy the orforglipron dip into Q3'"},
                    "thesis": {"type": "string", "description": "3–5 sentences: setup, why now, catalyst path, why this structure."},
                    "risks": {"type": "array", "items": {"type": "string"}, "description": "2–3 specific risks."},
                },
                "required": ["ticker", "headline", "thesis", "risks"],
                "additionalProperties": False,
            },
        },
        "top_stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "take": {"type": "string", "description": "One sentence: so-what for the stock / sector."},
                },
                "required": ["index", "take"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["market_take", "ideas", "top_stories"],
    "additionalProperties": False,
}


def _context(snap: "Snapshot") -> dict:
    b = snap.board

    def row(t):
        r = b.loc[t]
        keys = ["name", "segment", "last", "chg1d", "chg5d", "chg1m", "chg3m", "ytd", "rs3m", "rsi", "dist50",
                "dist200", "rv20", "vol_ratio", "mcap", "fwd_pe", "short_float", "target", "target_upside", "rec",
                "news_score", "news_count", "cat_type", "cat_days", "cat_event", "earn_days", "long_score", "short_score"]
        out = {}
        for k in keys:
            v = r.get(k)
            if hasattr(v, "item"):
                v = v.item()
            if isinstance(v, float):
                v = None if v != v else round(v, 4)
            out[k] = v
        return out

    return {
        "date": snap.generated_at.strftime("%A %d %B %Y"),
        "data_as_of": str(snap.as_of),
        "benchmarks": {t: row(t) for t in ("XBI", "IBB", "XPH", "SPY") if t in b.index},
        "breadth": snap.breadth,
        "segment_median_returns": json.loads(snap.segments.round(4).to_json()) if not snap.segments.empty else {},
        "ideas": [{**i.to_dict(), "signals": row(i.ticker)} for i in snap.ideas],
        "top_stories": [{"index": n, "title": i.title, "source": i.source, "tickers": i.tickers, "tags": i.tags,
                         "sentiment": round(i.sentiment, 2), "hours_ago": round(i.age_hours, 1)}
                        for n, i in enumerate(snap.top_news[:12])],
        "catalysts_next_30d": [{"ticker": c.ticker, "date": str(c.when), "type": c.type, "event": c.event}
                               for c in snap.calendar if c.days_out <= 30][:30],
    }


def claude_write(snap: "Snapshot", api_key: str, model: str) -> bool:
    try:
        import anthropic
    except ImportError:
        return False
    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        "Here is today's RXTERM data (JSON). Write the morning note content.\n\n"
        "- market_take: the lead paragraph.\n"
        "- ideas: one entry per idea, same tickers, same order. The tier, direction, structure, strikes and levels "
        "are fixed by the risk engine — explain and sharpen them, do not change them.\n"
        "- top_stories: a one-sentence so-what for the 6 most market-moving stories (by index).\n\n"
        + json.dumps(_context(snap), default=str)
    )
    try:
        resp = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIError as exc:
        log.warning("Claude thesis writer failed (%s); using rules writer", exc)
        return False
    if resp.stop_reason in ("refusal", "max_tokens"):
        log.warning("Claude thesis writer stopped with %s; using rules writer", resp.stop_reason)
        return False
    text = next((blk.text for blk in resp.content if blk.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False
    apply_theses(snap, data)
    snap.writer = f"Claude ({resp.model})"
    return True


def apply_theses(snap: "Snapshot", data: dict) -> None:
    """Merge externally-written thesis JSON (same shape as SCHEMA) into the snapshot."""
    by_ticker = {d.get("ticker", "").upper(): d for d in data.get("ideas", [])}
    for idea in snap.ideas:
        d = by_ticker.get(idea.ticker)
        if not d:
            continue
        idea.headline = d.get("headline") or idea.headline
        idea.thesis = d.get("thesis") or idea.thesis
        if d.get("risks"):
            idea.risks = list(d["risks"])[:4]
    if data.get("market_take"):
        snap.market_take = data["market_take"]
    for st in data.get("top_stories", []):
        i = st.get("index")
        if isinstance(i, int) and 0 <= i < len(snap.top_news):
            snap.story_takes[i] = st.get("take", "")


def write_all(snap: "Snapshot", api_key: str = "", model: str = "claude-opus-5-5", use_claude: bool = True) -> None:
    for idea in snap.ideas:
        idea.headline, idea.thesis = rules_thesis(idea, snap.board.loc[idea.ticker])
    snap.market_take = rules_market_take(snap)
    snap.writer = "RXTERM rules engine"
    if use_claude and api_key and snap.ideas:
        claude_write(snap, api_key, model)


__all__ = ["write_all", "apply_theses", "rules_thesis", "CONSERVATIVE", "AGGRESSIVE"]
