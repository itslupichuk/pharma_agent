"""RXTERM terminal — Bloomberg-style, keyboard-driven.

Type a command in the amber command line and press <Enter> (<GO>):

  LLY            security description (chart, stats, news)       → DES
  LLY GP 3M      price chart for a period (1M 3M 6M 1Y)
  LLY OMON       option monitor                                  → OMON
  LLY N          news for a ticker
  MON            sector monitor (home)        NEWS   news wire
  SCRN [CODE]    screener                     IDEAS  today's trades
  CAL            catalyst calendar            W      watchlist (WADD/WDEL TICK)
  REFRESH        reload data                  HELP   this help
"""

from __future__ import annotations

import webbrowser
from dataclasses import replace
from datetime import date

import pandas as pd
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import ContentSwitcher, DataTable, Input, OptionList, Static
from textual.widgets.option_list import Option

from .. import DISCLAIMER, __version__, universe
from ..analytics import screener
from ..analytics.ideas import AGGRESSIVE, CONSERVATIVE, TradeIdea
from ..config import Settings, settings as default_settings
from ..data.news import for_ticker
from ..engine import Engine, Snapshot
from . import fmt
from .fmt import AMBER, BLUE, DIM, DN, UP, WHITE
from .widgets import Clock, PriceChart, TickerTape

FUNCTIONS = ("MON", "NEWS", "SCRN", "IDEAS", "CAL", "DES", "OMON", "W", "HELP")
FKEYS = [("F1", "HELP"), ("F2", "MON"), ("F3", "NEWS"), ("F4", "SCRN"), ("F5", "IDEAS"), ("F6", "CAL"),
         ("F7", "DES"), ("F8", "OMON"), ("F9", "W"), ("F10", "REFRESH")]
PERIODS = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252, "YTD": None}


def _short(name: str, n: int = 18) -> str:
    return name if len(name) <= n else name[: n - 1] + "…"


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
        self.current = "MON"
        self.ticker = "LLY"
        self.period = "6M"
        self.mon_sort = "chg1d"
        self.history_stack: list[str] = []
        self.watch = self._load_watch()
        self.news_rows: list = []

    # ── layout ─────────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static(Text("RXTERM", style=f"bold {AMBER}"), id="logo")
            yield Input(placeholder="Enter command  e.g.  LLY <GO>   ·   SCRN PDUFA   ·   IDEAS   ·   HELP", id="cmd")
            yield Clock(self.cfg.tz, id="clock")
        yield TickerTape(id="tape")
        yield Static(self._fkeys_text(), id="fkeys")
        with ContentSwitcher(initial="MON", id="main"):
            # MON — sector monitor
            with Horizontal(id="MON"):
                with Vertical(id="mon-left"):
                    yield DataTable(id="mon-table", cursor_type="row", zebra_stripes=True)
                with Vertical(id="mon-right"):
                    yield Static(id="mon-bench", classes="panel")
                    yield Static(id="mon-sector", classes="panel")
                    yield DataTable(id="mon-news", cursor_type="row", show_header=False, classes="panel")
                    yield Static(id="mon-ideas", classes="panel")
            # NEWS
            with Vertical(id="NEWS"):
                yield DataTable(id="news-table", cursor_type="row", zebra_stripes=True)
                yield Static(id="news-preview", classes="panel")
            # SCRN
            with Horizontal(id="SCRN"):
                yield OptionList(*[Option(f"{s.code:<11}{s.title}", id=s.code) for s in screener.SCREENS.values()],
                                 id="scrn-list")
                with Vertical(id="scrn-right"):
                    yield Static(id="scrn-title", classes="panel")
                    yield DataTable(id="scrn-table", cursor_type="row", zebra_stripes=True)
            # IDEAS
            with Vertical(id="IDEAS"):
                yield Static(id="ideas-take", classes="panel")
                with Horizontal(id="ideas-cols"):
                    yield VerticalScroll(Static(id="ideas-cons"), id="ideas-cons-wrap")
                    yield VerticalScroll(Static(id="ideas-aggr"), id="ideas-aggr-wrap")
            # CAL
            with Vertical(id="CAL"):
                yield Static(id="cal-title", classes="panel")
                yield DataTable(id="cal-table", cursor_type="row", zebra_stripes=True)
            # DES
            with Vertical(id="DES"):
                yield Static(id="des-head", classes="panel")
                with Horizontal(id="des-body"):
                    with Vertical(id="des-chart-wrap"):
                        yield PriceChart(id="des-chart")
                    yield Static(id="des-stats", classes="panel")
                with Horizontal(id="des-bottom"):
                    yield DataTable(id="des-news", cursor_type="row", show_header=False)
                    yield Static(id="des-about", classes="panel")
            # OMON
            with Horizontal(id="OMON"):
                yield OptionList(id="omon-exp")
                with Vertical(id="omon-right"):
                    yield Static(id="omon-head", classes="panel")
                    yield DataTable(id="omon-table", cursor_type="row", zebra_stripes=True)
            # W — watchlist
            with Vertical(id="W"):
                yield Static(id="w-title", classes="panel")
                yield DataTable(id="w-table", cursor_type="row", zebra_stripes=True)
            # HELP
            yield VerticalScroll(Static(id="help-text"), id="HELP")
        yield Static(id="status")

    def _fkeys_text(self) -> Text:
        t = Text()
        for k, name in FKEYS:
            active = name == getattr(self, "current", "MON")
            t.append(f" {k} ", style="bold black on #ff9e1b")
            t.append(f" {name} ", style=f"bold {AMBER} on #1c2128" if active else f"{WHITE}")
            t.append(" ")
        t.append("  ESC command line · ↑↓ select · ⏎ open · CTRL+Q quit", style=DIM)
        return t

    def on_mount(self) -> None:
        self._setup_tables()
        self.query_one("#help-text", Static).update(self._help())
        self.query_one("#cmd", Input).focus()
        self.status("Loading prices…", busy=True)
        self.load_data()
        self.set_interval(300, self.reload_prices)

    def _setup_tables(self) -> None:
        mon = self.query_one("#mon-table", DataTable)
        mon.add_columns("TICKER", "NAME", "LAST", "CHG", "5D", "1M", "3M", "YTD", "RSI", "RV20", "VOL×",
                        "SIGNAL", "60D")
        self.query_one("#mon-news", DataTable).add_columns("T", "TKR", "HEADLINE")
        self.query_one("#news-table", DataTable).add_columns("TIME", "SRC", "TICKERS", "", "EVENT", "HEADLINE")
        self.query_one("#cal-table", DataTable).add_columns("DATE", "DAYS", "TICKER", "TYPE", "EVENT", "LAST",
                                                            "1M", "RV20", "SOURCE")
        self.query_one("#des-news", DataTable).add_columns("AGE", "", "HEADLINE")
        self.query_one("#omon-table", DataTable).add_columns(
            "C.BID", "C.ASK", "C.LAST", "C.IV", "C.VOL", "C.OI", "STRIKE", "P.BID", "P.ASK", "P.LAST", "P.IV",
            "P.VOL", "P.OI")
        self.query_one("#w-table", DataTable).add_columns("TICKER", "NAME", "LAST", "CHG", "5D", "1M", "RSI",
                                                          "SIGNAL", "NEXT CATALYST", "HEADLINE")

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

    @work(thread=True, exclusive=True, group="prices")
    def reload_prices(self) -> None:
        if self.snap.board.empty:
            return
        snap = replace(self.snap)
        self.engine.load_prices(snap)
        self.engine.compute(snap)
        self.call_from_thread(self._apply, snap, None)

    def _apply(self, snap: Snapshot, msg: str | None) -> None:
        self.snap = snap
        if snap.board.empty:
            self.status("No market data returned — check network or run with --demo", error=True)
            return
        self._render_tape()
        self.show(self.current, refresh_only=True)
        if msg:
            self.status(msg, busy=True)
        else:
            n = len(snap.board)
            self.status(f"Ready · {n} securities · data as of {snap.as_of} · {snap.provider}"
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
        t.append(f"   RXTERM v{__version__}", style=DIM)
        self.query_one("#status", Static).update(t)

    # ── command line ───────────────────────────────────────────────────
    def action_focus_cmd(self) -> None:
        cmd = self.query_one("#cmd", Input)
        cmd.value = ""
        cmd.focus()

    def action_fn(self, name: str) -> None:
        self.show(name)

    def action_refresh_data(self) -> None:
        self.engine.cache._mem.clear()
        self.status("Refreshing…", busy=True)
        self.load_data()

    @on(Input.Submitted, "#cmd")
    def on_command(self, event: Input.Submitted) -> None:
        raw = event.value.replace("<GO>", "").strip().upper()
        event.input.value = ""
        if raw:
            self.run_command(raw)

    def run_command(self, raw: str) -> None:
        toks = raw.split()
        head, args = toks[0], toks[1:]
        if head in ("REFRESH", "F10"):
            return self.action_refresh_data()
        if head in ("Q", "QUIT", "EXIT"):
            return self.exit()
        if head == "WADD" and args:
            for t in args:
                if t in universe.UNIVERSE and t not in self.watch:
                    self.watch.append(t)
            self._save_watch()
            return self.show("W")
        if head == "WDEL" and args:
            self.watch = [t for t in self.watch if t not in args]
            self._save_watch()
            return self.show("W")
        if head in FUNCTIONS:
            if head in ("DES", "OMON") and args and args[0] in universe.UNIVERSE:
                self.ticker = args[0]
            if head == "SCRN" and args and args[0] in screener.SCREENS:
                return self.show_screen(args[0])
            return self.show(head)
        if head in ("GP", "N") and args:
            head, args = args[0], [toks[0]] + args[1:]
        if head in universe.UNIVERSE:
            self.ticker = head
            sub = args[0] if args else "DES"
            if sub in PERIODS:
                self.period = sub
                return self.show("DES")
            if sub == "GP":
                if len(args) > 1 and args[1] in PERIODS:
                    self.period = args[1]
                return self.show("DES")
            if sub in ("N", "NEWS", "CN"):
                return self.show("NEWS", news_filter=head)
            if sub in ("OMON", "OM", "OPT", "OPTIONS"):
                return self.show("OMON")
            return self.show("DES")
        # fuzzy: company name
        for sec in universe.UNIVERSE.values():
            if raw in sec.name.upper():
                self.ticker = sec.ticker
                return self.show("DES")
        self.status(f"Unknown command: {raw}  (type HELP)", error=True)

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
        }[self.current]
        if not self.snap.board.empty or self.current == "HELP":
            render()
        if not refresh_only:
            focus = {"MON": "#mon-table", "NEWS": "#news-table", "SCRN": "#scrn-list", "CAL": "#cal-table",
                     "OMON": "#omon-exp", "W": "#w-table", "DES": "#des-news"}.get(name)
            if focus:
                self.query_one(focus).focus()

    # ── MON ────────────────────────────────────────────────────────────
    def render_mon(self) -> None:
        b = self.snap.board
        eq = b[b["segment"] != universe.ETF].sort_values(self.mon_sort, ascending=False)
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
        t.border_title = f"SECTOR MONITOR · {len(eq)} names · sorted by {self.mon_sort.upper()}  (s: cycle sort)"
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
        line.append(f"ADV/DEC ", style=DIM)
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

    def on_key(self, event) -> None:
        if self.current == "MON" and event.key == "s" and self.focused is not self.query_one("#cmd", Input):
            order = ["chg1d", "chg5d", "chg1m", "chg3m", "ytd", "rsi", "rv20", "vol_ratio", "long_score", "short_score"]
            self.mon_sort = order[(order.index(self.mon_sort) + 1) % len(order)] if self.mon_sort in order else "chg1d"
            self.render_mon()
        elif self.current == "DES" and event.key in ("1", "3", "6", "y") and self.focused is not self.query_one("#cmd", Input):
            self.period = {"1": "1M", "3": "3M", "6": "6M", "y": "1Y"}[event.key]
            self.render_des()
        elif event.key == "o" and self.current == "NEWS" and self.focused is not self.query_one("#cmd", Input):
            row = self.query_one("#news-table", DataTable).cursor_row
            if row is not None and row < len(self._news_view):
                webbrowser.open(self._news_view[row].link)

    @on(DataTable.RowSelected)
    def on_row(self, event: DataTable.RowSelected) -> None:
        tid = event.data_table.id
        key = event.row_key.value if event.row_key else None
        if tid in ("mon-table", "scrn-table", "w-table", "cal-table") and key:
            self.ticker = key.split(":")[0]
            self.show("DES")
        elif tid == "mon-news" and key:
            it = self.news_rows[int(key[1:])]
            if it.tickers:
                self.ticker = it.tickers[0]
                self.show("DES")
            else:
                self.show("NEWS")

    # ── NEWS ───────────────────────────────────────────────────────────
    _news_view: list = []

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
        t.border_title = f"NEWS WIRE{' · ' + ticker if ticker else ''} · {len(items)} stories  (o: open in browser)"
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
    _screen_code = "TOPLONG"

    def render_scrn(self) -> None:
        self.show_screen(self._screen_code, switch=False)

    def show_screen(self, code: str, switch: bool = True) -> None:
        self._screen_code = code
        if switch and self.current != "SCRN":
            self.current = "SCRN"
            self.query_one("#main", ContentSwitcher).current = "SCRN"
            self.query_one("#fkeys", Static).update(self._fkeys_text())
        s = screener.SCREENS[code]
        res = screener.run(self.snap.board, code, limit=60)
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
        self.show_screen(event.option.id)

    @on(OptionList.OptionHighlighted, "#scrn-list")
    def _scrn_hl(self, event: OptionList.OptionHighlighted) -> None:
        if not self.snap.board.empty:
            self.show_screen(event.option.id, switch=False)

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
        take.border_title = f"THE TAKE · theses by {self.snap.writer or '…'}"
        for tier, wid, title in ((CONSERVATIVE, "#ideas-cons", "CONSERVATIVE · large-cap · defined risk"),
                                 (AGGRESSIVE, "#ideas-aggr", "AGGRESSIVE · SMID / catalysts · convex")):
            panels = [self._idea_panel(i) for i in self.snap.ideas if i.tier == tier]
            w = self.query_one(wid, Static)
            w.update(Group(*panels) if panels else Text("No setup cleared the filters.", style=DIM))
            w.parent.border_title = title

    # ── CAL ────────────────────────────────────────────────────────────
    def render_cal(self) -> None:
        b = self.snap.board
        t = self.query_one("#cal-table", DataTable)
        t.clear()
        for n, c in enumerate(self.snap.calendar):
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
                               ("    curated: config/catalysts.yaml + ~/.rxterm/catalysts.yaml", DIM)))
        w.border_title = "CAL"

    # ── DES ────────────────────────────────────────────────────────────
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
        hw = self.query_one("#des-head", Static)
        hw.update(head)
        hw.border_title = "DES  (1/3/6/y: chart period · OMON for options · N for news)"

        df = self.snap.history.get(tk)
        if df is not None:
            n = PERIODS.get(self.period)
            sl = df[df.index.year == df.index[-1].year] if n is None else df.tail(n + 1)
            self.query_one("#des-chart", PriceChart).set_data(sl, f"{tk} · {self.period}")

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
        nt.border_title = f"{tk} NEWS"
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

    # ── OMON ───────────────────────────────────────────────────────────
    _omon_for = ""

    def render_omon(self) -> None:
        tk = self.ticker
        if self._omon_for != tk:
            self._omon_for = tk
            self.query_one("#omon-exp", OptionList).clear_options()
            self.query_one("#omon-table", DataTable).clear()
            self.query_one("#omon-head", Static).update(Text(f"{tk} · loading option expiries…", style=DIM))
            self._load_expiries(tk)

    @work(thread=True, exclusive=True, group="omon")
    def _load_expiries(self, tk: str) -> None:
        exps = self.engine.md.expiries(tk)
        self.call_from_thread(self._set_expiries, tk, exps)

    def _set_expiries(self, tk: str, exps: list[date]) -> None:
        ol = self.query_one("#omon-exp", OptionList)
        ol.clear_options()
        for e in exps[:24]:
            ol.add_option(Option(f"{e:%d %b %y}  {(e - date.today()).days:>4}d", id=e.isoformat()))
        ol.border_title = "EXPIRY"
        if exps:
            target = min(exps, key=lambda e: abs((e - date.today()).days - 30))
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
        if chain is None:
            head.update(Text("chain unavailable", style=DN))
            return
        from ..analytics.ideas import atm_iv, options_flow

        calls = chain.calls.set_index("strike")
        puts = chain.puts.set_index("strike")
        strikes = sorted(set(calls.index) | set(puts.index))
        spot = chain.spot
        near = [k for k in strikes if 0.65 * spot <= k <= 1.35 * spot] or strikes
        atm = min(near, key=lambda k: abs(k - spot)) if near else None

        def side(df, k, itm):
            if k not in df.index:
                return [Text("")] * 6
            r = df.loc[k]
            if isinstance(r, pd.DataFrame):
                r = r.iloc[0]
            bg = " on #12261e" if itm else ""
            return [Text(f"{r['bid']:.2f}", style=WHITE + bg), Text(f"{r['ask']:.2f}", style=WHITE + bg),
                    Text(f"{r['last']:.2f}", style=DIM + bg),
                    Text(f"{r['iv'] * 100:.0f}%" if r["iv"] == r["iv"] else "—", style=AMBER + bg),
                    Text(f"{int(r['volume']):,}", style=(UP if r["volume"] > r["openInterest"] > 0 else WHITE) + bg),
                    Text(f"{int(r['openInterest']):,}", style=DIM + bg)]

        for k in near:
            strike_style = "bold black on #ff9e1b" if k == atm else f"bold {WHITE}"
            t.add_row(*side(calls, k, k < spot), Text(f"{k:g}".center(8), style=strike_style),
                      *side(puts, k, k > spot), key=str(k))
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
        head.border_title = "OPTION MONITOR  (green volume = volume > open interest)"
        if atm is not None:
            t.move_cursor(row=near.index(atm))

    # ── Watchlist ──────────────────────────────────────────────────────
    def _load_watch(self) -> list[str]:
        p = self.cfg.watchlist_path
        if p.exists():
            return [x.strip().upper() for x in p.read_text().split() if x.strip().upper() in universe.UNIVERSE]
        return ["LLY", "NVO", "VRTX", "REGN", "MRNA", "VKTX", "MDGL", "SMMT"]

    def _save_watch(self) -> None:
        self.cfg.ensure_home()
        self.cfg.watchlist_path.write_text("\n".join(self.watch) + "\n")

    def render_watch(self) -> None:
        b = self.snap.board
        t = self.query_one("#w-table", DataTable)
        t.clear()
        for tk in self.watch:
            if tk not in b.index:
                continue
            r = b.loc[tk]
            cat = f"{r['cat_type']} {r['cat_date']:%d %b}" if r["cat_type"] else (
                f"EARN {r['earn_date']:%d %b}" if r["earn_date"] else "—")
            t.add_row(Text(tk, style=f"bold {AMBER}"), Text(_short(r["name"], 22), style=WHITE), fmt.num(r["last"]),
                      fmt.pct(r["chg1d"], 2), fmt.pct(r["chg5d"]), fmt.pct(r["chg1m"]), fmt.rsi(r["rsi"]),
                      fmt.signal(r["signal"]), Text(cat, style=WHITE), Text(r["headline"][:80], style=DIM), key=tk)
        w = self.query_one("#w-title", Static)
        w.update(Text.assemble(("WATCHLIST  ", f"bold {AMBER}"), (" ".join(self.watch), WHITE),
                               ("     WADD TICK / WDEL TICK to edit", DIM)))
        w.border_title = "W"

    # ── HELP ───────────────────────────────────────────────────────────
    def _help(self) -> Text:
        t = Text()
        t.append("RXTERM — PHARMA & BIOTECH TRADING TERMINAL\n\n", style=f"bold {AMBER}")
        rows = [
            ("<TICKER> ⏎", "Security description: chart, key stats, catalyst, news, RXTERM idea"),
            ("<TICKER> GP 3M", "Price chart for 1M / 3M / 6M / 1Y / YTD (keys 1 3 6 y on DES)"),
            ("<TICKER> OMON", "Option monitor — chain, IV, implied move, put/call, unusual volume"),
            ("<TICKER> N", "News for one ticker"),
            ("MON  (F2)", "Sector monitor — all names, benchmarks, segments, top news, today's trades"),
            ("NEWS (F3)", "Full news wire with event tags and sentiment (o opens the story)"),
            ("SCRN [CODE] (F4)", "Screener: " + ", ".join(screener.SCREENS)),
            ("IDEAS (F5)", "Today's conservative & aggressive trades with theses"),
            ("CAL  (F6)", "Catalyst calendar — PDUFA, AdCom, readouts, trial completions, earnings"),
            ("W (F9) · WADD/WDEL", "Watchlist"),
            ("REFRESH (F10)", "Reload all data"),
            ("ESC", "Jump to the command line"),
            ("CTRL+Q", "Quit"),
        ]
        for k, v in rows:
            t.append(f"  {k:<22}", style=f"bold {AMBER}")
            t.append(v + "\n", style=WHITE)
        t.append("\nSignals\n", style=f"bold {AMBER}")
        t.append("  Long/short scores (0–100) rank each name cross-sectionally on trend (50/200-DMA), 3M momentum and\n"
                 "  relative strength vs XBI, 1M momentum, recency-weighted news sentiment, Street upside, and\n"
                 "  mean-reversion (oversold-in-uptrend / overbought-in-downtrend). Conservative trades are large-cap,\n"
                 "  defined-risk spreads; aggressive trades are SMID / catalyst names in outright options or straddles.\n",
                 style=WHITE)
        t.append(f"\nData: {self.engine.md.name}. News: STAT, BioPharma Dive, Endpoints, Fierce, FDA, GlobeNewswire,\n"
                 "PR Newswire, Google News, Yahoo Finance. Trials: ClinicalTrials.gov.\n", style=DIM)
        t.append("\n" + DISCLAIMER, style=DIM)
        return t


def run(cfg: Settings | None = None) -> None:
    RxTerm(cfg).run()
