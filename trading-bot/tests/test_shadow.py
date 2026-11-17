"""Schatten-Konto (1000 CHF) und automatischer Quartals-Re-Pick."""
import datetime as dt
import json

import pandas as pd
import pytest

from src import bot as botmod
from src import data, settings, shadow
from src.tick import prev_quarter

HAVE = (settings.DIRS["research"] / "manifest.json").exists() and (settings.DIRS["rules"] / "config.json").exists()


def test_prev_quarter():
    NY = botmod.NY
    assert prev_quarter(dt.datetime(2026, 11, 17, tzinfo=NY)) == "2026Q3"
    assert prev_quarter(dt.datetime(2027, 1, 5, tzinfo=NY)) == "2026Q4"
    assert prev_quarter(dt.datetime(2027, 4, 1, tzinfo=NY)) == "2027Q1"


@pytest.mark.skipif(not HAVE, reason="Daten/Regeln fehlen")
def test_shadow_1000chf_whole_shares_and_follows_bot(tmp_path, monkeypatch):
    monkeypatch.setitem(settings.DIRS, "live", tmp_path / "live")
    monkeypatch.setitem(settings.DIRS, "reports", tmp_path / "rep")
    (tmp_path / "rep").mkdir()
    monkeypatch.setattr(shadow, "fx_usdchf", lambda on=None: 0.84)
    cfg = botmod.load_config()
    prices = data.load_all(botmod.needed_tickers(cfg))
    cal = prices["SPY"].index
    d0, d1, d2 = cal[-3], cal[-2], cal[-1]
    gld_open = float(prices["GLD"].loc[d0, "open"])
    acc = shadow.init(1000, str(d0.date()), {"GLD": gld_open}, cfg)
    usd = 1000 / 0.84
    assert acc["start_usd"] == pytest.approx(usd)
    st = json.loads((tmp_path / "live" / "shadow_1000chf" / "state.json").read_text())
    q = st["core"]["holdings"]["GLD"]
    assert q == int(usd // (gld_open * 1.0005)) and q >= 1           # nur ganze Aktien
    r1 = shadow.evening(1000, d1, prices, cfg)
    assert r1["status"] == "ok"
    r2 = shadow.evening(1000, d2, prices, cfg)
    assert r2["status"] == "ok"
    assert shadow.evening(1000, d2, prices, cfg)["status"] == "heute schon gelaufen"
    rep = (tmp_path / "rep" / "konto_1000chf.md").read_text()
    assert "Schatten-Konto 1000 CHF" in rep and "CHF" in rep
    for o in r1["orders"] + r2["orders"]:
        assert isinstance(o["qty"], int) and o["qty"] > 0


@pytest.mark.skipif(not HAVE, reason="Daten/Regeln fehlen")
def test_apply_lineup_keeps_open_trades_and_bumps_version(tmp_path, monkeypatch):
    from src import adapt
    rules = tmp_path / "rules"
    rules.mkdir()
    for f in ("config.json", "bench.json", "CHANGELOG.md"):
        (rules / f).write_text((settings.DIRS["rules"] / f).read_text())
    monkeypatch.setattr(adapt, "RULES", rules)
    monkeypatch.setattr(adapt, "write_kill_lines", lambda: None)
    cfg0 = json.loads((rules / "config.json").read_text())
    old = cfg0["sleeves"][0]
    picks = [{"id": "sleeve:GLD:ibs20_h5", "ticker": "GLD", "kind": "ibs",
              "rule": {"kind": "ibs", "a": 20, "b": 5, "trend": 200}}]
    cfg = adapt.apply_lineup(picks, "2026-12-31", holding={old["id"]}, quarter="2026Q4")
    ids = {s["id"]: s["enabled"] for s in cfg["sleeves"]}
    assert ids[old["id"]] is False                       # im Trade: bleibt, wird verkauft
    assert ids["sleeve:GLD:ibs20_h5"] is True
    assert len(ids) == 2                                 # flache, nicht gewählte Sleeves entfernt
    assert cfg["version"] == cfg0.get("version", 0) + 1 and cfg["lineup_quarter"] == "2026Q4"
