"""Phase Adapt (Prompt 13) – Wochen-, Monats- und Quartals-Review.

Läuft jeden Samstag (Claude-Skill `trading-review` oder Scheduler):
  jeden Samstag              -> Wochenbericht (Konto, Lücken, Fehler, verpasste Läufe, Kill-Line-Abstand)
  erster Samstag im Monat    -> + Sleeve-Check (keep/watch/review/out)
  erster Samstag nach Quartal-> + Re-Pick-Vorschlag mit Rotate-Checks (Dry-Run) – ändert NIE selbst
Jeder Teil merkt sich, was er schon erledigt hat (reports/review_state.json).
Die ersten drei Zeilen jedes Berichts gehen per Telegram ans Handy.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json

import pandas as pd

from . import adapt, notify, settings
from .bot import load_config, load_state

REP = settings.DIRS["reports"]
STATE = REP / "review_state.json"


def _jsonl(name):
    p = settings.DIRS["logs"] / f"{name}.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def weekly(today: dt.date) -> list[str]:
    since = today - dt.timedelta(days=7)
    runs = [r for r in _jsonl("runs") if since < pd.Timestamp(r["asof"]).date() <= today and not r.get("dry")]
    ok = [r for r in runs if r["status"] == "ok"]
    aborts = [r for r in runs if r["status"] == "ABORT"]
    trading_days = pd.bdate_range(since + dt.timedelta(days=1), min(today, dt.date.today()))
    ran = {pd.Timestamp(r["asof"]).date() for r in ok}
    missed = [d.date() for d in trading_days if d.date() not in ran]
    eq = [r["equity"] for r in ok]
    lines = [f"## Woche bis {today}",
             f"- Abend-Läufe ok: {len(ok)} · Stopps: {len(aborts)} · ohne Lauf (inkl. Feiertage): {len(missed)}",
             f"- Konto: {'$%s → $%s (%+.2f%%)' % (f'{eq[0]:,.0f}', f'{eq[-1]:,.0f}', 100 * (eq[-1] / eq[0] - 1)) if len(eq) > 1 else 'zu wenig Läufe'}"]
    lines += [f"- ⛔ {pd.Timestamp(r['asof']).date()}: {r['reason']}" for r in aborts]
    orders = [o for r in ok for o in r["orders"]]
    lines.append(f"- Orders: {len(orders)} " + ", ".join(f"{o['side']} {o['qty']} {o['symbol']}" for o in orders[:10]))
    reasons = sorted({x for r in ok for x in r["risk"]["reasons"]})
    lines += [f"- ⚠️ {x}" for x in reasons[:10]]
    lines.append("- AI-Layer: aus (keine Fed-Calls verwendet)")
    cmp = REP / "paper_vs_backtest.md"
    if cmp.exists():
        lines.append("- Paper vs. Backtest: " + next((l for l in cmp.read_text().splitlines() if l.startswith("- Fazit")), "–"))
    kl = adapt.kill_lines()
    st = load_state()
    for sid, sl in st["sleeves"].items():
        if sid in kl["sleeves"]:
            dd, n = adapt.live_drawdown(sl, None, settings.cost_per_side(sl["symbol"]))
            lines.append(f"- {sid.split(':',1)[1]} ({sl['symbol']}): Live-DD {dd:.1%} von Kill-Line "
                         f"{kl['sleeves'][sid]['kill_line']:.1%} · {n} Live-Trades · {sl['status']}")
    return lines


def monthly(today: dt.date) -> list[str]:
    kl = adapt.kill_lines()
    st = load_state()
    first = min((pd.Timestamp(r["asof"]).date() for r in _jsonl("runs") if r["status"] == "ok" and not r.get("dry")),
                default=today)
    live_days = len(pd.bdate_range(first, today))
    lines = [f"## Monats-Check {today:%Y-%m}"]
    if live_days < 10:
        lines.append(f"- Bot erst {live_days} Handelstage live – zu wenig für einen Sleeve-Vergleich.")
    for sid, sl in st["sleeves"].items():
        s = adapt.sleeve_status(sid, sl, None, live_days, kl)
        lines.append(f"- **{s['status'].upper()}** {sid.split(':',1)[1]} ({sl['symbol']}): {s['why']}")
    lines.append("- Kein Sleeve wird wegen einer schlechten Woche/eines Monats entfernt.")
    return lines


def quarterly(today: dt.date) -> list[str]:
    from . import data, repick
    data.freeze_research()
    prices = data.load_all()
    cal = prices["SPY"].index
    qend = max(pd.Timestamp(q) for q in repick.quarter_ends(cal))
    picks = repick.pick_sleeves(qend, prices)
    cfg = load_config()
    live = [s for s in cfg["sleeves"] if s.get("enabled", True)]
    lines = [f"## Quartals-Re-Pick per {qend.date()}",
             f"- Routine wählt: {', '.join(f'{p['ticker']} {p['kind']}' for p in picks) or 'nichts'}",
             f"- Live: {', '.join(f'{s['ticker']} {s['kind']}' for s in live)}"]
    pick_ids = [p["id"] for p in picks]
    extra = [p for p in picks if p["id"] not in {s["id"] for s in live}]
    if extra:
        (settings.DIRS["rules"] / "bench_extra.json").write_text(json.dumps(extra, indent=2, default=float))
    for s in live:
        if s["id"] in pick_ids:
            continue
        for p in extra:
            r = adapt.rotate(s["id"], p["id"], apply=False)
            mark = "✅" if r["ok"] else "❌"
            lines.append(f"- Vorschlag {mark}: {s['ticker']} {s['kind']} → {p['ticker']} {p['kind']} · Checks {r['checks']}"
                         + (f"\n  Befehl (nur nach deinem JA): `{r['command']}`" if r["ok"] else ""))
            if r["ok"]:
                break
    lines.append("- Es wurde nichts geändert. Antworte JA/NEIN pro Vorschlag.")
    return lines


def run(today: dt.date | None = None, force: str | None = None) -> str:
    today = today or dt.date.today()
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    parts = []
    wk = str(today - dt.timedelta(days=today.weekday()))
    if force == "weekly" or st.get("weekly") != wk:
        parts += weekly(today)
        st["weekly"] = wk
    if force == "monthly" or (today.day <= 7 and st.get("monthly") != f"{today:%Y-%m}"):
        parts += [""] + monthly(today)
        st["monthly"] = f"{today:%Y-%m}"
    q = f"{today.year}Q{(today.month - 1) // 3 + 1}"
    if force == "quarterly" or (today.month in (1, 4, 7, 10) and today.day <= 7 and st.get("quarterly") != q):
        parts += [""] + quarterly(today)
        st["quarterly"] = q
    if not parts:
        return "Nichts zu tun – diese Woche schon erledigt."
    text = f"# Review {today}\n\n" + "\n".join(parts) + "\n"
    (REP / f"{today}-review.md").write_text(text)
    STATE.write_text(json.dumps(st, indent=2))
    notify.send("📋 " + " | ".join(l for l in parts if l.startswith("-"))[:600])
    return text


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", choices=["weekly", "monthly", "quarterly"])
    ap.add_argument("--date")
    a = ap.parse_args()
    print(run(dt.date.fromisoformat(a.date) if a.date else None, a.force))
