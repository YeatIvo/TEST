"""Phase Adapt (Prompt 11) – Paper gegen Backtest an denselben Tagen.

Jede Lücke bekommt genau eine Gruppe:
  fills    – Fill-Preis ≠ Open in den Daten
  timing   – Order einen Tag zu früh/spät gefüllt
  data     – Live-Daten ≠ Forschungsdaten (nachträglich korrigiert)
  rounding – ganze Aktien, Rest bleibt in Cash
  limits   – ein Risiko-Limit hat eine Order verhindert/geändert
  rules    – Bot tat etwas, das die Regeln nicht sagen (sollte nie vorkommen)

CLI:  python -m src.compare --sim [--days 120]   (Simulator, ohne Keys)
      python -m src.compare --alpaca              (echtes Paper-Konto, auf deinem Computer)
"""
from __future__ import annotations

import argparse
import html
import json

import numpy as np
import pandas as pd

from . import backtest as bt
from . import data, settings
from .account import account_returns
from .core import core_returns, equity_svg


def backtest_daily(cfg: dict, prices: dict) -> pd.Series:
    core = core_returns(cfg["core"]["engine"], cfg["core"]["safe"], prices)
    return account_returns(core, [s for s in cfg["sleeves"] if s.get("enabled", True)], prices,
                           cfg["vol_sizing_half"])[0]


def compare(paper_eq: pd.Series, fills: list[dict], runs: list[dict], prices: dict, cfg: dict,
            live_prices: dict | None = None) -> dict:
    cal = prices["SPY"].index
    bt_r = backtest_daily(cfg, prices).reindex(paper_eq.index)
    paper_r = paper_eq.pct_change()
    df = pd.DataFrame({"paper": paper_r, "backtest": bt_r}).iloc[2:]   # Start: erster Kauf erst am 2. Tag
    gaps = []
    for f in fills:
        d = pd.Timestamp(f["filled_on"])
        sym = f["symbol"]
        if f["type"] == "market":
            o = float(prices[sym].loc[d, "open"]) if d in prices[sym].index else np.nan
            diff = f["filled_avg_price"] / o - 1 if o == o else np.nan
            sgn = 1 if f["side"] == "buy" else -1
            if abs(diff) > 1e-6:
                gaps.append({"date": d.date(), "group": "fills", "ticker": sym,
                             "pct": diff, "usd": -sgn * f["qty"] * (f["filled_avg_price"] - o),
                             "line": f"{sym} {f['side']} gefüllt zu {f['filled_avg_price']:.2f} statt Open {o:.2f}"})
            placed = pd.Timestamp(f.get("placed", d))
            nxt = cal[cal > placed]
            if len(nxt) and nxt[0] != d:
                gaps.append({"date": d.date(), "group": "timing", "ticker": sym, "pct": 0, "usd": 0,
                             "line": f"{sym}: Order vom {placed.date()} erst am {d.date()} gefüllt"})
    for r in runs:
        if r.get("status") != "ok":
            continue
        for reason in r["risk"]["reasons"]:
            if "blockiert" in reason or "abgeschaltet" in reason:
                gaps.append({"date": pd.Timestamp(r["asof"]).date(), "group": "limits", "ticker": reason.split("-")[0],
                             "pct": 0, "usd": 0, "line": reason})
        for o in r["orders"]:
            if o.get("target_value") and o["side"] == "buy":
                left = o["target_value"] - o["qty"] * o["price"]
                if left > 0:
                    gaps.append({"date": pd.Timestamp(r["asof"]).date(), "group": "rounding", "ticker": o["symbol"],
                                 "pct": left / r["equity"], "usd": left,
                                 "line": f"{o['symbol']}: ${left:,.0f} bleiben wegen ganzer Aktien in Cash"})
    if live_prices:
        for t, lp in live_prices.items():
            j = pd.concat([lp["close"], prices[t]["close"]], axis=1, keys=["live", "res"]).dropna()
            bad = j[(j.live / j.res - 1).abs() > 0.001]
            for d, row in bad.iterrows():
                gaps.append({"date": d.date(), "group": "data", "ticker": t, "pct": row.live / row.res - 1, "usd": 0,
                             "line": f"{t} {d.date()}: Live-Schluss {row.live:.2f} ≠ Daten {row.res:.2f}"})
    explained_days = {g["date"] for g in gaps if g["group"] in ("limits", "fills", "timing", "data")}
    # Ein blockierter Einstieg erklärt die ganze Haltedauer des Backtest-Trades, den der Bot nicht hatte
    from . import signals
    from .sleeves import sleeve_result
    blocked = {(g["ticker"], g["date"]) for g in gaps if g["group"] == "limits"}
    for s in cfg["sleeves"]:
        days_blocked = sorted(d for t, d in blocked if t == s["ticker"])
        if not days_blocked:
            continue
        tr = sleeve_result(s["ticker"], signals.rule_from_dict(s["rule"]), prices).trades
        for d in days_blocked:
            nxt = cal[cal > pd.Timestamp(d)]
            hit = tr[tr["entry_date"] == nxt[0]] if len(nxt) else tr.iloc[0:0]
            for _, t in hit.iterrows():
                for day in cal[(cal >= t["entry_date"]) & (cal <= t["exit_date"])]:
                    explained_days.add(day.date())
                gaps.append({"date": t["entry_date"].date(), "group": "limits", "ticker": s["ticker"], "pct": t["ret"] * s["weight"],
                             "usd": 0, "line": f"Backtest-Trade {s['ticker']} {t['entry_date'].date()}–{t['exit_date'].date()} "
                                               f"({t['ret']:+.1%}) fehlt im Paper: Einstieg durch Limit blockiert"})
    for d, row in df.iterrows():
        if abs(row.paper - row.backtest) > 0.005 and d.date() not in explained_days:
            gaps.append({"date": d.date(), "group": "rules", "ticker": "", "pct": row.paper - row.backtest, "usd": 0,
                         "line": f"{d.date()}: Paper {row.paper:+.2%} vs. Backtest {row.backtest:+.2%} – unerklärt"})
    groups = pd.Series([g["group"] for g in gaps]).value_counts().to_dict() if gaps else {}
    return {"paper_total": float((1 + df.paper).prod() - 1), "backtest_total": float((1 + df.backtest).prod() - 1),
            "max_daily_gap": float((df.paper - df.backtest).abs().max()) if len(df) else 0.0,
            "days": len(df), "groups": groups, "gaps": gaps, "daily": df}


def verdict(c: dict) -> str:
    if c["groups"].get("rules"):
        return "⚠️ Unerklärte Lücken (rules) – Bot tut etwas, das die Regeln nicht sagen. Prüfen!"
    if c["days"] == 0:
        return "Noch keine Live-Tage – Vergleich ist eingerichtet und läuft, sobald gehandelt wird."
    return "✅ Paper macht, was der Backtest sagt; Lücken nur aus Fills/Rundung/Limits."


def write_report(c: dict, label: str):
    lines = [f"# Paper vs. Backtest ({label})", "",
             f"- Tage: {c['days']} · Paper {c['paper_total']:+.2%} · Backtest {c['backtest_total']:+.2%} · "
             f"grösste Tageslücke {c['max_daily_gap']:.2%}", f"- Gruppen: {c['groups'] or 'keine'}",
             f"- Fazit: {verdict(c)}", "", "| Datum | Gruppe | Ticker | % | $ | Erklärung |", "|---|---|---|---|---|---|"]
    lines += [f"| {g['date']} | {g['group']} | {g['ticker']} | {g['pct']:+.2%} | {g['usd']:,.0f} | {g['line']} |"
              for g in c["gaps"][:200]]
    (settings.DIRS["reports"] / "paper_vs_backtest.md").write_text("\n".join(lines) + "\n")
    d = c["daily"]
    chart = equity_svg({"Paper": (1 + d.paper).cumprod(), "Backtest": (1 + d.backtest).cumprod()}) if len(d) else ""
    grp = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in c["groups"].items()) or "<tr><td colspan=2>keine</td></tr>"
    ex = "".join(f"<li>{html.escape(str(g['date']))} · <b>{g['group']}</b> · {html.escape(g['line'])}</li>"
                 for g in c["gaps"][:8])
    (settings.DIRS["dashboard"] / "panels" / "70_compare.html").write_text(
        f"<section><h2>Adapt · Paper vs. Backtest ({html.escape(label)})</h2><p class='sub'>{html.escape(verdict(c))} "
        f"Paper {c['paper_total']:+.2%} · Backtest {c['backtest_total']:+.2%} über {c['days']} Tage.</p>{chart}"
        f"<table style='width:auto'><tr><th>Gruppe</th><th>Anzahl</th></tr>{grp}</table><ul>{ex}</ul></section>")


def from_sim(days: int) -> dict:
    from . import paper_sim
    from .bot import load_config
    cfg = load_config()
    r = paper_sim.run(days)
    return compare(r["equity"], r["fills"], r["runs"], data.load_all(), cfg)


def from_alpaca() -> dict:
    from .bot import load_config
    from .broker import AlpacaBroker
    b = AlpacaBroker()
    cfg = load_config()
    h = b.c.get_portfolio_history()
    eq = pd.Series(h.equity, index=pd.to_datetime(h.timestamp, unit="s").normalize()).replace(0, np.nan).dropna()
    runs = [json.loads(x) for x in (settings.DIRS["logs"] / "runs.jsonl").read_text().splitlines()] \
        if (settings.DIRS["logs"] / "runs.jsonl").exists() else []
    runs = [r for r in runs if not r.get("dry")]
    fills = []
    p = settings.DIRS["logs"] / "orders.jsonl"
    for ln in (p.read_text().splitlines() if p.exists() else []):
        o = json.loads(ln)
        info = b.get_order(o["cid"])
        if info and info["status"] == "filled":
            fills.append({**info, "filled_on": pd.Timestamp(o["sent"]).normalize() + pd.offsets.BDay(1),
                          "placed": pd.Timestamp(o["sent"]).normalize()})
    data.freeze_research()
    return compare(eq, fills, runs, data.load_all(), cfg)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sim", action="store_true")
    g.add_argument("--alpaca", action="store_true")
    ap.add_argument("--days", type=int, default=120)
    a = ap.parse_args()
    c = from_sim(a.days) if a.sim else from_alpaca()
    write_report(c, f"Simulation {a.days} Tage" if a.sim else "Alpaca Paper")
    print(f"Paper {c['paper_total']:+.2%} vs Backtest {c['backtest_total']:+.2%} · Gruppen {c['groups']}")
    print(verdict(c))
