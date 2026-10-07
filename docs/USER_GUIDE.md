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
| **Update** | Download and run **RXTERM-Setup.exe** again from the same link. Your watchlist, alerts and settings are kept. |

When it opens, the bottom status line reads *Prices loaded…*, then *News loaded…*, *Fundamentals loaded…*, and finally **Ready**. That takes about a minute. You can start using it as soon as prices appear. Trade ideas fill in last.

---

## 2. The screen at a glance

```
┌ RXTERM  [ command line — type here and press Enter ]       Wed 07 Oct 2026 09:41 EDT  MKT OPEN ┐
│ XBI 152.20 ▲0.86%  IBB 205.45 ▲1.16%  XPH 63.49 ▲0.92%  SPY 775.43 ▼0.47%  LLY 1203.93 ▲4.01% … │  ← ticker tape
│ ◀ BACK  MONITOR  TRADES  STOCK  CHART COMPARE  OPTIONS  SCREENER  CALENDAR  NEWS  WATCHLIST  …  │  ← clickable tabs
│                                                                                                 │
│                              main panel (changes with each function)                           │
│                                                                                                 │
│ ● Ready · 95 securities · data as of 2026-10-07 · Yahoo Finance (delayed)                       │  ← status line
```

- **Tabs** (under the ticker tape). Click to switch screens. `F1`–`F10` do the same from the keyboard.
- **Search box** (top, optional). Type a ticker or command and press **Enter**, which works like Bloomberg's `<GO>` key.
- **Ticker tape.** Benchmarks first, then the largest names, scrolling continuously.
- **Market clock.** Shows PRE-MKT, MKT OPEN, AFTER-HRS or CLOSED for New York.
- **Status line.** Shows what's loading, the data source, and errors.

---

## 3. Using the mouse

Everything in RXTERM works with the mouse. Typing is optional.

| Click | What happens |
|---|---|
| **Tabs along the top** | `◀ BACK` · `MONITOR` · `TRADES` · `STOCK` · `CHART COMPARE` · `OPTIONS` · `SCREENER` · `CALENDAR` · `NEWS` · `WATCHLIST` · `HELP` · `🔍 FIND STOCK` · `⟳ REFRESH` |
| **Any stock in a list** | Opens its page. One click, in the monitor, screener, calendar, watchlist, top news and today's trades |
| **A column title** | Sorts by that column. Click again to reverse |
| **Monitor: SHOW buttons** | `ALL` · `BIG PHARMA` · `LARGE-CAP BIO` · `SMID BIO` · `SPECIALTY` · `★ WATCHLIST` |
| **Stock page buttons** | `◀ PREV` / `NEXT ▶` stock · `☆ ADD TO WATCHLIST` · `OPTIONS` · `NEWS` · `COMPARE +` · `🔔 SET ALERT` · `⧉ COPY` |
| **Chart buttons** | `1D` `5D` `1M` `3M` `6M` `YTD` `1Y` `2Y` `5Y` `10Y` · `LINE/CANDLE` · `MA` · `VOL` |
| **Compare buttons** | `TICKER ✕` removes · `+ XBI` `+ IBB` `+ XPH` `+ SPY` · `+ ANY STOCK…` opens the stock picker |
| **Options buttons** | Click an expiry on the left · `◀ EARLIER` / `LATER ▶` · click a strike row then `⧉ COPY SELECTED STRIKE` |
| **Watchlist buttons** | `+ ADD STOCK…` · `✕ REMOVE SELECTED` · `🔔 ALERT ON SELECTED…` · `✕` next to an alert deletes it |
| **News** | Click a story to preview it · `OPEN STORY ↗` opens it in your browser · `OPEN TICKER` buttons |
| **Today's trades** | Click a ticker button to open it · `⧉ COPY ALL TRADES` |
| **🔔 SET ALERT** | A pop-up with the current price, `−10%` … `+10%` quick buttons, and `Alert above ▲` / `Alert below ▼` |
| **🔍 FIND STOCK / + ADD STOCK** | A list of every stock: click one. Typing in the box filters the list, if you want to |
| **Mouse wheel** | Scrolls lists, tables and panels |

## 3b. Speed

RXTERM saves your last session when you close it. Next time it opens, that session appears in about a second and live data replaces it in the background over the next few seconds; the status line says when. The very first launch, with nothing saved yet, takes about 15 seconds.

## 4. Keyboard shortcuts (optional)

### Everywhere

| Key | Action |
|---|---|
| `/` or `Esc` | Jump to the command line |
| `↑` `↓` *(in the command line)* | Scroll back and forward through commands you've typed. The history is saved between sessions |
| `→` *(in the command line)* | Accept the grey autocomplete suggestion. Type `vk` and it suggests `VKTX` |
| `Enter` | Run the typed command, or open the highlighted row |
| `Backspace` | **Back** to the previous screen or ticker |
| `?` | Pop up the keys for the screen you're on |
| `+` / `−` | Add or remove the highlighted (or current) ticker on your watchlist |
| `y` | **Copy** to the clipboard: the trade line, option contract, or ticker and price (details below) |
| `↑` `↓` · `Page Up` / `Page Down` | Move through rows and lists |
| `Tab` / `Shift + Tab` | Move between panels |
| `F1` – `F10` | HELP · MON · NEWS · SCRN · IDEAS · CAL · DES · OMON · W · REFRESH |
| `Ctrl + Q` | Quit |

> On many laptops the F-keys need **Fn** held down. Every F-key also has a typed command (`HELP`, `MON`, `NEWS`, …).

### Charts (DES and COMP)

| Key | Action |
|---|---|
| `1` `2` `3` `4` `5` `6` `7` `8` `9` `0` | **1D · 5D · 1M · 3M · 6M · YTD · 1Y · 2Y · 5Y · 10Y**. You can also click the buttons above the chart |
| `[` / `]` | Step to a shorter / longer timeframe |
| `t` | Switch between **line** and **candlestick** chart |
| `m` | Moving average: off → 20 → 50 → 200 |
| `v` | Volume bars on / off |
| `,` / `.` | Previous / next ticker in the list you opened it from (monitor, screener, watchlist, calendar) |

1D shows 5-minute bars for the current session and 5D shows 30-minute bars; both refresh every minute while the market is open. 1M–1Y are daily bars, 2Y is daily, and 5Y/10Y are weekly. The header shows the last price, the % change over the period, and the period high and low.

### Tables

| Screen | Key | Action |
|---|---|---|
| MON, SCRN, W, CAL | **Click a column header** | Sort by that column. Click again to reverse |
| MON | `s` | Cycle the sort: 1D → 5D → 1M → 3M → YTD → RSI → RV20 → Volume× → Long score → Short score |
| MON | `f` | Cycle the segment filter: All → Big Pharma → Large-Cap Biotech → SMID Biotech → Specialty & Generics → Watchlist |
| MON, SCRN, CAL, W | `Enter` | Open the highlighted ticker. On MON's Top News panel, Enter opens the story's ticker |
| OMON | `[` / `]` | Previous / next expiry |
| NEWS, DES news | `Enter` or `o` | Open the story in your web browser |

### What `y` copies

| Where | What lands on your clipboard |
|---|---|
| IDEAS | All six trade lines, ready to paste into notes or a broker ticket |
| DES | Today's RXTERM trade for that ticker, or the ticker and price |
| OMON | The highlighted strike: `LLY 13NOV26 1195 CALL 60.20/71.05 \| LLY 13NOV26 1195 PUT …` (bid/ask) |
| MON, SCRN, W, CAL | The highlighted ticker and its price |

Single-letter keys only work when the cursor is in a table or chart, not in the command line. Press `Tab` or an arrow key to leave the command line first.

---

## 5. Typed commands (optional)

Type these in the command line and press **Enter**. Case doesn't matter, and `<GO>` is optional.

### Ticker commands

| Command | What you get |
|---|---|
| `LLY` | **DES** page: chart, key stats, next catalyst, news, the RXTERM idea if there is one, company profile |
| `LLY 5D` | DES with that timeframe. Any of `1D 5D 1M 3M 6M YTD 1Y 2Y 5Y 10Y` (`MAX` = 10Y) |
| `LLY GP 1Y` or `GP LLY` | Price chart (same as DES) |
| `LLY OMON` | Option chain. `OM`, `OPT` and `OPTIONS` also work |
| `LLY N` or `N LLY` | News for LLY only |
| `vertex` | Company names work too: opens the first match (VRTX) |

### Compare

| Command | What you get |
|---|---|
| `COMP LLY NVO XBI` | Up to six tickers on one chart, as % change from the start of the period |
| `COMP LLY NVO 5Y` | Same, with a timeframe |
| `LLY VS NVO` | Quick two-ticker comparison |
| `COMP` | Compares the current ticker with XBI |

### Alerts

| Command | Action |
|---|---|
| `ALRT LLY > 1250` | Alert when LLY trades at or above 1,250 |
| `ALRT VKTX < 25` | Alert when VKTX trades at or below 25 |
| `ALRT LLY 1250` | Direction picked automatically from the current price |
| `ALRT` | Show your alerts (on the W screen) |
| `ALRTDEL LLY` / `ALRTDEL ALL` | Remove one ticker's alerts / all alerts |

Alerts are checked every minute while the market is open. When one hits, RXTERM beeps and shows a pop-up for a minute, and the alert is marked ✔ on the W screen. A 🔔 count of armed alerts shows in the status line. Alerts only fire while RXTERM is open; the morning email doesn't check them.

### Screens and lists

| Command | Screen |
|---|---|
| `MON` | Sector monitor |
| `MON SMID` | Monitor filtered to a segment: `ALL` `BIG` `LARGE` `SMID` `SPEC` `W` (your watchlist) |
| `NEWS` | News wire |
| `SCRN` · `SCRN PDUFA` | Screener (last used, or a specific preset from section 7) |
| `IDEAS` | Today's trades |
| `CAL` | Catalyst calendar |
| `DES` / `OMON` | Description or options for the current ticker |
| `W` | Watchlist and price alerts |
| `WADD VKTX MDGL` / `WDEL VKTX` | Add / remove watchlist tickers (or press `+` / `−` on any row) |
| `BACK` | Previous screen (same as `Backspace`) |
| `HELP` | Help |
| `REFRESH` | Force-reload all prices, news and option chains (`F10`) |
| `Q`, `QUIT`, `EXIT` | Quit |

### RXTERM remembers

When you reopen RXTERM it comes back on the screen and ticker you left, with the same chart timeframe, chart style, moving average, monitor sort and filter, screener preset, and your command history.

---

## 6. Screens explained

### MON: Sector monitor (F2)

The home screen.

**Left panel:** every name in coverage (or the segment you filtered to). The title shows the filter and the sort. Click any header to sort, or use `s` and `f`.

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

**Right panels:** benchmarks (XBI, IBB, XPH, SPY) with breadth, segment performance, top news, and today's trades.

### DES: Description page (`LLY`, F7)

- **Header:** price, today's move, pre-market move when available, signal, long/short scores, ★ if it's on your watchlist, and 🔔 with any alert levels.
- **Timeframe bar:** clickable buttons `1D` … `10Y` plus `LINE/CANDLE`, `MA`, `VOL`. The active one is amber.
- **Chart:** line or candlesticks (green up, red down), the moving average in blue, and volume bars underneath. The axis shows times for 1D/5D and dates otherwise.
- **Key stats:** market cap, forward P/E, beta, 52-week range, distance from the 50- and 200-day averages, RSI, volatility, relative strength vs XBI, short interest, Street target and upside, consensus, cash, revenue growth, next earnings, next catalyst (red when it's an FDA event), and news count.
- **News:** this ticker's headlines. ▲ positive, ▼ negative. Press Enter to open the story.
- **Profile:** the next catalyst, RXTERM's trade idea and thesis if this ticker is one of today's picks, and the business description.

### COMP: Compare (`COMP LLY NVO XBI`)

Every ticker on one chart as % change from the start of the period, each in its own colour, with a dotted zero line. The legend shows each ticker's total change. Change the timeframe with `1`–`0`, `[` `]` or the buttons.

### OMON: Option monitor (`LLY OMON`, F8)

- **Left:** expiry dates with days to expiry. Use `↑` `↓` or `[` `]`, and the chain loads automatically. It opens on the expiry nearest 30 days.
- **Header:** spot price, ATM implied volatility, 20-day realized volatility, the **implied move** to expiry, and put/call ratios by volume and open interest.
- **Chain:** calls on the left, puts on the right, strike in the middle. Columns are bid, ask, last, implied volatility, **Δ (delta)**, volume and open interest. The at-the-money strike is amber, in-the-money rows have a dark-green background, and **green volume** means volume exceeded open interest (fresh positioning).
- Delta is roughly the option's price move for a $1 stock move, and a rough probability of finishing in the money. Press `y` to copy the highlighted strike's contracts with bid/ask.

### NEWS: News wire (F3)

Every story from STAT, BioPharma Dive, Endpoints, Fierce, FDA, GlobeNewswire, PR Newswire, Google News and Yahoo Finance, newest first, with source, tickers, tone (▲ ▼ •) and event tags (`FDA APPROVAL`, `CRL`, `TRIAL WIN`, `TRIAL FAIL`, `M&A`, `FINANCING`, `GUIDANCE`, `ANALYST`, `POLICY`, `SAFETY`). The panel underneath previews the highlighted story. Press `Enter` or `o` to open it in your browser.

### SCRN: Screener (F4)

Choose a screen on the left with the arrow keys; results update as you move. Press Enter on the list to jump into the results, click headers to sort, and press Enter on a row to open that ticker. All 15 presets are in section 7.

### IDEAS: Today's trades (F5)

- **The Take** (top): the market summary for the day.
- **Conservative** (blue, left): three large-cap trades using defined-risk spreads, 30–60 days to expiry.
- **Aggressive** (amber, right): three smaller-biotech or FDA-catalyst trades using outright calls/puts, spreads, or straddles into binary events.
- Press `y` to copy all six trade lines.

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

Upcoming events, sorted by date (click headers to re-sort):

| Type | Meaning |
|---|---|
| **PDUFA** (red) | FDA approval decision date |
| **ADCOM** (red) | FDA advisory committee meeting |
| **READOUT** (purple) | Expected trial data |
| **TRIAL** (purple) | ClinicalTrials.gov primary-completion date. Data usually follows weeks to months later |
| **EARNINGS** (blue) | Quarterly results, with the consensus EPS estimate |

Press Enter on a row to open the ticker.

### W: Watchlist and alerts (F9)

Your names with price, moves, RSI, signal, next catalyst and latest headline. Click headers to sort. Underneath, **Price alerts** lists each alert, how far the price is from it, and when it fired. Manage the list with `+` / `−` on any screen, `WADD` / `WDEL`, `ALRT` and `ALRTDEL`.

---

## 7. Screener presets

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

## 8. How the signals work

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

## 9. Daily e-mail

The morning brief arrives at **8:15 AM New York time** on weekdays. It's sent from GitHub, so your computer can be off. It contains the same trades, the market take, top stories, the catalyst calendar, movers, screens and sector performance.

- **Send one now:** on GitHub, go to **Actions → morning-brief → Run workflow**.
- **If one doesn't arrive:** GitHub e-mails you that the run failed, and the run log explains why.

---

## 10. Settings and files

Everything lives in your user folder (`C:\Users\<you>`):

| File | What it's for |
|---|---|
| `RXTERM\.env` | Settings. Add `ANTHROPIC_API_KEY=...` to have Claude write the theses in the terminal |
| `.rxterm\watchlist.txt` | Your watchlist, one ticker per line |
| `.rxterm\catalysts.yaml` | Your own catalyst dates, e.g. `- {ticker: MDGL, date: 2026-12-18, type: PDUFA, event: "Rezdiffra sNDA"}` |
| `.rxterm\alerts.json` | Your price alerts |
| `.rxterm\last_session.pkl` | Your last session, so RXTERM opens instantly. Safe to delete |
| `.rxterm\state.json` | Last screen, ticker, chart settings and command history |
| `.rxterm\cache.db` | Data cache. Safe to delete; it rebuilds automatically |

**Refresh timing:** quotes refresh **every minute while the market is open** (every 5 minutes otherwise); the status line shows the time of the last update. News refreshes every 10 minutes, fundamentals every 12 hours, and trial data daily. `F10` / `REFRESH` forces a fresh download of prices, news and option chains.

---

## 11. Command-line extras

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

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| Boxes or question marks instead of charts | Use **Windows Terminal** (free in the Microsoft Store), not the old black console |
| Layout cramped or cut off | Maximize the window or press `F11`. RXTERM is designed for at least 160 × 45 characters |
| F-keys do nothing | Hold `Fn`, or type the command (`MON`, `IDEAS`, …) |
| `s`, `1`, `t`, `y` keys do nothing | The cursor is in the command line. Press `Tab` or an arrow key to move into the table or chart |
| `y` doesn't copy | Use Windows Terminal (it supports clipboard copy from terminal apps). On the classic console RXTERM falls back to Windows' `clip`, which also works |
| 1D chart is empty before 9:30 ET | There's no intraday data yet today; 1D shows the last session once Yahoo publishes it. Use 5D |
| "No market data returned" | Check your internet connection and press `F10`. To try offline, run `rxterm --demo` |
| A ticker shows "no data" | It may have been acquired or delisted. RXTERM drops those automatically |
| Option chain says "unavailable" | Yahoo doesn't list options for that name, or rate-limited the request. Try again in a minute |

---

## 13. Important

- Prices and options come from Yahoo Finance: **about 15 minutes delayed** and unofficial. Option prices shown are mid-quotes. **Check live quotes with your broker before placing any order.**
- FDA dates come from public trackers and news. Confirm them against the company's own press release.
- RXTERM is a research tool, **not investment advice**. Options and short selling can lose more than you put in. Size every position to your own risk tolerance.
