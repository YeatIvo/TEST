"""Schatten-Konto: "Was hätte der Bot mit nur X Franken gemacht?"

Läuft bei jedem Bot-Lauf mit: gleiche Regeln, gleiche Signale, gleiche Kurse – aber mit
kleinem Startkapital und ganzen Aktien. Es wird nichts beim Broker gehandelt; ein
simuliertes Konto (SimBroker) füllt Market-on-Open-Orders zum echten Eröffnungskurs und
Stops zum Stop-Kurs. Ergebnis in Franken (zum aktuellen USD/CHF-Kurs) in
reports/konto_<X>chf.md.

Optionen pro Konto (config/settings.toml, [[shadow.accounts]]):
  monthly_chf – Einzahlung am ersten Handelstag jedes Monats (wird beim nächsten Lauf mitinvestiert)
  twins       – günstige Zwillings-ETFs: Signale kommen vom getesteten Original (z. B. QQQ),
                gehandelt wird der Zwilling (QQQM). Trend- und RSI-Signale sind preisunabhängig.

Setup (einmalig): python -m src.shadow init --chf 1000 --start 2026-11-16 --mirror GLD:354.02
                  python -m src.shadow init --chf 2000 --start 2026-11-16 --monthly 300 --twins QQQ:QQQM GLD:GLDM SPY:SPYM
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math

import pandas as pd

from . import data, risk, settings
from .bot import Bot, load_config, load_state, new_state, save_state
from .broker import SimBroker

FEE_EXAMPLE_CHF = 5.0            # typische Gebühr pro Trade bei einer Schweizer Bank (nur Info)


def accounts() -> list[dict]:
    sh = settings.load().get("shadow", {})
    return list(sh.get("accounts", [])) + [{"chf": c} for c in sh.get("accounts_chf", [])]


def _fetch_twin(twin: str) -> pd.DataFrame:
    return data.fetch(twin, (pd.Timestamp.today() - pd.DateOffset(years=2)).strftime("%Y-%m-%d"))


def _prices_for(acc: dict, prices: dict) -> dict:
    """Ersetzt Original-Kurse durch die Zwillings-ETFs (gleiche Schlüssel, damit die Regeln gleich bleiben)."""
    twins = acc.get("twins") or {}
    if not twins:
        return prices
    out = dict(prices)
    for orig, twin in twins.items():
        if orig in out:
            t = _fetch_twin(twin)
            out[orig] = t[t.index <= prices[orig].index[-1]]
    return out


def _dir(chf: int):
    return settings.DIRS["live"] / f"shadow_{chf}chf"


def fx_usdchf(on: str | None = None) -> float | None:
    """CHF pro 1 USD (Yahoo 'CHF=X'). on=Datum -> Schlusskurs bis zu diesem Tag."""
    try:
        import yfinance as yf
        d = yf.download("CHF=X", period="1mo", progress=False, auto_adjust=False)
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        c = d["Close"].dropna()
        if on:
            c = c[c.index <= pd.Timestamp(on)]
        return float(c.iloc[-1])
    except Exception:
        return None


def _load(chf):
    p = _dir(chf) / "account.json"
    return json.loads(p.read_text()) if p.exists() else None


def _broker(acc, prices) -> SimBroker:
    s = acc["sim"]
    b = SimBroker(prices, cash=s["cash"], date=pd.Timestamp(s["date"]) if s["date"] else None,
                  pos=dict(s["pos"]), orders={k: {**o, "placed": pd.Timestamp(o["placed"]) if o.get("placed") else None,
                                                  "filled_on": pd.Timestamp(o["filled_on"]) if o.get("filled_on") else None}
                                              for k, o in s["orders"].items()})
    b._prev_equity = s.get("prev_equity")
    return b


def _save(chf, acc, b: SimBroker):
    acc["sim"] = {"cash": b.cash, "date": str(b.date.date()) if b.date is not None else None, "pos": b.pos,
                  "orders": {k: {**o, "placed": str(o["placed"]) if o.get("placed") is not None else None,
                                 "filled_on": str(o["filled_on"]) if o.get("filled_on") is not None else None}
                             for k, o in b.orders.items()},
                  "prev_equity": b._prev_equity}
    (_dir(chf) / "account.json").write_text(json.dumps(acc, indent=2, default=str))


def _bot(chf, b, prices, cfg):
    d = _dir(chf)
    pf = d / "PAUSE"                       # spiegelt die PAUSE des Hauptkontos
    if risk.PAUSE_FILE.exists():
        pf.write_text("gespiegelt vom Hauptkonto\n")
    else:
        pf.unlink(missing_ok=True)
    c = json.loads(json.dumps(cfg))
    c["starting_cash"] = None
    return Bot(b, lambda _d: prices, state_path=d / "state.json", alerts=False, cfg=c, pause_file=pf, log_dir=d)


def init(chf: int, start: str, mirror: dict[str, float] | None = None, cfg=None,
         monthly: float = 0, twins: dict[str, str] | None = None) -> dict:
    """Startet das Schatten-Konto. mirror={'GLD': 354.02}: übernimmt die Core-Position des
    Hauptkontos zum echten Fill-Preis (so viele ganze Aktien wie das Kapital erlaubt)."""
    cfg = cfg or load_config()
    d = _dir(chf)
    d.mkdir(parents=True, exist_ok=True)
    fx = fx_usdchf(on=(pd.Timestamp(start) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")) or 0.84
    usd = chf / fx
    b = SimBroker({}, cash=usd, date=pd.Timestamp(start))
    st = new_state(cfg)
    for sym, px in (mirror or {}).items():
        q = math.floor(usd / (px * (1 + settings.cost_per_side(sym))))
        b.pos[sym] = q
        b.cash -= q * px * (1 + settings.cost_per_side(sym))
        b.orders[f"{start}-{sym}-mirror"] = {"id": f"{start}-{sym}-mirror", "cid": f"{start}-{sym}-mirror", "symbol": sym,
                                             "side": "buy", "qty": q, "type": "market", "stop": None, "status": "filled",
                                             "filled_qty": q, "filled_avg_price": px, "placed": None,
                                             "filled_on": pd.Timestamp(start)}
        st["core"]["holdings"][sym] = q
    st["last_run"] = st["last_morning"] = start
    st["runs"] = 1
    save_state(st, d / "state.json")
    acc = {"chf": chf, "start_date": start, "fx_start": fx, "start_usd": usd, "monthly_chf": monthly,
           "twins": twins or {}, "deposited_chf": chf, "deposits": [], "last_deposit_month": start[:7]}
    _save(chf, acc, b)
    return acc


def morning(chf, today, prices, cfg):
    acc = _load(chf)
    if not acc:
        return None
    prices = _prices_for(acc, prices)
    b = _broker(acc, prices)
    today = pd.Timestamp(today)
    if b.date is None or b.date < today:
        b.open_session(today)
    r = _bot(chf, b, prices, cfg).morning(today)
    _save(chf, acc, b)
    return r


def _deposit(acc: dict, b: SimBroker, session: pd.Timestamp):
    """Monatliche Einzahlung am ersten Handelstag eines neuen Monats. Zählt nicht als Gewinn."""
    m = session.strftime("%Y-%m")
    if not acc.get("monthly_chf") or m == acc.get("last_deposit_month"):
        return
    fx = fx_usdchf(on=str(session.date())) or acc["fx_start"]
    usd = acc["monthly_chf"] / fx
    b.cash += usd
    if b._prev_equity is not None:
        b._prev_equity += usd
    acc["deposited_chf"] = acc.get("deposited_chf", acc["chf"]) + acc["monthly_chf"]
    acc.setdefault("deposits", []).append({"date": str(session.date()), "chf": acc["monthly_chf"], "usd": usd})
    acc["last_deposit_month"] = m


def evening(chf, session, prices, cfg):
    acc = _load(chf)
    if not acc:
        return None
    prices = _prices_for(acc, prices)
    b = _broker(acc, prices)
    session = pd.Timestamp(session)
    st = load_state(_dir(chf) / "state.json", cfg)
    if st["last_run"] == str(session.date()):
        return {"status": "heute schon gelaufen"}
    bot = _bot(chf, b, prices, cfg)
    if b.date is None or b.date < session:          # Morgen-Check verpasst: nachholen
        b.open_session(session)
        bot.morning(session)
    b.run_stops()
    _deposit(acc, b, session)
    r = bot.evening(session)
    _save(chf, acc, b)
    write_report(chf, acc, b, prices)
    return r


def write_report(chf, acc, b: SimBroker, prices):
    fx = fx_usdchf() or acc["fx_start"]
    eq_usd = b.equity()
    eq_chf = eq_usd * fx
    trades = [o for o in b.orders.values() if o["status"] == "filled"]
    paid_chf = acc.get("deposited_chf", chf)
    paid_usd = acc["start_usd"] + sum(d["usd"] for d in acc.get("deposits", []))
    pl = eq_chf - paid_chf
    usd_pl = eq_usd - paid_usd
    tw = acc.get("twins") or {}
    name = lambda s: f"{tw[s]} (statt {s})" if s in tw else s
    invested = sum(q * float(prices[s]["close"].iloc[-1]) for s, q in b.pos.items() if q) / eq_usd if eq_usd else 0
    lines = [f"# Schatten-Konto {chf} CHF", "",
             f"Stand {b.date.date() if b.date is not None else '–'} · Start {acc['start_date']} mit {chf} CHF "
             f"(= ${acc['start_usd']:,.2f} bei {acc['fx_start']:.4f} CHF/USD)"
             + (f" · +{acc['monthly_chf']:.0f} CHF jeden Monat" if acc.get("monthly_chf") else "")
             + (f" · günstige Zwillings-ETFs: {', '.join(f'{k}→{v}' for k, v in tw.items())}" if tw else ""), "",
             "| | |", "|---|---|",
             f"| **Wert heute** | **{eq_chf:,.2f} CHF** (${eq_usd:,.2f} bei {fx:.4f}) |",
             f"| Eingezahlt | {paid_chf:,.0f} CHF ({len(acc.get('deposits', []))} Monats-Einzahlungen) |",
             f"| **Gewinn/Verlust** | **{pl:+,.2f} CHF ({pl / paid_chf:+.2%})** |",
             f"| davon Trading (in USD) | {usd_pl:+,.2f} USD ({usd_pl / paid_usd:+.2%}) |",
             f"| davon Wechselkurs | {pl - usd_pl * fx:+,.2f} CHF |",
             f"| Investiert | {invested:.0%} (Rest Cash – nur ganze Aktien möglich) |",
             f"| Cash | ${b.cash:,.2f} |",
             f"| Trades bisher | {len(trades)} · mit {FEE_EXAMPLE_CHF:.0f} CHF Bankgebühr/Trade wären es "
             f"{pl - len(trades) * FEE_EXAMPLE_CHF:+,.2f} CHF |", "",
             "| Position | Stück | Kurs | Wert |", "|---|---|---|---|"]
    for s, q in b.pos.items():
        if q:
            px = float(prices[s]["close"].iloc[-1])
            lines.append(f"| {name(s)} | {q} | ${px:,.2f} | ${q * px:,.2f} |")
    lines += ["", "Simuliert: gleiche Regeln und Signale wie das Paper-Konto, Kauf zum echten Eröffnungskurs, "
              "ganze Aktien, 0.05 % Spread. Alpaca selbst verlangt keine Kommission."]
    (settings.DIRS["reports"] / f"konto_{chf}chf.md").write_text("\n".join(lines) + "\n")
    return eq_chf


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["init", "report"])
    ap.add_argument("--chf", type=int, default=1000)
    ap.add_argument("--start")
    ap.add_argument("--mirror", nargs="*", default=[], help="z. B. GLD:354.02")
    ap.add_argument("--monthly", type=float, default=0, help="monatliche Einzahlung in CHF")
    ap.add_argument("--twins", nargs="*", default=[], help="z. B. QQQ:QQQM GLD:GLDM SPY:SPYM")
    a = ap.parse_args(argv)
    if a.cmd == "init":
        print(init(a.chf, a.start, {m.split(":")[0]: float(m.split(":")[1]) for m in a.mirror},
                   monthly=a.monthly, twins=dict(t.split(":") for t in a.twins)))
    else:
        acc = _load(a.chf)
        cfg = load_config()
        from .bot import live_prices
        prices = live_prices(cfg)
        prices = _prices_for(acc, prices)
        b = _broker(acc, prices)
        write_report(a.chf, acc, b, prices)
        print((settings.DIRS["reports"] / f"konto_{a.chf}chf.md").read_text())


if __name__ == "__main__":
    main()
