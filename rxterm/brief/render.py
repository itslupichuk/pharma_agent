"""Render the morning brief as HTML (email-safe, inline styles), plain text and JSON."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import DISCLAIMER, universe
from ..analytics import screener
from ..analytics.ideas import AGGRESSIVE, CONSERVATIVE
from ..engine import Snapshot

TEMPLATES = Path(__file__).parent / "templates"
TIERS = [
    (CONSERVATIVE, "Conservative", "#1f6feb", "large-cap · defined risk · 30–60 DTE"),
    (AGGRESSIVE, "Aggressive", "#ff9e1b", "SMID / catalysts · convex · 2–6 wks"),
]
BRIEF_SCREENS = [("MOMO", "Momentum"), ("BREAKOUT", "Breakouts"), ("OVERSOLD", "Oversold quality"),
                 ("BREAKDOWN", "Breakdowns"), ("SQUEEZE", "Squeeze watch"), ("UNUSUALVOL", "Unusual volume")]


def _age(hours: float) -> str:
    return f"{int(hours * 60)}m ago" if hours < 1 else f"{int(hours)}h ago" if hours < 48 else f"{int(hours / 24)}d ago"


def _pct_html(x: float, color: bool = True) -> str:
    if x is None or x != x:
        return "—"
    c = "#0a8f4a" if x >= 0 else "#d1242f"
    return f'<span style="color:{c}">{x * 100:+.1f}%</span>' if color else f"{x * 100:+.1f}%"


def subject_for(snap: Snapshot) -> str:
    longs = [i.ticker for i in snap.ideas if i.direction == "LONG"][:3]
    shorts = [i.ticker for i in snap.ideas if i.direction == "SHORT"][:2]
    vol = [i.ticker for i in snap.ideas if i.direction == "LONG VOL"][:1]
    bits = []
    if longs:
        bits.append("Long " + " ".join(longs))
    if shorts:
        bits.append("Short " + " ".join(shorts))
    if vol:
        bits.append("Vol " + " ".join(vol))
    xbi = snap.board.loc["XBI", "chg1d"] if "XBI" in snap.board.index else float("nan")
    tag = f"XBI {xbi * 100:+.1f}%" if xbi == xbi else ""
    return f"RXTERM Pharma Brief {snap.generated_at:%a %b %d} — {' | '.join(bits) or 'No trades'}{' · ' + tag if tag else ''}"


def context(snap: Snapshot) -> dict:
    b = snap.board
    eq = b[b["segment"] != universe.ETF]
    benchmarks = [{"ticker": t, "last": b.loc[t, "last"], "chg1d": b.loc[t, "chg1d"], "chg5d": b.loc[t, "chg5d"]}
                  for t in ("XBI", "IBB", "XPH", "SPY") if t in b.index]
    for extra in ("LLY", "NVO"):
        if extra in b.index:
            benchmarks.append({"ticker": extra, "last": b.loc[extra, "last"], "chg1d": b.loc[extra, "chg1d"],
                               "chg5d": b.loc[extra, "chg5d"]})
    stories = []
    for n, it in enumerate(snap.top_news[:8]):
        stories.append({"title": it.title, "link": it.link, "source": it.source, "age": _age(it.age_hours),
                        "tickers": it.tickers, "tags": it.tags, "tone": it.tone, "take": snap.story_takes.get(n, "")})
    gainers = eq.sort_values("chg1d", ascending=False).head(5)
    losers = eq.sort_values("chg1d").head(5)
    unusual = eq[eq["vol_ratio"] > 1.0].sort_values("vol_ratio", ascending=False).head(5)
    movers = [
        ("TOP GAINERS 1D", [{"ticker": t, "value": _pct_html(r.chg1d)} for t, r in gainers.iterrows()]),
        ("TOP LOSERS 1D", [{"ticker": t, "value": _pct_html(r.chg1d)} for t, r in losers.iterrows()]),
        ("VOLUME VS 20D", [{"ticker": t, "value": f"{r.vol_ratio:.1f}×"} for t, r in unusual.iterrows()]),
    ]
    screens = []
    for code, title in BRIEF_SCREENS:
        hits = screener.run(b, code, limit=8)
        screens.append((code, title, "  ".join(hits.index)))
    segs = [(seg, r) for seg, r in snap.segments.iterrows()]
    window = [c for c in snap.calendar if c.days_out <= 30]
    binary = [c for c in window if c.type in ("PDUFA", "ADCOM", "READOUT", "CONFERENCE", "OTHER")]
    earn = [c for c in window if c.type == "EARNINGS"]
    caps = snap.board["mcap"].to_dict() if "mcap" in snap.board else {}
    earn = sorted(earn, key=lambda c: -(caps.get(c.ticker) or 0))[:10]
    trials = [c for c in window if c.type == "TRIAL"][: max(0, 22 - len(binary) - len(earn))]
    cats = sorted(binary + earn + trials, key=lambda c: c.when)
    return {
        "subject": subject_for(snap),
        "preheader": (snap.market_take[:140] + "…") if snap.market_take else "",
        "date_long": f"{snap.generated_at:%A, %d %B %Y}".upper(),
        "time_str": f"{snap.generated_at:%H:%M} {snap.generated_at.tzname() or ''}",
        "benchmarks": benchmarks,
        "market_take": snap.market_take,
        "breadth": snap.breadth,
        "tiers": TIERS,
        "ideas": snap.ideas,
        "stories": stories,
        "catalysts": cats[:24],
        "movers": movers,
        "screens": screens,
        "segments": segs,
        "as_of": snap.as_of,
        "provider": snap.provider,
        "writer": snap.writer or "RXTERM rules engine",
        "n_cov": len(eq),
        "disclaimer": DISCLAIMER,
    }


def render_html(snap: Snapshot) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    html = env.get_template("brief.html").render(**context(snap))
    # e-mail clients cap message size (Gmail clips at ~100KB): drop inter-tag whitespace
    html = re.sub(r">\s+<", "><", html)
    return re.sub(r"\n\s*", "\n", html)


def compact_html(html: str) -> str:
    """Hoist repeated inline styles into a <style> block of short classes.

    Gmail, Apple Mail and Outlook.com honour class selectors in <head><style>. The result is
    roughly half the size, which matters when the brief is passed through a mail API verbatim.
    """
    styles: dict[str, str] = {}

    def repl(m: re.Match) -> str:
        css = m.group(1)
        if css not in styles:
            styles[css] = f"s{len(styles):x}"
        return f'class="{styles[css]}"'

    body = re.sub(r'style="([^"]*)"', repl, html)
    sheet = "".join(f".{c}{{{css}}}" for css, c in styles.items())
    return body.replace("</head>", f"<style>{sheet}</style></head>", 1)


def render_text(snap: Snapshot) -> str:
    ctx = context(snap)
    L: list[str] = []
    L.append(f"RXTERM PHARMA MORNING BRIEF — {ctx['date_long']}")
    L.append("  ".join(f"{b['ticker']} {b['last']:.2f} ({b['chg1d'] * 100:+.2f}%)" for b in ctx["benchmarks"]))
    L.append("")
    L.append("THE TAKE")
    L.append(snap.market_take)
    for tier, label, _, blurb in TIERS:
        L.append("")
        L.append(f"{label.upper()} TRADES ({blurb})")
        for i in snap.ideas:
            if i.tier != tier:
                continue
            L.append(f"\n  {i.ticker} — {i.direction} — {i.structure}   conviction {i.conviction}/5")
            L.append(f"  {i.headline}")
            L.append(f"  {i.trade_line}")
            basis = "premium" if i.basis == "premium" else "underlying"
            rr = f"{i.rr:.1f}" if i.rr == i.rr else "—"
            L.append(f"  Entry {i.entry:.2f} | Target {i.target:.2f} | Stop {i.stop:.2f} ({basis}) | R:R {rr} | {i.horizon}")
            L.append(f"  {i.thesis}")
            L.append("  Risks: " + "; ".join(i.risks[:3]))
    L.append("\nTOP STORIES")
    for s in ctx["stories"]:
        L.append(f"  [{' '.join(s['tickers']) or '—'}] {s['title']} ({s['source']}, {s['age']})")
        if s["take"]:
            L.append(f"      → {s['take']}")
    L.append("\nCATALYSTS — NEXT 30 DAYS")
    for c in ctx["catalysts"]:
        L.append(f"  {c.when:%a %d %b}  {c.ticker:<5} {c.type:<8} {c.event[:80]}")
    L.append("\n" + DISCLAIMER)
    return "\n".join(L)


def _clean(o):
    if isinstance(o, float):
        return None if math.isnan(o) or math.isinf(o) else round(o, 6)
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if hasattr(o, "item"):
        return _clean(o.item())
    return o


def export_json(snap: Snapshot) -> dict:
    from ..analytics.thesis import _context

    data = _context(snap)
    data["market_take"] = snap.market_take
    data["writer"] = snap.writer
    data["subject"] = subject_for(snap)
    data["ideas"] = [{**i.to_dict(), "signals": d.get("signals")} for i, d in zip(snap.ideas, data["ideas"])]
    return _clean(data)


def write_outputs(snap: Snapshot, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "html": out_dir / "brief.html",
        "text": out_dir / "brief.txt",
        "json": out_dir / "brief.json",
        "subject": out_dir / "subject.txt",
    }
    html = render_html(snap)
    paths["html"].write_text(html, encoding="utf-8")
    paths["compact"] = out_dir / "brief_compact.html"
    paths["compact"].write_text(compact_html(html), encoding="utf-8")
    paths["text"].write_text(render_text(snap), encoding="utf-8")
    paths["json"].write_text(json.dumps(export_json(snap), indent=2, default=str), encoding="utf-8")
    paths["subject"].write_text(subject_for(snap), encoding="utf-8")
    return paths
