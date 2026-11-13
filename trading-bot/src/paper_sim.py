"""Lässt den echten Bot-Code Tag für Tag über vergangene Handelstage laufen –
mit simuliertem Paper-Broker (MOO-Fills zum Open, Stops beim Broker, ganze Aktien).

Ablauf je Tag d:  Abend-Lauf(d) → Open(d+1): MOO-Fills → Morgen-Check → Stops im Tagesverlauf.
Nützlich, um ohne Alpaca-Keys alles zu prüfen, und als Vergleich Bot vs. Backtest (Phase Adapt).
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import pandas as pd

from . import data, settings
from .bot import Bot, load_config, needed_tickers
from .broker import SimBroker


def run(days: int = 60, end: pd.Timestamp | None = None, workdir: Path | None = None,
        day_limits: bool = True) -> dict:
    """day_limits=False schaltet die Tagesverlust-Limits (3 %/5 %) ab – nur um den reinen
    Handelscode 1:1 mit dem Backtest zu vergleichen (der Backtest kennt diese Limits nicht)."""
    r = settings.load()["risk"]
    saved = dict(r)
    if not day_limits:
        r["daily_loss_block_pct"] = r["bad_day_pause_pct"] = 9.99
    try:
        return _run(days, end, workdir)
    finally:
        r.update(saved)


def _run(days, end, workdir) -> dict:
    cfg = load_config()
    prices = data.load_all(needed_tickers(cfg))
    cal = prices["SPY"].index
    end = pd.Timestamp(end) if end is not None else cal[-1]
    span = cal[cal <= end][-(days + 1):]
    wd = Path(workdir or tempfile.mkdtemp())
    broker = SimBroker(prices, cash=cfg["starting_cash"], date=span[0])
    bot = Bot(broker, lambda d: prices, state_path=wd / "state.json", alerts=False, cfg=cfg,
              pause_file=wd / "PAUSE", log_dir=wd)
    eq, runs, mornings = {}, [], []
    for i, d in enumerate(span):
        if i > 0:
            broker.open_session(d)
            mornings.append(bot.morning(d))
            broker.run_stops()
        eq[d] = broker.equity()
        if i < len(span) - 1:
            runs.append(bot.evening(d))
    fills = [o for o in broker.orders.values() if o["status"] == "filled"]
    return {"equity": pd.Series(eq), "runs": runs, "mornings": mornings, "fills": fills,
            "positions": broker.positions(), "state": json.loads((wd / "state.json").read_text())}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    a = ap.parse_args()
    r = run(a.days)
    e = r["equity"]
    print(f"{len(e)-1} Tage: ${e.iloc[0]:,.0f} → ${e.iloc[-1]:,.0f} ({e.iloc[-1]/e.iloc[0]-1:+.2%}), "
          f"{len(r['fills'])} Fills, Positionen jetzt {r['positions']}")
    for f in r["fills"]:
        print(f"  {pd.Timestamp(f['filled_on']).date()} {f['side']:4s} {f['qty']:5d} {f['symbol']:4s} "
              f"@ {f['filled_avg_price']:.2f} ({f['type']}, {f['cid']})")
