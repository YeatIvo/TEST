"""Phase P: Backtester-Mechanik und Ergebnisse prüfen."""
import json

import numpy as np
import pandas as pd
import pytest

from src import backtest as bt
from src import selfcheck, settings, signals

HAVE = (settings.DIRS["rules"] / "config.json").exists()


def _df(o, h, l, c):
    idx = pd.bdate_range("2024-01-01", periods=len(o))
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": 1}, index=idx)


def test_entry_next_open_and_exit_next_open():
    df = _df([10, 11, 12, 13, 14], [10, 11, 12, 13, 14], [10, 11, 12, 13, 14], [10, 11, 12, 13, 14])
    ent = pd.Series([True, False, False, False, False], df.index)
    ext = pd.Series([False, True, False, False, False], df.index)
    res = bt.simulate_trades(df, ent, ext, cost=0.0)
    tr = res.trades.iloc[0]
    assert tr["entry_px"] == 11 and tr["exit_px"] == 12          # Signal Tag 0 -> Open Tag 1; Exit Tag 1 -> Open Tag 2
    assert res.daily.add(1).prod() == pytest.approx(12 / 11)


def test_stop_and_gap():
    # Tag 1 Einstieg @100, Tag 2 Tief 91 -> Stop 92 (8 %), Tag-2-Verlust exakt -8 %
    df = _df([100, 100, 99, 95], [100, 101, 99, 95], [100, 99, 91, 95], [100, 100, 95, 95])
    ent = pd.Series([True, False, False, False], df.index)
    res = bt.simulate_trades(df, ent, None, cost=0.0, stop_pct=0.08)
    assert res.trades.iloc[0]["exit_px"] == pytest.approx(92)
    assert res.trades.iloc[0]["reason"] == "stop"
    # Gap: Open schon unter dem Stop -> Verkauf zum Open
    df2 = _df([100, 100, 85, 85], [100, 101, 86, 86], [100, 99, 80, 80], [100, 100, 85, 85])
    res2 = bt.simulate_trades(df2, ent, None, cost=0.0, stop_pct=0.08)
    assert res2.trades.iloc[0]["exit_px"] == pytest.approx(85)


def test_weights_constant_equals_buy_and_hold():
    rng = np.random.default_rng(3)
    c = 100 * np.cumprod(1 + rng.normal(0, 0.01, 300))
    o = c * (1 + rng.normal(0, 0.002, 300))
    df = _df(o, np.maximum(o, c), np.minimum(o, c), c)
    w = pd.DataFrame({"X": 1.0}, index=df.index)
    r = bt.simulate_weights({"X": df}, w, {"X": 0.0})
    # ab Tag 1 (Kauf zum Open) gleich Buy&Hold ab Open Tag 1
    assert (1 + r.iloc[1:]).prod() == pytest.approx(c[-1] / o[1], rel=1e-9)


def test_selfcheck_passes():
    assert selfcheck.run()["all_pass"]


def test_lock_once_never_reruns(tmp_path, monkeypatch):
    monkeypatch.setitem(settings.DIRS, "results", tmp_path)
    calls = []
    f = lambda: calls.append(1) or {"cagr": 0.1}
    assert bt.lock_once("x", f) == {"cagr": 0.1}
    assert bt.lock_once("x", f) == {"cagr": 0.1}
    assert len(calls) == 1


@pytest.mark.skipif(not HAVE, reason="Phase P noch nicht gelaufen")
def test_config_is_valid():
    cfg = json.loads((settings.DIRS["rules"] / "config.json").read_text())
    assert cfg["core"]["engine"] in settings.load()["universe"]["engine_candidates"]
    assert len(cfg["sleeves"]) <= settings.load()["portfolio"]["max_sleeves"]
    assert len({s["ticker"] for s in cfg["sleeves"]}) == len(cfg["sleeves"])
    for s in cfg["sleeves"]:
        signals.rule_from_dict(s["rule"])
    assert 1 + sum(s["weight"] for s in cfg["sleeves"]) <= cfg["margin"]["max_gross"] + 1e-9
