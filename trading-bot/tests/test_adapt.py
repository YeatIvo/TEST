"""Phase Adapt: Kill-Lines, Status, Rotation, Vergleich Paper vs. Backtest."""
import json

import pytest

from src import adapt, settings
from src import bot as botmod
from src import broker as brokermod
from src import data

HAVE = (settings.DIRS["rules"] / "kill_lines.json").exists()
pytestmark = pytest.mark.skipif(not HAVE, reason="Kill-Lines fehlen (python -m src.adapt kill-lines)")


def test_live_drawdown():
    sl = {"closed": [0.05, -0.10, -0.10, 0.02], "status": "flat", "symbol": "XLK"}
    dd, n = adapt.live_drawdown(sl, None, 0.0)
    assert n == 4 and dd == pytest.approx(1 - 0.9 * 0.9)
    sl2 = {"closed": [], "status": "in_trade", "entry_px": 100, "symbol": "XLK"}
    assert adapt.live_drawdown(sl2, 80, 0.0)[0] == pytest.approx(0.2)


def test_status_levels():
    kl = {"sleeves": {"x": {"kill_line": 0.20, "trades_per_year": 8}}}
    base = {"symbol": "XLK", "status": "flat"}
    assert adapt.sleeve_status("x", {**base, "closed": [-0.25]}, None, 10, kl)["status"] == "out"
    assert adapt.sleeve_status("x", {**base, "closed": [-0.12]}, None, 10, kl)["status"] == "watch"
    assert adapt.sleeve_status("x", {**base, "closed": [0.01] * 6}, None, 10, kl)["status"] == "keep"
    # nach 1 Jahr live: 6 Trades/J bei 8 im Test = im Rahmen; 1 Trade/J (< halb so oft) = review; 20/J = review
    assert adapt.sleeve_status("x", {**base, "closed": [0.01] * 6}, None, 252, kl)["status"] == "keep"
    assert adapt.sleeve_status("x", {**base, "closed": [0.01] * 1}, None, 252, kl)["status"] == "review"
    assert adapt.sleeve_status("x", {**base, "closed": [0.01] * 20}, None, 252, kl)["status"] == "review"


def test_kill_line_switches_sleeve_off_in_bot(tmp_path, monkeypatch):
    monkeypatch.setattr(botmod, "LOCK_PATH", tmp_path / "lock")
    cfg = botmod.load_config()
    prices = data.load_all(botmod.needed_tickers(cfg))
    cal = prices["SPY"].index
    br = brokermod.SimBroker(prices, cash=cfg["starting_cash"], date=cal[-5])
    b = botmod.Bot(br, lambda d: prices, state_path=tmp_path / "s.json", alerts=False, cfg=cfg,
                   pause_file=tmp_path / "P", log_dir=tmp_path)
    st = botmod.load_state(tmp_path / "s.json", cfg)
    sid = cfg["sleeves"][0]["id"]
    st["sleeves"][sid]["closed"] = [-0.2, -0.2, -0.2]        # weit über jeder Kill-Line
    botmod.save_state(st, tmp_path / "s.json")
    before = (settings.DIRS["rules"] / "config.json").read_text()
    r = b.evening(cal[-5])
    assert any("abgeschaltet" in x for x in r["risk"]["reasons"])
    assert (settings.DIRS["rules"] / "config.json").read_text() == before   # Simulation ändert rules/ nie


def test_rotate_dry_run_never_changes_config():
    before = (settings.DIRS["rules"] / "config.json").read_text()
    cfg = json.loads(before)
    live = cfg["sleeves"][0]["id"]
    bench = adapt.bench_list()
    if not bench:
        pytest.skip("Bank leer")
    r = adapt.rotate(live, bench[0]["id"], apply=False)
    assert set(r["checks"]) == {"ticker_frei", "korrelation<=0.6", "konto_besser_oder_gleich"}
    assert (settings.DIRS["rules"] / "config.json").read_text() == before


def test_compare_on_sim_has_no_unexplained_gaps():
    from src import compare
    c = compare.from_sim(60)
    assert "rules" not in c["groups"]
