"""RXTERM command line.

  rxterm                      launch the terminal
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
        thesis.apply_theses(snap, json.loads(Path(args.theses).read_text()))
        snap.writer = args.writer or "Claude (desk analyst)"
    paths = render.write_outputs(snap, out)
    print(f"· brief written: {paths['html']}  ({len(snap.ideas)} ideas, theses by {snap.writer})", file=sys.stderr)
    if args.send:
        from .brief.send import send_email

        to = send_email(cfg, render.subject_for(snap), paths["html"].read_text(), paths["text"].read_text(), args.to)
        print(f"· e-mailed to {to}", file=sys.stderr)
    if args.print:
        print(paths["text"].read_text())
    return 0


def cmd_ideas(args) -> int:
    from rich.console import Console
    from rich.table import Table

    from .engine import Engine

    snap = Engine(_cfg(args)).full(ideas=True, use_claude=not args.no_claude)
    con = Console()
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
    Console().print(t)
    return 0


def main(argv: list[str] | None = None) -> int:
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

    t = sub.add_parser("terminal", help="launch the terminal (default)")
    t.add_argument("--demo", action="store_true", default=argparse.SUPPRESS)
    t.set_defaults(fn=cmd_terminal)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    return args.fn(args) if args.cmd else cmd_terminal(args)


if __name__ == "__main__":
    raise SystemExit(main())
