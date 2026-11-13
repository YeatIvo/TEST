"""Phase P / Schritt 4 – das ganze Konto (Prompt 5): Core + bis zu 3 Sleeves.

  * Core 100 % investiert, Sleeves je 20 % OBENDRAUF (auf Margin, Zins 6.5 %/J).
  * Auswahl (nur Training): Start mit Core allein, füge jeweils den Sleeve hinzu,
    der Rendite/Drawdown am meisten verbessert. Max. 1 Sleeve pro Ticker, kein
    Sleeve mit Korrelation > 0.6 zu einem schon gewählten. Stopp, wenn keiner hilft.
  * Grössen-Check (Training): Sleeves an volatilen Tagen halb so gross (10 %)?
  * Finales Konto: genau EIN Lock-Lauf (Kontrolle – Sleeves haben den Lock schon bestanden).
Ergebnis -> rules/config.json (die Datei, die der Bot handelt).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import backtest as bt
from . import data, settings, signals
from .core import calendar, core_returns, core_weights, equity_svg
from .indicators import vol_high
from .sleeves import sleeve_result

MAX_CORR = 0.6


def sleeve_stream(item: dict, prices: dict, vol_sizing: bool, allowed=None) -> tuple[pd.Series, pd.Series]:
    """-> (gewichteter Beitrag zur Kontorendite, Gewicht am Schluss jedes Tages)."""
    s = settings.load()
    base = s["portfolio"]["sleeve_weight"]
    t = item["ticker"]
    res = sleeve_result(t, signals.rule_from_dict(item["rule"]), prices, allowed=allowed)
    idx = calendar()
    w = pd.Series(0.0, index=idx)
    vh = vol_high(prices[t]["close"], s["regime"]["vol_window_days"], s["regime"]["vol_lookback_days"]).reindex(idx)
    for _, tr in res.trades.iterrows():
        sig_day = idx[idx.get_loc(tr["entry_date"]) - 1]
        size = base / 2 if (vol_sizing and vh.get(sig_day) == True) else base
        w.loc[tr["entry_date"]:tr["exit_date"]] = size
    # offener Trade am Ende
    open_days = res.in_trade & (w == 0)
    if open_days.any():
        first = open_days[open_days].index[0]
        sig_day = idx[idx.get_loc(first) - 1]
        size = base / 2 if (vol_sizing and vh.get(sig_day) == True) else base
        w.loc[first:] = np.where(res.in_trade.loc[first:] | (res.daily.loc[first:] != 0), size, 0)
    contrib = (w * res.daily.reindex(idx).fillna(0))
    held_w = w.where(res.in_trade.reindex(idx).fillna(False), 0.0)
    return contrib, held_w


def account_returns(core_r: pd.Series, sleeves: list[dict], prices: dict, vol_sizing: bool,
                    allowed: dict | None = None) -> tuple[pd.Series, pd.Series]:
    s = settings.load()
    r = core_r.copy()
    borrowed = pd.Series(0.0, index=core_r.index)
    for it in sleeves:
        c, hw = sleeve_stream(it, prices, vol_sizing, (allowed or {}).get(it["id"]))
        r = r + c
        borrowed = borrowed + hw
    interest = borrowed.shift(1).fillna(0) * s["portfolio"]["margin_rate_year"] / 252
    return r - interest, borrowed


def run() -> dict:
    s = settings.load()
    prices = data.load_all()
    core = json.loads((settings.DIRS["rules"] / "core.json").read_text())
    bench = json.loads((settings.DIRS["rules"] / "bench.json").read_text())
    core_r = core_returns(core["engine"], core["safe"], prices)
    tr = lambda x: bt.metrics(bt.window_slice(x, "train"))

    streams = {b["id"]: sleeve_stream(b, prices, False)[0] for b in bench}
    picked, steps = [], [{"step": "Core allein", **tr(core_r)}]
    best_score = steps[0]["ret_dd"]
    while len(picked) < s["portfolio"]["max_sleeves"]:
        cands = []
        for b in bench:
            if b in picked or any(p["ticker"] == b["ticker"] for p in picked):
                continue
            corr = max((bt.window_slice(streams[b["id"]], "train").corr(
                bt.window_slice(streams[p["id"]], "train")) for p in picked), default=0)
            if corr > MAX_CORR:
                continue
            m = tr(account_returns(core_r, picked + [b], prices, False)[0])
            cands.append((m["ret_dd"], b, m))
        if not cands:
            break
        score, b, m = max(cands, key=lambda x: x[0])
        if score <= best_score:
            break
        picked.append(b)
        best_score = score
        steps.append({"step": f"+ {b['ticker']} {b['kind']}", **m})

    full_r, _ = account_returns(core_r, picked, prices, False)
    half_r, _ = account_returns(core_r, picked, prices, True)
    size_cmp = {"full": tr(full_r), "half_on_volatile": tr(half_r)}
    vol_sizing = size_cmp["half_on_volatile"]["ret_dd"] > size_cmp["full"]["ret_dd"]
    acc_r, borrowed = account_returns(core_r, picked, prices, vol_sizing)

    ids = "+".join(p["id"] for p in picked) or "none"
    lock = bt.lock_once(f"account:{core['engine']}->{core['safe']}|{ids}|vol={vol_sizing}",
                        lambda: bt.metrics(bt.window_slice(acc_r, "lock")))
    spy = prices["SPY"]["close"].reindex(calendar()).pct_change()
    lock_core = bt.metrics(bt.window_slice(core_r, "lock"))
    lock_spy = bt.metrics(bt.window_slice(spy, "lock"))
    full_period = (pd.Timestamp(settings.window("train")[0]), pd.Timestamp(settings.window("lock")[1]))
    all_m = bt.metrics(bt.window_slice(acc_r, full_period))
    spy_all = bt.metrics(bt.window_slice(spy, full_period))
    yearly = bt.window_slice(acc_r, full_period).groupby(lambda d: d.year).apply(lambda x: (1 + x).prod() - 1)
    spy_yearly = bt.window_slice(spy, full_period).groupby(lambda d: d.year).apply(lambda x: (1 + x).prod() - 1)

    cmat = pd.DataFrame({"Core": bt.window_slice(core_r, "train"),
                         **{f"{p['ticker']} {p['kind']}": bt.window_slice(streams[p["id"]], "train") for p in picked}}).corr()

    config = {
        "starting_cash": s["portfolio"]["starting_cash"],
        "core": core,
        "sleeves": [{"id": p["id"], "ticker": p["ticker"], "kind": p["kind"], "rule": p["rule"],
                     "weight": s["portfolio"]["sleeve_weight"], "enabled": True} for p in picked],
        "vol_sizing_half": bool(vol_sizing),
        "margin": {"allowed": True, "max_gross": s["portfolio"]["max_gross"]},
    }
    (settings.DIRS["rules"] / "config.json").write_text(json.dumps(config, indent=2))
    out = {"steps": steps, "size_cmp": size_cmp, "vol_sizing": bool(vol_sizing), "lock": lock,
           "lock_core": lock_core, "lock_spy": lock_spy, "all": all_m, "spy_all": spy_all,
           "yearly": yearly.to_dict(), "spy_yearly": spy_yearly.to_dict(),
           "max_borrowed": float(borrowed.max()), "avg_borrowed": float(bt.window_slice(borrowed, full_period).mean()),
           "corr": cmat.round(2).to_dict()}
    (settings.DIRS["results"] / "account.json").write_text(json.dumps(out, indent=2, default=float))
    acc_eq = bt.equity(bt.window_slice(acc_r, full_period), s["portfolio"]["starting_cash"])
    acc_eq.to_csv(settings.DIRS["results"] / "account_equity.csv", header=["equity"])
    write_panel(out, config, acc_r, core_r, spy, borrowed, full_period, cmat)
    return out


def _f(x, pct=True, d=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x*100:.{d}f} %" if pct else f"{x:.2f}"


def write_panel(o, cfg, acc_r, core_r, spy, borrowed, period, cmat):
    sc = cfg["starting_cash"]
    eq = lambda r: bt.equity(bt.window_slice(r, period), sc)
    chart_all = equity_svg({"Konto (Core+Sleeves)": eq(acc_r) / sc, "SPY Buy&Hold": eq(spy) / sc,
                            "Core allein": eq(core_r) / sc})
    lk = lambda r: bt.equity(bt.window_slice(r, "lock"))
    chart_lock = equity_svg({"Konto": lk(acc_r), "SPY": lk(spy), "Core allein": lk(core_r)})
    steps = "".join(f"<tr><td>{st['step']}</td><td>{_f(st['cagr'])}</td><td>{_f(st['maxdd'])}</td>"
                    f"<td><b>{_f(st['ret_dd'],False)}</b></td></tr>" for st in o["steps"])
    sl = "".join(f"<tr><td>{x['ticker']}</td><td>{'Dip-Buy' if x['kind']=='dip' else 'Breakout'}</td>"
                 f"<td>{x['weight']*100:.0f} %</td></tr>" for x in cfg["sleeves"])
    yrs = "".join(f"<tr><td>{y}</td><td>{_f(v)}</td><td>{_f(o['spy_yearly'][y])}</td></tr>" for y, v in o["yearly"].items())
    cm = "".join(f"<tr><th>{a}</th>" + "".join(f"<td>{cmat.loc[a,b]:.2f}</td>" for b in cmat.columns) + "</tr>"
                 for a in cmat.index)
    L, A = o["lock"], o["all"]
    final = sc * (1 + bt.window_slice(acc_r, period)).prod()
    html_out = f"""<section><h2>Gesamtsystem · Core {cfg['core']['engine']}↔{cfg['core']['safe']} + {len(cfg['sleeves'])} Sleeves</h2>
<p class="sub">Das Konto, das der Bot handelt (rules/config.json). Start ${sc:,.0f} am {period[0]:%d.%m.%Y} → <b>${final:,.0f}</b> heute.</p>
<table><tr><th></th><th>CAGR</th><th>Max-DD</th><th>Rendite/DD</th></tr>
<tr><td><b>Konto Lock-Test 2025–heute</b></td><td><b>{_f(L['cagr'])}</b></td><td>{_f(L['maxdd'])}</td><td>{_f(L['ret_dd'],False)}</td></tr>
<tr><td>Core allein Lock</td><td>{_f(o['lock_core']['cagr'])}</td><td>{_f(o['lock_core']['maxdd'])}</td><td>{_f(o['lock_core']['ret_dd'],False)}</td></tr>
<tr><td>SPY Buy&amp;Hold Lock</td><td>{_f(o['lock_spy']['cagr'])}</td><td>{_f(o['lock_spy']['maxdd'])}</td><td>{_f(o['lock_spy']['ret_dd'],False)}</td></tr>
<tr><td>Konto 2022–heute</td><td>{_f(A['cagr'])}</td><td>{_f(A['maxdd'])}</td><td>{_f(A['ret_dd'],False)}</td></tr>
<tr><td>SPY 2022–heute</td><td>{_f(o['spy_all']['cagr'])}</td><td>{_f(o['spy_all']['maxdd'])}</td><td>{_f(o['spy_all']['ret_dd'],False)}</td></tr></table>
{chart_all}</section>
<section><h2>Phase P · Konto zusammenbauen</h2>
<h3>Auswahl-Schritte (Training)</h3><table><tr><th>Schritt</th><th>CAGR</th><th>Max-DD</th><th>Rendite/DD</th></tr>{steps}</table>
<h3>Gewählte Sleeves</h3><table><tr><th>Ticker</th><th>Typ</th><th>Slot</th></tr>{sl}</table>
<p>Grössen-Check (Training): voll Rendite/DD {_f(o['size_cmp']['full']['ret_dd'],False)} vs. halb an volatilen Tagen {_f(o['size_cmp']['half_on_volatile']['ret_dd'],False)} → <b>{'halbe Grösse an volatilen Tagen' if o['vol_sizing'] else 'immer volle Grösse'}</b>.</p>
<p>Margin: max. geliehen {o['max_borrowed']*100:.0f} % des Kontos, im Schnitt {o['avg_borrowed']*100:.1f} %.</p>
<h3>Lock-Test-Verlauf</h3>{chart_lock}
<h3>Jahre</h3><table><tr><th>Jahr</th><th>Konto</th><th>SPY</th></tr>{yrs}</table>
<h3>Korrelation der Bausteine (Training)</h3><table style="width:auto"><tr><th></th>{''.join(f'<th>{c}</th>' for c in cmat.columns)}</tr>{cm}</table>
</section>"""
    (settings.DIRS["dashboard"] / "panels" / "05_account.html").write_text(html_out)


if __name__ == "__main__":
    o = run()
    for st in o["steps"]:
        print(f"  {st['step']:24s} CAGR={st['cagr']:.3f} DD={st['maxdd']:.3f} R/DD={st['ret_dd']:.2f}")
    print("vol_sizing:", o["vol_sizing"], o["size_cmp"]["full"]["ret_dd"], o["size_cmp"]["half_on_volatile"]["ret_dd"])
    print("LOCK  acct", {k: round(v, 3) for k, v in o["lock"].items()})
    print("LOCK  core", round(o["lock_core"]["cagr"], 3), round(o["lock_core"]["maxdd"], 3))
    print("LOCK  spy ", round(o["lock_spy"]["cagr"], 3), round(o["lock_spy"]["maxdd"], 3))
    print("ALL   acct", round(o["all"]["cagr"], 3), round(o["all"]["maxdd"], 3), "spy", round(o["spy_all"]["cagr"], 3))
    print("yearly", {k: round(v, 3) for k, v in o["yearly"].items()}, "max borrowed", o["max_borrowed"])
