"""Catalyst calendar: earnings, FDA decision dates (PDUFA/AdCom), trial readouts.

Sources, merged and de-duplicated:
  * earnings dates from the market-data provider
  * PDUFA dates extracted from the news wire
  * Phase 2/3 primary-completion dates from ClinicalTrials.gov (API v2)
  * curated entries in config/catalysts.yaml (repo) and ~/.rxterm/catalysts.yaml (yours)
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import httpx
import yaml

from .. import universe
from ..cache import Cache
from .news import NewsItem

log = logging.getLogger(__name__)

REPO_CATALYSTS = Path(__file__).resolve().parents[2] / "config" / "catalysts.yaml"
CTGOV = "https://clinicaltrials.gov/api/v2/studies"
CTGOV_TTL = 24 * 3600

# How much a catalyst type matters for options pricing / binary risk.
TYPE_WEIGHT = {"PDUFA": 1.0, "ADCOM": 0.9, "READOUT": 0.8, "EARNINGS": 0.5, "TRIAL": 0.4, "CONFERENCE": 0.3, "OTHER": 0.3}


@dataclass(frozen=True)
class Catalyst:
    ticker: str
    when: date
    type: str            # PDUFA | ADCOM | READOUT | EARNINGS | TRIAL (CT.gov primary completion) | CONFERENCE | OTHER
    event: str
    source: str
    confirmed: bool = True

    @property
    def days_out(self) -> int:
        return (self.when - date.today()).days

    @property
    def weight(self) -> float:
        return TYPE_WEIGHT.get(self.type, 0.3)


def _as_date(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        s = v.strip()
        for fmt in ("%Y-%m-%d", "%Y-%m"):
            try:
                d = datetime.strptime(s, fmt).date()
                return d if fmt == "%Y-%m-%d" else d.replace(day=28)
            except ValueError:
                pass
    return None


def load_yaml(path: Path) -> list[Catalyst]:
    if not path.exists():
        return []
    try:
        rows = yaml.safe_load(path.read_text()) or []
    except yaml.YAMLError as exc:
        log.warning("bad catalysts file %s: %s", path, exc)
        return []
    out = []
    for r in rows if isinstance(rows, list) else []:
        d = _as_date(r.get("date"))
        if not d or not r.get("ticker"):
            continue
        out.append(Catalyst(str(r["ticker"]).upper(), d, str(r.get("type", "OTHER")).upper(),
                            str(r.get("event", "")), str(r.get("source", "curated")), bool(r.get("confirmed", True))))
    return out


def from_profiles(profiles: dict[str, dict]) -> list[Catalyst]:
    out = []
    for t, p in profiles.items():
        d = _as_date(p.get("earningsDate"))
        if d and d >= date.today() - timedelta(days=1):
            eps = p.get("epsEstimate")
            note = f"Q earnings · cons. EPS {eps:.2f}" if isinstance(eps, (int, float)) else "Quarterly earnings"
            out.append(Catalyst(t, d, "EARNINGS", note, "consensus", confirmed=False))
    return out


def from_news(items: Iterable[NewsItem]) -> list[Catalyst]:
    out = []
    for it in items:
        for tick, d in it.pdufa:
            if d >= date.today() - timedelta(days=1):
                out.append(Catalyst(tick, d, "PDUFA", it.title[:110], it.source))
    return out


def _ctgov_sponsor(name: str, ticker: str, horizon_days: int) -> list[Catalyst]:
    start, end = date.today(), date.today() + timedelta(days=horizon_days)
    params = {
        "query.spons": name,
        "filter.advanced": f"AREA[Phase](PHASE3 OR PHASE2) AND AREA[PrimaryCompletionDate]RANGE[{start},{end}]",
        "filter.overallStatus": "ACTIVE_NOT_RECRUITING|RECRUITING|ENROLLING_BY_INVITATION|COMPLETED",
        "fields": "NCTId,BriefTitle,Phase,PrimaryCompletionDate,LeadSponsorName",
        "pageSize": 10,
    }
    try:
        r = httpx.get(CTGOV, params=params, timeout=15)
        studies = r.json().get("studies", []) if r.status_code == 200 else []
    except (httpx.HTTPError, ValueError):
        return []
    out = []
    first_word = name.split()[0].lower()
    for s in studies:
        ps = s.get("protocolSection", {})
        lead = ps.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", "")
        if first_word not in lead.lower():
            continue
        d = _as_date(ps.get("statusModule", {}).get("primaryCompletionDateStruct", {}).get("date"))
        if not d:
            continue
        phases = "/".join(p.replace("PHASE", "Ph") for p in ps.get("designModule", {}).get("phases", []))
        nct = ps.get("identificationModule", {}).get("nctId", "")
        title = ps.get("identificationModule", {}).get("briefTitle", "")
        out.append(Catalyst(ticker, d, "TRIAL", f"{phases} primary completion · {title[:80]} ({nct})",
                            "ClinicalTrials.gov", confirmed=False))
    return out


def from_clinicaltrials(cache: Cache, horizon_days: int = 120) -> list[Catalyst]:
    def run():
        secs = [s for s in universe.equities() if s.segment in (universe.LARGE_BIO, universe.MID_BIO)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            batches = list(pool.map(lambda s: _ctgov_sponsor(s.name, s.ticker, horizon_days), secs))
        return [c for b in batches for c in b] or None

    return cache.memo(f"ctgov:{horizon_days}", CTGOV_TTL, run) or []


def build_calendar(profiles: dict[str, dict], news: Iterable[NewsItem], cache: Cache | None,
                   user_file: Path | None = None, horizon_days: int = 120, demo: bool = False) -> list[Catalyst]:
    cats = load_yaml(REPO_CATALYSTS) + (load_yaml(user_file) if user_file else [])
    cats += from_news(news) + from_profiles(profiles)
    if cache is not None and not demo:
        cats += from_clinicaltrials(cache, horizon_days)
    if demo:
        cats += _demo_catalysts()
    today, end = date.today() - timedelta(days=1), date.today() + timedelta(days=horizon_days)
    seen: dict[tuple[str, str, date], Catalyst] = {}
    for c in cats:
        if not (today <= c.when <= end) or c.ticker not in universe.UNIVERSE:
            continue
        key = (c.ticker, c.type, c.when)
        if key not in seen or (c.confirmed and not seen[key].confirmed):
            seen[key] = c
    # collapse multiple trial readouts per ticker/month to the earliest
    out, readouts = [], set()
    for c in sorted(seen.values(), key=lambda c: (c.when, -c.weight)):
        if c.type == "TRIAL":
            k = (c.ticker, c.when.strftime("%Y-%m"))
            if k in readouts:
                continue
            readouts.add(k)
        out.append(c)
    return out


def next_catalyst(cal: list[Catalyst], ticker: str, types: Iterable[str] | None = None) -> Catalyst | None:
    types = set(types) if types else None
    for c in cal:
        if c.ticker == ticker and c.days_out >= 0 and (types is None or c.type in types):
            return c
    return None


def _demo_catalysts() -> list[Catalyst]:
    t = date.today()
    rows = [("MDGL", 12, "PDUFA", "Rezdiffra sNDA — compensated MASH cirrhosis"),
            ("RVMD", 21, "READOUT", "RASolute-302 Ph3 topline (2L PDAC)"),
            ("CYTK", 9, "ADCOM", "FDA advisory committee — aficamten oHCM"),
            ("VKTX", 33, "READOUT", "VANQUISH-1 Ph3 interim (obesity)"),
            ("SRRK", 18, "PDUFA", "Apitegromab BLA resubmission — SMA"),
            ("AXSM", 26, "PDUFA", "AXS-05 sNDA — Alzheimer's agitation")]
    return [Catalyst(tk, t + timedelta(days=d), ty, ev, "demo") for tk, d, ty, ev in rows]
