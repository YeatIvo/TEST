"""Phase P / Schritt 5 – die Auswahl-METHODE testen (Prompt 6).

pick_sleeves(asof) benutzt nur Daten bis `asof`:
  Pick-Fenster  = 3 bis 1 Jahr vor asof   (Labels + Gates)
  Check-Fenster = letztes Jahr vor asof    (muss Geld verdienen, Ranking nach Rendite/DD)
  Gates im Pick-Fenster: nach Kosten > 0, Trades Dip >= 10 / Breakout >= 4,
  Profit-Faktor >= 1.3, Nachbarn > 0. Max. 3 Sleeves, 1 pro Ticker, Korrelation <= 0.6.
  Leere Slots bleiben leer (nie mit einem durchgefallenen Sleeve auffüllen).

Test: (1) Look-Ahead-Probe, (2) 11 Quartalsenden 2024Q1–letztes Quartal,
(3) Backtest der Routine vs. Core allein vs. fixe Sleeves aus Prompt 5.
"""
from __future__ import annotations

import html
import json

import numpy as np
import pandas as pd

from . import backtest as bt
from . import data, settings, signals, study
from .account import account_returns
from .core import calendar, core_returns, equity_svg
from .indicators import trend_up

MIN_TRADES = {"dip": 10, "breakout": 4}
MIN_PF = 1.3
MAX_CORR = 0.6


def _trunc(prices: dict, asof: pd.Timestamp) -> dict:
    return {t: d[d.index <= asof] for t, d in prices.items()}


def pick_sleeves(asof: pd.Timestamp, prices: dict) -> list[dict]:
    s = settings.load()
    p = _trunc(prices, asof)
    pick = (asof - pd.DateOffset(years=3), asof - pd.DateOffset(years=1))
    check = (asof - pd.DateOffset(years=1) + pd.Timedelta(days=1), asof)
    spy = p["SPY"]["close"]
    spy_ret, spy_up = spy.pct_change(), trend_up(spy, s["regime"]["trend_ma_days"])
    cal = p["SPY"].index
    cands = []
    for t in settings.tradable_tickers():
        df = p[t].reindex(cal).dropna()
        labels = study.study_ticker(t, df, spy_ret, spy_up, win=pick)["labels"]
        for kind, rule in signals.BASE_SLEEVES.items():
            if signals.FITS[kind] not in labels:
                continue
            sim = lambda r: bt.simulate_trades(df, r.entry(df), r.exit(df), settings.cost_per_side(t),
                                               r.stop_pct(s), r.max_hold)
            res = sim(rule)
            m = bt.metrics(bt.window_slice(res.daily, pick), bt.trades_in(res.trades, pick))
            if not (m["total"] > 0 and m["trades"] >= MIN_TRADES[kind] and m["profit_factor"] >= MIN_PF):
                continue
            if not all(bt.window_slice(sim(n).daily, pick).add(1).prod() > 1 for n in rule.neighbors()):
                continue
            cm = bt.metrics(bt.window_slice(res.daily, check))
            if not cm["total"] > 0:
                continue
            cands.append({"ticker": t, "kind": kind, "rule": signals.rule_to_dict(rule),
                          "id": f"sleeve:{t}:{rule.name}", "score": cm["ret_dd"] if np.isfinite(cm["ret_dd"]) else -1,
                          "_stream": bt.window_slice(res.daily, check)})
    cands.sort(key=lambda c: -c["score"])
    chosen = []
    for c in cands:
        if len(chosen) >= s["portfolio"]["max_sleeves"]:
            break
        if any(x["ticker"] == c["ticker"] for x in chosen):
            continue
        if any(c["_stream"].corr(x["_stream"]) > MAX_CORR for x in chosen):
            continue
        chosen.append(c)
    return [{k: v for k, v in c.items() if k != "_stream"} for c in chosen]


def quarter_ends(cal: pd.DatetimeIndex, start="2024-01-01") -> list[pd.Timestamp]:
    c = cal[cal >= pd.Timestamp(start)]
    q = pd.Series(c, index=c).groupby(c.to_period("Q")).max()
    last_complete = q[q.index < pd.Timestamp(cal[-1]).to_period("Q")]
    return list(last_complete.values.astype("datetime64[ns]").astype(object))


def run() -> dict:
    prices = data.load_all()
    cal = calendar()
    qs = [pd.Timestamp(x) for x in quarter_ends(cal)]

    # 1) Look-Ahead-Probe: mittleres Quartal mit vollen vs. abgeschnittenen Daten
    probe = qs[len(qs) // 2]
    a = [x["id"] for x in pick_sleeves(probe, prices)]
    b = [x["id"] for x in pick_sleeves(probe, _trunc(prices, probe))]
    probe_ok = a == b

    # 2) Routine an jedem Quartalsende
    lineups = {q: pick_sleeves(q, prices) for q in qs}

    # 3) Backtest: Lineup gilt ab nächstem Open bis zum nächsten Quartalsende
    allowed, items = {}, {}
    bounds = qs + [cal[-1]]
    for i, q in enumerate(qs):
        days = (cal > q) & (cal <= bounds[i + 1])
        for it in lineups[q]:
            items[it["id"]] = it
            m = allowed.setdefault(it["id"], pd.Series(False, index=cal))
            m[days] = True
    cfg = json.loads((settings.DIRS["rules"] / "config.json").read_text())
    core = cfg["core"]
    core_r = core_returns(core["engine"], core["safe"], prices)
    routine_r, _ = account_returns(core_r, list(items.values()), prices, cfg["vol_sizing_half"], allowed)
    fixed_r, _ = account_returns(core_r, cfg["sleeves"], prices, cfg["vol_sizing_half"])
    start = cal[cal > qs[0]][0]
    per = (start, cal[-1])
    lock_per = (pd.Timestamp(settings.window("lock")[0]), cal[-1])
    res = {name: {"since_2024q2": bt.metrics(bt.window_slice(r, per)),
                  "since_2025": bt.metrics(bt.window_slice(r, lock_per))}
           for name, r in [("routine", routine_r), ("core", core_r), ("fixed_p5", fixed_r)]}
    latest = lineups[qs[-1]]
    out = {"probe_date": str(probe.date()), "probe_ok": probe_ok,
           "lineups": {str(q.date()): [f"{x['ticker']} {x['kind']}" for x in v] for q, v in lineups.items()},
           "results": res, "latest_pick": [f"{x['ticker']} {x['kind']}" for x in latest],
           "current_config": [f"{x['ticker']} {x['kind']}" for x in cfg["sleeves"]]}
    (settings.DIRS["results"] / "repick.json").write_text(json.dumps(out, indent=2, default=float))
    write_panel(out, routine_r, core_r, fixed_r, per)
    return out


def _f(x, pct=True):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else (f"{x*100:.1f} %" if pct else f"{x:.2f}")


def write_panel(o, routine_r, core_r, fixed_r, per):
    allsl = sorted({s for v in o["lineups"].values() for s in v})
    qs = list(o["lineups"])
    grid = "<table style='width:auto'><tr><th></th>" + "".join(f"<th style='font-size:.7rem'>{q[:7]}</th>" for q in qs) + "</tr>"
    for sl in allsl:
        grid += f"<tr><td>{sl}</td>" + "".join(
            f"<td style='text-align:center'>{'■' if sl in o['lineups'][q] else ''}</td>" for q in qs) + "</tr>"
    grid += "</table>"
    rows = "".join(
        f"<tr><td>{n}</td><td>{_f(v['since_2024q2']['cagr'])}</td><td>{_f(v['since_2024q2']['maxdd'])}</td>"
        f"<td>{_f(v['since_2025']['cagr'])}</td><td>{_f(v['since_2025']['maxdd'])}</td><td>{_f(v['since_2025']['ret_dd'],False)}</td></tr>"
        for n, v in [("Routine (Quartals-Re-Pick)", o["results"]["routine"]), ("Core allein", o["results"]["core"]),
                     ("Fixe Sleeves aus Prompt 5*", o["results"]["fixed_p5"])])
    chart = equity_svg({"Routine": bt.equity(bt.window_slice(routine_r, per)),
                        "Core allein": bt.equity(bt.window_slice(core_r, per)),
                        "Fixe Sleeves": bt.equity(bt.window_slice(fixed_r, per))})
    ok = '<b class="good">PASS</b>' if o["probe_ok"] else '<b class="bad">FAIL</b>'
    html_out = f"""<section><h2>Phase P · Re-Pick-Routine (Methode testen)</h2>
<p class="sub">Jedes Quartal wählt die Routine neu – nur mit Daten bis zu diesem Tag. Look-Ahead-Probe am {o['probe_date']}: {ok}</p>
{grid}<table><tr><th></th><th>CAGR seit 2024Q2</th><th>Max-DD</th><th>CAGR seit 2025</th><th>Max-DD</th><th>Rendite/DD</th></tr>{rows}</table>
<p class="sub">* Die fixen Sleeves wurden mit Daten bis Ende 2024 gewählt – fair vergleichbar ist nur der Teil ab 2025.</p>
{chart}<p>Neueste Auswahl (Quartal bis {qs[-1]}): <b>{html.escape(', '.join(o['latest_pick']) or 'keine')}</b> · aktuell im Konto: {html.escape(', '.join(o['current_config']))} · <i>nichts wurde geändert</i>.</p>
</section>"""
    (settings.DIRS["dashboard"] / "panels" / "50_repick.html").write_text(html_out)


if __name__ == "__main__":
    o = run()
    print("probe ok:", o["probe_ok"])
    for q, v in o["lineups"].items():
        print(" ", q, v)
    for n, v in o["results"].items():
        print(f"  {n:9s} since24Q2 CAGR={v['since_2024q2']['cagr']:.3f} DD={v['since_2024q2']['maxdd']:.3f} | "
              f"since25 CAGR={v['since_2025']['cagr']:.3f} DD={v['since_2025']['maxdd']:.3f}")
    print("latest:", o["latest_pick"], "config:", o["current_config"])
