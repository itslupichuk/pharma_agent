"""RXTERM terminal — Bloomberg-style, keyboard-driven.

Type a command in the amber command line and press <Enter> (<GO>). See HELP (F1) or
docs/USER_GUIDE.md for every command and key.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import webbrowser
from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.suggester import SuggestFromList
from textual.widgets import ContentSwitcher, DataTable, Input, OptionList, Static
from textual.widgets.option_list import Option

from .. import DISCLAIMER, __version__, universe
from ..alerts import AlertBook, parse as parse_alert
from ..analytics import screener
from ..analytics.ideas import AGGRESSIVE, CONSERVATIVE, TradeIdea
from ..config import Settings, settings as default_settings
from ..data import bars as tfs
from ..data.news import for_ticker
from ..engine import Engine, Snapshot
from . import fmt
from .fmt import AMBER, BLUE, DIM, DN, UP, WHITE
from .widgets import Clock, PriceChart, TickerTape

FUNCTIONS = ("MON", "NEWS", "SCRN", "IDEAS", "CAL", "DES", "OMON", "W", "HELP", "COMP")
FKEYS = [("F1", "HELP"), ("F2", "MON"), ("F3", "NEWS"), ("F4", "SCRN"), ("F5", "IDEAS"), ("F6", "CAL"),
         ("F7", "DES"), ("F8", "OMON"), ("F9", "W"), ("F10", "REFRESH")]
MA_CYCLE = (0, 20, 50, 200)
MON_FILTERS = {"ALL": None, "BIG": universe.BIG_PHARMA, "LARGE": universe.LARGE_BIO, "SMID": universe.MID_BIO,
               "SPEC": universe.SPEC, "W": "WATCH"}
MON_FILTER_ALIASES = {"PHARMA": "BIG", "BIGPHARMA": "BIG", "BIOTECH": "LARGE", "SMALL": "SMID", "MID": "SMID",
                      "GENERICS": "SPEC", "WATCH": "W", "WATCHLIST": "W", "*": "ALL"}
# (header, board field used for sorting)
MON_COLUMNS = [("TICKER", "_ticker"), ("NAME", "name"), ("LAST", "last"), ("CHG", "chg1d"), ("5D", "chg5d"),
               ("1M", "chg1m"), ("3M", "chg3m"), ("YTD", "ytd"), ("RSI", "rsi"), ("RV20", "rv20"),
               ("VOL×", "vol_ratio"), ("SIGNAL", "long_score"), ("60D", "chg3m")]
W_COLUMNS = [("TICKER", "_ticker"), ("NAME", "name"), ("LAST", "last"), ("CHG", "chg1d"), ("5D", "chg5d"),
             ("1M", "chg1m"), ("RSI", "rsi"), ("SIGNAL", "long_score"), ("NEXT CATALYST", "cat_days"),
             ("HEADLINE", "headline")]
CAL_COLUMNS = [("DATE", "when"), ("DAYS", "when"), ("TICKER", "ticker"), ("TYPE", "type"), ("EVENT", "event"),
               ("LAST", "_last"), ("1M", "_chg1m"), ("RV20", "_rv20"), ("SOURCE", "source")]
CONTEXT_HELP = {
    "MON": "s cycle sort · click header to sort · f segment filter · ⏎ open · + / − watchlist · y copy ticker",
    "DES": "1-9,0 or [ ] timeframe · t line/candle · m moving avg · v volume · , . prev/next ticker · "
           "+ / − watchlist · y copy · ⏎ on news opens story · ⌫ back",
    "OMON": "↑↓ expiry · [ ] prev/next expiry · y copy contract · , . prev/next ticker · ⌫ back",
    "NEWS": "⏎ or o open story in browser · ↑↓ preview · ⌫ back",
    "SCRN": "↑↓ pick screen · ⏎ open ticker · click header to sort · + watchlist · y copy ticker",
    "IDEAS": "y copy all trade lines · F2 monitor · type a ticker to open it",
    "CAL": "⏎ open ticker · click header to sort · + watchlist",
    "W": "WADD/WDEL TICK · + / − on a row · ALRT TICK > PRICE adds an alert · ALRTDEL TICK",
    "COMP": "COMP LLY NVO XBI 1Y · [ ] or 1-9,0 timeframe · ⌫ back",
    "HELP": "F1-F10 functions · / or Esc command line · ↑↓ in command line = history · → accepts suggestion",
}
NY = ZoneInfo("America/New_York")


def _short(name: str, n: int = 18) -> str:
    return name if len(name) <= n else name[: n - 1] + "…"


def _sort_key(v):
    if v is None or (isinstance(v, float) and v != v):
        return (1, 0)
    if isinstance(v, (int, float)):
        return (0, float(v))
    return (0, str(v))


def market_open(now: datetime | None = None) -> bool:
    ny = (now or datetime.now(NY)).astimezone(NY)
    mins = ny.hour * 60 + ny.minute
    return ny.weekday() < 5 and 570 <= mins < 960


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_delta(spot: float, strike: float, t_years: float, iv: float, call: bool, r: float = 0.04) -> float | None:
    if not (spot > 0 and strike > 0 and t_years > 0 and iv and iv == iv and iv > 0):
        return None
    d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    return _norm_cdf(d1) if call else _norm_cdf(d1) - 1


class RxTerm(App):
    CSS_PATH = "rxterm.tcss"
    TITLE = "RXTERM"
    BINDINGS = [
        Binding("f1", "fn('HELP')", "Help", show=False),
        Binding("f2", "fn('MON')", "Monitor", show=False),
        Binding("f3", "fn('NEWS')", "News", show=False),
        Binding("f4", "fn('SCRN')", "Screener", show=False),
        Binding("f5", "fn('IDEAS')", "Ideas", show=False),
        Binding("f6", "fn('CAL')", "Calendar", show=False),
        Binding("f7", "fn('DES')", "Describe", show=False),
        Binding("f8", "fn('OMON')", "Options", show=False),
        Binding("f9", "fn('W')", "Watchlist", show=False),
        Binding("f10", "refresh_data", "Refresh", show=False),
        Binding("escape", "focus_cmd", "Command", show=False),
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
        Binding("ctrl+q", "quit", "Quit", show=False, priority=True),
    ]

    def __init__(self, cfg: Settings | None = None):
        super().__init__()
        self.cfg = cfg or default_settings
        self.engine = Engine(self.cfg)
        self.snap: Snapshot = self.engine.new_snapshot()
        st = self._load_state()
        self.current = st.get("screen", "MON") if st.get("screen") in FUNCTIONS else "MON"
        if self.current == "COMP":
            self.current = "MON"
        self.ticker = st.get("ticker", "LLY")
        self.tf = st.get("tf", "6M") if st.get("tf") in tfs.TF else "6M"
        self.chart_mode = st.get("chart_mode", "line")
        self.chart_ma = st.get("chart_ma", 50)
        self.chart_vol = st.get("chart_vol", True)
        self.mon_sort = st.get("mon_sort", "chg1d")
        self.mon_desc = st.get("mon_desc", True)
        self.mon_filter = st.get("mon_filter", "ALL") if st.get("mon_filter") in MON_FILTERS else "ALL"
        self._screen_code = st.get("screen_code", "TOPLONG") if st.get("screen_code") in screener.SCREENS else "TOPLONG"
        self.cmd_history: list[str] = st.get("cmd_history", [])[-200:]
        self._hist_pos: int | None = None
        self.back_stack: list[tuple[str, str]] = []
        self._view: tuple[str, str] | None = None
        self.browse: list[str] = []
        self.comp: list[str] = []
        self.sorts: dict[str, tuple[str, bool]] = {}
        self.watch = self._load_watch()
        self.alerts = AlertBook(self.cfg.home / "alerts.json")
        self.news_rows: list = []
        self._news_view: list = []
        self._chain = None
        self._updated: datetime | None = None
        self._ticks = 0

    # ── state ──────────────────────────────────────────────────────────
    @property
    def _state_path(self):
        return self.cfg.home / "state.json"

    def _load_state(self) -> dict:
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save_state(self) -> None:
        st = {"screen": self.current, "ticker": self.ticker, "tf": self.tf, "chart_mode": self.chart_mode,
              "chart_ma": self.chart_ma, "chart_vol": self.chart_vol, "mon_sort": self.mon_sort,
              "mon_desc": self.mon_desc, "mon_filter": self.mon_filter, "screen_code": self._screen_code,
              "cmd_history": self.cmd_history[-200:]}
        try:
            self.cfg.ensure_home()
            self._state_path.write_text(json.dumps(st), encoding="utf-8")
        except OSError:
            pass

    def on_unmount(self) -> None:
        self.save_state()

    # ── layout ─────────────────────────────────────────────────────────
    def _suggestions(self) -> list[str]:
        ticks = [s.ticker for s in universe.equities()] + list(universe.BENCHMARKS)
        out = list(FUNCTIONS) + ["REFRESH", "BACK", "ALRT ", "ALRTDEL ", "WADD ", "WDEL ", "COMP "]
        out += [f"SCRN {c}" for c in screener.SCREENS] + [f"MON {f}" for f in MON_FILTERS]
        out += ticks + [f"{t} OMON" for t in ticks] + [f"{t} N" for t in ticks]
        out += [f"{t} GP {tf.code}" for t in ticks for tf in tfs.TIMEFRAMES]
        return out

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static(Text("RXTERM", style=f"bold {AMBER}"), id="logo")
            yield Input(placeholder="Enter command  e.g.  LLY <GO>  ·  LLY 5D  ·  SCRN PDUFA  ·  COMP LLY NVO  ·  HELP",
                        id="cmd", suggester=SuggestFromList(self._suggestions(), case_sensitive=False))
            yield Clock(self.cfg.tz, id="clock")
        yield TickerTape(id="tape")
        yield Static(self._fkeys_text(), id="fkeys")
        with ContentSwitcher(initial="MON", id="main"):
            with Horizontal(id="MON"):
                with Vertical(id="mon-left"):
                    yield DataTable(id="mon-table", cursor_type="row", zebra_stripes=True)
                with Vertical(id="mon-right"):
                    yield Static(id="mon-bench", classes="panel")
                    yield Static(id="mon-sector", classes="panel")
                    yield DataTable(id="mon-news", cursor_type="row", show_header=False, classes="panel")
                    yield Static(id="mon-ideas", classes="panel")
            with Vertical(id="NEWS"):
                yield DataTable(id="news-table", cursor_type="row", zebra_stripes=True)
                yield Static(id="news-preview", classes="panel")
            with Horizontal(id="SCRN"):
                yield OptionList(*[Option(f"{s.code:<11}{s.title}", id=s.code) for s in screener.SCREENS.values()],
                                 id="scrn-list")
                with Vertical(id="scrn-right"):
                    yield Static(id="scrn-title", classes="panel")
                    yield DataTable(id="scrn-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="IDEAS"):
                yield Static(id="ideas-take", classes="panel")
                with Horizontal(id="ideas-cols"):
                    yield VerticalScroll(Static(id="ideas-cons"), id="ideas-cons-wrap")
                    yield VerticalScroll(Static(id="ideas-aggr"), id="ideas-aggr-wrap")
            with Vertical(id="CAL"):
                yield Static(id="cal-title", classes="panel")
                yield DataTable(id="cal-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="DES"):
                yield Static(id="des-head", classes="panel")
                with Horizontal(id="des-body"):
                    with Vertical(id="des-chart-wrap"):
                        yield Static(id="des-tf")
                        yield PriceChart(id="des-chart")
                    yield Static(id="des-stats", classes="panel")
                with Horizontal(id="des-bottom"):
                    yield DataTable(id="des-news", cursor_type="row", show_header=False)
                    yield Static(id="des-about", classes="panel")
            with Vertical(id="COMP"):
                yield Static(id="comp-tf")
                yield PriceChart(id="comp-chart")
            with Horizontal(id="OMON"):
                yield OptionList(id="omon-exp")
                with Vertical(id="omon-right"):
                    yield Static(id="omon-head", classes="panel")
                    yield DataTable(id="omon-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="W"):
                yield Static(id="w-title", classes="panel")
                yield DataTable(id="w-table", cursor_type="row", zebra_stripes=True)
                yield Static(id="w-alerts", classes="panel")
            yield VerticalScroll(Static(id="help-text"), id="HELP")
        yield Static(id="status")

    def _fkeys_text(self) -> Text:
        t = Text()
        for k, name in FKEYS:
            active = name == getattr(self, "current", "MON")
            t.append(f" {k} ", style="bold black on #ff9e1b")
            t.append(f" {name} ", style=f"bold {AMBER} on #1c2128" if active else f"{WHITE}")
            t.append(" ")
        t.append("  / command · ? keys · ⌫ back · CTRL+Q quit", style=DIM)
        return t

    def on_mount(self) -> None:
        self._setup_tables()
        self.query_one("#help-text", Static).update(self._help())
        chart = self.query_one("#des-chart", PriceChart)
        chart.mode, chart.ma, chart.volume = self.chart_mode, self.chart_ma, self.chart_vol
        self.query_one("#main", ContentSwitcher).current = self.current
        self.query_one("#fkeys", Static).update(self._fkeys_text())
        self.query_one("#cmd", Input).focus()
        self.status("Loading prices…", busy=True)
        self.load_data()
        self.set_interval(60, self.tick)

    def _setup_tables(self) -> None:
        self.query_one("#mon-table", DataTable).add_columns(*[h for h, _ in MON_COLUMNS])
        self.query_one("#mon-news", DataTable).add_columns("T", "TKR", "HEADLINE")
        self.query_one("#news-table", DataTable).add_columns("TIME", "SRC", "TICKERS", "", "EVENT", "HEADLINE")
        self.query_one("#cal-table", DataTable).add_columns(*[h for h, _ in CAL_COLUMNS])
        self.query_one("#des-news", DataTable).add_columns("AGE", "", "HEADLINE")
        self.query_one("#omon-table", DataTable).add_columns(
            "C.BID", "C.ASK", "C.LAST", "C.IV", "C.Δ", "C.VOL", "C.OI", "STRIKE",
            "P.BID", "P.ASK", "P.LAST", "P.IV", "P.Δ", "P.VOL", "P.OI")
        self.query_one("#w-table", DataTable).add_columns(*[h for h, _ in W_COLUMNS])

    # ── data loading ───────────────────────────────────────────────────
    @work(thread=True, exclusive=True, group="load")
    def load_data(self) -> None:
        snap = self.engine.new_snapshot()
        try:
            self.engine.load_prices(snap)
            self.engine.compute(snap)
            self.call_from_thread(self._apply, snap, "Prices loaded · fetching news…")
            self.engine.load_news(snap)
            self.engine.compute(snap)
            self.call_from_thread(self._apply, snap, "News loaded · fetching fundamentals & catalysts…")
            self.engine.load_profiles(snap)
            self.engine.load_calendar(snap)
            self.engine.compute(snap)
            self.call_from_thread(self._apply, snap, "Fundamentals loaded · building trade ideas…")
            self.engine.make_ideas(snap)
            self.call_from_thread(self._apply, snap, None)
        except Exception as exc:  # keep the terminal alive on network failures
            self.call_from_thread(self.status, f"Data error: {exc}", False, True)

    def tick(self) -> None:
        """Every minute: fresh quotes while the market is open (every 5 minutes otherwise)."""
        self._ticks += 1
        if self.snap.board.empty:
            return
        if market_open() or self._ticks % 5 == 0:
            self.refresh_quotes()

    @work(thread=True, exclusive=True, group="quotes")
    def refresh_quotes(self) -> None:
        try:
            snap = self.engine.refresh_quotes(self.snap)
        except Exception as exc:
            self.call_from_thread(self.status, f"Quote refresh failed: {exc}", False, True)
            return
        self.call_from_thread(self._apply, snap, None)
        if self.current == "DES" and tfs.TF[self.tf].intraday:
            self.call_from_thread(self._chart_des)

    def _apply(self, snap: Snapshot, msg: str | None) -> None:
        self.snap = snap
        if snap.board.empty:
            self.status("No market data returned — check your connection, press F10, or run rxterm --demo", error=True)
            return
        self._updated = datetime.now(self.cfg.tz)
        self._render_tape()
        self.show(self.current, refresh_only=True)
        self._check_alerts()
        if msg:
            self.status(msg, busy=True)
        else:
            self.status(f"Ready · {len(snap.board)} securities · {snap.provider} · updated {self._updated:%H:%M:%S}"
                        + (f" · theses: {snap.writer}" if snap.writer else ""))

    def _render_tape(self) -> None:
        b = self.snap.board
        order = list(universe.BENCHMARKS) + [t for t in b.sort_values("mcap", ascending=False).index
                                             if t not in universe.BENCHMARKS]
        quotes = [(t, float(b.loc[t, "last"]), float(b.loc[t, "chg1d"])) for t in order
                  if t in b.index and b.loc[t, "chg1d"] == b.loc[t, "chg1d"]]
        self.query_one("#tape", TickerTape).set_quotes(quotes[:60])

    def status(self, msg: str, busy: bool = False, error: bool = False) -> None:
        t = Text()
        t.append(" ● " if not busy else " ◌ ", style=DN if error else (AMBER if busy else UP))
        t.append(msg, style=DN if error else WHITE)
        armed = sum(a.armed for a in self.alerts.alerts)
        if armed:
            t.append(f"   🔔 {armed} alert{'s' if armed > 1 else ''}", style=AMBER)
        t.append(f"   RXTERM v{__version__}", style=DIM)
        self.query_one("#status", Static).update(t)

    # ── command line ───────────────────────────────────────────────────
    def action_focus_cmd(self) -> None:
        cmd = self.query_one("#cmd", Input)
        cmd.value = ""
        self._hist_pos = None
        cmd.focus()

    def action_fn(self, name: str) -> None:
        self.show(name)

    def action_refresh_data(self) -> None:
        self.engine.cache.invalidate("hist:", "news:", "chain:", "exp:", "bars:")
        self.status("Refreshing everything…", busy=True)
        self.load_data()

    @on(Input.Submitted, "#cmd")
    def on_command(self, event: Input.Submitted) -> None:
        raw = " ".join(event.value.replace("<GO>", "").upper().split())
        event.input.value = ""
        self._hist_pos = None
        if raw:
            if not self.cmd_history or self.cmd_history[-1] != raw:
                self.cmd_history.append(raw)
            self.run_command(raw)

    def _history_step(self, delta: int) -> None:
        if not self.cmd_history:
            return
        cmd = self.query_one("#cmd", Input)
        pos = len(self.cmd_history) if self._hist_pos is None else self._hist_pos
        pos = max(0, min(len(self.cmd_history), pos + delta))
        self._hist_pos = pos
        cmd.value = self.cmd_history[pos] if pos < len(self.cmd_history) else ""
        cmd.cursor_position = len(cmd.value)

    def run_command(self, raw: str) -> None:
        toks = raw.split()
        head, args = toks[0], toks[1:]
        if head in ("REFRESH", "F10"):
            return self.action_refresh_data()
        if head in ("Q", "QUIT", "EXIT"):
            return self.exit()
        if head in ("BACK", "BK"):
            return self.action_back()
        if head == "WADD" and args:
            for t in args:
                self._watch_add(t, quiet=len(args) > 1)
            return self.show("W")
        if head == "WDEL" and args:
            for t in args:
                self._watch_remove(t, quiet=len(args) > 1)
            return self.show("W")
        if head in ("ALRT", "ALERT"):
            return self._cmd_alert(args)
        if head in ("ALRTDEL", "ALERTDEL"):
            n = self.alerts.remove(args[0] if args else "ALL")
            self.notify(f"Removed {n} alert{'s' if n != 1 else ''}", timeout=4)
            return self.show("W")
        if head == "COMP" or (len(toks) == 3 and toks[1] in ("VS", "V")):
            names = [t for t in (args if head == "COMP" else [toks[0], toks[2]])]
            return self._cmd_comp(names)
        if head == "MON" and args:
            f = MON_FILTER_ALIASES.get(args[0], args[0])
            if f in MON_FILTERS:
                self.mon_filter = f
            return self.show("MON")
        if head in FUNCTIONS:
            if head in ("DES", "OMON") and args and args[0] in universe.UNIVERSE:
                self.ticker = args[0]
            if head == "SCRN" and args and args[0] in screener.SCREENS:
                self._screen_code = args[0]
            if head == "COMP":
                return self._cmd_comp(args)
            return self.show(head)
        if head in ("GP", "N") and args:
            head, args = args[0], [toks[0]] + args[1:]
        if head in universe.UNIVERSE:
            self.ticker = head
            sub = args[0] if args else "DES"
            if tfs.resolve(sub):
                self.tf = tfs.resolve(sub)
                return self.show("DES")
            if sub == "GP":
                if len(args) > 1 and tfs.resolve(args[1]):
                    self.tf = tfs.resolve(args[1])
                return self.show("DES")
            if sub in ("N", "NEWS", "CN"):
                return self.show("NEWS", news_filter=head)
            if sub in ("OMON", "OM", "OPT", "OPTIONS"):
                return self.show("OMON")
            if sub in ("ALRT", "ALERT"):
                return self._cmd_alert([head] + args[1:])
            return self.show("DES")
        for sec in universe.UNIVERSE.values():  # fuzzy: company name
            if raw in sec.name.upper():
                self.ticker = sec.ticker
                return self.show("DES")
        self.status(f"Unknown command: {raw}  (press ? for keys, F1 for help)", error=True)

    # ── navigation ─────────────────────────────────────────────────────
    def show(self, name: str, refresh_only: bool = False, news_filter: str | None = None) -> None:
        if name == "REFRESH":
            return self.action_refresh_data()
        if not refresh_only:
            self.current = name
            self.query_one("#main", ContentSwitcher).current = name
            self.query_one("#fkeys", Static).update(self._fkeys_text())
        render = {
            "MON": self.render_mon, "NEWS": lambda: self.render_news(news_filter if not refresh_only else None),
            "SCRN": self.render_scrn, "IDEAS": self.render_ideas, "CAL": self.render_cal,
            "DES": self.render_des, "OMON": self.render_omon, "W": self.render_watch, "HELP": lambda: None,
            "COMP": lambda: None if refresh_only else self._load_comp(),
        }[self.current]
        if not self.snap.board.empty or self.current in ("HELP", "W"):
            render()
        if not refresh_only:
            focus = {"MON": "#mon-table", "NEWS": "#news-table", "SCRN": "#scrn-list", "CAL": "#cal-table",
                     "OMON": "#omon-exp", "W": "#w-table", "DES": "#des-news"}.get(name)
            if focus:
                self.query_one(focus).focus()
            self._push_view()
            self.save_state()

    def _push_view(self) -> None:
        new = (self.current, self.ticker)
        if self._view and self._view != new:
            self.back_stack.append(self._view)
            self.back_stack = self.back_stack[-50:]
        self._view = new

    def action_back(self) -> None:
        while self.back_stack:
            screen, ticker = self.back_stack.pop()
            if (screen, ticker) != (self.current, self.ticker):
                self.ticker, self.current = ticker, screen
                self._view = (screen, ticker)
                self.query_one("#main", ContentSwitcher).current = screen
                self.query_one("#fkeys", Static).update(self._fkeys_text())
                self.show(screen, refresh_only=True)
                self.save_state()
                return
        self.notify("Nothing to go back to", timeout=2)

    def _focused_table(self) -> DataTable | None:
        return self.focused if isinstance(self.focused, DataTable) else None

    def _context_ticker(self) -> str | None:
        """Ticker under the cursor (tables) or the current security (DES/OMON)."""
        t = self._focused_table()
        if t is not None and t.id in ("mon-table", "scrn-table", "w-table", "cal-table") and t.row_count:
            try:
                key = t.coordinate_to_cell_key((t.cursor_row, 0)).row_key.value
                return key.split(":")[0]
            except Exception:
                pass
        return self.ticker if self.current in ("DES", "OMON") else None

    def _browse_step(self, delta: int) -> None:
        order = self.browse or list(self._mon_frame().index)
        if not order:
            return
        i = order.index(self.ticker) if self.ticker in order else -1
        self.ticker = order[(i + delta) % len(order)]
        self.show(self.current, refresh_only=True)
        self._push_view()
        self.save_state()

    def on_key(self, event) -> None:
        cmd = self.query_one("#cmd", Input)
        if self.focused is cmd:
            if event.key in ("up", "down"):
                self._history_step(-1 if event.key == "up" else 1)
                event.stop()
            return
        ch = event.character or ""
        key = event.key
        handled = True
        if ch == "/":
            self.action_focus_cmd()
        elif ch == "?":
            self.notify(CONTEXT_HELP.get(self.current, ""), title=f"{self.current} keys", timeout=12)
        elif key == "backspace":
            self.action_back()
        elif ch in ("+", "="):
            t = self._context_ticker()
            if t:
                self._watch_add(t)
        elif ch in ("-", "_"):
            t = self._context_ticker()
            if t:
                self._watch_remove(t)
        elif ch == "y":
            self._copy_context()
        elif self.current == "MON" and ch == "s":
            order = ["chg1d", "chg5d", "chg1m", "chg3m", "ytd", "rsi", "rv20", "vol_ratio", "long_score", "short_score"]
            self.mon_sort = order[(order.index(self.mon_sort) + 1) % len(order)] if self.mon_sort in order else "chg1d"
            self.mon_desc = True
            self.render_mon()
            self.save_state()
        elif self.current == "MON" and ch == "f":
            keys = list(MON_FILTERS)
            self.mon_filter = keys[(keys.index(self.mon_filter) + 1) % len(keys)]
            self.render_mon()
            self.save_state()
        elif self.current in ("DES", "COMP") and (ch in tfs.DIGIT_KEYS or ch in ("[", "]")):
            self.action_set_tf(tfs.DIGIT_KEYS[ch] if ch in tfs.DIGIT_KEYS else tfs.step(self.tf, -1 if ch == "[" else 1))
        elif self.current == "DES" and ch == "t":
            self.action_chart("mode")
        elif self.current == "DES" and ch == "m":
            self.action_chart("ma")
        elif self.current == "DES" and ch == "v":
            self.action_chart("vol")
        elif self.current in ("DES", "OMON") and ch in (",", "<"):
            self._browse_step(-1)
        elif self.current in ("DES", "OMON") and ch in (".", ">"):
            self._browse_step(1)
        elif self.current == "OMON" and ch in ("[", "]"):
            ol = self.query_one("#omon-exp", OptionList)
            if ol.option_count:
                ol.highlighted = max(0, min(ol.option_count - 1, (ol.highlighted or 0) + (-1 if ch == "[" else 1)))
        elif self.current == "NEWS" and ch == "o":
            self._open_news_row()
        else:
            handled = False
        if handled:
            event.stop()

    @on(DataTable.RowSelected)
    def on_row(self, event: DataTable.RowSelected) -> None:
        tid = event.data_table.id
        key = event.row_key.value if event.row_key else None
        if tid in ("mon-table", "scrn-table", "w-table", "cal-table") and key:
            seen, order = set(), []
            for rk in event.data_table.rows:
                tk = rk.value.split(":")[0]
                if tk not in seen:
                    seen.add(tk)
                    order.append(tk)
            self.browse = order
            self.ticker = key.split(":")[0]
            self.show("DES")
        elif tid == "mon-news" and key:
            it = self.news_rows[int(key[1:])]
            if it.tickers:
                self.ticker = it.tickers[0]
                self.show("DES")
            else:
                self.show("NEWS")
        elif tid == "news-table":
            self._open_news_row()
        elif tid == "des-news" and key:
            items = for_ticker(self.snap.news, self.ticker)
            i = int(key[1:])
            if i < len(items):
                webbrowser.open(items[i].link)

    @on(DataTable.HeaderSelected)
    def on_header(self, event: DataTable.HeaderSelected) -> None:
        tid = event.data_table.id
        i = event.column_index
        if tid == "mon-table":
            field = MON_COLUMNS[i][1]
            self.mon_desc = not self.mon_desc if field == self.mon_sort else field not in ("_ticker", "name")
            self.mon_sort = field
            self.render_mon()
            self.save_state()
        elif tid in ("scrn-table", "w-table", "cal-table"):
            if tid == "scrn-table":
                cols = ["_ticker", "name"] + list(screener.SCREENS[self._screen_code].columns)
            elif tid == "w-table":
                cols = [f for _, f in W_COLUMNS]
            else:
                cols = [f for _, f in CAL_COLUMNS]
            field = cols[i]
            prev = self.sorts.get(tid)
            desc = (not prev[1]) if prev and prev[0] == field else field not in ("_ticker", "name", "when", "ticker",
                                                                                  "type", "event", "source", "cat_days")
            self.sorts[tid] = (field, desc)
            {"scrn-table": self.render_scrn, "w-table": self.render_watch, "cal-table": self.render_cal}[tid]()
        self.notify(f"Sorted by {getattr(event.label, 'plain', event.label)}", timeout=2)

    # ── watchlist / alerts / clipboard ─────────────────────────────────
    def _watch_add(self, t: str, quiet: bool = False) -> None:
        t = t.upper()
        if t not in universe.UNIVERSE:
            self.notify(f"{t}: not in coverage", severity="warning", timeout=3)
        elif t in self.watch:
            if not quiet:
                self.notify(f"{t} is already on your watchlist", timeout=2)
        else:
            self.watch.append(t)
            self._save_watch()
            if not quiet:
                self.notify(f"Added {t} to watchlist", timeout=2)
            if self.current == "W":
                self.render_watch()

    def _watch_remove(self, t: str, quiet: bool = False) -> None:
        t = t.upper()
        if t in self.watch:
            self.watch.remove(t)
            self._save_watch()
            if not quiet:
                self.notify(f"Removed {t} from watchlist", timeout=2)
            if self.current == "W":
                self.render_watch()

    def _cmd_alert(self, args: list[str]) -> None:
        if not args:
            return self.show("W")
        parsed = parse_alert(args)
        if not parsed or parsed[0] not in universe.UNIVERSE:
            self.notify("Usage: ALRT LLY > 1250   ·   ALRT LLY < 1100   ·   ALRTDEL LLY", severity="warning", timeout=6)
            return
        tk, op, level = parsed
        last = float(self.snap.board.loc[tk, "last"]) if tk in self.snap.board.index else None
        a = self.alerts.add(tk, level, op, last)
        self.notify(f"Alert set: {a.describe()}" + (f" (now {last:,.2f})" if last else ""), timeout=5)
        self._check_alerts()
        self.status(f"Alert set: {a.describe()}")

    def _check_alerts(self) -> None:
        b = self.snap.board
        if b.empty or not self.alerts.alerts:
            return
        hits = self.alerts.check({t: float(b.loc[t, "last"]) for t in b.index})
        for a, px in hits:
            self.notify(f"{a.ticker} at {px:,.2f} — crossed {'above' if a.op == '>' else 'below'} {a.level:,.2f}",
                        title="🔔 PRICE ALERT", severity="warning", timeout=60)
            self.bell()
        if hits and self.current == "W":
            self.render_watch()

    def _copy(self, text: str, label: str | None = None) -> None:
        try:
            self.copy_to_clipboard(text)  # OSC 52 (Windows Terminal, iTerm2, most modern terminals)
        except Exception:
            pass
        try:  # native clipboard as a fallback for consoles without OSC 52
            if sys.platform == "win32":
                subprocess.run(["clip"], input=text.encode("utf-16-le"), check=False, creationflags=0x08000000)
            elif sys.platform == "darwin":
                subprocess.run(["pbcopy"], input=text.encode(), check=False)
        except OSError:
            pass
        self.notify(f"Copied: {label or text[:80]}", timeout=3)

    def _copy_context(self) -> None:
        if self.current == "IDEAS" and self.snap.ideas:
            lines = [f"{i.tier[:4]} {i.direction:<8} {i.ticker:<5} {i.trade_line}" for i in self.snap.ideas]
            return self._copy("\n".join(lines), f"{len(lines)} trade lines")
        if self.current == "OMON" and self._chain is not None:
            t = self.query_one("#omon-table", DataTable)
            if t.row_count:
                k = float(t.coordinate_to_cell_key((t.cursor_row, 0)).row_key.value)
                ch = self._chain

                def q(df):
                    r = df[df["strike"] == k]
                    return f"{r['bid'].iloc[0]:.2f}/{r['ask'].iloc[0]:.2f}" if len(r) else "—"
                text = (f"{ch.ticker} {ch.expiry:%d%b%y}".upper() + f" {k:g} CALL {q(ch.calls)} | "
                        + f"{ch.ticker} {ch.expiry:%d%b%y}".upper() + f" {k:g} PUT {q(ch.puts)}")
                return self._copy(text)
        if self.current == "DES":
            idea = next((i for i in self.snap.ideas if i.ticker == self.ticker), None)
            if idea:
                return self._copy(f"{idea.ticker} {idea.trade_line}")
        t = self._context_ticker()
        if t:
            b = self.snap.board
            px = f" {b.loc[t, 'last']:,.2f}" if t in b.index else ""
            self._copy(f"{t}{px}")

    def _open_news_row(self) -> None:
        row = self.query_one("#news-table", DataTable).cursor_row
        if row is not None and row < len(self._news_view):
            webbrowser.open(self._news_view[row].link)

    # ── MON ────────────────────────────────────────────────────────────
    def _mon_frame(self) -> pd.DataFrame:
        b = self.snap.board
        if b.empty:
            return b
        eq = b[b["segment"] != universe.ETF]
        f = MON_FILTERS.get(self.mon_filter)
        if f == "WATCH":
            eq = eq[eq.index.isin(self.watch)]
        elif f:
            eq = eq[eq["segment"] == f]
        if self.mon_sort == "_ticker":
            return eq.sort_index(ascending=not self.mon_desc)
        if self.mon_sort in eq:
            return eq.sort_values(self.mon_sort, ascending=not self.mon_desc, na_position="last")
        return eq

    def render_mon(self) -> None:
        b = self.snap.board
        eq = self._mon_frame()
        t = self.query_one("#mon-table", DataTable)
        keep = t.cursor_row
        t.clear()
        for tk, r in eq.iterrows():
            t.add_row(Text(tk, style=f"bold {AMBER}"), Text(_short(r["name"]), style=WHITE),
                      fmt.num(r["last"], 2, 9), fmt.pct(r["chg1d"], 2, width=7), fmt.pct(r["chg5d"], 1, width=6),
                      fmt.pct(r["chg1m"], 1, width=7), fmt.pct(r["chg3m"], 1, width=7), fmt.pct(r["ytd"], 1, width=7),
                      fmt.rsi(r["rsi"]), fmt.pct(r["rv20"], 0, plus=False), fmt.num(r["vol_ratio"], 1),
                      fmt.signal(r["signal"]),
                      Text(r["spark"], style=UP if r["chg3m"] >= 0 else DN), key=tk)
        label = next((h for h, f in MON_COLUMNS if f == self.mon_sort), self.mon_sort.upper())
        t.border_title = (f"SECTOR MONITOR · {len(eq)} names · {self.mon_filter} · sort {label} "
                          f"{'▼' if self.mon_desc else '▲'}  (s sort · f filter · click headers)")
        if keep is not None and keep < t.row_count:
            t.move_cursor(row=keep)

        bench = Table.grid(padding=(0, 2), expand=True)
        for _ in range(5):
            bench.add_column(justify="right")
        bench.add_row(*[Text(h, style=DIM) for h in ("", "LAST", "1D", "1M", "YTD")])
        for tk in ("XBI", "IBB", "XPH", "SPY"):
            if tk in b.index:
                r = b.loc[tk]
                bench.add_row(Text(tk, style=f"bold {AMBER}"), fmt.num(r["last"]), fmt.pct(r["chg1d"], 2),
                              fmt.pct(r["chg1m"]), fmt.pct(r["ytd"]))
        br = self.snap.breadth
        line = Text()
        line.append("ADV/DEC ", style=DIM)
        line.append(f"{br['advancers']}/{br['decliners']}", style=WHITE)
        line.append("  >50D ", style=DIM)
        line.append(f"{br['above50'] * 100:.0f}%", style=WHITE)
        line.append("  >200D ", style=DIM)
        line.append(f"{br['above200'] * 100:.0f}%", style=WHITE)
        line.append("  52W HI ", style=DIM)
        line.append(f"{br['new_highs']}", style=WHITE)
        w = self.query_one("#mon-bench", Static)
        w.update(Group(bench, line))
        w.border_title = "BENCHMARKS"

        seg = Table.grid(padding=(0, 1), expand=True)
        seg.add_column()
        for _ in range(4):
            seg.add_column(justify="right")
        seg.add_column()
        seg.add_row(*[Text(h, style=DIM) for h in ("SEGMENT", "1D", "1M", "3M", "YTD", "")])
        for name, r in self.snap.segments.iterrows():
            bar_len = int(min(abs(r["chg1m"]) * 100, 12)) if r["chg1m"] == r["chg1m"] else 0
            seg.add_row(Text(name, style=WHITE), fmt.pct(r["chg1d"]), fmt.pct(r["chg1m"]), fmt.pct(r["chg3m"]),
                        fmt.pct(r["ytd"]), Text("█" * bar_len, style=UP if r["chg1m"] >= 0 else DN))
        w = self.query_one("#mon-sector", Static)
        w.update(seg)
        w.border_title = "SEGMENT PERFORMANCE (MEDIAN)"

        nt = self.query_one("#mon-news", DataTable)
        nt.clear()
        self.news_rows = self.snap.top_news[:30]
        for n, it in enumerate(self.news_rows):
            nt.add_row(fmt.tone(it.tone), Text(" ".join(it.tickers[:2]) or "—", style=AMBER),
                       Text(it.title[:120], style=WHITE), key=f"n{n}")
        nt.border_title = f"TOP NEWS · {len(self.snap.news)} items"

        ideas = Text()
        for i in self.snap.ideas:
            ideas.append(f"{'CONS' if i.tier == CONSERVATIVE else 'AGGR'} ", style=BLUE if i.tier == CONSERVATIVE else AMBER)
            ideas.append_text(fmt.direction(i.direction))
            ideas.append(f" {i.ticker:<5} ", style=f"bold {WHITE}")
            ideas.append(f"{i.structure:<17}", style=DIM)
            ideas.append(f"{'●' * i.conviction}{'○' * (5 - i.conviction)}\n", style=AMBER)
        w = self.query_one("#mon-ideas", Static)
        w.update(ideas if self.snap.ideas else Text("building ideas…", style=DIM))
        w.border_title = "TODAY'S TRADES  (F5)"

    # ── NEWS ───────────────────────────────────────────────────────────
    def render_news(self, ticker: str | None = None) -> None:
        items = for_ticker(self.snap.news, ticker) if ticker else self.snap.news
        self._news_view = items
        t = self.query_one("#news-table", DataTable)
        t.clear()
        for n, it in enumerate(items[:400]):
            local = it.published.astimezone(self.cfg.tz)
            t.add_row(Text(f"{local:%d%b %H:%M}", style=DIM), Text(it.source[:16], style=BLUE),
                      Text(" ".join(it.tickers[:3]), style=f"bold {AMBER}"), fmt.tone(it.tone),
                      Text(", ".join(it.tags[:2]), style=WHITE), Text(it.title, style=WHITE), key=f"x{n}")
        t.border_title = f"NEWS WIRE{' · ' + ticker if ticker else ''} · {len(items)} stories  (⏎ or o: open story)"
        self._preview_news(0)

    @on(DataTable.RowHighlighted, "#news-table")
    def _news_hl(self, event: DataTable.RowHighlighted) -> None:
        self._preview_news(event.cursor_row)

    def _preview_news(self, row: int) -> None:
        w = self.query_one("#news-preview", Static)
        if not self._news_view or row is None or row >= len(self._news_view):
            w.update("")
            return
        it = self._news_view[row]
        t = Text()
        t.append(it.title + "\n", style=f"bold {WHITE}")
        t.append(f"{it.source} · {it.published.astimezone(self.cfg.tz):%a %d %b %H:%M} · sentiment {it.sentiment:+.2f}"
                 f" · impact {it.impact:.2f} · {', '.join(it.tags) or 'no event tag'}\n", style=DIM)
        if it.summary:
            t.append(it.summary[:500] + "\n", style=WHITE)
        t.append(it.link, style=f"underline {BLUE}")
        w.update(t)
        w.border_title = "STORY"

    # ── SCRN ───────────────────────────────────────────────────────────
    def render_scrn(self) -> None:
        self.show_screen(self._screen_code, switch=False)

    def show_screen(self, code: str, switch: bool = True) -> None:
        if code != self._screen_code:
            self.sorts.pop("scrn-table", None)
        self._screen_code = code
        if switch and self.current != "SCRN":
            return self.show("SCRN")
        s = screener.SCREENS[code]
        res = screener.run(self.snap.board, code, limit=60)
        if "scrn-table" in self.sorts:
            field, desc = self.sorts["scrn-table"]
            if field == "_ticker":
                res = res.sort_index(ascending=not desc)
            elif field in res:
                res = res.sort_values(field, ascending=not desc, na_position="last",
                                      key=(lambda c: c.astype(str)) if res[field].dtype == object else None)
        t = self.query_one("#scrn-table", DataTable)
        t.clear(columns=True)
        labels = {"last": "LAST", "chg1d": "CHG", "chg5d": "5D", "chg1m": "1M", "chg3m": "3M", "rsi": "RSI",
                  "rv20": "RV20", "vol_ratio": "VOL×", "signal": "SIGNAL", "rs3m": "RS3M", "news_score": "NEWS",
                  "long_score": "L.SCORE", "short_score": "S.SCORE", "short_float": "SI%", "dist50": "vs50D",
                  "dist200": "vs200D", "target_upside": "UPSIDE", "off_hi": "vs52H", "cat_type": "TYPE",
                  "cat_days": "DAYS", "cat_event": "EVENT", "earn_days": "EARN", "fwd_pe": "FWD P/E",
                  "dollar_vol": "$VOL", "news_count": "#NEWS", "news_tags": "TAGS", "headline": "HEADLINE",
                  "target": "TARGET", "rec": "REC", "atr_pct": "ATR%"}
        t.add_columns("TICKER", "NAME", *[labels.get(c, c.upper()) for c in s.columns])
        for tk, r in res.iterrows():
            cells = []
            for c in s.columns:
                v = r[c]
                if c in ("chg1d", "chg5d", "chg1m", "chg3m", "rs3m", "dist50", "dist200", "target_upside", "off_hi"):
                    cells.append(fmt.pct(v))
                elif c in ("rv20", "short_float", "atr_pct"):
                    cells.append(fmt.pct(v, 1, plus=False))
                elif c == "signal":
                    cells.append(fmt.signal(v))
                elif c == "rsi":
                    cells.append(fmt.rsi(v))
                elif c == "cat_type":
                    cells.append(fmt.cat_type(v))
                elif c in ("cat_days", "earn_days", "long_score", "short_score", "news_count"):
                    cells.append(fmt.num(v, 0))
                elif c == "dollar_vol":
                    cells.append(Text(fmt.big(v), style=WHITE))
                elif isinstance(v, float):
                    cells.append(fmt.num(v, 2))
                else:
                    cells.append(Text(str(v)[:70], style=WHITE))
            t.add_row(Text(tk, style=f"bold {AMBER}"), Text(_short(r["name"], 22), style=WHITE), *cells, key=tk)
        head = self.query_one("#scrn-title", Static)
        head.update(Text.assemble((f"{s.code}  ", f"bold {AMBER}"), (s.title + "\n", f"bold {WHITE}"),
                                  (s.description + f"   ·  {len(res)} matches", DIM)))
        head.border_title = "SCREEN"

    @on(OptionList.OptionSelected, "#scrn-list")
    def _scrn_pick(self, event: OptionList.OptionSelected) -> None:
        self.show_screen(event.option.id, switch=False)
        self.query_one("#scrn-table", DataTable).focus()

    @on(OptionList.OptionHighlighted, "#scrn-list")
    def _scrn_hl(self, event: OptionList.OptionHighlighted) -> None:
        if not self.snap.board.empty:
            self.show_screen(event.option.id, switch=False)
            self.save_state()

    # ── IDEAS ──────────────────────────────────────────────────────────
    def _idea_panel(self, i: TradeIdea) -> Panel:
        head = Text()
        head.append(f"{i.ticker} ", style=f"bold {AMBER}")
        head.append(f"{i.name} ", style=WHITE)
        head.append_text(fmt.direction(i.direction))
        head.append(f" {i.structure.upper()} ", style=f"bold {WHITE} on #30363d")
        head.append(f"  {'●' * i.conviction}{'○' * (5 - i.conviction)}", style=AMBER)
        lv = Table.grid(padding=(0, 2))
        for _ in range(6):
            lv.add_column()
        basis = "PREM" if i.basis == "premium" else "REF"
        lv.add_row(*[Text(x, style=DIM) for x in (basis, "TARGET", "STOP", "R:R", "DEBIT", "B/E")])
        be = (f"{i.breakeven_low:.2f}/" if i.breakeven_low else "") + (f"{i.breakeven:.2f}" if i.breakeven else "—")
        lv.add_row(fmt.num(i.entry), fmt.num(i.target, style=UP), fmt.num(i.stop, style=DN),
                   fmt.num(i.rr, 1), fmt.num(i.net_premium) if i.net_premium else Text("—", style=DIM),
                   Text(be, style=WHITE))
        body = [head, Text(i.headline, style=f"bold {WHITE}"), Text(i.trade_line, style=f"bold {AMBER} on #0d1117"), lv,
                Text(f"{i.horizon}" + (f" · ATM IV {i.iv * 100:.0f}%" if i.iv else "") +
                     (f" · RV20 {i.rv * 100:.0f}%" if i.rv else "") + (f" · {i.catalyst[:70]}" if i.catalyst else ""),
                     style=DIM),
                Text(""), Text(i.thesis, style=WHITE), Text("")]
        for d in i.drivers[:5]:
            body.append(Text(f"▸ {d}", style="#c9d1d9"))
        body.append(Text("RISKS", style=f"bold {DN}"))
        for r in i.risks[:3]:
            body.append(Text(f"▸ {r}", style="#c9d1d9"))
        col = BLUE if i.tier == CONSERVATIVE else AMBER
        return Panel(Group(*body), border_style=col, padding=(0, 1))

    def render_ideas(self) -> None:
        take = self.query_one("#ideas-take", Static)
        take.update(Text(self.snap.market_take or "Building today's ideas…", style=WHITE))
        take.border_title = f"THE TAKE · theses by {self.snap.writer or '…'}  (y: copy all trade lines)"
        for tier, wid, title in ((CONSERVATIVE, "#ideas-cons", "CONSERVATIVE · large-cap · defined risk"),
                                 (AGGRESSIVE, "#ideas-aggr", "AGGRESSIVE · SMID / catalysts · convex")):
            panels = [self._idea_panel(i) for i in self.snap.ideas if i.tier == tier]
            w = self.query_one(wid, Static)
            w.update(Group(*panels) if panels else Text("No setup cleared the filters.", style=DIM))
            w.parent.border_title = title

    # ── CAL ────────────────────────────────────────────────────────────
    def render_cal(self) -> None:
        b = self.snap.board
        cal = list(enumerate(self.snap.calendar))
        if "cal-table" in self.sorts:
            field, desc = self.sorts["cal-table"]

            def val(c):
                if field.startswith("_"):
                    col = field[1:]
                    return _sort_key(b.loc[c.ticker, col] if c.ticker in b.index else None)
                return _sort_key(getattr(c, field).toordinal() if field == "when" else getattr(c, field))
            cal.sort(key=lambda nc: val(nc[1]), reverse=desc)
        t = self.query_one("#cal-table", DataTable)
        t.clear()
        for n, c in cal:
            r = b.loc[c.ticker] if c.ticker in b.index else None
            t.add_row(Text(f"{c.when:%a %d %b %y}", style=WHITE), fmt.num(c.days_out, 0),
                      Text(c.ticker, style=f"bold {AMBER}"), fmt.cat_type(c.type), Text(c.event[:90], style=WHITE),
                      fmt.num(r["last"]) if r is not None else Text("—"),
                      fmt.pct(r["chg1m"]) if r is not None else Text("—"),
                      fmt.pct(r["rv20"], 0, plus=False) if r is not None else Text("—"),
                      Text(c.source[:20], style=DIM), key=f"{c.ticker}:{n}")
        types = pd.Series([c.type for c in self.snap.calendar]).value_counts().to_dict()
        w = self.query_one("#cal-title", Static)
        w.update(Text.assemble(("CATALYST CALENDAR  ", f"bold {AMBER}"),
                               ("  ".join(f"{k} {v}" for k, v in types.items()), WHITE),
                               ("    click headers to sort · curated: config/catalysts.yaml + ~/.rxterm/catalysts.yaml", DIM)))
        w.border_title = "CAL"

    # ── DES ────────────────────────────────────────────────────────────
    def _tf_bar(self, prefix: str = "des") -> str:
        """Clickable timeframe / chart-option bar (Textual markup)."""
        parts = []
        for k, tf in enumerate(tfs.TIMEFRAMES):
            digit = next(d for d, c in tfs.DIGIT_KEYS.items() if c == tf.code)
            style = "bold #000000 on #ff9e1b" if tf.code == self.tf else "#e6edf3 on #1c2128"
            parts.append(f"[{style} @click=app.set_tf('{tf.code}')] {tf.code} [/] ")
        bar = "".join(parts)
        if prefix == "des":
            mode = "CANDLE" if self.chart_mode == "candle" else "LINE"
            bar += (f"  [#6e7681]│[/]  [#e6edf3 on #1c2128 @click=app.chart('mode')] {mode} [/] "
                    f"[#e6edf3 on #1c2128 @click=app.chart('ma')] MA {self.chart_ma or 'off'} [/] "
                    f"[#e6edf3 on #1c2128 @click=app.chart('vol')] VOL {'on' if self.chart_vol else 'off'} [/]"
                    f"  [#6e7681]keys: 1-9 0 · [ ] · t m v[/]")
        else:
            bar += "  [#6e7681]keys: 1-9 0 · [ ][/]"
        return bar

    def action_set_tf(self, code: str) -> None:
        if code not in tfs.TF:
            return
        self.tf = code
        self.save_state()
        if self.current == "COMP":
            self._load_comp()
        else:
            self._chart_des()

    def action_chart(self, what: str) -> None:
        chart = self.query_one("#des-chart", PriceChart)
        if what == "mode":
            self.chart_mode = "candle" if self.chart_mode == "line" else "line"
        elif what == "ma":
            self.chart_ma = MA_CYCLE[(MA_CYCLE.index(self.chart_ma) + 1) % len(MA_CYCLE)] if self.chart_ma in MA_CYCLE else 50
        elif what == "vol":
            self.chart_vol = not self.chart_vol
        chart.mode, chart.ma, chart.volume = self.chart_mode, self.chart_ma, self.chart_vol
        self.query_one("#des-tf", Static).update(self._tf_bar())
        chart.refresh()
        self.save_state()

    def _chart_des(self) -> None:
        tk, code = self.ticker, self.tf
        self.query_one("#des-tf", Static).update(self._tf_bar())
        chart = self.query_one("#des-chart", PriceChart)
        chart.mode, chart.ma, chart.volume = self.chart_mode, self.chart_ma, self.chart_vol
        daily = self.snap.history.get(tk)
        sliced = tfs.from_daily(daily, tfs.TF[code])
        if sliced is not None and len(sliced) >= 3:
            chart.set_data(sliced, f"{tk} · {code}", intraday=False)
        else:
            chart.set_data(None, f"{tk} · {code}")
            self._load_bars(tk, code)

    @work(thread=True, exclusive=True, group="bars")
    def _load_bars(self, tk: str, code: str) -> None:
        df = tfs.get_bars(self.engine.md, tk, code)
        self.call_from_thread(self._set_bars, tk, code, df)

    def _set_bars(self, tk: str, code: str, df) -> None:
        if tk != self.ticker or code != self.tf:
            return  # user moved on
        chart = self.query_one("#des-chart", PriceChart)
        if df is None or len(df) < 2:
            chart.set_data(pd.DataFrame(), f"{tk} · {code}")
            self.status(f"{tk}: no {code} data (market data provider returned nothing)", error=True)
            return
        chart.set_data(df, f"{tk} · {code}", intraday=tfs.TF[code].intraday)

    def render_des(self) -> None:
        tk = self.ticker
        b = self.snap.board
        if tk not in b.index:
            self.status(f"{tk}: no data", error=True)
            return
        r = b.loc[tk]
        sec = universe.get(tk)
        head = Text()
        head.append(f" {tk} US Equity ", style="bold black on #ff9e1b")
        head.append(f"  {r['name']}", style=f"bold {WHITE}")
        head.append(f"  ·  {r['segment']}   ", style=DIM)
        head.append(f"{r['last']:,.2f} ", style=f"bold {WHITE}")
        head.append_text(fmt.pct(r["chg1d"], 2))
        if r.get("premkt") == r.get("premkt") and r.get("premkt") is not None:
            head.append("   PRE ", style=DIM)
            head.append_text(fmt.pct(r["premkt"], 2))
        head.append("   SIGNAL ", style=DIM)
        head.append_text(fmt.signal(r["signal"]))
        head.append(f"   L {r['long_score']:.0f} / S {r['short_score']:.0f}" if r["long_score"] == r["long_score"] else "",
                    style=DIM)
        if tk in self.watch:
            head.append("   ★ WATCH", style=AMBER)
        alerts = [a for a in self.alerts.alerts if a.ticker == tk and a.armed]
        if alerts:
            head.append("   🔔 " + ", ".join(f"{a.op}{a.level:,.2f}" for a in alerts), style=AMBER)
        hw = self.query_one("#des-head", Static)
        hw.update(head)
        hw.border_title = "DES   , . prev/next · + watch · y copy · ? keys · ⌫ back"
        self._chart_des()

        prof = self.snap.profiles.get(tk, {}) or {}
        st = Table.grid(padding=(0, 1), expand=True)
        st.add_column(style=DIM)
        st.add_column(justify="right")

        def row(k, v):
            st.add_row(k, v if isinstance(v, Text) else Text(str(v), style=WHITE))

        row("Mkt Cap", fmt.big(r["mcap"]))
        row("Fwd P/E", fmt.num(r["fwd_pe"], 1))
        row("Beta", fmt.num(r["beta"], 2))
        row("52W Range", f"{r['lo52']:,.2f} – {r['hi52']:,.2f}")
        row("vs 52W High", fmt.pct(r["off_hi"]))
        row("vs 50 / 200 DMA", Text.assemble(fmt.pct(r["dist50"]), " / ", fmt.pct(r["dist200"])))
        row("RSI(14)", fmt.rsi(r["rsi"]))
        row("RV20 / ATR%", f"{r['rv20'] * 100:.0f}% / {r['atr_pct'] * 100:.1f}%" if r["rv20"] == r["rv20"] else "—")
        row("Vol × 20D", fmt.num(r["vol_ratio"], 1))
        row("RS vs XBI 3M", fmt.pct(r["rs3m"]))
        row("1M / 3M / YTD", Text.assemble(fmt.pct(r["chg1m"]), " ", fmt.pct(r["chg3m"]), " ", fmt.pct(r["ytd"])))
        row("Short % Float", fmt.pct(r["short_float"], 1, plus=False))
        row("Street Target", Text.assemble(fmt.num(r["target"]), " ", fmt.pct(r["target_upside"])))
        row("Consensus", (r["rec"] or "—").replace("_", " ").upper() + (f" ({r['analysts']})" if r["analysts"] else ""))
        row("Cash", fmt.big(prof.get("totalCash")))
        row("Rev Growth", fmt.pct(prof.get("revenueGrowth")))
        row("Next Earnings", f"{r['earn_date']:%d %b %Y} ({int(r['earn_days'])}d)" if r["earn_date"] else "—")
        cat = Text(f"{r['cat_type']} {r['cat_date']:%d %b} ({int(r['cat_days'])}d)", style=DN) if r["cat_type"] else Text("—", style=DIM)
        row("Next Catalyst", cat)
        row("News (72h)", Text(f"{int(r['news_count'])} · score {r['news_score']:+.2f}", style=WHITE))
        sw = self.query_one("#des-stats", Static)
        sw.update(st)
        sw.border_title = "KEY STATS"

        nt = self.query_one("#des-news", DataTable)
        nt.clear()
        for n, it in enumerate(for_ticker(self.snap.news, tk)[:40]):
            age = it.age_hours
            nt.add_row(Text(f"{int(age)}h" if age < 48 else f"{int(age / 24)}d", style=DIM), fmt.tone(it.tone),
                       Text(it.title, style=WHITE), key=f"d{n}")
        nt.border_title = f"{tk} NEWS  (⏎ opens story)"
        about = Text()
        if r["cat_event"]:
            about.append("CATALYST  ", style=f"bold {DN}")
            about.append(r["cat_event"] + "\n\n", style=WHITE)
        idea = next((i for i in self.snap.ideas if i.ticker == tk), None)
        if idea:
            about.append(f"RXTERM IDEA  {idea.direction} · {idea.structure}\n", style=f"bold {AMBER}")
            about.append(idea.trade_line + "\n", style=AMBER)
            about.append(idea.thesis + "\n\n", style=WHITE)
        summary = prof.get("longBusinessSummary") or (sec.name if sec else "")
        about.append(summary[:900], style="#c9d1d9")
        aw = self.query_one("#des-about", Static)
        aw.update(about)
        aw.border_title = "PROFILE"

    # ── COMP ───────────────────────────────────────────────────────────
    def _cmd_comp(self, names: list[str]) -> None:
        picks, period = [], None
        for n in names:
            if tfs.resolve(n) and n not in universe.UNIVERSE:
                period = tfs.resolve(n)
            elif n in universe.UNIVERSE and n not in picks:
                picks.append(n)
        if not picks:
            picks = self.comp or [self.ticker, universe.SECTOR_BENCH]
        if len(picks) == 1:
            picks.append(universe.SECTOR_BENCH if picks[0] != universe.SECTOR_BENCH else "SPY")
        self.comp = picks[:6]
        if period:
            self.tf = period
        self.show("COMP")

    def _load_comp(self) -> None:
        if not self.comp:
            self.comp = [self.ticker, universe.SECTOR_BENCH]
        self.query_one("#comp-tf", Static).update(self._tf_bar("comp"))
        self.query_one("#comp-chart", PriceChart).set_compare([], f"COMP · loading {' '.join(self.comp)}")
        self._fetch_comp(list(self.comp), self.tf)

    @work(thread=True, exclusive=True, group="comp")
    def _fetch_comp(self, names: list[str], code: str) -> None:
        series = []
        for n in names:
            df = tfs.get_bars(self.engine.md, n, code, self.snap.history.get(n))
            if df is not None and len(df) >= 2:
                series.append((n, df["Close"]))
        self.call_from_thread(self._set_comp, names, code, series)

    def _set_comp(self, names, code, series) -> None:
        if names != self.comp or code != self.tf:
            return
        chart = self.query_one("#comp-chart", PriceChart)
        chart.intraday = tfs.TF[code].intraday
        chart.set_compare(series, f"COMP · {code} · % change")

    # ── OMON ───────────────────────────────────────────────────────────
    _omon_for = ""

    def render_omon(self) -> None:
        tk = self.ticker
        if self._omon_for != tk:
            self._omon_for = tk
            self._chain = None
            self.query_one("#omon-exp", OptionList).clear_options()
            self.query_one("#omon-table", DataTable).clear()
            self.query_one("#omon-head", Static).update(Text(f"{tk} · loading option expiries…", style=DIM))
            self._load_expiries(tk)

    @work(thread=True, exclusive=True, group="omon")
    def _load_expiries(self, tk: str) -> None:
        exps = self.engine.md.expiries(tk)
        self.call_from_thread(self._set_expiries, tk, exps)

    def _set_expiries(self, tk: str, exps: list[date]) -> None:
        if tk != self.ticker:
            return
        ol = self.query_one("#omon-exp", OptionList)
        ol.clear_options()
        for e in exps[:24]:
            ol.add_option(Option(f"{e:%d %b %y}  {(e - date.today()).days:>4}d", id=e.isoformat()))
        ol.border_title = "EXPIRY  [ ]"
        if exps:
            target = min(exps[:24], key=lambda e: abs((e - date.today()).days - 30))
            ol.highlighted = exps.index(target)
            self._load_chain(tk, target)
        else:
            self.query_one("#omon-head", Static).update(Text(f"{tk}: no listed options", style=DN))

    @on(OptionList.OptionHighlighted, "#omon-exp")
    def _omon_pick(self, event: OptionList.OptionHighlighted) -> None:
        self._load_chain(self.ticker, date.fromisoformat(event.option.id))

    @work(thread=True, exclusive=True, group="chain")
    def _load_chain(self, tk: str, exp: date) -> None:
        chain = self.engine.md.option_chain(tk, exp)
        self.call_from_thread(self._set_chain, chain)

    def _set_chain(self, chain) -> None:
        t = self.query_one("#omon-table", DataTable)
        t.clear()
        head = self.query_one("#omon-head", Static)
        self._chain = chain
        if chain is None:
            head.update(Text("chain unavailable — Yahoo returned nothing for this expiry; try another or press F10", style=DN))
            return
        from ..analytics.ideas import atm_iv, options_flow

        calls = chain.calls.set_index("strike")
        puts = chain.puts.set_index("strike")
        strikes = sorted(set(calls.index) | set(puts.index))
        spot = chain.spot
        near = [k for k in strikes if 0.65 * spot <= k <= 1.35 * spot] or strikes
        atm = min(near, key=lambda k: abs(k - spot)) if near else None
        t_years = max(chain.dte, 1) / 365

        def side(df, k, itm, call):
            if k not in df.index:
                return [Text("")] * 7
            r = df.loc[k]
            if isinstance(r, pd.DataFrame):
                r = r.iloc[0]
            bg = " on #12261e" if itm else ""
            d = bs_delta(spot, k, t_years, r["iv"], call)
            return [Text(f"{r['bid']:.2f}", style=WHITE + bg), Text(f"{r['ask']:.2f}", style=WHITE + bg),
                    Text(f"{r['last']:.2f}", style=DIM + bg),
                    Text(f"{r['iv'] * 100:.0f}%" if r["iv"] == r["iv"] else "—", style=AMBER + bg),
                    Text(f"{d:+.2f}" if d is not None else "—", style=BLUE + bg),
                    Text(f"{int(r['volume']):,}", style=(UP if r["volume"] > r["openInterest"] > 0 else WHITE) + bg),
                    Text(f"{int(r['openInterest']):,}", style=DIM + bg)]

        for k in near:
            strike_style = "bold black on #ff9e1b" if k == atm else f"bold {WHITE}"
            t.add_row(*side(calls, k, k < spot, True), Text(f"{k:g}".center(8), style=strike_style),
                      *side(puts, k, k > spot, False), key=str(k))
        iv = atm_iv(chain)
        fl = options_flow(chain)
        rv = self.snap.board.loc[chain.ticker, "rv20"] if chain.ticker in self.snap.board.index else float("nan")
        h = Text()
        h.append(f"{chain.ticker} OMON  ", style=f"bold {AMBER}")
        h.append(f"spot {spot:,.2f}  exp {chain.expiry:%d %b %Y} ({chain.dte}d)   ", style=WHITE)
        h.append(f"ATM IV {iv * 100:.0f}%  " if iv else "ATM IV —  ", style=AMBER)
        h.append(f"RV20 {rv * 100:.0f}%  " if rv == rv else "", style=WHITE)
        if iv:
            h.append(f"implied move ±{iv * (chain.dte / 365) ** 0.5 * 100:.1f}%   ", style=WHITE)
        h.append(f"P/C vol {fl['pc_vol']:.2f}  P/C OI {fl['pc_oi']:.2f}", style=DIM)
        head.update(h)
        head.border_title = "OPTION MONITOR   [ ] expiry · y copy contract · green volume = vol > OI · Δ = delta"
        if atm is not None:
            t.move_cursor(row=near.index(atm))

    # ── Watchlist ──────────────────────────────────────────────────────
    def _load_watch(self) -> list[str]:
        p = self.cfg.watchlist_path
        if p.exists():
            return [x.strip().upper() for x in p.read_text(encoding="utf-8").split() if x.strip().upper() in universe.UNIVERSE]
        return ["LLY", "NVO", "VRTX", "REGN", "MRNA", "VKTX", "MDGL", "SMMT"]

    def _save_watch(self) -> None:
        self.cfg.ensure_home()
        self.cfg.watchlist_path.write_text("\n".join(self.watch) + "\n", encoding="utf-8")

    def render_watch(self) -> None:
        b = self.snap.board
        rows = [tk for tk in self.watch if tk in b.index]
        if "w-table" in self.sorts and rows:
            field, desc = self.sorts["w-table"]
            rows.sort(key=lambda tk: _sort_key(tk if field == "_ticker" else b.loc[tk, field]), reverse=desc)
        t = self.query_one("#w-table", DataTable)
        t.clear()
        for tk in rows:
            r = b.loc[tk]
            cat = f"{r['cat_type']} {r['cat_date']:%d %b}" if r["cat_type"] else (
                f"EARN {r['earn_date']:%d %b}" if r["earn_date"] else "—")
            t.add_row(Text(tk, style=f"bold {AMBER}"), Text(_short(r["name"], 22), style=WHITE), fmt.num(r["last"]),
                      fmt.pct(r["chg1d"], 2), fmt.pct(r["chg5d"]), fmt.pct(r["chg1m"]), fmt.rsi(r["rsi"]),
                      fmt.signal(r["signal"]), Text(cat, style=WHITE), Text(r["headline"][:80], style=DIM), key=tk)
        w = self.query_one("#w-title", Static)
        w.update(Text.assemble(("WATCHLIST  ", f"bold {AMBER}"), (" ".join(self.watch) or "empty", WHITE),
                               ("     + / − on any row · WADD TICK · WDEL TICK · click headers to sort", DIM)))
        w.border_title = "W"
        al = Text()
        if not self.alerts.alerts:
            al.append("No price alerts.  Set one:  ALRT LLY > 1250   ·   ALRT VKTX < 30   ·   remove: ALRTDEL LLY",
                      style=DIM)
        for a in self.alerts.alerts:
            px = b.loc[a.ticker, "last"] if a.ticker in b.index else float("nan")
            al.append("🔔 " if a.armed else "✔ ", style=AMBER if a.armed else UP)
            al.append(f"{a.describe():<26}", style=f"bold {WHITE}" if a.armed else DIM)
            al.append(f" now {px:,.2f}" if px == px else "", style=WHITE)
            if a.armed and px == px:
                al.append(f"  ({(a.level / px - 1) * 100:+.1f}% away)", style=DIM)
            if a.triggered:
                al.append(f"  triggered {a.triggered.replace('T', ' ')}", style=UP)
            al.append("\n")
        aw = self.query_one("#w-alerts", Static)
        aw.update(al)
        aw.border_title = "PRICE ALERTS  (checked every minute while the market is open)"

    # ── HELP ───────────────────────────────────────────────────────────
    def _help(self) -> Text:
        t = Text()
        t.append("RXTERM — PHARMA & BIOTECH TRADING TERMINAL\n\n", style=f"bold {AMBER}")
        sections = [
            ("COMMANDS", [
                ("LLY ⏎", "Security page: chart, key stats, catalyst, news, RXTERM idea"),
                ("LLY 5D · LLY GP 1Y", "Chart timeframe: 1D 5D 1M 3M 6M YTD 1Y 2Y 5Y 10Y"),
                ("LLY OMON", "Option chain with IV, delta, implied move, put/call"),
                ("LLY N", "News for one ticker"),
                ("COMP LLY NVO XBI 1Y", "Compare tickers (% change).  LLY VS NVO also works"),
                ("SCRN PDUFA", "Screener:  " + " ".join(screener.SCREENS)),
                ("MON SMID", "Monitor filtered to a segment: ALL BIG LARGE SMID SPEC W"),
                ("ALRT LLY > 1250", "Price alert (or <).  ALRTDEL LLY / ALRTDEL ALL removes"),
                ("WADD VKTX · WDEL VKTX", "Edit the watchlist"),
                ("BACK · REFRESH · Q", "Previous screen · reload everything · quit"),
            ]),
            ("KEYS — EVERYWHERE", [
                ("F1–F10", "HELP MON NEWS SCRN IDEAS CAL DES OMON W REFRESH"),
                ("/ or Esc", "Command line"),
                ("↑ ↓ (command line)", "Previous / next command"),
                ("→ (command line)", "Accept the grey autocomplete suggestion"),
                ("⌫ Backspace", "Back to the previous screen"),
                ("?", "Keys for the current screen"),
                ("+ / −", "Add / remove the highlighted or current ticker on the watchlist"),
                ("y", "Copy (ticker, trade line, option contract, or all trades on IDEAS)"),
                ("Ctrl+Q", "Quit"),
            ]),
            ("KEYS — CHART (DES / COMP)", [
                ("1 2 3 4 5 6 7 8 9 0", "1D 5D 1M 3M 6M YTD 1Y 2Y 5Y 10Y   (or click the buttons)"),
                ("[ ]", "Shorter / longer timeframe"),
                ("t · m · v", "Line ↔ candles · moving average off/20/50/200 · volume on/off"),
                (", .", "Previous / next ticker in the list you came from"),
            ]),
            ("KEYS — TABLES", [
                ("click a column header", "Sort by it (click again to reverse)"),
                ("s · f (MON)", "Cycle sort · cycle segment filter"),
                ("[ ] (OMON)", "Previous / next expiry"),
                ("⏎ / o (NEWS)", "Open the story in your browser"),
            ]),
        ]
        for title, rows in sections:
            t.append(f"{title}\n", style=f"bold {AMBER}")
            for k, v in rows:
                t.append(f"  {k:<24}", style=f"bold {WHITE}")
                t.append(v + "\n", style="#c9d1d9")
            t.append("\n")
        t.append("Signals\n", style=f"bold {AMBER}")
        t.append("  Long/short scores (0–100) rank each name on trend, momentum and relative strength vs XBI, news\n"
                 "  sentiment, Street upside and mean reversion. Conservative trades: large-cap defined-risk spreads.\n"
                 "  Aggressive trades: SMID / catalyst names in outright options, spreads or straddles.\n", style=WHITE)
        t.append(f"\nData: {self.engine.md.name}. Quotes refresh every minute while the market is open. Your settings,\n"
                 "watchlist, alerts and command history are saved in ~/.rxterm.\n", style=DIM)
        t.append("\n" + DISCLAIMER, style=DIM)
        return t


def run(cfg: Settings | None = None) -> None:
    RxTerm(cfg).run()
