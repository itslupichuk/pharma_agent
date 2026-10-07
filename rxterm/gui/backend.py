"""Data service behind the RXTERM desktop window.

Holds the engine and the live snapshot, refreshes quotes in the background, checks
price alerts, and answers small JSON requests from the window. Every method returns
plain JSON-serialisable data.
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
import webbrowser
from datetime import date, datetime
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import pandas as pd

from .. import DISCLAIMER, __version__, universe
from ..alerts import AlertBook
from ..analytics import screener
from ..analytics.ideas import AGGRESSIVE, CONSERVATIVE, atm_iv, options_flow
from ..config import Settings
from ..data import bars as tfs
from ..data.news import for_ticker
from ..engine import Engine, Snapshot

log = logging.getLogger(__name__)
NY = ZoneInfo("America/New_York")


# ── helpers ────────────────────────────────────────────────────────────
def f(x, digits: int = 4):
    """JSON-safe float (None for NaN/inf)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else round(v, digits)


def market_state(now: datetime | None = None) -> str:
    ny = (now or datetime.now(NY)).astimezone(NY)
    mins = ny.hour * 60 + ny.minute
    if ny.weekday() >= 5:
        return "CLOSED"
    if 570 <= mins < 960:
        return "OPEN"
    if 240 <= mins < 570:
        return "PRE-MARKET"
    if 960 <= mins < 1200:
        return "AFTER-HOURS"
    return "CLOSED"


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_delta(spot, strike, t_years, iv, call, r=0.04):
    if not (spot and strike and t_years > 0 and iv and iv == iv and iv > 0):
        return None
    d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    return _norm_cdf(d1) if call else _norm_cdf(d1) - 1


def _age(hours: float) -> str:
    return f"{int(hours * 60)}m" if hours < 1 else f"{int(hours)}h" if hours < 48 else f"{int(hours / 24)}d"


def _bar_time(ts, intraday: bool):
    ts = pd.Timestamp(ts)
    if intraday:  # show New York wall-clock time: encode the naive NY time as if it were UTC
        return int(ts.tz_localize(None).tz_localize("UTC").timestamp()) if ts.tzinfo is None else int(
            ts.tz_convert(NY).tz_localize(None).tz_localize("UTC").timestamp())
    return ts.strftime("%Y-%m-%d")


class Backend:
    REFRESH_OPEN, REFRESH_CLOSED = 60, 300

    def __init__(self, cfg: Settings):
        self.cfg = cfg
        cfg.ensure_home()
        self.engine = Engine(cfg)
        self.lock = threading.RLock()
        self.snap: Snapshot | None = None
        self.version = 0
        self.loading: str | None = "Starting…"
        self.from_cache = False
        self.updated: datetime | None = None
        self.error: str | None = None
        self.alerts = AlertBook(cfg.home / "alerts.json")
        self.events: list[dict] = []
        self.watch = self._load_watch()
        self.last_seen = time.time()
        self._full_running = False
        self._tnews: dict[str, tuple[float, list]] = {}

    # ── lifecycle ──────────────────────────────────────────────────────
    def start(self) -> None:
        cached = self.engine.load_snapshot()
        if cached is not None:
            self._set(cached, from_cache=True)
            self.loading = f"Showing your last session ({cached.generated_at:%a %H:%M}) · refreshing live data…"
        else:
            self.loading = "Loading live data (first launch takes ~15 seconds)…"
        self.refresh_all()
        threading.Thread(target=self._quote_loop, daemon=True, name="quotes").start()

    def refresh_all(self) -> dict:
        if self._full_running:
            return {"ok": True, "already": True}
        self._full_running = True
        threading.Thread(target=self._full_load, daemon=True, name="full-load").start()
        return {"ok": True}

    def _full_load(self) -> None:
        try:
            def progress(snap: Snapshot, msg: str) -> None:
                self.loading = msg
                if self.snap is None or not self.from_cache:
                    self._set(snap)

            snap = self.engine.load_all(progress=progress)
            self.engine.save_snapshot(snap)
            self._set(snap)
            self.loading = None
            self.error = None
        except Exception as exc:  # network trouble: keep what we have
            log.exception("full load failed")
            self.error = f"Could not refresh data: {exc}"
            self.loading = None
        finally:
            self._full_running = False

    NEWS_EVERY = 600

    def _quote_loop(self) -> None:
        last_news = time.time()
        while True:
            time.sleep(self.REFRESH_OPEN if market_state() == "OPEN" else self.REFRESH_CLOSED)
            if self.snap is None or self._full_running:
                continue
            try:
                snap = self.engine.refresh_quotes(self.snap)
                if time.time() - last_news >= self.NEWS_EVERY:
                    last_news = time.time()
                    self.engine.load_news(snap)
                    self.engine.compute(snap)
                self._set(snap)
            except Exception as exc:
                log.debug("quote refresh failed: %s", exc)

    def _set(self, snap: Snapshot, from_cache: bool = False) -> None:
        with self.lock:
            if self.snap is not None and not snap.ideas and self.snap.ideas:
                snap.ideas, snap.market_take, snap.writer = self.snap.ideas, self.snap.market_take, self.snap.writer
            self.snap = snap
            self.from_cache = from_cache
            self.version += 1
            self.updated = datetime.now(self.cfg.tz)
        self._check_alerts()

    def shutdown(self) -> None:
        if self.snap is not None and self.snap.ideas and not self.from_cache:
            self.engine.save_snapshot(self.snap)

    # ── persistence ────────────────────────────────────────────────────
    def _load_watch(self) -> list[str]:
        p = self.cfg.watchlist_path
        if p.exists():
            return [x.strip().upper() for x in p.read_text(encoding="utf-8").split() if x.strip().upper() in universe.UNIVERSE]
        return ["LLY", "NVO", "VRTX", "REGN", "MRNA", "VKTX", "MDGL", "SMMT"]

    def _save_watch(self) -> None:
        self.cfg.watchlist_path.write_text("\n".join(self.watch) + "\n", encoding="utf-8")

    @property
    def _prefs_path(self):
        return self.cfg.home / "app_prefs.json"

    def prefs(self) -> dict:
        try:
            return json.loads(self._prefs_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def set_prefs(self, **kw) -> dict:
        p = self.prefs()
        p.update(kw)
        try:
            self._prefs_path.write_text(json.dumps(p), encoding="utf-8")
        except OSError:
            pass
        return p

    # ── alerts ─────────────────────────────────────────────────────────
    def _check_alerts(self) -> None:
        b = self.snap.board if self.snap is not None else None
        if b is None or b.empty or not self.alerts.alerts:
            return
        for a, px in self.alerts.check({t: float(b.loc[t, "last"]) for t in b.index}):
            self.events.append({"ticker": a.ticker, "price": f(px, 2), "level": a.level, "op": a.op,
                                "text": f"{a.ticker} at {px:,.2f} crossed {'above' if a.op == '>' else 'below'} {a.level:,.2f}"})

    def alert_add(self, ticker: str, op: str, level: float) -> dict:
        b = self.snap.board if self.snap is not None else pd.DataFrame()
        last = float(b.loc[ticker, "last"]) if ticker in b.index else None
        a = self.alerts.add(ticker, float(level), op if op in (">", "<") else None, last)
        self._check_alerts()
        return {"ok": True, "alert": a.describe()}

    def alert_del(self, index: int) -> dict:
        i = int(index)
        if 0 <= i < len(self.alerts.alerts):
            self.alerts.alerts.pop(i)
            self.alerts.save()
        return {"ok": True}

    def pop_events(self) -> list[dict]:
        ev, self.events = self.events, []
        return ev

    # ── watchlist ──────────────────────────────────────────────────────
    def watch_toggle(self, ticker: str) -> dict:
        t = ticker.upper()
        if t in self.watch:
            self.watch.remove(t)
        elif t in universe.UNIVERSE:
            self.watch.append(t)
        self._save_watch()
        return {"ticker": t, "watch": t in self.watch}

    # ── read API ───────────────────────────────────────────────────────
    def status(self) -> dict:
        self.last_seen = time.time()
        s = self.snap
        return {"version": self.version, "ready": s is not None and not s.board.empty,
                "updated": f"{self.updated:%H:%M:%S}" if self.updated else None, "loading": self.loading,
                "error": self.error, "from_cache": self.from_cache, "market": market_state(),
                "provider": s.provider if s else "", "writer": s.writer if s else "",
                "alerts": sum(a.armed for a in self.alerts.alerts), "app_version": __version__,
                "events": self.pop_events(), "now": datetime.now(self.cfg.tz).strftime("%a %d %b %Y %H:%M:%S %Z")}

    def _row(self, t: str, r) -> dict:
        hist = self.snap.history.get(t)
        spark = []
        if hist is not None and len(hist):
            c = hist["Close"].tail(60)
            step = max(1, len(c) // 40)
            spark = [f(v, 2) for v in c.iloc[::step].tolist()]
        return {"ticker": t, "name": r["name"], "segment": r["segment"], "last": f(r["last"], 2),
                "chg1d": f(r["chg1d"]), "chg5d": f(r["chg5d"]), "chg1m": f(r["chg1m"]), "chg3m": f(r["chg3m"]),
                "ytd": f(r["ytd"]), "rsi": f(r["rsi"], 1), "rv20": f(r["rv20"]), "vol_ratio": f(r["vol_ratio"], 2),
                "signal": r.get("signal") or "", "long_score": f(r.get("long_score"), 0),
                "short_score": f(r.get("short_score"), 0), "mcap": f(r.get("mcap"), 0), "spark": spark,
                "watch": t in self.watch, "cat_type": r.get("cat_type") or "",
                "cat_days": f(r.get("cat_days"), 0), "headline": r.get("headline") or ""}

    def _ideas_brief(self) -> list[dict]:
        return [{"ticker": i.ticker, "tier": i.tier, "direction": i.direction, "structure": i.structure,
                 "conviction": i.conviction} for i in (self.snap.ideas if self.snap else [])]

    def _news_item(self, it) -> dict:
        return {"title": it.title, "source": it.source, "link": it.link, "tickers": it.tickers, "tags": it.tags,
                "tone": it.tone, "sentiment": f(it.sentiment, 2), "age": _age(it.age_hours),
                "time": it.published.astimezone(self.cfg.tz).strftime("%d %b %H:%M"), "summary": it.summary[:600]}

    def monitor(self) -> dict:
        s = self.snap
        if s is None or s.board.empty:
            return {"ready": False}
        b = s.board
        eq = b[b["segment"] != universe.ETF]
        bench = [{"ticker": t, "last": f(b.loc[t, "last"], 2), "chg1d": f(b.loc[t, "chg1d"]),
                  "chg1m": f(b.loc[t, "chg1m"]), "ytd": f(b.loc[t, "ytd"])} for t in universe.BENCHMARKS if t in b.index]
        segs = [{"segment": n, **{k: f(v) for k, v in r.items()}} for n, r in s.segments.iterrows()]
        return {"ready": True, "rows": [self._row(t, r) for t, r in eq.iterrows()], "benchmarks": bench,
                "segments": segs, "breadth": {k: f(v) for k, v in s.breadth.items()},
                "news": [self._news_item(i) for i in s.top_news[:25]], "ideas": self._ideas_brief(),
                "segments_list": list(universe.SEGMENTS)}

    def tape(self) -> list[dict]:
        s = self.snap
        if s is None or s.board.empty:
            return []
        b = s.board
        order = list(universe.BENCHMARKS) + [t for t in b.sort_values("mcap", ascending=False).index
                                             if t not in universe.BENCHMARKS]
        return [{"ticker": t, "last": f(b.loc[t, "last"], 2), "chg": f(b.loc[t, "chg1d"])} for t in order[:60]
                if t in b.index]

    def stock(self, ticker: str) -> dict:
        s = self.snap
        t = ticker.upper()
        if s is None or t not in s.board.index:
            return {"ready": False, "ticker": t}
        r = s.board.loc[t]
        prof = s.profiles.get(t, {}) or {}

        def p(x, d=1):
            v = f(x)
            return None if v is None else v

        stats = [
            ("Market cap", "big", p(r["mcap"])), ("Forward P/E", "num1", p(r["fwd_pe"])), ("Beta", "num2", p(r["beta"])),
            ("52-week low", "num2", p(r["lo52"])), ("52-week high", "num2", p(r["hi52"])), ("vs 52-week high", "pct", p(r["off_hi"])),
            ("vs 50-day avg", "pct", p(r["dist50"])), ("vs 200-day avg", "pct", p(r["dist200"])), ("RSI (14)", "rsi", p(r["rsi"])),
            ("Volatility (20d)", "pct0u", p(r["rv20"])), ("Volume vs avg", "x", p(r["vol_ratio"])),
            ("vs XBI (3 months)", "pct", p(r["rs3m"])), ("1 month", "pct", p(r["chg1m"])), ("3 months", "pct", p(r["chg3m"])),
            ("Year to date", "pct", p(r["ytd"])), ("Short interest", "pct1u", p(r["short_float"])),
            ("Street target", "num2", p(r["target"])), ("Upside to target", "pct", p(r["target_upside"])),
            ("Analyst view", "text", (r["rec"] or "—").replace("_", " ").title() + (f" ({r['analysts']})" if r["analysts"] else "")),
            ("Cash", "big", p(prof.get("totalCash"))), ("Revenue growth", "pct", p(prof.get("revenueGrowth"))),
            ("Next earnings", "text", f"{r['earn_date']:%d %b %Y} ({int(r['earn_days'])}d)" if r["earn_date"] else "—"),
            ("Next catalyst", "cat", f"{r['cat_type']} {r['cat_date']:%d %b} ({int(r['cat_days'])}d)" if r["cat_type"] else "—"),
        ]
        idea = next((i for i in s.ideas if i.ticker == t), None)
        return {
            "ready": True, "ticker": t, "name": r["name"], "segment": r["segment"], "last": f(r["last"], 2),
            "chg1d": f(r["chg1d"]), "premkt": f(r.get("premkt")), "signal": r.get("signal") or "",
            "long_score": f(r.get("long_score"), 0), "short_score": f(r.get("short_score"), 0),
            "watch": t in self.watch, "stats": [{"label": a, "fmt": b_, "value": c} for a, b_, c in stats],
            "alerts": [{"index": n, "text": a.describe(), "armed": a.armed, "level": a.level}
                       for n, a in enumerate(self.alerts.alerts)
                       if a.ticker == t],
            "news": [self._news_item(i) for i in for_ticker(s.news, t)[:30]],
            "catalyst": r.get("cat_event") or "", "summary": (prof.get("longBusinessSummary") or "")[:1200],
            "website": prof.get("website") or "", "idea": idea.to_dict() if idea else None,
        }

    def stock_news(self, ticker: str) -> dict:
        """The wire's stories for a stock, topped up from its own Yahoo feed (cached 10 min)."""
        from ..data.news import YAHOO_TICKER_FEED

        t = ticker.upper()
        have = for_ticker(self.snap.news, t) if self.snap else []
        extra: list = []
        if not self.cfg.demo and len(have) < 12:
            hit = self._tnews.get(t)
            if hit and time.time() - hit[0] < 600:
                extra = hit[1]
            else:
                try:
                    wire = self.engine.wire
                    extra = wire._fetch_feed("Yahoo Finance", YAHOO_TICKER_FEED.format(symbols=t), (t,))
                    if not extra:  # Yahoo rate-limits now and then; Google News by company name instead
                        q = quote_plus(f'"{universe.name_of(t)}" OR {t} stock')
                        extra = wire._fetch_feed("Google News", f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en")
                    extra = [i for i in extra if i.age_hours < 24 * 30]
                except Exception as exc:
                    log.debug("ticker news %s: %s", t, exc)
                self._tnews[t] = (time.time(), extra)
        seen, out = set(), []
        for i in sorted(have + extra, key=lambda i: i.published, reverse=True):
            if i.id not in seen:
                seen.add(i.id)
                out.append(i)
        return {"ticker": t, "items": [self._news_item(i) for i in out[:30]]}

    def bars(self, ticker: str, tf: str = "6M") -> dict:
        t, code = ticker.upper(), tfs.resolve(tf) or "6M"
        daily = self.snap.history.get(t) if self.snap else None
        df = tfs.get_bars(self.engine.md, t, code, daily)
        if df is None or df.empty:
            return {"ticker": t, "tf": code, "bars": [], "intraday": tfs.TF[code].intraday}
        intraday = tfs.TF[code].intraday
        out, seen = [], set()
        for ts, row in df.iterrows():
            tm = _bar_time(ts, intraday)
            if tm in seen:
                continue
            seen.add(tm)
            out.append({"time": tm, "open": f(row["Open"], 4), "high": f(row["High"], 4), "low": f(row["Low"], 4),
                        "close": f(row["Close"], 4), "volume": f(row["Volume"], 0)})
        out = [o for o in out if o["close"] is not None]
        return {"ticker": t, "tf": code, "intraday": intraday, "bars": out}

    def compare(self, tickers: list[str] | str, tf: str = "1Y") -> dict:
        if isinstance(tickers, str):
            tickers = [t for t in tickers.split(",") if t.strip()]
        code = tfs.resolve(tf) or "1Y"
        intraday = tfs.TF[code].intraday
        series = []
        for t in tickers[:6]:
            t = t.upper()
            df = tfs.get_bars(self.engine.md, t, code, self.snap.history.get(t) if self.snap else None)
            if df is None or len(df) < 2:
                continue
            c = df["Close"].astype(float)
            base = float(c.iloc[0])
            pts, seen = [], set()
            for ts, v in c.items():
                tm = _bar_time(ts, intraday)
                if tm not in seen:
                    seen.add(tm)
                    pts.append({"time": tm, "value": round((float(v) / base - 1) * 100, 3)})
            series.append({"ticker": t, "name": universe.name_of(t), "points": pts, "change": pts[-1]["value"]})
        return {"tf": code, "intraday": intraday, "series": series}

    def ideas(self) -> dict:
        s = self.snap
        if s is None:
            return {"ready": False}
        return {"ready": True, "market_take": s.market_take, "writer": s.writer,
                "ideas": [{**i.to_dict(), "legs": [l.label() for l in i.legs]} for i in s.ideas]}

    def screens(self) -> list[dict]:
        return [{"code": x.code, "title": x.title, "description": x.description} for x in screener.SCREENS.values()]

    COL_FMT = {"chg1d": "pct", "chg5d": "pct", "chg1m": "pct", "chg3m": "pct", "rs3m": "pct", "dist50": "pct",
               "dist200": "pct", "target_upside": "pct", "off_hi": "pct", "rv20": "pct0u", "short_float": "pct1u",
               "atr_pct": "pct1u", "signal": "signal", "rsi": "rsi", "cat_type": "cat", "cat_days": "int",
               "earn_days": "int", "long_score": "int", "short_score": "int", "news_count": "int", "dollar_vol": "big",
               "last": "num2", "target": "num2", "fwd_pe": "num1", "vol_ratio": "x", "news_score": "num2"}
    COL_LABEL = {"last": "Last", "chg1d": "Today", "chg5d": "5D", "chg1m": "1M", "chg3m": "3M", "rsi": "RSI",
                 "rv20": "Volatility", "vol_ratio": "Volume×", "signal": "Signal", "rs3m": "vs XBI 3M",
                 "news_score": "News score", "long_score": "Long score", "short_score": "Short score",
                 "short_float": "Short int.", "dist50": "vs 50d", "dist200": "vs 200d", "target_upside": "Upside",
                 "off_hi": "vs 52w high", "cat_type": "Type", "cat_days": "Days", "cat_event": "Event",
                 "earn_days": "Earnings in", "fwd_pe": "Fwd P/E", "dollar_vol": "$ Volume", "news_count": "# News",
                 "news_tags": "Tags", "headline": "Headline", "target": "Target", "rec": "Analysts", "atr_pct": "ATR %"}

    def screen(self, code: str) -> dict:
        s = self.snap
        sc = screener.SCREENS.get(code.upper()) or screener.SCREENS["TOPLONG"]
        if s is None:
            return {"ready": False}
        res = screener.run(s.board, sc.code, limit=80)
        cols = [{"key": c, "label": self.COL_LABEL.get(c, c), "fmt": self.COL_FMT.get(c, "text")} for c in sc.columns]
        rows = []
        for t, r in res.iterrows():
            row = {"ticker": t, "name": r["name"]}
            for c in sc.columns:
                v = r[c]
                row[c] = f(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else (v if v == v else None)
            rows.append(row)
        return {"ready": True, "code": sc.code, "title": sc.title, "description": sc.description, "columns": cols,
                "rows": rows}

    def calendar(self) -> dict:
        s = self.snap
        if s is None:
            return {"ready": False}
        b = s.board
        rows = []
        for c in s.calendar:
            r = b.loc[c.ticker] if c.ticker in b.index else None
            rows.append({"date": c.when.isoformat(), "label": f"{c.when:%a %d %b %Y}", "days": c.days_out,
                         "ticker": c.ticker, "name": universe.name_of(c.ticker), "type": c.type, "event": c.event,
                         "source": c.source, "last": f(r["last"], 2) if r is not None else None,
                         "chg1m": f(r["chg1m"]) if r is not None else None})
        return {"ready": True, "rows": rows}

    def news(self, ticker: str = "") -> dict:
        s = self.snap
        if s is None:
            return {"ready": False}
        items = for_ticker(s.news, ticker.upper()) if ticker else s.news
        return {"ready": True, "items": [self._news_item(i) for i in items[:400]]}

    def expiries(self, ticker: str) -> list[str]:
        today = date.today()
        return [e.isoformat() for e in self.engine.md.expiries(ticker.upper()) if e > today][:24]

    def chain(self, ticker: str, expiry: str = "") -> dict:
        t = ticker.upper()
        exps = self.engine.md.expiries(t)
        if not exps:
            return {"ticker": t, "ok": False, "message": "No listed options for this stock."}
        exp = date.fromisoformat(expiry) if expiry else min(exps[:24], key=lambda e: abs((e - date.today()).days - 30))
        ch = self.engine.md.option_chain(t, exp)
        if ch is None:
            return {"ticker": t, "ok": False, "expiry": exp.isoformat(),
                    "message": "The data provider returned no chain for this expiry. Try another date."}
        calls, puts = ch.calls.set_index("strike"), ch.puts.set_index("strike")
        strikes = sorted(set(calls.index) | set(puts.index))
        spot = ch.spot
        near = [k for k in strikes if 0.65 * spot <= k <= 1.35 * spot] or strikes
        atm = min(near, key=lambda k: abs(k - spot)) if near else None
        ty = max(ch.dte, 1) / 365

        def side(df, k, call):
            if k not in df.index:
                return None
            r = df.loc[k]
            if isinstance(r, pd.DataFrame):
                r = r.iloc[0]
            return {"bid": f(r["bid"], 2), "ask": f(r["ask"], 2), "last": f(r["last"], 2), "iv": f(r["iv"]),
                    "delta": f(bs_delta(spot, k, ty, r["iv"], call), 3), "vol": int(r["volume"] or 0),
                    "oi": int(r["openInterest"] or 0), "hot": bool(r["volume"] > r["openInterest"] > 0)}

        iv = atm_iv(ch)
        fl = options_flow(ch)
        rv = self.snap.board.loc[t, "rv20"] if self.snap is not None and t in self.snap.board.index else None
        return {"ticker": t, "ok": True, "expiry": ch.expiry.isoformat(), "dte": ch.dte, "spot": f(spot, 2),
                "atm_iv": f(iv), "rv20": f(rv), "implied_move": f(iv * (ch.dte / 365) ** 0.5) if iv else None,
                "pc_vol": f(fl["pc_vol"], 2), "pc_oi": f(fl["pc_oi"], 2),
                "rows": [{"strike": k, "atm": k == atm, "call": side(calls, k, True), "put": side(puts, k, False)}
                         for k in near],
                "expiries": [e.isoformat() for e in exps[:24]]}

    def watchlist(self) -> dict:
        s = self.snap
        rows = []
        if s is not None:
            for t in self.watch:
                if t in s.board.index:
                    rows.append(self._row(t, s.board.loc[t]))
        b = s.board if s is not None else pd.DataFrame()
        alerts = []
        for n, a in enumerate(self.alerts.alerts):
            px = float(b.loc[a.ticker, "last"]) if a.ticker in b.index else None
            alerts.append({"index": n, "ticker": a.ticker, "text": a.describe(), "armed": a.armed, "now": f(px, 2),
                           "away": f(a.level / px - 1) if px else None, "triggered": a.triggered.replace("T", " ")})
        return {"rows": rows, "alerts": alerts}

    def search(self, q: str = "") -> list[dict]:
        q = q.strip().upper()
        out = []
        for sec in list(universe.equities()) + [universe.UNIVERSE[t] for t in universe.BENCHMARKS]:
            if not q or sec.ticker.startswith(q) or q in sec.name.upper() or any(q in a.upper() for a in sec.aliases):
                out.append({"ticker": sec.ticker, "name": sec.name, "segment": sec.segment})
        out.sort(key=lambda x: (not x["ticker"].startswith(q), x["ticker"]) if q else (x["segment"] == "ETF", 0))
        return out

    def help(self) -> dict:
        return {"disclaimer": DISCLAIMER, "version": __version__,
                "screens": self.screens(), "home": str(self.cfg.home)}

    # ── misc ───────────────────────────────────────────────────────────
    def open_url(self, url: str) -> dict:
        if url.startswith(("http://", "https://")):
            webbrowser.open(url)
        return {"ok": True}

    def copy_text(self, text: str) -> dict:
        """Clipboard fallback when the window can't write to it directly."""
        import subprocess
        import sys

        try:
            if sys.platform == "win32":
                subprocess.run(["clip"], input=text.encode("utf-16-le"), check=False, creationflags=0x08000000)
            elif sys.platform == "darwin":
                subprocess.run(["pbcopy"], input=text.encode(), check=False)
        except OSError:
            pass
        return {"ok": True}
