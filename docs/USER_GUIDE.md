# RXTERM User Guide

RXTERM is a desktop app for trading pharma and biotech stocks and options. It opens in its own window, like any other Windows program, and everything works with the mouse. You never need a command prompt.

---

## 1. Opening RXTERM

| | |
|---|---|
| **Open** | Double-click **RXTERM** on your Desktop or in the Start menu. It opens maximized in its own window. |
| **Close** | Click the **✕** at the top right, like any program. |
| **Update** | Download and run **RXTERM-Setup.exe** again from the same link. Your watchlist, alerts and settings are kept. |

RXTERM opens instantly with your last session, then refreshes everything in the background. The status line at the bottom left shows what it's doing. The very first launch takes about 15 seconds to download prices, news, fundamentals and catalysts.

---

## 2. The window at a glance

```
┌─ RXTERM ─ [ Search a stock… ] ◀  Monitor  Trade Ideas  Screener  Calendar  News  Options  Compare  Watchlist  Help ─ OPEN  14:32 ET ┐
│ XBI 92.40 +0.8%   IBB 141.20 +0.5%   LLY 1,032.10 +1.2%   … (scrolling ticker tape: click any name)                                   │
│                                                                                                                                       │
│                                          the page you picked                                                                          │
│                                                                                                                                       │
│ Live · prices refresh every minute…                                   🔔 2 alerts armed   Data: Yahoo   Updated 14:32:05   ⟳ Refresh │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Top bar:** search box, the **◀ Back** button, the page tabs, and market status (PRE-MARKET / OPEN / AFTER-HOURS / CLOSED) with the New York clock.
- **Ticker tape:** benchmarks and the largest names, live. Hover to pause it, click a name to open it.
- **Status line:** what's loading, how many alerts are armed, the data source, the last update time, and **⟳ Refresh** to reload everything now.

---

## 3. Using it

| To… | Do this |
|---|---|
| Open a stock | Click it anywhere (table row, tape, news chip, calendar, trade card), or click the search box, type part of a ticker or name, and click a result. You can also just start typing anywhere. |
| Go back | Click **◀** at the top, or press your mouse's back button. |
| Switch page | Click a tab: **Monitor, Trade Ideas, Screener, Calendar, News, Options, Compare, Watchlist, Help**. |
| Sort a table | Click a column heading. Click again to reverse the order. |
| Filter the Monitor | Click the chips above the table: a sector, **★ My watchlist**, **Buy signals**, **Sell signals**, **Catalyst ≤ 30 days**. |
| More options for a stock | **Right-click** its row: chart, options chain, news, compare with XBI, watchlist, price alert, copy ticker. |
| Add to watchlist | Click the **☆** next to a stock, or **☆ Add to watchlist** on its page. |
| Set a price alert | **🔔 Price alert** on a stock page (or right-click → *Set price alert…*). Click a **±2 / 5 / 10 %** button or type a price, then **Alert when ABOVE** or **Alert when BELOW**. |
| Copy a trade | **Copy trade** on any trade card, or click any price in the options chain to copy that contract. |
| Read a story | Click it for a preview; **Open article in browser** (or double-click) to read the full article. |

When an alert triggers, RXTERM plays a chime and shows a pop-up while it's open. Triggered alerts stay listed on the Watchlist page until you delete them.

---

## 4. Pages explained

### Monitor
The whole universe of about 95 pharma and biotech names: last price, today / 5-day / 1-month / year-to-date moves, a 3-month sparkline, RSI, volume vs average, the RXTERM signal and score, and the next catalyst. The right side shows the benchmarks (XBI, IBB, XPH, SPY) with market breadth, sector performance, today's six trade ideas and the top stories. Click a sector to filter by it.

### Stock page
- **Header:** price, today's move, signal and long/short scores, plus buttons for watchlist, price alert, options, compare, and **◀ ▶** to step through the list you came from.
- **Chart:** periods **1D, 5D, 1M, 3M, 6M, YTD, 1Y, 2Y, 5Y, 10Y**; **Candles / Line / Area**; **Moving avgs** (20, 50 and 200 bars) and **Volume** toggles. Hover for exact open/high/low/close and volume. Scroll to zoom, drag to pan, and **Reset zoom** shows the whole period. Your alert levels show as amber dashed lines; if the stock is one of today's trades, its target (green) and stop (red) are drawn too.
- **Key stats:** market cap, P/E, beta, 52-week range, distance from the 50- and 200-day averages, RSI, volatility, relative strength vs XBI, short interest, Street target and upside, analyst view, cash, revenue growth, next earnings and next catalyst.
- **News** for the stock, and the **trade idea** (if any) and company profile.

### Trade Ideas
Three **conservative** trades (liquid names, defined-risk spreads, 30–60 days) and three **aggressive** trades (higher-volatility names and catalysts, outright options). Each card shows the exact contracts, entry / target / stop, reward-to-risk, horizon, max gain / max loss / breakeven, implied vs realized volatility, the thesis, **Why** and **Risks**. The buttons open the chart or the options chain, copy the trade, or set an alert at the target or stop. The **Market take** at the top summarizes the session.

### Screener
Click a screen on the left; the matching stocks appear on the right. Click a column to sort and a row to open the stock. See section 5 for the full list.

### Calendar
FDA decision dates (PDUFA), advisory committees, clinical-trial readouts and earnings, soonest first. Click the chips to show one type only.

### News
The pharma newswire from FDA, trade press, wires and Yahoo, tagged by stock and event type and scored for tone. Use **All / Positive / Negative** and the filter box. Click a story to preview it on the right.

### Options
The call and put chain for one stock: bid, ask, last, implied volatility, delta, volume and open interest. Click the dates to change expiry. In-the-money strikes are shaded and the at-the-money strike is highlighted in amber. Volume shows in amber where it's above open interest (new positioning). The strip above the chain shows at-the-money IV vs 20-day realized volatility, the implied move to expiry, and put/call ratios. **Change stock…** picks another name.

### Compare
Up to six stocks or ETFs on one percentage chart. **+ Add stock** adds a line, the **✕** on a chip removes one, and the period buttons change the range.

### Watchlist
Your stocks (sortable, with ✕ to remove and **+ Add stock**) and your price alerts, showing the distance from the current price and whether each is armed or triggered.

### Help
A short version of this guide, plus credits and the disclaimer.

---

## 5. Screener presets

Click one on the Screener page.

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

## 6. How the signals work

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

## 7. Daily e-mail

The morning brief arrives at **8:15 AM New York time** on weekdays. It's sent from GitHub, so your computer can be off. It contains the same trades, the market take, top stories, the catalyst calendar, movers, screens and sector performance.

- **Send one now:** on GitHub, go to **Actions → morning-brief → Run workflow**.
- **If one doesn't arrive:** GitHub e-mails you that the run failed, and the run log explains why.

---

## 8. Settings and files

Everything lives in your user folder (`C:\Users\<you>`):

| File | What it's for |
|---|---|
| `.rxterm\.env` | Settings. Add `ANTHROPIC_API_KEY=...` to have Claude write the theses in the app |
| `.rxterm\watchlist.txt` | Your watchlist, one ticker per line |
| `.rxterm\catalysts.yaml` | Your own catalyst dates, e.g. `- {ticker: MDGL, date: 2026-12-18, type: PDUFA, event: "Rezdiffra sNDA"}` |
| `.rxterm\alerts.json` | Your price alerts |
| `.rxterm\last_session.pkl` | Your last session, so RXTERM opens instantly. Safe to delete |
| `.rxterm\window\` | The window's own settings (chart style, last filters) |
| `.rxterm\rxterm.log` | A log of what the app did. Useful if something goes wrong |
| `.rxterm\cache.db` | Data cache. Safe to delete; it rebuilds automatically |

**Refresh timing:** quotes refresh **every minute while the market is open** (every 5 minutes otherwise); the status line shows the time of the last update. News refreshes every 10 minutes, fundamentals every 12 hours, and trial data daily. **⟳ Refresh** (bottom right) reloads prices, news, fundamentals and catalysts now.

---

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| "Windows protected your PC" when installing | The app isn't code-signed. Click **More info → Run anyway** |
| The window opens in Microsoft Edge without tabs instead of its own frame | Your PC is missing the Microsoft Edge WebView2 Runtime; RXTERM falls back to an Edge app window, which works the same. To get the native frame, install WebView2 from Microsoft (free) |
| Stuck on the loading screen | Check your internet connection. RXTERM keeps trying in the background; click **⟳ Refresh** once you're back online |
| 1D chart is empty before 9:30 ET | There's no intraday data yet today. Use 5D |
| A ticker shows "no data" | It may have been acquired or delisted. RXTERM drops those automatically |
| Option chain says "no chain" | Yahoo doesn't list options for that name, or rate-limited the request. Try another expiry or wait a minute |
| Anything else | Close and reopen RXTERM. If it persists, the details are in `.rxterm\rxterm.log` in your user folder |

---

## 10. Command-line extras (optional)

You never need these. The installed folder (`%LOCALAPPDATA%\Programs\RXTERM`) also contains **rxterm-cli.exe** for people who like a command line:

| Command | What it does |
|---|---|
| `rxterm-cli ideas` | Print today's trades and theses |
| `rxterm-cli screen SQUEEZE` | Run one screen and print the results |
| `rxterm-cli brief` | Build the morning brief into `.\out\brief.html` |
| `rxterm-cli brief --send` | Build and e-mail it (needs the e-mail settings in `.env`) |
| `rxterm-cli smtp-check` | Diagnose e-mail problems. Never prints your password |
| `rxterm-cli terminal` | The original keyboard-driven text terminal |
| `RXTERM.exe --demo` | The app on made-up data (works offline) |

---

## 11. Important

- Prices and options come from Yahoo Finance: **about 15 minutes delayed** and unofficial. Option prices shown are mid-quotes. **Check live quotes with your broker before placing any order.**
- FDA dates come from public trackers and news. Confirm them against the company's own press release.
- RXTERM is a research tool, **not investment advice**. Options and short selling can lose more than you put in. Size every position to your own risk tolerance.
