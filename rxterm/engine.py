"""Orchestration: pull data, compute the board, generate ideas and theses.

Both the terminal and the morning brief consume a `Snapshot`. Loading is
staged so the terminal can paint prices first and enrich in the background.
"""

from __future__ import annotations

import logging
import pickle
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd

from . import __version__, universe
from .analytics import ideas as ideas_mod
from .analytics import signals, thesis
from .cache import Cache
from .config import Settings, settings as default_settings
from .data import catalysts as cat_mod
from .data.market import MarketData, make_market
from .data.news import NewsItem, NewsWire, ticker_sentiment

log = logging.getLogger(__name__)


@dataclass
class Snapshot:
    generated_at: datetime
    provider: str
    history: dict[str, pd.DataFrame] = field(default_factory=dict)
    profiles: dict[str, dict] = field(default_factory=dict)
    news: list[NewsItem] = field(default_factory=list)
    calendar: list[cat_mod.Catalyst] = field(default_factory=list)
    board: pd.DataFrame = field(default_factory=pd.DataFrame)
    ideas: list[ideas_mod.TradeIdea] = field(default_factory=list)
    market_take: str = ""
    story_takes: dict[int, str] = field(default_factory=dict)
    writer: str = ""

    @property
    def as_of(self) -> date | None:
        return signals.as_of(self.history)

    @property
    def segments(self) -> pd.DataFrame:
        return signals.segment_perf(self.board) if not self.board.empty else pd.DataFrame()

    @property
    def breadth(self) -> dict:
        return signals.breadth(self.board) if not self.board.empty else {}

    @property
    def top_news(self) -> list[NewsItem]:
        """Most market-relevant stories: covered tickers first, then impact × recency."""
        ranked = sorted(self.news, key=lambda i: (i.impact + (0.35 if i.tickers else 0)) * (1 if i.age_hours < 36 else 0.5),
                        reverse=True)
        out, seen_t = [], set()
        for i in ranked:
            key = tuple(i.tickers[:1]) or (i.id,)
            if key in seen_t and len(out) < 6:
                continue  # diversity: one story per lead ticker in the first page
            seen_t.add(key)
            out.append(i)
        return out


class Engine:
    def __init__(self, cfg: Settings | None = None):
        self.cfg = cfg or default_settings
        self.cfg.ensure_home()
        self.cache = Cache(None if self.cfg.demo else self.cfg.cache_path)
        self.md: MarketData = make_market(self.cache, self.cfg.demo)
        self.wire = NewsWire(self.cache, demo=self.cfg.demo)

    @property
    def tickers(self) -> list[str]:
        return list(universe.UNIVERSE)

    def new_snapshot(self) -> Snapshot:
        return Snapshot(generated_at=datetime.now(self.cfg.tz), provider=self.md.name)

    # ── stages ─────────────────────────────────────────────────────────
    def load_prices(self, snap: Snapshot) -> None:
        snap.history = self.md.history(self.tickers, "1y")

    def load_profiles(self, snap: Snapshot) -> None:
        names = [t for t in snap.history if not universe.UNIVERSE[t].is_etf] or [s.ticker for s in universe.equities()]
        snap.profiles = self.md.profiles(names)

    def load_news(self, snap: Snapshot) -> None:
        snap.news = self.wire.fetch()

    def load_calendar(self, snap: Snapshot) -> None:
        snap.calendar = cat_mod.build_calendar(snap.profiles, snap.news, self.cache, self.cfg.catalysts_path,
                                               demo=self.cfg.demo)

    def refresh_quotes(self, snap: Snapshot) -> Snapshot:
        """Splice the latest daily bars (≈1-min fresh) into the snapshot without reloading everything."""
        from dataclasses import replace as _replace

        fresh = self.md.history(list(snap.history), "5d", ttl=55)
        hist = dict(snap.history)
        for t, f in fresh.items():
            old = hist.get(t)
            if old is None or f is None or f.empty:
                continue
            hist[t] = pd.concat([old[old.index < f.index[0]], f]).tail(max(len(old), 30))
        new = _replace(snap, history=hist)
        self.compute(new)
        return new

    def compute(self, snap: Snapshot) -> None:
        snap.board = signals.build_board(snap.history, snap.profiles, ticker_sentiment(snap.news), snap.calendar)

    def make_ideas(self, snap: Snapshot, use_claude: bool = True) -> None:
        snap.ideas = ideas_mod.generate(snap.board, self.md)
        thesis.write_all(snap, self.cfg.anthropic_api_key, self.cfg.model, use_claude=use_claude)

    def load_all(self, progress=None, use_claude: bool = True) -> Snapshot:
        """Everything, with independent sources fetched in parallel (~2× faster than `full`).

        `progress(snapshot, message)` is called with usable partial snapshots as stages land.
        """
        snap = self.new_snapshot()
        with ThreadPoolExecutor(max_workers=4) as pool:
            f_prices = pool.submit(self.load_prices, snap)
            f_news = pool.submit(self.load_news, snap)
            f_prof = pool.submit(lambda: self.md.profiles([s.ticker for s in universe.equities()]))
            f_trials = None if self.cfg.demo else pool.submit(cat_mod.from_clinicaltrials, self.cache)
            f_prices.result()
            if progress:
                early = replace(snap)
                self.compute(early)
                progress(early, "Prices loaded · fetching news, fundamentals & catalysts…")
            f_news.result()
            snap.profiles = f_prof.result()
            if f_trials:
                f_trials.result()
        self.load_calendar(snap)
        self.compute(snap)
        if progress:
            progress(replace(snap), "Data loaded · building trade ideas…")
        self.make_ideas(snap, use_claude=use_claude)
        return snap

    # ── last-session cache: show something instantly on launch ───────
    SNAPSHOT_SCHEMA = 2

    @property
    def _snapshot_path(self):
        return self.cfg.home / "last_session.pkl"

    def save_snapshot(self, snap: Snapshot) -> None:
        if self.cfg.demo:
            return
        try:
            tmp = self._snapshot_path.with_suffix(".tmp")
            tmp.write_bytes(pickle.dumps((self.SNAPSHOT_SCHEMA, __version__, snap), protocol=pickle.HIGHEST_PROTOCOL))
            tmp.replace(self._snapshot_path)
        except Exception as exc:  # never let caching break the app
            log.debug("snapshot save failed: %s", exc)

    def load_snapshot(self, max_age_hours: float = 96) -> Snapshot | None:
        if self.cfg.demo:
            return None
        p = self._snapshot_path
        try:
            if not p.exists() or time.time() - p.stat().st_mtime > max_age_hours * 3600:
                return None
            schema, version, snap = pickle.loads(p.read_bytes())
            if schema != self.SNAPSHOT_SCHEMA or version != __version__ or not isinstance(snap, Snapshot):
                return None
            return snap
        except Exception as exc:
            log.debug("snapshot load failed: %s", exc)
            return None

    def full(self, ideas: bool = True, use_claude: bool = True) -> Snapshot:
        snap = self.new_snapshot()
        self.load_prices(snap)
        self.load_news(snap)
        self.load_profiles(snap)
        self.load_calendar(snap)
        self.compute(snap)
        if ideas:
            self.make_ideas(snap, use_claude=use_claude)
        return snap
