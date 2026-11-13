"""Phase P / Schritt 2 – den Core finden (Prompt 3).

  1. Engine  = Engine-Kandidat mit dem grössten Trend-Gap (Training).
  2. Safe    = sicherer Kandidat mit der besten Rendite an den Downtrend-Tagen
               der Engine, Korrelation zur Engine < 0.5. Schlägt keiner Cash -> Cash.
  3. Schalter: Engine über SMA200 -> Engine, sonst Safe.
  4. Nachbarn (SMA100/150/250, EMA200, SMA50>SMA200) müssen im Training nach
     Kosten Geld verdienen.
  5. Lock-Test: genau EIN Lauf, muss Geld verdienen. Zusätzlich 2x Kosten.
Besteht alles, wird der Core nach rules/core.json geschrieben.
"""
from __future__ import annotations

import html
import json

import numpy as np
import pandas as pd

from . import backtest as bt
from . import data, settings, signals
from .indicators import trend_up


def calendar() -> pd.DatetimeIndex:
    return data.load_research("SPY").index


def core_weights(engine: str, safe: str, prices: dict, kind="sma", n=200) -> pd.DataFrame:
    idx = calendar()
    on = signals.trend_switch(prices[engine]["close"], kind, n).reindex(idx)
    w = pd.DataFrame(0.0, index=idx, columns=sorted({engine, safe}))
    w.loc[on == True, engine] = 1.0
    w.loc[on == False, safe] = 1.0
    w.loc[on.isna(), :] = np.nan        # Anlaufphase: noch keine Position
    return w


def core_returns(engine, safe, prices, kind="sma", n=200, cost_mult=1.0) -> pd.Series:
    w = core_weights(engine, safe, prices, kind, n)
    costs = {t: settings.cost_per_side(t) * cost_mult for t in w.columns}
    return bt.simulate_weights(prices, w, costs)


def switches(w: pd.DataFrame, win: str) -> int:
    x = w.dropna().idxmax(axis=1)
    x = x[(x.index >= pd.Timestamp(settings.window(win)[0])) & (x.index <= pd.Timestamp(settings.window(win)[1]))]
    return int((x != x.shift()).sum() - 1)


def pick_engine(prices) -> tuple[str, dict]:
    s = settings.load()
    tr_s, tr_e = (pd.Timestamp(x) for x in settings.window("train"))
    gaps = {}
    for t in s["universe"]["engine_candidates"]:
        c = prices[t]["close"]
        up = trend_up(c, s["regime"]["trend_ma_days"])
        rn = c.pct_change().shift(-1)
        m = (c.index >= tr_s) & (c.index <= tr_e) & rn.notna()
        gaps[t] = {"up": rn[m & (up == True)].mean() * 252, "down": rn[m & (up == False)].mean() * 252}
        gaps[t]["gap"] = gaps[t]["up"] - gaps[t]["down"]
    return max(gaps, key=lambda k: gaps[k]["gap"]), gaps


def pick_safe(engine, prices) -> tuple[str, dict]:
    s = settings.load()
    tr_s, tr_e = (pd.Timestamp(x) for x in settings.window("train"))
    ec = prices[engine]["close"]
    dn = (trend_up(ec, s["regime"]["trend_ma_days"]) == False)
    er = ec.pct_change()
    res = {}
    for t in s["universe"]["safe_candidates"]:
        c = prices[t]["close"]
        rn = c.pct_change().shift(-1).reindex(ec.index)
        m = (ec.index >= tr_s) & (ec.index <= tr_e) & rn.notna()
        tr = (er.index >= tr_s) & (er.index <= tr_e)
        res[t] = {"down_days_ann": rn[m & dn].mean() * 252,
                  "corr_engine": c.pct_change().reindex(ec.index)[tr].corr(er[tr])}
    cash = s["universe"]["cash_proxy"]
    ok = {t: v for t, v in res.items() if v["corr_engine"] < 0.5}
    best = max(ok, key=lambda k: ok[k]["down_days_ann"])
    if res[best]["down_days_ann"] <= res[cash]["down_days_ann"]:
        best = cash
    return best, res


def run() -> dict:
    s = settings.load()
    prices = data.load_all()
    engine, gaps = pick_engine(prices)
    safe, safes = pick_safe(engine, prices)

    base = core_returns(engine, safe, prices)
    train = bt.metrics(bt.window_slice(base, "train"))
    bh = bt.metrics(bt.window_slice(prices[engine]["close"].reindex(calendar()).pct_change(), "train"))
    spy_bh = prices["SPY"]["close"].reindex(calendar()).pct_change()

    neigh = {}
    for kind, n in signals.CORE_NEIGHBORS:
        m = bt.metrics(bt.window_slice(core_returns(engine, safe, prices, kind, n), "train"))
        neigh[f"{kind}{n}" if kind != "cross" else "sma50>sma200"] = m
    gates = {
        "train_profitable": train["cagr"] > 0,
        "neighbors_profitable": all(v["cagr"] > 0 for v in neigh.values()),
    }
    idea = f"core:{engine}->{safe}:sma200"
    lock = None
    if all(gates.values()):
        lock = bt.lock_once(idea, lambda: bt.metrics(bt.window_slice(base, "lock")))
        gates["lock_profitable"] = lock["cagr"] is not None and lock["cagr"] > 0
    stress = bt.metrics(bt.window_slice(core_returns(engine, safe, prices, cost_mult=s["costs"]["stress_multiplier"]), "lock"))
    lock_spy = bt.metrics(bt.window_slice(spy_bh, "lock"))
    lock_eng = bt.metrics(bt.window_slice(prices[engine]["close"].reindex(calendar()).pct_change(), "lock"))
    passed = all(gates.values())

    w = core_weights(engine, safe, prices)
    out = dict(engine=engine, safe=safe, rule="sma", n=200, gaps=gaps, safes=safes, train=train,
               engine_bh_train=bh, neighbors=neigh, lock=lock, lock_2x_cost=stress, lock_spy=lock_spy,
               lock_engine_bh=lock_eng, gates=gates, passed=passed,
               switches_train=switches(w, "train"), switches_lock=switches(w, "lock"))
    (settings.DIRS["results"] / "core.json").write_text(json.dumps(out, indent=2, default=float))
    if passed:
        (settings.DIRS["rules"] / "core.json").write_text(json.dumps(
            {"engine": engine, "safe": safe, "kind": "sma", "n": 200, "weight": 1.0}, indent=2))
    write_panel(out, base, w, prices)
    return out


def _f(x, pct=True, d=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x*100:.{d}f} %" if pct else f"{x:.2f}"


def equity_svg(series: dict[str, pd.Series], shade: pd.Series | None = None, w=1000, h=260) -> str:
    """Einfaches Linien-Chart (Equity normiert auf 1). shade: True-Bereiche grau hinterlegt."""
    allv = pd.concat(series.values(), axis=1)
    lo, hi = float(np.nanmin(allv.values)), float(np.nanmax(allv.values))
    idx = allv.index
    X = lambda i: 40 + i / max(len(idx) - 1, 1) * (w - 50)
    Y = lambda v: 10 + (hi - v) / (hi - lo or 1) * (h - 30)
    out = [f'<svg viewBox="0 0 {w} {h}">']
    if shade is not None:
        sh = shade.reindex(idx).fillna(False).to_numpy()
        start = None
        for i, v in enumerate(list(sh) + [False]):
            if v and start is None:
                start = i
            if not v and start is not None:
                out.append(f'<rect x="{X(start):.1f}" y="10" width="{X(i-1)-X(start)+1:.1f}" '
                           f'height="{h-30}" fill="var(--warn)" opacity=".15"/>')
                start = None
    for v in np.linspace(lo, hi, 4):
        out.append(f'<text x="0" y="{Y(v)+4:.0f}" font-size="10" fill="currentColor" opacity=".6">{v:.2f}</text>')
        out.append(f'<line x1="40" x2="{w-10}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="currentColor" opacity=".1"/>')
    for k in range(0, len(idx), max(len(idx) // 6, 1)):
        out.append(f'<text x="{X(k):.0f}" y="{h-4}" font-size="10" fill="currentColor" opacity=".6">'
                   f'{idx[k]:%Y-%m}</text>')
    palette = ["var(--accent)", "currentColor", "var(--good)", "var(--bad)"]
    legend = []
    for n, (name, s) in enumerate(series.items()):
        pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(s.reindex(idx).to_numpy()) if np.isfinite(v))
        dash = ' stroke-dasharray="4 3" opacity=".6"' if n == 1 else ""
        out.append(f'<polyline points="{pts}" fill="none" stroke="{palette[n % 4]}" stroke-width="1.6"{dash}/>')
        legend.append(f'<tspan fill="{palette[n % 4]}">■ {html.escape(name)}</tspan>  ')
    out.append(f'<text x="50" y="22" font-size="11">{"".join(legend)}</text></svg>')
    return "".join(out)


def write_panel(o, base, w, prices):
    eng, safe = o["engine"], o["safe"]
    lock_r = bt.window_slice(base, "lock")
    eq = bt.equity(lock_r)
    eng_eq = bt.equity(bt.window_slice(prices[eng]["close"].reindex(calendar()).pct_change(), "lock"))
    in_safe = (w[safe] == 1.0) if safe in w else None
    safe_rows = "".join(f"<tr><td>{t}</td><td>{_f(v['down_days_ann'])}</td><td>{v['corr_engine']:.2f}</td>"
                        f"<td>{'✅' if t == safe else ''}</td></tr>" for t, v in o["safes"].items())
    gap_rows = "".join(f"<tr><td>{t}</td><td>{_f(v['up'])}</td><td>{_f(v['down'])}</td><td><b>{_f(v['gap'])}</b></td>"
                       f"<td>{'✅' if t == eng else ''}</td></tr>" for t, v in o["gaps"].items())
    nrows = "".join(f"<tr><td>{k}</td><td>{_f(v['cagr'])}</td><td>{_f(v['maxdd'])}</td><td>{_f(v['ret_dd'],False)}</td>"
                    f"<td>{'✅' if v['cagr'] > 0 else '❌'}</td></tr>" for k, v in o["neighbors"].items())
    t, L = o["train"], o["lock"] or {}
    status = '<b class="good">BESTANDEN</b>' if o["passed"] else '<b class="bad">DURCHGEFALLEN</b>'
    html_out = f"""<section><h2>Phase P · Core: {eng} ↔ {safe} {status}</h2>
<p class="sub">Regel: {eng} über seinem 200-Tage-Schnitt → {eng} halten, sonst {safe}. Wechsel im Training: {o['switches_train']}, im Lock: {o['switches_lock']}.</p>
<table><tr><th></th><th>CAGR</th><th>Max-DD</th><th>Rendite/DD</th></tr>
<tr><td>Core Training 2022–24</td><td>{_f(t['cagr'])}</td><td>{_f(t['maxdd'])}</td><td>{_f(t['ret_dd'],False)}</td></tr>
<tr><td>{eng} Buy&amp;Hold Training</td><td>{_f(o['engine_bh_train']['cagr'])}</td><td>{_f(o['engine_bh_train']['maxdd'])}</td><td>{_f(o['engine_bh_train']['ret_dd'],False)}</td></tr>
<tr><td><b>Core Lock-Test 2025–heute (1 Lauf)</b></td><td><b>{_f(L.get('cagr'))}</b></td><td>{_f(L.get('maxdd'))}</td><td>{_f(L.get('ret_dd'),False)}</td></tr>
<tr><td>Core Lock mit 2× Kosten</td><td>{_f(o['lock_2x_cost']['cagr'])}</td><td>{_f(o['lock_2x_cost']['maxdd'])}</td><td>{_f(o['lock_2x_cost']['ret_dd'],False)}</td></tr>
<tr><td>{eng} Buy&amp;Hold Lock</td><td>{_f(o['lock_engine_bh']['cagr'])}</td><td>{_f(o['lock_engine_bh']['maxdd'])}</td><td>{_f(o['lock_engine_bh']['ret_dd'],False)}</td></tr>
<tr><td>SPY Buy&amp;Hold Lock</td><td>{_f(o['lock_spy']['cagr'])}</td><td>{_f(o['lock_spy']['maxdd'])}</td><td>{_f(o['lock_spy']['ret_dd'],False)}</td></tr></table>
<h3>Lock-Test-Verlauf (orange = hält {safe})</h3>{equity_svg({'Core': eq, eng + ' Buy&Hold': eng_eq}, in_safe)}
<h3>1 · Engine (Trend-Gap, Training)</h3><table><tr><th>Ticker</th><th>Uptrend-Tage/J</th><th>Downtrend-Tage/J</th><th>Gap</th><th></th></tr>{gap_rows}</table>
<h3>2 · Sicheres Asset (an {eng}-Downtrend-Tagen)</h3><table><tr><th>Ticker</th><th>Rendite/J</th><th>Korr. {eng}</th><th></th></tr>{safe_rows}</table>
<h3>4 · Nachbarn (Training, nach Kosten)</h3><table><tr><th>Variante</th><th>CAGR</th><th>Max-DD</th><th>Rendite/DD</th><th></th></tr>{nrows}</table>
</section>"""
    (settings.DIRS["dashboard"] / "panels" / "30_core.html").write_text(html_out)


if __name__ == "__main__":
    o = run()
    print(f"Engine={o['engine']} Safe={o['safe']} passed={o['passed']} gates={o['gates']}")
    for k in ("train", "lock", "lock_2x_cost", "lock_engine_bh", "lock_spy"):
        v = o[k] or {}
        print(f"  {k:15s} CAGR={v.get('cagr', float('nan')):.3f} DD={v.get('maxdd', float('nan')):.3f}")
    for k, v in o["neighbors"].items():
        print(f"  neighbor {k:14s} CAGR={v['cagr']:.3f}")
