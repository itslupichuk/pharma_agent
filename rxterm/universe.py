"""The RXTERM coverage universe: US-listed pharma & biotech plus sector ETFs.

Each entry carries the segment used for screening/risk tiering and the name
aliases used to tag news headlines to tickers. Tickers that stop returning
data (delistings, M&A) are dropped automatically at load time.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Security:
    ticker: str
    name: str
    segment: str
    aliases: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_etf(self) -> bool:
        return self.segment == "ETF"


BIG_PHARMA = "Big Pharma"
LARGE_BIO = "Large-Cap Biotech"
MID_BIO = "SMID Biotech"
SPEC = "Specialty & Generics"
ETF = "ETF"

SEGMENTS = (BIG_PHARMA, LARGE_BIO, MID_BIO, SPEC)

_U: list[Security] = [
    # ── Sector benchmarks ───────────────────────────────────────────────
    Security("XBI", "SPDR S&P Biotech ETF", ETF),
    Security("IBB", "iShares Biotechnology ETF", ETF),
    Security("XPH", "SPDR S&P Pharmaceuticals ETF", ETF),
    Security("SPY", "SPDR S&P 500 ETF", ETF),
    # ── Big Pharma ──────────────────────────────────────────────────────
    Security("LLY", "Eli Lilly", BIG_PHARMA, ("Lilly", "Eli Lilly", "Zepbound", "Mounjaro", "orforglipron")),
    Security("NVO", "Novo Nordisk", BIG_PHARMA, ("Novo Nordisk", "Novo", "Wegovy", "Ozempic", "semaglutide")),
    Security("JNJ", "Johnson & Johnson", BIG_PHARMA, ("Johnson & Johnson", "J&J", "Janssen")),
    Security("MRK", "Merck & Co.", BIG_PHARMA, ("Merck", "Keytruda", "MSD")),
    Security("ABBV", "AbbVie", BIG_PHARMA, ("AbbVie", "Skyrizi", "Rinvoq")),
    Security("PFE", "Pfizer", BIG_PHARMA, ("Pfizer",)),
    Security("BMY", "Bristol Myers Squibb", BIG_PHARMA, ("Bristol Myers", "Bristol-Myers", "BMS", "Cobenfy")),
    Security("AZN", "AstraZeneca", BIG_PHARMA, ("AstraZeneca", "Astra Zeneca")),
    Security("NVS", "Novartis", BIG_PHARMA, ("Novartis",)),
    Security("GSK", "GSK plc", BIG_PHARMA, ("GSK", "GlaxoSmithKline")),
    Security("SNY", "Sanofi", BIG_PHARMA, ("Sanofi", "Dupixent")),
    Security("AMGN", "Amgen", BIG_PHARMA, ("Amgen", "MariTide")),
    Security("GILD", "Gilead Sciences", BIG_PHARMA, ("Gilead", "lenacapavir")),
    Security("TAK", "Takeda", BIG_PHARMA, ("Takeda",)),
    # ── Large-cap biotech ───────────────────────────────────────────────
    Security("VRTX", "Vertex Pharmaceuticals", LARGE_BIO, ("Vertex", "Journavx", "suzetrigine")),
    Security("REGN", "Regeneron", LARGE_BIO, ("Regeneron", "Eylea")),
    Security("BIIB", "Biogen", LARGE_BIO, ("Biogen", "Leqembi")),
    Security("MRNA", "Moderna", LARGE_BIO, ("Moderna",)),
    Security("BNTX", "BioNTech", LARGE_BIO, ("BioNTech",)),
    Security("ALNY", "Alnylam", LARGE_BIO, ("Alnylam", "Amvuttra")),
    Security("ARGX", "argenx", LARGE_BIO, ("argenx", "Vyvgart")),
    Security("INSM", "Insmed", LARGE_BIO, ("Insmed", "brensocatib", "Brinsupri")),
    Security("BMRN", "BioMarin", LARGE_BIO, ("BioMarin", "Voxzogo")),
    Security("INCY", "Incyte", LARGE_BIO, ("Incyte", "Jakafi")),
    Security("NBIX", "Neurocrine Biosciences", LARGE_BIO, ("Neurocrine",)),
    Security("UTHR", "United Therapeutics", LARGE_BIO, ("United Therapeutics", "Tyvaso")),
    Security("EXEL", "Exelixis", LARGE_BIO, ("Exelixis", "zanzalintinib")),
    Security("ASND", "Ascendis Pharma", LARGE_BIO, ("Ascendis",)),
    Security("BBIO", "BridgeBio Pharma", LARGE_BIO, ("BridgeBio", "Attruby")),
    Security("RVMD", "Revolution Medicines", LARGE_BIO, ("Revolution Medicines", "daraxonrasib")),
    Security("ROIV", "Roivant Sciences", LARGE_BIO, ("Roivant", "brepocitinib")),
    Security("SMMT", "Summit Therapeutics", LARGE_BIO, ("Summit Therapeutics", "ivonescimab")),
    Security("JAZZ", "Jazz Pharmaceuticals", LARGE_BIO, ("Jazz Pharmaceuticals",)),
    Security("IONS", "Ionis Pharmaceuticals", LARGE_BIO, ("Ionis", "olezarsen")),
    Security("SRPT", "Sarepta Therapeutics", LARGE_BIO, ("Sarepta", "Elevidys")),
    Security("HALO", "Halozyme", LARGE_BIO, ("Halozyme",)),
    # ── SMID biotech ────────────────────────────────────────────────────
    Security("MDGL", "Madrigal Pharmaceuticals", MID_BIO, ("Madrigal", "Rezdiffra", "resmetirom")),
    Security("VKTX", "Viking Therapeutics", MID_BIO, ("Viking Therapeutics", "VK2735")),
    Security("AXSM", "Axsome Therapeutics", MID_BIO, ("Axsome",)),
    Security("ACAD", "ACADIA Pharmaceuticals", MID_BIO, ("Acadia Pharmaceuticals", "ACADIA")),
    Security("CYTK", "Cytokinetics", MID_BIO, ("Cytokinetics", "aficamten")),
    Security("KRYS", "Krystal Biotech", MID_BIO, ("Krystal Biotech",)),
    Security("PTCT", "PTC Therapeutics", MID_BIO, ("PTC Therapeutics",)),
    Security("RYTM", "Rhythm Pharmaceuticals", MID_BIO, ("Rhythm Pharmaceuticals", "setmelanotide")),
    Security("TGTX", "TG Therapeutics", MID_BIO, ("TG Therapeutics", "Briumvi")),
    Security("ALKS", "Alkermes", MID_BIO, ("Alkermes",)),
    Security("CRSP", "CRISPR Therapeutics", MID_BIO, ("CRISPR Therapeutics", "Casgevy")),
    Security("NTLA", "Intellia Therapeutics", MID_BIO, ("Intellia",)),
    Security("BEAM", "Beam Therapeutics", MID_BIO, ("Beam Therapeutics",)),
    Security("VRDN", "Viridian Therapeutics", MID_BIO, ("Viridian",)),
    Security("IMVT", "Immunovant", MID_BIO, ("Immunovant",)),
    Security("ARWR", "Arrowhead Pharmaceuticals", MID_BIO, ("Arrowhead",)),
    Security("DNLI", "Denali Therapeutics", MID_BIO, ("Denali",)),
    Security("XENE", "Xenon Pharmaceuticals", MID_BIO, ("Xenon",)),
    Security("PCVX", "Vaxcyte", MID_BIO, ("Vaxcyte",)),
    Security("VERA", "Vera Therapeutics", MID_BIO, ("Vera Therapeutics", "atacicept")),
    Security("CORT", "Corcept Therapeutics", MID_BIO, ("Corcept", "relacorilant")),
    Security("KYMR", "Kymera Therapeutics", MID_BIO, ("Kymera",)),
    Security("IDYA", "IDEAYA Biosciences", MID_BIO, ("IDEAYA",)),
    Security("CELC", "Celcuity", MID_BIO, ("Celcuity", "gedatolisib")),
    Security("TVTX", "Travere Therapeutics", MID_BIO, ("Travere", "Filspari")),
    Security("PRAX", "Praxis Precision Medicines", MID_BIO, ("Praxis Precision",)),
    Security("MIRM", "Mirum Pharmaceuticals", MID_BIO, ("Mirum",)),
    Security("ARQT", "Arcutis Biotherapeutics", MID_BIO, ("Arcutis",)),
    Security("HRMY", "Harmony Biosciences", MID_BIO, ("Harmony Biosciences",)),
    Security("LEGN", "Legend Biotech", MID_BIO, ("Legend Biotech", "Carvykti")),
    Security("MLYS", "Mineralys Therapeutics", MID_BIO, ("Mineralys", "lorundrostat")),
    Security("CGON", "CG Oncology", MID_BIO, ("CG Oncology",)),
    Security("ELVN", "Enliven Therapeutics", MID_BIO, ("Enliven",)),
    Security("OLMA", "Olema Pharmaceuticals", MID_BIO, ("Olema",)),
    Security("ANAB", "AnaptysBio", MID_BIO, ("AnaptysBio",)),
    Security("RCKT", "Rocket Pharmaceuticals", MID_BIO, ("Rocket Pharmaceuticals",)),
    Security("SRRK", "Scholar Rock", MID_BIO, ("Scholar Rock", "apitegromab")),
    Security("OCUL", "Ocular Therapeutix", MID_BIO, ("Ocular Therapeutix", "Axpaxli")),
    Security("GPCR", "Structure Therapeutics", MID_BIO, ("Structure Therapeutics", "aleniglipron")),
    Security("NVAX", "Novavax", MID_BIO, ("Novavax",)),
    Security("IOVA", "Iovance Biotherapeutics", MID_BIO, ("Iovance",)),
    Security("AUPH", "Aurinia Pharmaceuticals", MID_BIO, ("Aurinia",)),
    Security("ALT", "Altimmune", MID_BIO, ("Altimmune", "pemvidutide")),
    Security("VIR", "Vir Biotechnology", MID_BIO, ("Vir Biotechnology",)),
    Security("SANA", "Sana Biotechnology", MID_BIO, ("Sana Biotechnology",)),
    Security("DYN", "Dyne Therapeutics", MID_BIO, ("Dyne Therapeutics",)),
    Security("WVE", "Wave Life Sciences", MID_BIO, ("Wave Life Sciences",)),
    # ── Specialty & generics ────────────────────────────────────────────
    Security("TEVA", "Teva Pharmaceutical", SPEC, ("Teva",)),
    Security("VTRS", "Viatris", SPEC, ("Viatris",)),
    Security("OGN", "Organon", SPEC, ("Organon",)),
    Security("PRGO", "Perrigo", SPEC, ("Perrigo",)),
    Security("AMRX", "Amneal Pharmaceuticals", SPEC, ("Amneal",)),
    Security("ZTS", "Zoetis", SPEC, ("Zoetis",)),
    Security("SUPN", "Supernus Pharmaceuticals", SPEC, ("Supernus",)),
    Security("LNTH", "Lantheus", SPEC, ("Lantheus",)),
]

UNIVERSE: dict[str, Security] = {s.ticker: s for s in _U}
BENCHMARKS = ("XBI", "IBB", "XPH", "SPY")
SECTOR_BENCH = "XBI"


def equities() -> list[Security]:
    return [s for s in UNIVERSE.values() if not s.is_etf]


def get(ticker: str) -> Security | None:
    return UNIVERSE.get(ticker.upper())


def name_of(ticker: str) -> str:
    sec = get(ticker)
    return sec.name if sec else ticker.upper()
