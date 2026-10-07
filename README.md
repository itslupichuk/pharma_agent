# RXTERM — Pharma & Biotech Trading Terminal

A Bloomberg-style terminal and 8:15 AM morning brief for trading pharma and biotech equities and options, long or short.

```
┌ RXTERM  LLY <GO> ──────────────────────────────── Wed 07 Oct 2026 08:15:02 EDT  PRE-MKT ┐
│ XBI 152.02 ▲0.74%  IBB 205.50 ▲1.18%  XPH 63.47 ▲0.89%  LLY 1201.66 ▲3.82%  NVO 38.22 ▲1.84% … │
│ F1 HELP  F2 MON  F3 NEWS  F4 SCRN  F5 IDEAS  F6 CAL  F7 DES  F8 OMON  F9 W  F10 REFRESH     │
```

## What it does

| | |
|---|---|
| **Coverage** | ~95 names: Big Pharma, large-cap biotech, SMID biotech, specialty/generics, plus XBI / IBB / XPH / SPY |
| **Signals** | Trend (50/200-DMA), 3M momentum and relative strength vs XBI, RSI mean reversion, realized vol, unusual volume, short interest, Street upside, news sentiment and catalyst proximity, combined into cross-sectional long and short scores (0–100) |
| **News wire** | STAT, BioPharma Dive, Endpoints, Fierce, FDA, GlobeNewswire, PR Newswire, Google News, Yahoo Finance. Each headline is tagged to tickers, classified (FDA approval, CRL, trial win/fail, M&A, financing, guidance, policy…) and sentiment-scored |
| **Catalysts** | PDUFA / AdCom (curated plus extracted from news), ClinicalTrials.gov Phase 2/3 completions, consensus earnings dates |
| **Screeners** | 15 presets: `TOPLONG` `TOPSHORT` `MOMO` `OVERSOLD` `BREAKOUT` `BREAKDOWN` `CATALYST` `PDUFA` `EARNINGS` `UNUSUALVOL` `SQUEEZE` `NEWSPOS` `NEWSNEG` `VALUE` `HIGHVOL` |
| **Trade ideas** | 3 **conservative** trades (large-cap, defined-risk call/put spreads, 30–60 DTE) and 3 **aggressive** trades (SMID and catalyst names, outright calls/puts, or straddles into binary FDA events). Each has strikes, expiry, debit, breakeven, target, stop, R:R, conviction, and a thesis with risks |
| **Theses** | Written by Claude when `ANTHROPIC_API_KEY` is set (or by the scheduled Claude routine). Otherwise a built-in rules-based analyst writer is used |
| **Morning brief** | HTML e-mail in a sell-side note format: the take, trades, top stories with so-whats, catalyst calendar, movers, screens, segment performance |

## Install: one line, with a Desktop icon

**Mac.** Open Terminal (⌘ Space, type *Terminal*), paste this and press Enter:

```bash
curl -fsSL https://raw.githubusercontent.com/itslupichuk/pharma_agent/HEAD/scripts/install_mac.sh | bash
```

**Windows.** Press Start, type *PowerShell*, open it, paste this and press Enter:

```powershell
irm https://raw.githubusercontent.com/itslupichuk/pharma_agent/HEAD/scripts/install_windows.ps1 | iex
```

For the best look, use Windows Terminal (preinstalled on Windows 11, free in the Microsoft Store on Windows 10). The shortcut opens in it automatically.

The installer downloads RXTERM to `~/RXTERM` and sets up its own Python 3.12 (via [uv](https://docs.astral.sh/uv/), so it doesn't touch your system Python). It then puts an **RXTERM** icon on your Desktop, in Applications/Launchpad (or the Start menu), and adds an `rxterm` command. Double-click the icon to open the terminal in a large dark window. Run the same line again any time to update; your watchlist and settings are kept.

The first time you launch on a Mac, it may ask to let RXTERM control Terminal. Click **OK**.

Manual install for developers: `git clone`, then `pip install -e .`, then `rxterm`. Add `--demo` to run offline on synthetic data.

## Terminal commands

**Full guide with every screen, key and command: [docs/USER_GUIDE.md](docs/USER_GUIDE.md).**

Type in the amber command line and press Enter (`<GO>`). `ESC` returns to the command line.

| Command | Function |
|---|---|
| `LLY` | **DES**: price chart, key stats, catalyst, news, RXTERM idea and profile |
| `LLY GP 3M` | Chart period `1M` `3M` `6M` `1Y` `YTD` (keys `1` `3` `6` `y` on DES) |
| `LLY OMON` | Option monitor: chain by expiry, IV, implied move, put/call ratios, volume > open interest flagged |
| `LLY N` | News for one ticker |
| `MON` / F2 | Sector monitor: every name, benchmarks, breadth, segment heatmap, top news, today's trades (`s` cycles the sort) |
| `NEWS` / F3 | Full wire with event tags and sentiment (`o` opens the story in your browser) |
| `SCRN PDUFA` / F4 | Screener |
| `IDEAS` / F5 | Today's conservative and aggressive trades with full theses |
| `CAL` / F6 | Catalyst calendar |
| `W` / F9, `WADD VKTX`, `WDEL VKTX` | Watchlist |
| `REFRESH` / F10 | Reload everything (prices also refresh every 5 minutes) |

## CLI

```bash
rxterm brief                  # build ./out/brief.html, brief.txt, brief.json
rxterm brief --send           # …and e-mail it (SMTP settings in .env)
rxterm ideas                  # today's trades in the shell
rxterm screen --list          # list screens
rxterm screen SQUEEZE         # run one
```

## The 8:15 AM e-mail (runs in the cloud, laptop can be off)

**Option A — Claude routine (active).** A scheduled Claude Code routine runs at 8:05 ET on weekdays. It builds the brief, writes the theses as a desk analyst, and sends the e-mail through your connected Gmail. No setup needed. Each run uses some of your Claude plan's usage. The prompt is in `docs/morning_routine_prompt.md`. Manage it under *Routines* at claude.ai/code.

**Option B — GitHub Actions (no Claude usage).** `.github/workflows/morning-brief.yml` runs on GitHub's servers and sends at exactly 8:15 ET:
1. Create a Gmail App Password: <https://myaccount.google.com/apppasswords> (requires 2-Step Verification).
2. In the repo, go to *Settings → Secrets and variables → Actions* and add `RXTERM_SMTP_USER` (your Gmail address) and `RXTERM_SMTP_PASSWORD` (the app password). Optionally add `RXTERM_EMAIL_TO` and `ANTHROPIC_API_KEY` (Claude-written theses, billed to the API at a few cents a day).
3. Merge to the default branch (GitHub only runs scheduled workflows from it). Test it from *Actions → morning-brief → Run workflow*.

Use one option, not both, or you'll get two e-mails.

## Adding catalysts

Free feeds don't publish FDA action dates reliably. Add binary events to `config/catalysts.yaml` (shared) or `~/.rxterm/catalysts.yaml` (personal):

```yaml
- {ticker: MDGL, date: 2026-12-18, type: PDUFA, event: "Rezdiffra sNDA — compensated cirrhosis"}
```

## Data and limitations

- Prices and options come from Yahoo Finance: free, about 15 minutes delayed, unofficial. `rxterm/data/market.py` defines a five-method `MarketData` interface, so a Polygon, Tradier or IBKR feed is a drop-in replacement.
- Fundamentals and calendars are cached for 12 hours, prices for 10 minutes and news for 10 minutes, in `~/.rxterm/cache.db`.
- Option levels use mid prices. Check live quotes before trading.

## Layout

```
rxterm/
  data/       market.py (Yahoo + demo providers) · news.py (wire, tagging, sentiment) · catalysts.py
  analytics/  indicators.py · signals.py (board + scores) · screener.py · ideas.py (structuring) · thesis.py (Claude / rules)
  brief/      render.py · send.py · templates/brief.html
  tui/        app.py · widgets.py (braille chart, ticker tape) · rxterm.tcss
  engine.py   orchestration → Snapshot
config/catalysts.yaml   curated FDA calendar
```

---
*RXTERM is a research tool, not investment advice. Options and short selling carry substantial risk, including loss of more than the amount invested.*
