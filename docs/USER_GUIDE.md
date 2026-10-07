# RXTERM User Guide

RXTERM is a keyboard-driven terminal for trading pharma and biotech stocks and options. This guide covers opening it, moving around, every command and shortcut, and how to read each screen.

---

## 1. Opening RXTERM

| | |
|---|---|
| **Open** | Double-click **RXTERM** on your Desktop or in the Start menu. Or type `rxterm` in any new terminal window. |
| **Quit** | `Ctrl + Q` |
| **Best view** | Maximize the window. `F11` or `Alt + Enter` switches Windows Terminal to full screen. |
| **Offline demo** | `rxterm --demo` runs on made-up data, which is useful for learning the keys. |
| **Update** | Run the installer again. Your watchlist and settings are kept. |

When it opens, the bottom status line reads *Prices loaded…*, then *News loaded…*, *Fundamentals loaded…*, and finally **Ready**. That takes about a minute. You can start using it as soon as prices appear. Trade ideas fill in last.

---

## 2. The screen at a glance

```
┌ RXTERM  [ command line — type here and press Enter ]       Wed 07 Oct 2026 09:41 EDT  MKT OPEN ┐
│ XBI 152.20 ▲0.86%  IBB 205.45 ▲1.16%  XPH 63.49 ▲0.92%  SPY 775.43 ▼0.47%  LLY 1203.93 ▲4.01% … │  ← ticker tape
│ F1 HELP  F2 MON  F3 NEWS  F4 SCRN  F5 IDEAS  F6 CAL  F7 DES  F8 OMON  F9 W  F10 REFRESH         │  ← function keys
│                                                                                                 │
│                              main panel (changes with each function)                           │
│                                                                                                 │
│ ● Ready · 95 securities · data as of 2026-10-07 · Yahoo Finance (delayed)                       │  ← status line
```

- **Command line** (amber, top). Type a command and press **Enter**, which works like Bloomberg's `<GO>` key.
- **Ticker tape.** Benchmarks first, then the largest names, scrolling continuously.
- **Market clock.** Shows PRE-MKT, MKT OPEN, AFTER-HRS or CLOSED for New York.
- **Status line.** Shows what's loading, the data source, and errors.

---

## 3. Keyboard shortcuts

### Everywhere

| Key | Action |
|---|---|
| `Esc` | Jump to the command line and clear it |
| `Enter` | Run the typed command, or open the highlighted row |
| `↑` `↓` | Move through rows and lists |
| `Page Up` / `Page Down` | Scroll a page |
| `Tab` / `Shift + Tab` | Move between panels on the current screen |
| `F1` | **HELP**: command reference |
| `F2` | **MON**: sector monitor (home screen) |
| `F3` | **NEWS**: full news wire |
| `F4` | **SCRN**: screener |
| `F5` | **IDEAS**: today's trades |
| `F6` | **CAL**: catalyst calendar |
| `F7` | **DES**: description page for the current ticker |
| `F8` | **OMON**: option monitor for the current ticker |
| `F9` | **W**: watchlist |
| `F10` | **REFRESH**: reload all data |
| `Ctrl + Q` (or `Ctrl + C`) | Quit |

> On many laptops the F-keys need **Fn** held down. Every F-key also has a typed command (`HELP`, `MON`, `NEWS`, …), so you never strictly need them.

### Keys that work on one screen

| Screen | Key | Action |
|---|---|---|
| MON | `s` | Cycle the sort column: 1D → 5D → 1M → 3M → YTD → RSI → RV20 → Volume× → Long score → Short score |
| DES | `1` `3` `6` `y` | Chart period 1 month / 3 months / 6 months / 1 year |
| NEWS | `o` | Open the highlighted story in your web browser |
| MON, SCRN, CAL, W | `Enter` | Open the highlighted ticker's DES page. On MON's Top News panel, Enter opens the story's ticker |

Single-letter keys only work when the cursor is in a table, not in the command line. Press an arrow key or `Tab` to move into the table first.

---

## 4. Commands

Type these in the command line and press **Enter**. Case doesn't matter, and `<GO>` is optional.

### Ticker commands

| Command | What you get |
|---|---|
| `LLY` | **DES** page: price chart, key stats, next catalyst, news, the RXTERM idea if there is one, company profile |
| `LLY 3M` | DES with a 3-month chart. Periods: `1M` `3M` `6M` `1Y` `YTD` |
| `LLY GP` or `GP LLY` | Price chart (same as DES) |
| `LLY GP 1Y` | Price chart, 1-year period |
| `LLY OMON` | Option chain for LLY. `OM`, `OPT` and `OPTIONS` also work |
| `OMON LLY` | Same |
| `LLY N` or `N LLY` | News for LLY only. `NEWS` and `CN` also work |
| `DES LLY` | Description page (same as `LLY`) |
| `vertex` | Company names work too: opens the first match (VRTX) |

### Function commands

| Command | Screen |
|---|---|
| `MON` | Sector monitor |
| `NEWS` | News wire |
| `SCRN` | Screener (opens the last screen used) |
| `SCRN PDUFA` | Screener with a specific preset (list in section 6) |
| `IDEAS` | Today's conservative and aggressive trades |
| `CAL` | Catalyst calendar |
| `DES` / `OMON` | Description or options for the current ticker |
| `W` | Watchlist |
| `HELP` | Help |
| `REFRESH` | Reload all data |
| `Q`, `QUIT`, `EXIT` | Quit |

### Watchlist commands

| Command | Action |
|---|---|
| `WADD VKTX` | Add a ticker. You can list several: `WADD VKTX MDGL SMMT` |
| `WDEL VKTX` | Remove a ticker |

---

## 5. Screens explained

### MON: Sector monitor (F2)

The home screen.

**Left panel:** every name in coverage, with these columns:

| Column | Meaning |
|---|---|
| LAST | Last price (about 15 minutes delayed) |
| CHG | Today's % change |
| 5D / 1M / 3M / YTD | Returns over 5 days, 1 month, 3 months, and year to date |
| RSI | 14-day RSI. **Red at 70 or above** (overbought), **green at 30 or below** (oversold) |
| RV20 | 20-day realized volatility, annualized |
| VOL× | Today's volume ÷ the 20-day average. Above 2× is unusual |
| SIGNAL | STRONG BUY / BUY / NEUTRAL / SELL / STRONG SELL, from RXTERM's scores |
| 60D | 60-day mini chart |

**Right panels:** benchmarks (XBI, IBB, XPH, SPY) with breadth, segment performance (Big Pharma, Large-Cap Biotech, SMID Biotech, Specialty & Generics), top news, and today's trades.

### DES: Description page (`LLY`, F7)

- **Header:** price, today's move, pre-market move when available, signal, and long/short scores.
- **Chart:** green or red price line with the moving average in blue. Use `1` `3` `6` `y` to change the period.
- **Key stats:** market cap, forward P/E, beta, 52-week range, distance from the 50- and 200-day averages, RSI, volatility, relative strength vs XBI, short interest, Street target and upside, analyst consensus, cash, revenue growth, next earnings, next catalyst (in red when it's an FDA event), and news count.
- **News:** this ticker's headlines. ▲ is positive, ▼ is negative.
- **Profile:** the next catalyst, RXTERM's trade idea and thesis if this ticker is one of today's picks, and the business description.

### OMON: Option monitor (`LLY OMON`, F8)

- **Left:** expiry dates with days to expiry. Use the arrow keys to choose one, and the chain loads automatically. It opens on the expiry nearest 30 days.
- **Header:** spot price, ATM implied volatility, 20-day realized volatility, the **implied move** to expiry, and put/call ratios by volume and open interest.
- **Chain:** calls on the left, puts on the right, strike in the middle. The at-the-money strike is highlighted amber, in-the-money rows have a dark-green background, and **green volume** means volume exceeded open interest (fresh positioning).

### NEWS: News wire (F3)

Every story from STAT, BioPharma Dive, Endpoints, Fierce, FDA, GlobeNewswire, PR Newswire, Google News and Yahoo Finance, newest first. Columns show time, source, tickers, tone (▲ ▼ •) and event tags such as `FDA APPROVAL`, `CRL`, `TRIAL WIN`, `TRIAL FAIL`, `M&A`, `FINANCING`, `GUIDANCE`, `ANALYST`, `POLICY` and `SAFETY`. The panel underneath previews the highlighted story. Press `o` to open it in your browser.

### SCRN: Screener (F4)

Choose a screen on the left with the arrow keys; results update as you move. Press Enter on a result row to open that ticker. All 15 presets are listed in section 6.

### IDEAS: Today's trades (F5)

- **The Take** (top): the market summary for the day.
- **Conservative** (blue, left): three large-cap trades using defined-risk spreads, 30–60 days to expiry.
- **Aggressive** (amber, right): three smaller-biotech or FDA-catalyst trades using outright calls/puts, spreads, or straddles into binary events.

Each card shows:

| Field | Meaning |
|---|---|
| LONG / SHORT / LONG VOL | Direction. LONG VOL is a straddle that profits from a big move either way |
| Structure | Bull Call Spread, Bear Put Spread, Long Call, Long Put, Long Straddle, or Shares |
| Amber order line | The exact legs, e.g. `BUY 20NOV26 270 CALL @ 12.40 / SELL 20NOV26 290 CALL @ 4.55` |
| REF / PREM | Reference stock price, or the premium for straddles |
| TARGET / STOP | Exit levels on the stock price (premium for straddles). Stops are meant to be applied on the closing price |
| R:R | Reward ÷ risk |
| DEBIT | Cost per share of the option structure. Multiply by 100 per contract |
| B/E | Breakeven at expiry |
| ●●●●○ | Conviction, from 1 to 5 |
| Thesis, signals, risks | Why the trade, the supporting data, and what would make it wrong |

### CAL: Catalyst calendar (F6)

Upcoming events sorted by date:

| Type | Meaning |
|---|---|
| **PDUFA** (red) | FDA approval decision date |
| **ADCOM** (red) | FDA advisory committee meeting |
| **READOUT** (purple) | Expected trial data |
| **TRIAL** (purple) | ClinicalTrials.gov primary-completion date. Data usually follows weeks to months later |
| **EARNINGS** (blue) | Quarterly results, with the consensus EPS estimate |

Press Enter on a row to open the ticker.

### W: Watchlist (F9)

Your names with price, moves, RSI, signal, next catalyst and latest headline. Manage it with `WADD` and `WDEL`.

---

## 6. Screener presets

Run one with `SCRN <CODE>`, e.g. `SCRN SQUEEZE`.

| Code | Name | What it finds |
|---|---|---|
| `TOPLONG` | Top Long Setups | Highest composite long score (trend, momentum, news, upside) |
| `TOPSHORT` | Top Short Setups | Highest composite short score (downtrend, weak relative strength, negative news) |
| `MOMO` | Momentum Leaders | Above the 50- and 200-day averages, top-quartile 3-month return, RSI 50–75 |
| `OVERSOLD` | Oversold Quality | RSI below 35 on large caps still near or above the 200-day average; mean-reversion longs |
| `BREAKOUT` | 52-Week High Breakouts | Within 2% of the 52-week high on above-average volume |
| `BREAKDOWN` | Breakdowns | Below the 50- and 200-day averages, 1-month return worse than −10%; short candidates |
| `CATALYST` | Binary Catalysts ≤ 45d | PDUFA, AdCom or trial readout within 45 days |
| `PDUFA` | FDA Decisions ≤ 60d | PDUFA dates and advisory committees within 60 days |
| `EARNINGS` | Earnings ≤ 14d | Reporting within two weeks |
| `UNUSUALVOL` | Unusual Volume | Volume at least 2× the 20-day average |
| `SQUEEZE` | Short-Squeeze Watch | Short interest above 15% of float with positive 1-month momentum |
| `NEWSPOS` | Positive Newsflow | Strongest positive recent news sentiment |
| `NEWSNEG` | Negative Newsflow | Strongest negative recent news sentiment |
| `VALUE` | Value Pharma | Forward P/E below 15 with Street upside above 10% |
| `HIGHVOL` | Highest Realized Vol | Highest 20-day realized volatility; premium-rich names |

---

## 7. How the signals work

Every name is ranked against the rest of the coverage on:

- **Trend:** price vs the 50- and 200-day averages, and whether the 50-day is above the 200-day
- **Momentum:** 3-month return and relative strength vs XBI, plus 1-month return
- **News:** recency-weighted sentiment of tagged headlines
- **Street upside:** analyst mean target vs price
- **Mean reversion:** oversold-in-uptrend adds to the long score; overbought-in-downtrend adds to the short score
- **Penalties:** very overbought names lose long score; washed-out names and crowded shorts lose short score

This produces a **long score** and a **short score** from 0 to 100:

| Signal | Rule |
|---|---|
| STRONG BUY | long score ≥ 85 |
| BUY | long score ≥ 70 |
| STRONG SELL | short score ≥ 85 |
| SELL | short score ≥ 70 |
| NEUTRAL | everything else |

**Trade construction rules.** Conservative trades use a 2× ATR stop and roughly a 2:1 target. Aggressive trades use a 1.75× ATR stop and a 2.5:1 target. When implied volatility is more than 1.6× realized volatility, aggressive trades switch from buying options outright to spreads, so you aren't overpaying for premium.

---

## 8. Daily e-mail

The morning brief arrives at **8:15 AM New York time** on weekdays. It's sent from GitHub, so your computer can be off. It contains the same trades, the market take, top stories, the catalyst calendar, movers, screens and sector performance.

- **Send one now:** on GitHub, go to **Actions → morning-brief → Run workflow**.
- **If one doesn't arrive:** GitHub e-mails you that the run failed, and the run log explains why.

---

## 9. Settings and files

Everything lives in your user folder (`C:\Users\<you>`):

| File | What it's for |
|---|---|
| `RXTERM\.env` | Settings. Add `ANTHROPIC_API_KEY=...` to have Claude write the theses in the terminal |
| `.rxterm\watchlist.txt` | Your watchlist, one ticker per line |
| `.rxterm\catalysts.yaml` | Your own catalyst dates, e.g. `- {ticker: MDGL, date: 2026-12-18, type: PDUFA, event: "Rezdiffra sNDA"}` |
| `.rxterm\cache.db` | Data cache. Safe to delete; it rebuilds automatically |

**Refresh timing:** prices and news refresh about every 5–10 minutes on their own. `F10` reloads anything older than that. Fundamentals refresh every 12 hours and trial data daily. To force a completely fresh load, delete `.rxterm\cache.db` and restart RXTERM.

---

## 10. Command-line extras

Run these in any terminal window:

| Command | What it does |
|---|---|
| `rxterm` | Open the terminal |
| `rxterm --demo` | Terminal on made-up data |
| `rxterm ideas` | Print today's trades and theses |
| `rxterm screen --list` | List the screener presets |
| `rxterm screen SQUEEZE` | Run one screen and print the results |
| `rxterm brief` | Build the morning brief into `.\out\brief.html`. Open it in a browser |
| `rxterm brief --send` | Build and e-mail it (needs the e-mail settings in `.env`) |
| `rxterm smtp-check` | Diagnose e-mail problems. Never prints your password |

---

## 11. Troubleshooting

| Problem | Fix |
|---|---|
| Boxes or question marks instead of charts | Use **Windows Terminal** (free in the Microsoft Store), not the old black console |
| Layout cramped or cut off | Maximize the window or press `F11`. RXTERM is designed for at least 160 × 45 characters |
| F-keys do nothing | Hold `Fn`, or type the command (`MON`, `IDEAS`, …) |
| `s`, `1`, `o` keys do nothing | The cursor is in the command line. Press an arrow key or `Tab` to move into the table |
| "No market data returned" | Check your internet connection and press `F10`. To try offline, run `rxterm --demo` |
| A ticker shows "no data" | It may have been acquired or delisted. RXTERM drops those automatically |
| Option chain says "unavailable" | Yahoo doesn't list options for that name, or rate-limited the request. Try again in a minute |

---

## 12. Important

- Prices and options come from Yahoo Finance: **about 15 minutes delayed** and unofficial. Option prices shown are mid-quotes. **Check live quotes with your broker before placing any order.**
- FDA dates come from public trackers and news. Confirm them against the company's own press release.
- RXTERM is a research tool, **not investment advice**. Options and short selling can lose more than you put in. Size every position to your own risk tolerance.
