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
