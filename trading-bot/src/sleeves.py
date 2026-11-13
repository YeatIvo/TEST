"""Phase P / Schritt 3 – Sleeve-Funnel (Prompt 4).

Jede Idee = (Ticker, Sleeve-Typ). 22 handelbare Ticker x 2 Typen = 44 Ideen.
Gates (vor dem Lauf festgelegt), der Reihe nach:
  1. passt zum Asset   (Dip -> Label snaps_back, Breakout -> keeps_going)
  2. Training: verdient nach Kosten Geld
  3. genug Trades      (Dip >= 15, Breakout >= 6)
  4. Profit-Faktor >= 1.3
  5. alle Nachbarn verdienen im Training Geld
  6. Lock-Test (genau 1 Lauf) verdient Geld
Wer alles besteht, kommt auf die Bank (rules/bench.json).
"""
from __future__ import annotations

import html
import json

import numpy as np
import pandas as pd

from . import backtest as bt
from . import data, settings, signals
from .core import calendar

MIN_TRADES = {"dip": 15, "breakout": 6}
MIN_PF = 1.3


def sleeve_result(ticker: str, rule: signals.SleeveRule, prices: dict, allowed=None,
                  cost_mult: float = 1.0, df: pd.DataFrame | None = None) -> bt.TradeResult:
    s = settings.load()
    df = df if df is not None else prices[ticker].reindex(calendar()).dropna()
    return bt.simulate_trades(df, rule.entry(df), rule.exit(df),
                              cost=settings.cost_per_side(ticker) * cost_mult,
                              stop_pct=rule.stop_pct(s), max_hold=rule.max_hold, allowed=allowed)


def eval_window(res: bt.TradeResult, win) -> dict:
    return bt.metrics(bt.window_slice(res.daily, win), bt.trades_in(res.trades, win))


def run() -> dict:
    prices = data.load_all()
    labels = json.loads((settings.DIRS["rules"] / "labels.json").read_text())
    ideas = []
    for t in settings.tradable_tickers():
        for kind, rule in signals.BASE_SLEEVES.items():
            idea = {"ticker": t, "kind": kind, "rule": signals.rule_to_dict(rule),
                    "id": f"sleeve:{t}:{rule.name}", "gates": {}}
            g = idea["gates"]
            g["fits"] = signals.FITS[kind] in labels[t]
            if g["fits"]:
                res = sleeve_result(t, rule, prices)
                tm = eval_window(res, "train")
                idea["train"] = tm
                g["profit"] = tm["total"] > 0
                g["trades"] = g["profit"] and tm["trades"] >= MIN_TRADES[kind]
                g["pf"] = g["trades"] and tm["profit_factor"] >= MIN_PF
                if g["pf"]:
                    nb = {}
                    for n in rule.neighbors():
                        nb[n.name] = eval_window(sleeve_result(t, n, prices), "train")["total"]
                    idea["neighbors"] = nb
                    g["neighbors"] = all(v > 0 for v in nb.values())
                if g.get("neighbors"):
                    lk = bt.lock_once(idea["id"], lambda: eval_window(res, "lock"))
                    idea["lock"] = lk
                    g["lock"] = lk["total"] is not None and lk["total"] > 0
            idea["passed"] = all(g.get(k, False) for k in ("fits", "profit", "trades", "pf", "neighbors", "lock"))
            ideas.append(idea)

    order = ["fits", "profit", "trades", "pf", "neighbors", "lock"]
    funnel = {"ideas": len(ideas)}
    for k in order:
        funnel[k] = sum(all(i["gates"].get(x, False) for x in order[: order.index(k) + 1]) for i in ideas)
    bench = [{"ticker": i["ticker"], "kind": i["kind"], "rule": i["rule"], "id": i["id"],
              "train": i["train"], "lock": i["lock"]} for i in ideas if i["passed"]]
    (settings.DIRS["results"] / "sleeve_funnel.json").write_text(
        json.dumps({"funnel": funnel, "ideas": ideas}, indent=2, default=float))
    (settings.DIRS["rules"] / "bench.json").write_text(json.dumps(bench, indent=2, default=float))
    write_panel(funnel, ideas, prices)
    return {"funnel": funnel, "bench": bench}


def _f(x, d=1):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x*100:.{d}f} %"


def write_panel(funnel, ideas, prices):
    from .core import equity_svg
    names = {"ideas": "Ideen", "fits": "passt zum Asset", "profit": "Training nach Kosten > 0",
             "trades": "genug Trades", "pf": "Profit-Faktor ≥ 1.3", "neighbors": "Nachbarn profitabel",
             "lock": "Lock-Test profitabel"}
    mx = funnel["ideas"]
    bars = "".join(
        f'<div style="display:flex;align-items:center;gap:10px;margin:4px 0"><span style="width:190px">{names[k]}</span>'
        f'<span style="display:inline-block;height:16px;width:{v/mx*60:.1f}%;background:var(--accent);'
        f'border-radius:3px"></span><b>{v}</b></div>' for k, v in funnel.items())
    passed = [i for i in ideas if i["passed"]]
    rows = "".join(
        f"<tr><td><b>{i['ticker']}</b></td><td>{'Dip-Buy' if i['kind']=='dip' else 'Breakout'}</td>"
        f"<td>{i['train']['trades']}</td><td>{_f(i['train']['total'])}</td><td>{i['train']['profit_factor']:.2f}</td>"
        f"<td>{i['lock']['trades']}</td><td>{_f(i['lock']['total'])}</td><td>{_f(i['lock']['maxdd'])}</td></tr>"
        for i in passed)
    curves = {}
    for i in passed[:4]:
        res = sleeve_result(i["ticker"], signals.rule_from_dict(i["rule"]), prices)
        curves[f"{i['ticker']} {i['kind']}"] = bt.equity(bt.window_slice(res.daily, "lock"))
    chart = equity_svg(curves) if curves else ""
    fail_rows = "".join(
        f"<tr><td>{i['ticker']}</td><td>{i['kind']}</td><td>{next((k for k in ['fits','profit','trades','pf','neighbors','lock'] if not i['gates'].get(k)), '')}</td></tr>"
        for i in ideas if not i["passed"] and i["gates"].get("fits"))
    out = f"""<section><h2>Phase P · Sleeve-Funnel</h2>
<p class="sub">Jede Idee durchläuft dieselben Gates. Nur wer alle besteht, darf auf die Bank. Ein Slot = 20 % des Kontos; Renditen unten pro Slot.</p>
{bars}
<h3>Bestanden ({len(passed)})</h3>
<table><tr><th>Ticker</th><th>Typ</th><th>Trades Train</th><th>Rendite Train</th><th>PF Train</th><th>Trades Lock</th><th>Rendite Lock</th><th>Max-DD Lock</th></tr>{rows}</table>
<h3>Lock-Verlauf (Slot-Equity)</h3>{chart}
<details><summary>Durchgefallen (passend, aber an Gate gescheitert)</summary><table><tr><th>Ticker</th><th>Typ</th><th>gescheitert an</th></tr>{fail_rows}</table></details>
</section>"""
    (settings.DIRS["dashboard"] / "panels" / "40_sleeves.html").write_text(out)


if __name__ == "__main__":
    r = run()
    print("Funnel:", r["funnel"])
    for b in r["bench"]:
        print(f"  {b['ticker']:5s} {b['kind']:9s} train={b['train']['total']:.3f} PF={b['train']['profit_factor']:.2f} "
              f"n={b['train']['trades']}  lock={b['lock']['total']:.3f} n={b['lock']['trades']}")
