import json
from dataclasses import replace
from datetime import date

import pytest

from rxterm.analytics import screener, thesis
from rxterm.analytics.ideas import AGGRESSIVE, CONSERVATIVE
from rxterm.brief import render
from rxterm.config import settings
from rxterm.data import catalysts, news
from rxterm.engine import Engine


@pytest.fixture(scope="module")
def snap(tmp_path_factory):
    cfg = replace(settings, demo=True, home=tmp_path_factory.mktemp("rx"), anthropic_api_key="")
    return Engine(cfg).full()


def test_board_has_scores(snap):
    b = snap.board
    assert len(b) > 80
    eq = b[b["segment"] != "ETF"]
    assert eq["long_score"].between(0, 100).all()
    assert set(eq["signal"]) <= {"STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL"}


def test_ideas_cover_both_tiers(snap):
    tiers = {i.tier for i in snap.ideas}
    assert tiers == {CONSERVATIVE, AGGRESSIVE}
    assert sum(i.tier == CONSERVATIVE for i in snap.ideas) == 3
    assert sum(i.tier == AGGRESSIVE for i in snap.ideas) == 3
    assert len({i.ticker for i in snap.ideas}) == len(snap.ideas)
    for i in snap.ideas:
        assert i.thesis and i.headline and i.legs
        assert 1 <= i.conviction <= 5
        if i.direction == "LONG" and i.basis == "underlying":
            assert i.stop < i.entry < i.target
        if i.direction == "SHORT":
            assert i.target < i.entry < i.stop
        if i.structure in ("Bull Call Spread", "Bear Put Spread"):
            assert 0 < i.net_premium and i.max_gain > 0


def test_conservative_is_large_cap(snap):
    for i in snap.ideas:
        if i.tier == CONSERVATIVE:
            assert i.segment != "SMID Biotech"


def test_screens_run(snap):
    for code in screener.SCREENS:
        res = screener.run(snap.board, code)
        assert "ETF" not in set(res["segment"])


def test_news_classification():
    tags, s, _ = news.classify("Acme receives complete response letter from FDA for lead drug")
    assert "CRL" in tags and s < 0
    tags, s, _ = news.classify("Acme Phase 3 trial met its primary endpoint with statistically significant benefit")
    assert "TRIAL WIN" in tags and s > 0
    tags, s, _ = news.classify("Acme's drug fails key late-stage trial, stock tanks")
    assert "TRIAL FAIL" in tags and s < 0
    assert news.tag_tickers("Eli Lilly's Zepbound sales beat; (NASDAQ: VKTX) rallies") == ["VKTX", "LLY"]


def test_pdufa_extraction():
    out = news.extract_pdufa("FDA sets PDUFA target action date of December 18, 2026 for Madrigal", ["MDGL"])
    assert out == [("MDGL", date(2026, 12, 18))]


def test_curated_calendar_loads():
    rows = catalysts.load_yaml(catalysts.REPO_CATALYSTS)
    assert rows and all(r.type in catalysts.TYPE_WEIGHT for r in rows)


def test_brief_renders(snap, tmp_path):
    paths = render.write_outputs(snap, tmp_path)
    html = paths["html"].read_text()
    for i in snap.ideas:
        assert i.ticker in html
    assert "Conservative Trades" in html and "Aggressive Trades" in html
    data = json.loads(paths["json"].read_text())
    assert len(data["ideas"]) == len(snap.ideas)
    assert paths["subject"].read_text().startswith("RXTERM Pharma Brief")


def test_external_theses_merge(snap):
    t = snap.ideas[0].ticker
    thesis.apply_theses(snap, {"market_take": "Desk take.", "ideas": [
        {"ticker": t, "headline": "H", "thesis": "T", "risks": ["R1", "R2"]}], "top_stories": [{"index": 0, "take": "so what"}]})
    assert snap.market_take == "Desk take."
    assert snap.ideas[0].thesis == "T" and snap.ideas[0].risks == ["R1", "R2"]
    assert snap.story_takes[0] == "so what"


def test_email_secret_cleaning_and_diagnosis(monkeypatch):
    from rxterm.brief import send

    assert send._clean_secret("abcd efgh ijkl mnop\n") == "abcdefghijklmnop"
    notes = send._diagnose("me", "short", "smtp.gmail.com")
    assert any("full Gmail address" in n for n in notes) and any("16 letters" in n for n in notes)

    cfg = replace(settings, smtp_host="127.0.0.1", smtp_port=1, smtp_user="me@gmail.com",
                  smtp_password="abcd efgh ijkl mnop", email_to="me@gmail.com")
    monkeypatch.setattr(send, "_send", lambda *a, **k: (_ for _ in ()).throw(OSError("refused")))
    with pytest.raises(send.EmailSendFailed) as exc:
        send.send_email(cfg, "s", "<p>h</p>", "t")
    assert "port 1" in str(exc.value) and "port 587" in str(exc.value)


def test_timeframes_cover_intraday_to_10y():
    from rxterm.data import bars
    from rxterm.data.market import DemoMarketData

    md = DemoMarketData()
    daily = md.history(["LLY"], "1y")["LLY"]
    last = float(daily["Close"].iloc[-1])
    for tf in bars.TIMEFRAMES:
        df = bars.get_bars(md, "LLY", tf.code, daily)
        assert df is not None and len(df) >= 2, tf.code
        assert abs(float(df["Close"].iloc[-1]) / last - 1) < 0.05, tf.code
    assert bars.resolve("max") == "10Y" and bars.resolve("5d") == "5D" and bars.resolve("XYZ") is None
    assert bars.step("1D", -1) == "1D" and bars.step("6M", 1) == "YTD" and bars.step("10Y", 1) == "10Y"


def test_alerts_parse_trigger_persist(tmp_path):
    from rxterm.alerts import AlertBook, parse

    assert parse(["LLY", ">", "1,250"]) == ("LLY", ">", 1250.0)
    assert parse(["LLY", "<1100"]) == ("LLY", "<", 1100.0)
    assert parse(["LLY", "abc"]) is None
    book = AlertBook(tmp_path / "alerts.json")
    up = book.add("LLY", 1250, None, last=1200)      # auto direction: above
    dn = book.add("NVO", 30, None, last=38)          # auto direction: below
    assert (up.op, dn.op) == (">", "<")
    assert book.check({"LLY": 1240, "NVO": 31}) == []
    hits = book.check({"LLY": 1251, "NVO": 29.5})
    assert {a.ticker for a, _ in hits} == {"LLY", "NVO"}
    assert book.check({"LLY": 1300}) == []           # fires once
    assert len(AlertBook(tmp_path / "alerts.json").alerts) == 2
    assert book.remove("LLY") == 1 and book.remove("ALL") == 1


def test_option_delta():
    from rxterm.tui.app import bs_delta

    c = bs_delta(100, 100, 0.25, 0.3, True)
    p = bs_delta(100, 100, 0.25, 0.3, False)
    assert 0.5 < c < 0.6 and abs(c - p - 1) < 1e-9
    assert bs_delta(100, 150, 0.1, 0.3, True) < 0.05
    assert bs_delta(100, 100, 0.25, float("nan"), True) is None


def test_gui_service_endpoints(tmp_path):
    """The desktop window's local service answers every page's request on demo data."""
    import time
    from dataclasses import replace

    from rxterm.config import settings
    from rxterm.gui.backend import Backend
    from rxterm.gui.server import Server

    cfg = replace(settings, demo=True, home=tmp_path, anthropic_api_key="")
    be = Backend(cfg)
    be.start()
    for _ in range(240):
        if be.status()["ready"] and not be.loading:
            break
        time.sleep(0.25)
    srv = Server(be)
    m = srv.call("monitor", {})
    assert m["ready"] and len(m["rows"]) > 50
    assert srv.call("stock", {"ticker": "LLY"})["stats"]
    assert srv.call("bars", {"ticker": "LLY", "tf": "1D"})["intraday"]
    assert len(srv.call("ideas", {})["ideas"]) == 6
    assert srv.call("chain", {"ticker": "LLY"})["rows"]
    assert len(srv.call("compare", {"tickers": "LLY,NVO", "tf": "6M"})["series"]) == 2
    srv.call("alert_add", {"ticker": "LLY", "op": "<", "level": 999999})
    assert be.status()["events"], "alert below a huge level triggers immediately"
    srv.httpd.server_close()
