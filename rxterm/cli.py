"""RXTERM command line.

  rxterm                      open the RXTERM desktop window
  rxterm terminal             the classic text terminal (runs inside a console)
  rxterm brief [--send]       build the morning brief (HTML/text/JSON in ./out), optionally e-mail it
  rxterm ideas                print today's trade ideas
  rxterm screen CODE          run a preset screen (rxterm screen --list)
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import sys
from dataclasses import replace
from pathlib import Path

from . import __version__
from .config import settings


def _cfg(args):
    cfg = settings
    if getattr(args, "demo", False):  # subcommand flags use SUPPRESS so a global --demo survives
        cfg = replace(cfg, demo=True)
    return cfg


def cmd_terminal(args) -> int:
    from .tui.app import run

    run(_cfg(args))
    return 0


def cmd_gui(args) -> int:
    from .gui.app import run

    return run(_cfg(args), getattr(args, "mode", "auto"))


def cmd_serve(args) -> int:
    """Run only the window's data service (for development / headless use)."""
    import time

    from .gui.backend import Backend
    from .gui.server import Server

    backend = Backend(_cfg(args))
    backend.start()
    srv = Server(backend, port=args.port)
    srv.start()
    print(srv.url, flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


def cmd_gui_selftest(args) -> int:
    """Start the window service on demo data and exercise every endpoint (used by the app build)."""
    import tempfile
    import time
    import urllib.request

    from .gui.backend import Backend
    from .gui.server import STATIC, Server

    cfg = replace(settings, demo=True, home=Path(tempfile.mkdtemp()), anthropic_api_key="")
    backend = Backend(cfg)
    backend.start()
    srv = Server(backend)
    srv.start()
    base = f"http://127.0.0.1:{srv.port}"

    def get(path: str, post: dict | None = None):
        req = urllib.request.Request(base + path, headers={"X-RX-Token": srv.token, "Content-Type": "application/json"},
                                     data=json.dumps(post).encode() if post is not None else None)
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
            return json.loads(body) if path.startswith("/api/") else body

    for _ in range(240):
        st = get("/api/status")
        if st["ready"] and not st["loading"]:
            break
        time.sleep(0.25)
    assert st["ready"], "service never became ready"
    for f in ("index.html", "app.js", "style.css", "icon.png", "vendor/lightweight-charts.standalone.production.js"):
        assert (STATIC / f).exists() and len(get("/" + f)) > 500, f"static {f}"
    m = get("/api/monitor")
    assert len(m["rows"]) > 50 and m["benchmarks"], "monitor"
    assert get("/api/stock?ticker=LLY")["ready"], "stock"
    for tf in ("1D", "5D", "1M", "6M", "1Y", "5Y", "10Y"):
        assert len(get(f"/api/bars?ticker=LLY&tf={tf}")["bars"]) > 5, f"bars {tf}"
    assert len(get("/api/ideas")["ideas"]) == 6, "ideas"
    for sc in get("/api/screens"):
        assert get(f"/api/screen?code={sc['code']}")["ready"], sc["code"]
    assert get("/api/calendar")["rows"], "calendar"
    assert get("/api/news")["items"], "news"
    assert get("/api/news?ticker=LLY")["ready"], "news ticker"
    assert get("/api/chain?ticker=LLY")["ok"], "chain"
    assert len(get("/api/compare?tickers=LLY,NVO,XBI&tf=1Y")["series"]) == 3, "compare"
    assert get("/api/search?q=lilly")[0]["ticker"] == "LLY", "search"
    get("/api/watch_toggle", {"ticker": "ABBV"})
    assert any(r["ticker"] == "ABBV" for r in get("/api/watchlist")["rows"]), "watchlist"
    get("/api/alert_add", {"ticker": "LLY", "op": ">", "level": 1})
    assert get("/api/watchlist")["alerts"], "alerts"
    get("/api/alert_del", {"index": 0})
    assert get("/api/tape"), "tape"
    req = urllib.request.Request(base + "/api/status")
    try:
        urllib.request.urlopen(req, timeout=5)
        raise AssertionError("token check")
    except urllib.error.HTTPError as e:
        assert e.code == 403
    srv.stop()
    try:
        import webview  # noqa: F401

        try:
            from importlib.metadata import version

            wv = f"pywebview {version('pywebview')}"
        except Exception:
            wv = "pywebview loaded"
    except Exception as exc:
        wv = f"pywebview not available ({exc.__class__.__name__}) - will use Edge app window"
    print(f"RXTERM gui-selftest OK · {len(m['rows'])} stocks · {wv}")
    return 0


def cmd_brief(args) -> int:
    from .analytics import thesis
    from .brief import render
    from .engine import Engine

    cfg = _cfg(args)
    out = Path(args.out)
    snap_file = out / "snapshot.pkl"
    if args.reuse and snap_file.exists():
        snap = pickle.loads(snap_file.read_bytes())
        print(f"· reusing snapshot from {snap.generated_at:%H:%M}", file=sys.stderr)
    else:
        print("· pulling market data, news, fundamentals and catalysts…", file=sys.stderr)
        snap = Engine(cfg).full(ideas=True, use_claude=not args.no_claude and not args.theses)
        out.mkdir(parents=True, exist_ok=True)
        snap_file.write_bytes(pickle.dumps(snap))
    if args.theses:
        thesis.apply_theses(snap, json.loads(Path(args.theses).read_text(encoding="utf-8")))
        snap.writer = args.writer or "Claude (desk analyst)"
    paths = render.write_outputs(snap, out)
    print(f"· brief written: {paths['html']}  ({len(snap.ideas)} ideas, theses by {snap.writer})", file=sys.stderr)
    if args.send:
        from .brief.send import EmailNotConfigured, EmailSendFailed, send_email

        try:
            to = send_email(cfg, render.subject_for(snap), paths["html"].read_text(encoding="utf-8"), paths["text"].read_text(encoding="utf-8"), args.to)
        except EmailNotConfigured as exc:
            print(f"· {exc}", file=sys.stderr)
            return 2
        except EmailSendFailed:
            return 1
        print(f"· e-mailed to {to}", file=sys.stderr)
    if args.print:
        print(paths["text"].read_text(encoding="utf-8"))
    return 0


def cmd_ideas(args) -> int:
    from rich.console import Console
    from rich.table import Table

    from .engine import Engine

    snap = Engine(_cfg(args)).full(ideas=True, use_claude=not args.no_claude)
    con = _console()
    t = Table(title=f"RXTERM ideas — {snap.generated_at:%a %d %b %Y}", header_style="bold #ff9e1b")
    for col in ("Tier", "Ticker", "Dir", "Structure", "Trade", "Tgt", "Stop", "Conv"):
        t.add_column(col)
    for i in snap.ideas:
        t.add_row(i.tier[:5], i.ticker, i.direction, i.structure, i.trade_line, f"{i.target:.2f}", f"{i.stop:.2f}",
                  "●" * i.conviction)
    con.print(t)
    for i in snap.ideas:
        con.print(f"\n[bold #ff9e1b]{i.ticker}[/] [bold]{i.headline}[/]\n{i.thesis}")
    return 0


def cmd_screen(args) -> int:
    from rich.console import Console
    from rich.table import Table

    from .analytics import screener
    from .engine import Engine

    if args.list or not args.code:
        for s in screener.SCREENS.values():
            print(f"{s.code:<11} {s.title:<28} {s.description}")
        return 0
    snap = Engine(_cfg(args)).full(ideas=False)
    s = screener.SCREENS[args.code.upper()]
    res = screener.run(snap.board, s.code)
    t = Table(title=f"{s.code} · {s.title} ({len(res)})", header_style="bold #ff9e1b")
    t.add_column("Ticker")
    for c in s.columns:
        t.add_column(c)
    for tk, r in res.iterrows():
        t.add_row(tk, *[f"{r[c]:.3f}" if isinstance(r[c], float) else str(r[c]) for c in s.columns])
    _console().print(t)
    return 0


def cmd_smtp_check(args) -> int:
    from .brief.send import probe

    for line in probe(_cfg(args)):
        print(line)
    return 0


def cmd_selftest(args) -> int:
    """End-to-end check used by the app build: engine, screens, brief rendering and the TUI (headless)."""
    import asyncio
    import tempfile

    from .analytics import screener
    from .brief import render
    from .engine import Engine
    from .tui.app import RxTerm

    cfg = replace(settings, demo=True, home=Path(tempfile.mkdtemp()), anthropic_api_key="")
    snap = Engine(cfg).full()
    assert len(snap.board) > 50 and len(snap.ideas) == 6, "engine"
    for code in screener.SCREENS:
        screener.run(snap.board, code)
    out = render.write_outputs(snap, Path(tempfile.mkdtemp()))
    assert out["html"].stat().st_size > 10_000, "brief"
    from .data.catalysts import REPO_CATALYSTS, load_yaml
    assert load_yaml(REPO_CATALYSTS), f"catalysts file missing at {REPO_CATALYSTS}"

    async def tui() -> int:
        app = RxTerm(cfg)
        async with app.run_test(size=(200, 56)) as pilot:
            for _ in range(80):
                await pilot.pause(0.25)
                if app.snap.ideas:
                    break
            for cmd in ("LLY", "IDEAS", "SCRN PDUFA", "NEWS", "CAL", "LLY OMON", "W", "HELP", "MON", "MON SMID",
                        "ALRT LLY > 1", "COMP LLY NVO XBI 1Y", "LLY 1D", "BACK", "LLY 10Y"):
                app.run_command(cmd)
                await pilot.pause(0.3)
            for code in ("5D", "2Y", "1M"):
                app.action_set_tf(code)
                await pilot.pause(0.3)
            for what in ("mode", "ma", "vol"):
                app.action_chart(what)
            # mouse actions (the same handlers the on-screen buttons call)
            app.action_mon_filter("SMID")
            app.action_open("LLY")
            app.action_watch_toggle()
            app.action_browse("next")
            app.action_compare_current()
            app.action_comp_add("SPY")
            app.action_comp_remove("SPY")
            app.action_fn("OMON")
            await pilot.pause(1.0)
            app.action_omon_step("later")
            app.action_fn("W")
            await pilot.pause(0.3)
            await pilot.pause(0.3)
            assert app.alerts.alerts and app.alerts.alerts[0].triggered, "alerts"
            assert app.query_one("#des-chart").df is not None, "chart"
            return len(app.snap.ideas)

    n = asyncio.run(tui())
    assert n == 6, "tui"
    print(f"RXTERM selftest OK · {len(snap.board)} securities · {n} ideas · catalysts {REPO_CATALYSTS}")
    return 0


def _utf8_stdio() -> None:
    """Windows consoles and pipes default to a legacy code page; RXTERM prints ▲ ▼ ≤ − etc."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def _console():
    from rich.console import Console

    return Console(legacy_windows=False)


def main(argv: list[str] | None = None) -> int:
    _utf8_stdio()
    p = argparse.ArgumentParser(prog="rxterm", description="RXTERM pharma & biotech trading terminal")
    p.add_argument("--version", action="version", version=f"rxterm {__version__}")
    p.add_argument("--demo", action="store_true", help="run on synthetic data (offline)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd")

    b = sub.add_parser("brief", help="build (and optionally e-mail) the morning brief")
    b.add_argument("--out", default="out", help="output directory (default ./out)")
    b.add_argument("--send", action="store_true", help="e-mail the brief via SMTP")
    b.add_argument("--to", help="override recipient")
    b.add_argument("--no-claude", action="store_true", help="skip the Claude thesis writer")
    b.add_argument("--theses", help="JSON file with externally written theses to merge in")
    b.add_argument("--writer", help="label for who wrote the --theses file")
    b.add_argument("--reuse", action="store_true", help="re-render from OUT/snapshot.pkl instead of re-fetching")
    b.add_argument("--print", action="store_true", help="print the text version to stdout")
    b.add_argument("--demo", action="store_true", default=argparse.SUPPRESS)
    b.set_defaults(fn=cmd_brief)

    i = sub.add_parser("ideas", help="print today's trade ideas")
    i.add_argument("--no-claude", action="store_true")
    i.add_argument("--demo", action="store_true", default=argparse.SUPPRESS)
    i.set_defaults(fn=cmd_ideas)

    s = sub.add_parser("screen", help="run a preset screen")
    s.add_argument("code", nargs="?")
    s.add_argument("--list", action="store_true")
    s.add_argument("--demo", action="store_true", default=argparse.SUPPRESS)
    s.set_defaults(fn=cmd_screen)

    st = sub.add_parser("selftest")
    st.set_defaults(fn=cmd_selftest)

    c = sub.add_parser("smtp-check", help="diagnose e-mail delivery (prints server replies, never secrets)")
    c.set_defaults(fn=cmd_smtp_check)

    g = sub.add_parser("gui", help="open the desktop window (default)")
    g.add_argument("--mode", choices=("auto", "window", "app", "browser"), default="auto",
                   help="native window, Edge/Chrome app window, or the default browser")
    g.add_argument("--demo", action="store_true", default=argparse.SUPPRESS)
    g.set_defaults(fn=cmd_gui)

    sv = sub.add_parser("serve", help="run only the window's local data service and print its URL")
    sv.add_argument("--port", type=int, default=0)
    sv.add_argument("--demo", action="store_true", default=argparse.SUPPRESS)
    sv.set_defaults(fn=cmd_serve)

    gs = sub.add_parser("gui-selftest")
    gs.set_defaults(fn=cmd_gui_selftest)

    t = sub.add_parser("terminal", help="the classic text terminal (inside a console)")
    t.add_argument("--demo", action="store_true", default=argparse.SUPPRESS)
    t.set_defaults(fn=cmd_terminal)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    return args.fn(args) if args.cmd else cmd_gui(args)


if __name__ == "__main__":
    raise SystemExit(main())
