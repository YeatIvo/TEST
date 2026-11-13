"""Phase Adapt (Prompt 12) – wann ein Sleeve rausfliegt, Bank und Rotation.

Drei Gründe, VORHER festgelegt (rules/removal_rules.md), nie "eine schlechte Woche":
  1. Kill-Line: Live-Drawdown des Sleeves > 2x sein schlimmster getesteter Drawdown
     -> Bot schaltet ihn selbst ab, verkauft zum nächsten Open, meldet sich.
  2. Quartals-Re-Pick wählt ihn nicht mehr -> Vorschlag zum Tausch (du sagst ja/nein).
  3. Nach >= 3 Monaten live handelt er < 0.5x oder > 2x so oft wie im Test -> Status "review".
Core: Konto-Drawdown > 1.5x schlimmster Core-Drawdown -> nur Alarm + keine neuen Sleeves;
den Core ändert nur der Mensch.

Status: keep · watch (> halbe Kill-Line oder < 5 Live-Trades) · review · out.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json

import numpy as np
import pandas as pd

from . import backtest as bt
from . import data, settings, signals
from .core import calendar, core_returns

RULES = settings.DIRS["rules"]


def _full_period():
    return (pd.Timestamp(settings.window("train")[0]), pd.Timestamp(data.research_end()))


def tested_profile(item: dict, prices=None) -> dict:
    from .sleeves import sleeve_result
    prices = prices or data.load_all()
    res = sleeve_result(item["ticker"], signals.rule_from_dict(item["rule"]), prices)
    per = _full_period()
    daily = bt.window_slice(res.daily, per)
    tr = bt.trades_in(res.trades, per)
    years = len(daily) / 252
    return {"worst_dd": abs(bt.max_drawdown(bt.equity(daily))), "trades_per_year": len(tr) / years,
            "win_rate": float((tr["ret"] > 0).mean()) if len(tr) else np.nan,
            "avg_trade": float(tr["ret"].mean()) if len(tr) else np.nan}


def write_kill_lines() -> dict:
    prices = data.load_all()
    cfg = json.loads((RULES / "config.json").read_text())
    bench = json.loads((RULES / "bench.json").read_text())
    core = cfg["core"]
    core_dd = abs(bt.max_drawdown(bt.equity(bt.window_slice(core_returns(core["engine"], core["safe"], prices),
                                                             _full_period()))))
    out = {"core": {"worst_dd": core_dd, "alert_line": 1.5 * core_dd}, "sleeves": {}}
    for it in {x["id"]: x for x in cfg["sleeves"] + bench}.values():
        p = tested_profile(it, prices)
        out["sleeves"][it["id"]] = {**p, "kill_line": 2 * p["worst_dd"]}
    (RULES / "kill_lines.json").write_text(json.dumps(out, indent=2))
    return out


def kill_lines() -> dict:
    p = RULES / "kill_lines.json"
    return json.loads(p.read_text()) if p.exists() else write_kill_lines()


def live_drawdown(sl_state: dict, close: float | None, cost: float) -> tuple[float, int]:
    """Drawdown der Slot-Equity aus abgeschlossenen Live-Trades + offener Position."""
    rets = list(sl_state.get("closed", []))
    if sl_state.get("status") == "in_trade" and sl_state.get("entry_px") and close:
        rets.append(close / sl_state["entry_px"] * (1 - cost) ** 2 - 1)
    if not rets:
        return 0.0, 0
    eq = np.cumprod([1.0] + [1 + r for r in rets])
    return float(abs((eq / np.maximum.accumulate(eq) - 1).min())), len(sl_state.get("closed", []))


def sleeve_status(sid: str, sl_state: dict, close: float | None, live_days: int, kl: dict) -> dict:
    k = kl["sleeves"].get(sid)
    if not k:
        return {"status": "watch", "why": "keine Kill-Line"}
    dd, n = live_drawdown(sl_state, close, settings.cost_per_side(sl_state["symbol"]))
    if dd > k["kill_line"]:
        return {"status": "out", "dd": dd, "kill": k["kill_line"], "why": f"DD {dd:.1%} > Kill-Line {k['kill_line']:.1%}"}
    if live_days >= 63:
        rate = n / (live_days / 252)
        if rate < 0.5 * k["trades_per_year"] or rate > 2 * k["trades_per_year"]:
            return {"status": "review", "dd": dd, "kill": k["kill_line"],
                    "why": f"{rate:.1f} Trades/J live vs. {k['trades_per_year']:.1f} im Test"}
    if dd > 0.5 * k["kill_line"] or n < 5:
        return {"status": "watch", "dd": dd, "kill": k["kill_line"],
                "why": "über halber Kill-Line" if dd > 0.5 * k["kill_line"] else f"erst {n} Live-Trades"}
    return {"status": "keep", "dd": dd, "kill": k["kill_line"], "why": "im Rahmen"}


def changelog(change: str, why: str, test: str):
    with (RULES / "CHANGELOG.md").open("a") as f:
        f.write(f"| {dt.date.today()} | {change} | {why} | {test} |\n")


# ------------------------------------------------------------------ Bank & Rotation
def bench_list() -> list[dict]:
    cfg = json.loads((RULES / "config.json").read_text())
    live = {s["id"] for s in cfg["sleeves"] if s.get("enabled", True)}
    bench = json.loads((RULES / "bench.json").read_text())
    extra = RULES / "bench_extra.json"                 # z. B. aus 4B, neuen Ideen, letztem Re-Pick
    if extra.exists():
        bench += json.loads(extra.read_text())
    return [b for b in {x["id"]: x for x in bench}.values() if b["id"] not in live]


def rotate(out_id: str, in_id: str, apply: bool = False) -> dict:
    """Prüft (und setzt bei apply=True) den Tausch eines Live-Sleeves gegen einen Bank-Sleeve."""
    from .account import account_returns
    from .sleeves import sleeve_result
    cfg = json.loads((RULES / "config.json").read_text())
    prices = data.load_all()
    live = [s for s in cfg["sleeves"] if s.get("enabled", True)]
    new = next((b for b in bench_list() if b["id"] == in_id), None)
    if new is None or not any(s["id"] == out_id for s in live):
        return {"ok": False, "checks": {}, "why": "Sleeve-ID nicht gefunden (Live oder Bank)"}
    rest = [s for s in live if s["id"] != out_id]
    per = _full_period()
    stream = lambda it: bt.window_slice(sleeve_result(it["ticker"], signals.rule_from_dict(it["rule"]), prices).daily, per)
    core_r = core_returns(cfg["core"]["engine"], cfg["core"]["safe"], prices)
    ns = stream(new)
    corr = max([ns.corr(bt.window_slice(core_r, per))] + [ns.corr(stream(s)) for s in rest])
    with_new = bt.metrics(bt.window_slice(account_returns(core_r, rest + [new], prices, cfg["vol_sizing_half"])[0], per))
    without = bt.metrics(bt.window_slice(account_returns(core_r, rest, prices, cfg["vol_sizing_half"])[0], per))
    checks = {"ticker_frei": new["ticker"] not in {s["ticker"] for s in rest},
              "korrelation<=0.6": bool(corr <= 0.6),
              "konto_besser_oder_gleich": bool(with_new["ret_dd"] >= without["ret_dd"])}
    res = {"ok": all(checks.values()), "checks": checks, "corr": float(corr),
           "ret_dd_with": with_new["ret_dd"], "ret_dd_without": without["ret_dd"],
           "command": f"python -m src.adapt rotate {out_id} {in_id} --apply"}
    if apply and res["ok"]:
        for s in cfg["sleeves"]:
            if s["id"] == out_id:
                s["enabled"] = False                   # Bot verkauft beim nächsten Abend-Lauf
        cfg["sleeves"].append({"id": new["id"], "ticker": new["ticker"], "kind": new["kind"], "rule": new["rule"],
                               "weight": settings.load()["portfolio"]["sleeve_weight"], "enabled": True})
        (RULES / "config.json").write_text(json.dumps(cfg, indent=2))
        write_kill_lines()
        changelog(f"Rotation: {out_id} → {new['id']}", "Bank-Sleeve besteht Rotate-Checks",
                  f"Rendite/DD {without['ret_dd']:.2f} → {with_new['ret_dd']:.2f}, Korr {corr:.2f}")
    return res


def disable_sleeve(sid: str, why: str):
    cfg = json.loads((RULES / "config.json").read_text())
    for s in cfg["sleeves"]:
        if s["id"] == sid:
            s["enabled"] = False
    (RULES / "config.json").write_text(json.dumps(cfg, indent=2))
    changelog(f"Sleeve abgeschaltet: {sid}", why, "Kill-Line (rules/kill_lines.json)")


def write_panel(kl: dict, statuses: dict | None = None):
    rows = "".join(
        f"<tr><td>{sid.split(':',1)[1]}</td><td>{v['worst_dd']*100:.1f} %</td><td><b>{v['kill_line']*100:.1f} %</b></td>"
        f"<td>{v['trades_per_year']:.1f}</td>"
        f"<td>{(statuses or {}).get(sid, {}).get('status', '–')}</td></tr>" for sid, v in kl["sleeves"].items())
    bench = "".join(f"<li>{b['ticker']} {b['kind']}</li>" for b in bench_list()) or "<li>leer</li>"
    html = f"""<section><h2>Adapt · Kill-Lines, Bank &amp; Rotation</h2>
<p class="sub">Kill-Line = 2× schlimmster getesteter Drawdown des Sleeves. Core-Alarm bei {kl['core']['alert_line']*100:.0f} % Konto-Drawdown (1.5× {kl['core']['worst_dd']*100:.0f} %). Nie wegen einer schlechten Woche.</p>
<table><tr><th>Sleeve</th><th>schlimmster DD getestet</th><th>Kill-Line</th><th>Trades/Jahr Test</th><th>Status</th></tr>{rows}</table>
<h3>Bank (getestet, wartet auf freien Slot)</h3><ul>{bench}</ul>
<p class="mono">Tausch prüfen: python -m src.adapt rotate &lt;live-id&gt; &lt;bank-id&gt; · erst mit --apply wird geändert.</p></section>"""
    (settings.DIRS["dashboard"] / "panels" / "60_adapt.html").write_text(html)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["kill-lines", "bench", "rotate"])
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "kill-lines":
        kl = write_kill_lines()
        write_panel(kl)
        print(json.dumps(kl, indent=2))
    elif a.cmd == "bench":
        for b in bench_list():
            print(b["id"])
    else:
        print(json.dumps(rotate(a.ids[0], a.ids[1], a.apply), indent=2, default=float))


if __name__ == "__main__":
    main()
