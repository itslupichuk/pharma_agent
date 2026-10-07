"""News wire: RSS aggregation, ticker tagging, event classification, sentiment.

Sources are free public feeds. Each headline is tagged to universe tickers
(by `$TICK`, `(NASDAQ: TICK)` and company/drug-name aliases), classified into
pharma event types (FDA approval, CRL, trial readout, M&A, financing…) and
scored with a domain lexicon. PDUFA dates mentioned in the text are extracted
into the catalyst calendar.
"""

from __future__ import annotations

import hashlib
import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import quote_plus

import feedparser
import httpx

from .. import universe
from ..cache import Cache

log = logging.getLogger(__name__)

NEWS_TTL = 10 * 60
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"

FEEDS: dict[str, str] = {
    "STAT": "https://www.statnews.com/feed/",
    "BioPharma Dive": "https://www.biopharmadive.com/feeds/news/",
    "Fierce Pharma": "https://www.fiercepharma.com/rss/xml",
    "Fierce Biotech": "https://www.fiercebiotech.com/rss/xml",
    "Endpoints": "https://endpts.com/feed/",
    "FDA": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml",
    "GlobeNewswire": "https://www.globenewswire.com/RssFeed/industry/4573-Biotechnology/feedTitle/GlobeNewswire%20-%20Industry%20News%20on%20Biotechnology",
    "PR Newswire": "https://www.prnewswire.com/rss/health-latest-news/health-latest-news-list.rss",
}
GOOGLE_QUERIES = (
    "biotech stock FDA when:2d",
    "PDUFA date when:7d",
    "phase 3 topline results when:2d",
    "pharma acquisition when:3d",
    "complete response letter FDA when:7d",
)
YAHOO_TICKER_FEED = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbols}&region=US&lang=en-US"

# ── Classification ─────────────────────────────────────────────────────
# (tag, regex, sentiment weight, impact weight)
EVENT_RULES: tuple[tuple[str, str, float, float], ...] = (
    ("CRL", r"complete response letter|\bCRL\b|fda (?:rejects|declines)|refuse[sd]? to file", -0.9, 1.0),
    ("FDA APPROVAL", r"\bfda (?:approv|clear|grant)|approval (?:of|for)|wins? (?:fda )?approval|\bapproved\b|\bEC approv|CHMP (?:positive|recommend)", 0.8, 0.9),
    ("PDUFA", r"pdufa|target action date|accept(?:s|ed)? .{0,40}(?:NDA|BLA|sBLA|sNDA)|priority review", 0.25, 0.6),
    ("TRIAL WIN", r"met (?:its |the )?primary endpoint|\d+% (?:lower|reduction)|reduc\w* (?:the )?risk of|positive (?:topline|top-line|phase|pivotal|results|data)|statistically significant|superior(?:ity)? |beat placebo", 0.75, 0.85),
    ("TRIAL FAIL", r"fail(?:s|ed)? to (?:meet|show|hit)|fail(?:s|ed)? (?:a |its |the )?(?:key |pivotal |late-stage |phase \w+ |mid-stage )*(?:trial|study|test)|flops?\b|did not meet|missed (?:its |the )?primary|futility|discontinu|halts? (?:trial|study|development)|clinical hold|terminate[sd]? (?:the )?(?:trial|study|program)", -0.9, 1.0),
    ("SAFETY", r"(?<!or )(?<!and )\bdeaths? (?:in|of|reported|linked)|patient deaths?|safety (?:signal|concern|issue)|black box|boxed warning|serious adverse|liver injury|recall", -0.6, 0.7),
    ("M&A", r"\bacquir|\bacquisition|to buy\b|buyout|takeover|merger|tender offer|definitive agreement", 0.6, 0.9),
    ("LICENSING", r"licens(?:e|ing) (?:deal|agreement)|collaboration|partnership|upfront|milestone payments", 0.35, 0.5),
    ("FINANCING", r"public offering|proposed offering|priced .{0,30}offering|private placement|\bATM\b|at-the-market|convertible notes|dilut", -0.5, 0.6),
    ("GUIDANCE", r"raises? (?:full-year |fy |annual )?(?:guidance|outlook|forecast)|beats? (?:estimates|expectations)|record (?:sales|revenue)", 0.6, 0.6),
    ("GUIDANCE CUT", r"cuts? (?:guidance|outlook|forecast)|lowers? (?:guidance|outlook)|misses? (?:estimates|expectations)|below (?:estimates|expectations)", -0.6, 0.7),
    ("ANALYST", r"upgrade[sd]?|downgrade[sd]?|price target|initiat(?:es|ed) coverage|outperform|overweight|underweight", 0.0, 0.4),
    ("POLICY", r"most.favou?red.nation|\bMFN\b|drug pric|tariff|medicare negotiat|inflation reduction act|\bIRA\b|\bRFK\b|\bHHS\b|\bCMS\b|biosecure", -0.3, 0.5),
    ("RESTRUCTURING", r"layoffs?|lays? off|job cuts|restructur|workforce reduction|cash runway", -0.4, 0.4),
    ("LEGAL", r"lawsuit|litigation|patent (?:challenge|ruling|loss)|settle(?:s|ment)|\bDOJ\b|\bFTC\b|subpoena", -0.3, 0.4),
)
_EVENT_RX = [(tag, re.compile(rx, re.I), s, w) for tag, rx, s, w in EVENT_RULES]

POS_WORDS = {
    "surge": 0.6, "soar": 0.7, "jump": 0.5, "rally": 0.5, "gain": 0.3, "climb": 0.4, "rise": 0.25, "rises": 0.25,
    "upgrade": 0.5, "outperform": 0.4, "overweight": 0.35, "breakthrough": 0.5, "fast track": 0.35,
    "accelerated approval": 0.6, "strong": 0.25, "robust": 0.25, "durable": 0.25, "best-in-class": 0.4,
    "beat": 0.4, "beats": 0.4, "record": 0.3, "momentum": 0.2, "win": 0.4, "wins": 0.4, "positive": 0.35,
}
NEG_WORDS = {
    "plunge": -0.8, "plummet": -0.8, "tumble": -0.6, "sink": -0.5, "slump": -0.5, "crater": -0.8, "fall": -0.3,
    "falls": -0.3, "drop": -0.35, "drops": -0.35, "slide": -0.35, "downgrade": -0.5, "underweight": -0.35,
    "underperform": -0.4, "delay": -0.4, "delays": -0.4, "setback": -0.6, "disappoint": -0.6, "concern": -0.3,
    "warning": -0.4, "probe": -0.4, "investigation": -0.4, "short seller": -0.5, "miss": -0.4, "weak": -0.3,
    "negative": -0.35, "risk": -0.1, "pressure": -0.25, "loss": -0.25, "shortfall": -0.4,
}
_WORD_RX = {w: re.compile(rf"\b{re.escape(w)}\w*", re.I) for w in {**POS_WORDS, **NEG_WORDS}}

_TICK_RXS = (
    re.compile(r"\((?:NASDAQ|NYSE|Nasdaq|NYSE American|NASDAQGS|NASDAQGM)\s*:\s*([A-Z]{1,5})\)"),
    re.compile(r"\$([A-Z]{1,5})\b"),
    re.compile(r"\(([A-Z]{2,5})\)"),
)
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
_PDUFA_RX = re.compile(
    rf"(?:PDUFA|target action)[^.]{{0,80}}?\b((?:{_MONTHS})\.? \d{{1,2}},? \d{{4}})", re.I)


def _alias_index() -> list[tuple[re.Pattern, str]]:
    idx: list[tuple[re.Pattern, str]] = []
    for sec in universe.equities():
        for alias in (sec.name, *sec.aliases):
            if len(alias) < 3:
                continue
            flags = 0 if alias.isupper() or len(alias) <= 4 else re.I
            idx.append((re.compile(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", flags), sec.ticker))
    return idx


_ALIASES = _alias_index()


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published: datetime
    summary: str = ""
    tickers: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    sentiment: float = 0.0
    impact: float = 0.0
    pdufa: list[tuple[str, date]] = field(default_factory=list)

    @property
    def id(self) -> str:
        return hashlib.md5(re.sub(r"\W+", "", self.title.lower())[:90].encode()).hexdigest()

    @property
    def age_hours(self) -> float:
        return (datetime.now(timezone.utc) - self.published).total_seconds() / 3600

    @property
    def tone(self) -> str:
        return "POS" if self.sentiment > 0.15 else "NEG" if self.sentiment < -0.15 else "NEU"


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _parse_date(entry) -> datetime:
    for key in ("published", "updated", "pubDate"):
        raw = entry.get(key)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            return datetime(*st[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def tag_tickers(text: str, hint: Iterable[str] = ()) -> list[str]:
    found: list[str] = []
    for rx in _TICK_RXS:
        for m in rx.findall(text):
            if m in universe.UNIVERSE and not universe.UNIVERSE[m].is_etf and m not in found:
                found.append(m)
    for rx, tick in _ALIASES:
        if tick not in found and rx.search(text):
            found.append(tick)
    for t in hint:
        if t not in found and t in universe.UNIVERSE:
            found.append(t)
    return found[:6]


def classify(text: str) -> tuple[list[str], float, float]:
    tags: list[str] = []
    score = 0.0
    impact = 0.15
    for tag, rx, s, w in _EVENT_RX:
        if rx.search(text):
            tags.append(tag)
            score += s
            impact = max(impact, w)
    if "ANALYST" in tags:
        if re.search(r"downgrade|underweight|underperform|cuts? (?:price )?target|lowers? (?:price )?target", text, re.I):
            score -= 0.5
        elif re.search(r"upgrade|outperform|overweight|raises? (?:price )?target|initiat", text, re.I):
            score += 0.45
    for w, rx in _WORD_RX.items():
        if rx.search(text):
            score += POS_WORDS.get(w, 0) + NEG_WORDS.get(w, 0)
    # "fails to" + "approval" etc. — let the negative event dominate
    if "TRIAL FAIL" in tags or "CRL" in tags:
        score = min(score, -0.5)
    return tags, max(-1.0, min(1.0, score)), impact


def extract_pdufa(text: str, tickers: list[str]) -> list[tuple[str, date]]:
    out = []
    for m in _PDUFA_RX.finditer(text):
        raw = m.group(1).replace(".", "").replace(",", "").replace("Sept", "Sep")
        for fmt in ("%B %d %Y", "%b %d %Y"):
            try:
                d = datetime.strptime(raw, fmt).date()
                break
            except ValueError:
                d = None
        if d and tickers:
            out.append((tickers[0], d))
    return out


def enrich(item: NewsItem, hint: Iterable[str] = ()) -> NewsItem:
    text = f"{item.title}. {item.summary}"
    item.tickers = tag_tickers(text, hint)
    item.tags, item.sentiment, impact = classify(text)
    recency = max(0.2, 1 - item.age_hours / 72)
    item.impact = round(impact * recency * (1.25 if item.tickers else 0.55), 3)
    item.pdufa = extract_pdufa(text, item.tickers)
    return item


_JUNK_RX = re.compile(
    r"market (?:size|share|report|outlook|analysis|to (?:gain|grow|witness|reach|expand|exceed))|forecast period|\bCAGR\b|"
    r"market research|industry report|\bcrore\b|\bRs\.? ?\d|¥|\bASX\b|\bNSE\b|\bBSE\b|FDA Approvals, PDUFA Dates & Drug Alerts|"
    r"stocks? (?:at|hitting) 52-week|top (?:\d+ )?(?:gainers|losers)", re.I)


def _is_relevant(item: NewsItem) -> bool:
    if _JUNK_RX.search(item.title):
        return False
    if item.tickers:
        return True
    return bool(re.search(r"pharm|biotech|\bFDA\b|drug|therap|vaccine|clinical|trial|oncolog|GLP-1|obesity|biosimilar", item.title, re.I))


class NewsWire:
    def __init__(self, cache: Cache, demo: bool = False):
        self.cache = cache
        self.demo = demo

    def _get(self, url: str) -> bytes | None:
        try:
            r = httpx.get(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"},
                          timeout=8, follow_redirects=True)
            return r.content if r.status_code == 200 else None
        except httpx.HTTPError as exc:
            log.debug("feed %s failed: %s", url, exc)
            return None

    def _fetch_feed(self, source: str, url: str, hint: tuple[str, ...] = ()) -> list[NewsItem]:
        raw = self._get(url)
        if not raw:
            return []
        items = []
        for e in feedparser.parse(raw).entries[:60]:
            title = _clean(e.get("title", ""))
            src = source
            if source == "Google News":
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2:
                    title, src = parts[0], parts[1]
            if not title:
                continue
            items.append(NewsItem(title=title, link=e.get("link", ""), source=src, published=_parse_date(e),
                                  summary=_clean(e.get("summary", ""))[:600]))
        return [enrich(i, hint if source == "Yahoo Finance" and len(hint) == 1 else ()) for i in items]

    def fetch(self, watch: Iterable[str] = ()) -> list[NewsItem]:
        if self.demo:
            return demo_news()

        def run() -> list[NewsItem]:
            jobs: list[tuple[str, str, tuple[str, ...]]] = [(s, u, ()) for s, u in FEEDS.items()]
            jobs += [("Google News", f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=en-US&gl=US&ceid=US:en", ())
                     for q in GOOGLE_QUERIES]
            ticks = [s.ticker for s in universe.equities()]
            for i in range(0, len(ticks), 12):
                chunk = ticks[i:i + 12]
                jobs.append(("Yahoo Finance", YAHOO_TICKER_FEED.format(symbols=",".join(chunk)), tuple(chunk)))
            for t in watch:
                jobs.append(("Yahoo Finance", YAHOO_TICKER_FEED.format(symbols=t), (t,)))
            with ThreadPoolExecutor(max_workers=12) as pool:
                batches = list(pool.map(lambda j: self._fetch_feed(*j), jobs))
            seen: dict[str, NewsItem] = {}
            cutoff = datetime.now(timezone.utc) - timedelta(days=5)
            for batch in batches:
                for it in batch:
                    if it.published < cutoff or not _is_relevant(it):
                        continue
                    prev = seen.get(it.id)
                    if prev is None or (it.tickers and not prev.tickers):
                        seen[it.id] = it
            return sorted(seen.values(), key=lambda i: i.published, reverse=True) or None

        return self.cache.memo("news:all", NEWS_TTL, run) or []


def for_ticker(items: list[NewsItem], ticker: str) -> list[NewsItem]:
    return [i for i in items if ticker.upper() in i.tickers]


def ticker_sentiment(items: list[NewsItem], hours: float = 72) -> dict[str, dict]:
    """Recency-weighted sentiment and headline count per ticker."""
    agg: dict[str, dict] = {}
    for it in items:
        if it.age_hours > hours:
            continue
        w = max(0.15, 1 - it.age_hours / hours) * (0.5 + it.impact)
        for t in it.tickers:
            a = agg.setdefault(t, {"score": 0.0, "weight": 0.0, "count": 0, "tags": set(), "top": None,
                                   "top_pos": None, "top_neg": None})
            a["score"] += it.sentiment * w
            a["weight"] += w
            a["count"] += 1
            a["tags"].update(it.tags)
            if a["top"] is None or it.impact > a["top"].impact:
                a["top"] = it
            if it.sentiment > 0.15 and (a["top_pos"] is None or it.impact > a["top_pos"].impact):
                a["top_pos"] = it
            if it.sentiment < -0.15 and (a["top_neg"] is None or it.impact > a["top_neg"].impact):
                a["top_neg"] = it
    for a in agg.values():
        a["score"] = a["score"] / a["weight"] if a["weight"] else 0.0
        # headline that matches the net tone
        if a["score"] > 0.15 and a["top_pos"]:
            a["top"] = a["top_pos"]
        elif a["score"] < -0.15 and a["top_neg"]:
            a["top"] = a["top_neg"]
    return agg


# ── Demo news ──────────────────────────────────────────────────────────

_DEMO_HEADLINES = (
    ("Eli Lilly's orforglipron hits primary endpoint in Phase 3 ATTAIN-MAINTAIN study", "STAT", 2),
    ("FDA approves Insmed's brensocatib label expansion, shares rise", "FDA", 5),
    ("Viking Therapeutics (NASDAQ: VKTX) announces proposed $400 million public offering", "GlobeNewswire", 9),
    ("Sarepta shares tumble after FDA places clinical hold on gene therapy program", "BioPharma Dive", 14),
    ("Madrigal Pharmaceuticals PDUFA target action date set for December 18, 2026 for Rezdiffra sNDA", "PR Newswire", 20),
    ("Pfizer to acquire obesity biotech in $4.9B deal", "Endpoints", 26),
    ("Novo Nordisk cuts full-year sales outlook on Wegovy pricing pressure", "Fierce Pharma", 30),
    ("Analyst upgrades Vertex to Outperform citing Journavx launch momentum", "Yahoo Finance", 33),
    ("Cytokinetics receives complete response letter for aficamten", "BioPharma Dive", 40),
    ("HHS outlines most-favored-nation drug pricing framework; big pharma shares slip", "STAT", 44),
    ("Summit Therapeutics ivonescimab shows statistically significant overall survival benefit", "Fierce Biotech", 50),
    ("Revolution Medicines daraxonrasib Phase 3 readout expected in Q4, PDUFA date of March 3, 2027 for first indication", "Endpoints", 58),
)


def demo_news() -> list[NewsItem]:
    now = datetime.now(timezone.utc)
    items = [NewsItem(title=t, link="https://example.com/demo", source=s, published=now - timedelta(hours=h),
                      summary="Synthetic demo headline.") for t, s, h in _DEMO_HEADLINES]
    return [enrich(i) for i in items]
