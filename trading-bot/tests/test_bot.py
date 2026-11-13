"""Phase H: Bot-Tests (ohne echte Keys, mit simuliertem Paper-Broker)."""
import json

import pandas as pd
import pytest

from src import bot as botmod
from src import broker as brokermod
from src import data, risk, settings, signals
from src.core import core_weights

HAVE = (settings.DIRS["rules"] / "config.json").exists() and (settings.DIRS["research"] / "manifest.json").exists()
pytestmark = pytest.mark.skipif(not HAVE, reason="Phase P/Daten fehlen")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(botmod, "LOCK_PATH", tmp_path / "bot.lock")
    cfg = botmod.load_config()
    prices = data.load_all(botmod.needed_tickers(cfg))
    cal = prices["SPY"].index
    br = brokermod.SimBroker(prices, cash=cfg["starting_cash"], date=cal[-30])
    b = botmod.Bot(br, lambda d: prices, state_path=tmp_path / "state.json", alerts=False, cfg=cfg,
                   pause_file=tmp_path / "PAUSE")
    return b, br, prices, cal, tmp_path


def test_bot_signals_equal_backtest_last_60_days(env):
    b, br, prices, cal, _ = env
    cfg = b.cfg
    w = core_weights(cfg["core"]["engine"], cfg["core"]["safe"], data.load_all())
    full = {s["id"]: (signals.rule_from_dict(s["rule"]).entry(prices[s["ticker"]]),
                      signals.rule_from_dict(s["rule"]).exit(prices[s["ticker"]])) for s in cfg["sleeves"]}
    for d in cal[-60:]:
        dec = botmod.decide(prices, d, cfg)
        assert dec["core_symbol"] == w.loc[d].idxmax(), d
        for sid, (en, ex) in full.items():
            assert dec["sleeves"][sid]["entry"] == bool(en.loc[d]), (sid, d)
            assert dec["sleeves"][sid]["exit"] == bool(ex.loc[d]), (sid, d)


def test_second_run_sends_nothing(env):
    b, br, prices, cal, _ = env
    d = cal[-30]
    r1 = b.evening(d)
    n = len(br.orders)
    assert r1["status"] == "ok" and n >= 1
    assert b.evening(d)["status"] == "heute schon gelaufen"
    b.send(r1["orders"], [])                       # auch direktes Nachsenden: keine Duplikate
    assert len(br.orders) == n


def test_reconcile_mismatch_stops(env):
    b, br, prices, cal, _ = env
    d = cal[-30]
    b.evening(d)
    br.open_session(cal[-29]); b.morning(cal[-29])
    br.pos["XLF"] = 7                              # Fremd-Position, die der Bot nicht kennt
    with pytest.raises(botmod.Abort, match="Reconcile"):
        b.evening(cal[-29])


def test_first_run_with_foreign_positions_stops(env):
    b, br, *_ , cal, _ = env
    br.pos["SPY"] = 10
    with pytest.raises(botmod.Abort, match="Erster Lauf"):
        b.evening(cal[-30])


def test_stale_data_stops(env):
    b, br, prices, cal, _ = env
    old = {t: d[d.index < cal[-30]] if t == "QQQ" else d for t, d in prices.items()}
    b.prices_fn = lambda d: old
    with pytest.raises(botmod.Abort, match="nicht von heute"):
        b.evening(cal[-30])


def test_bad_day_creates_pause_and_blocks_new_sleeves(tmp_path):
    pf = tmp_path / "PAUSE"
    rs = risk.assess(94_000, 100_000, 100_000, False, pf)
    assert pf.exists() and rs.bad_day and not rs.allow_new_sleeves
    rs2 = risk.assess(100_500, 100_000, 100_500, False, pf)   # Folgetag gut: PAUSE bleibt
    assert rs2.paused and not rs2.allow_new_sleeves
    rs3 = risk.assess(97_000, 100_000, 100_000, False, tmp_path / "none")
    assert rs3.day_block and not rs3.bad_day                  # 3 %: nur heute geblockt


def test_borrow_stop_hysteresis():
    worst = risk.worst_backtest_dd()
    assert risk.assess(100, 100, 100 / (1 - worst * 1.1), False, persist=False).borrow_blocked
    assert risk.assess(100, 100, 100 / (1 - worst * 0.7), True, persist=False).borrow_blocked
    assert not risk.assess(100, 100, 100 / (1 - worst * 0.4), True, persist=False).borrow_blocked


def test_order_size_check():
    errs = risk.check_orders([{"symbol": "QQQ", "qty": 200, "side": "buy", "price": 100, "target_value": 10_000}],
                             100_000, 1.6, 1.05)
    assert errs


def test_full_loop_matches_backtest(tmp_path):
    from src import paper_sim
    from src.account import account_returns
    from src.core import core_returns
    cfg = botmod.load_config()
    prices = data.load_all()
    r = paper_sim.run(60, workdir=tmp_path, day_limits=False)
    e = r["equity"]
    acc, _ = account_returns(core_returns(cfg["core"]["engine"], cfg["core"]["safe"], prices),
                             cfg["sleeves"], prices, cfg["vol_sizing_half"])
    d = pd.DataFrame({"sim": e.pct_change(), "bt": acc.reindex(e.index)}).iloc[2:]
    assert abs((1 + d.sim).prod() - (1 + d.bt).prod()) < 0.01
    assert (d.sim - d.bt).abs().max() < 0.005


def test_alpaca_refuses_without_paper(monkeypatch):
    monkeypatch.setattr(brokermod, "_env_flags", lambda: {"ALPACA_API_KEY": True, "ALPACA_SECRET_KEY": True,
                                                           "ALPACA_PAPER": True})
    monkeypatch.setenv("ALPACA_PAPER", "false")
    with pytest.raises(brokermod.BrokerSafetyError):
        brokermod.AlpacaBroker()


def test_env_values_never_printed(capsys):
    botmod.main(["check-keys"])
    out = capsys.readouterr().out
    assert all(w in ("gesetzt", "FEHLT") for w in (ln.split()[-1] for ln in out.strip().splitlines()))
