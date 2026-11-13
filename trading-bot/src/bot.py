"""Phase H – der Bot (Prompt 8/8B). Handelt rules/config.json mit derselben Signal-Datei
wie der Backtest. Nur Paper.

Abend-Lauf (nach 19:05 New York, Orders gelten zum nächsten Open):
   1 Lock            – nie zwei Läufe gleichzeitig
   2 Handelstag?     – sonst Ende
   3 Reconcile       – Broker-Positionen == was der Bot glaubt? Sonst STOPP + Alert
   4 Daten           – frische Tagesbalken nach data/live/ (Forschungsdaten bleiben unberührt)
   5 Frische         – letzter Balken jedes Tickers == heute, sonst STOPP
   6 Regime+Signale  – Core-Ziel, Sleeve-Einstiege/Ausstiege (src/signals.py)
   7 AI-Call         – nur wenn der AI-Layer eingeschaltet ist (Standard: aus, nur Log)
   8 Gewichte→Aktien – ganze Aktien, abgerundet
   9 Risiko          – Limits aus src/risk.py
  10 Orders          – Market-on-Open, eindeutige client_order_id (nie doppelt)
  11 Log + Alert
Morgen-Check (kurz nach dem Open): Fills verbuchen, Stops für neue Sleeve-Käufe beim
Broker setzen (8 %/10 % unter dem echten Fill), fehlende Stops neu setzen.

CLI:  python -m src.bot evening [--dry-run] [--asof YYYY-MM-DD] [--sim]
      python -m src.bot morning | status | pause | resume | flatten | check-keys
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from zoneinfo import ZoneInfo

import pandas as pd

from . import data, notify, risk, settings, signals
from .indicators import vol_high

NY = ZoneInfo("America/New_York")
STATE_PATH = settings.DIRS["live"] / "state.json"
LOCK_PATH = settings.DIRS["logs"] / "bot.lock"


class Abort(RuntimeError):
    pass


# ------------------------------------------------------------------ Zustand
def load_config() -> dict:
    return json.loads((settings.DIRS["rules"] / "config.json").read_text())


def new_state(cfg: dict) -> dict:
    return {"core": {"holdings": {}}, "pending": [], "hwm": None, "borrow_blocked": False,
            "last_run": None, "last_morning": None, "runs": 0,
            "sleeves": {s["id"]: {"status": "flat", "symbol": s["ticker"], "shares": 0, "entry_px": None,
                                  "entry_date": None, "hold_days": 0, "stop_cid": None, "exit_date": None,
                                  "size": None} for s in cfg["sleeves"]}}


def load_state(path=STATE_PATH, cfg=None) -> dict:
    cfg = cfg or load_config()
    st = json.loads(path.read_text()) if path.exists() else new_state(cfg)
    for s in cfg["sleeves"]:                       # neue Sleeves aus der Config ergänzen
        st["sleeves"].setdefault(s["id"], new_state({"sleeves": [s]})["sleeves"][s["id"]])
    return st


def save_state(st: dict, path=STATE_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2, default=str))
    tmp.replace(path)


def expected_positions(st: dict) -> dict[str, int]:
    exp = {k: v for k, v in st["core"]["holdings"].items() if v}
    for s in st["sleeves"].values():
        if s["shares"]:
            exp[s["symbol"]] = exp.get(s["symbol"], 0) + s["shares"]
    return exp


def _log(name: str, rec: dict):
    p = settings.DIRS["logs"] / f"{name}.jsonl"
    p.parent.mkdir(exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(rec, default=str) + "\n")


class Lock:
    def __enter__(self):
        LOCK_PATH.parent.mkdir(exist_ok=True)
        if LOCK_PATH.exists():
            age = dt.datetime.now().timestamp() - LOCK_PATH.stat().st_mtime
            if age < 2 * 3600:
                raise Abort("Ein anderer Lauf ist aktiv (Lock-Datei).")
        LOCK_PATH.write_text(str(os.getpid()))
        return self

    def __exit__(self, *a):
        LOCK_PATH.unlink(missing_ok=True)


# ------------------------------------------------------------------ Signale
def needed_tickers(cfg) -> list[str]:
    t = {cfg["core"]["engine"], cfg["core"]["safe"], "SPY"} | {s["ticker"] for s in cfg["sleeves"]}
    return sorted(t)


def decide(prices: dict, asof: pd.Timestamp, cfg: dict) -> dict:
    """Reine Funktion: was sagen die Regeln am Schluss von `asof`? (nur Daten <= asof)"""
    s = settings.load()
    p = {t: d[d.index <= asof] for t, d in prices.items()}
    core = cfg["core"]
    on = signals.trend_switch(p[core["engine"]]["close"], core["kind"], core["n"]).iloc[-1]
    out = {"asof": asof, "core_on": None if pd.isna(on) else bool(on),
           "core_symbol": core["engine"] if on == True else core["safe"],
           "closes": {t: float(d["close"].iloc[-1]) for t, d in p.items()},
           "last_dates": {t: d.index[-1] for t, d in p.items()}, "sleeves": {}}
    for sl in cfg["sleeves"]:
        df = p[sl["ticker"]]
        rule = signals.rule_from_dict(sl["rule"])
        vh = vol_high(df["close"], s["regime"]["vol_window_days"], s["regime"]["vol_lookback_days"]).iloc[-1]
        out["sleeves"][sl["id"]] = {"entry": bool(rule.entry(df).iloc[-1]), "exit": bool(rule.exit(df).iloc[-1]),
                                    "vol_high": bool(vh == True), "max_hold": rule.max_hold,
                                    "stop_pct": rule.stop_pct(s)}
    return out


def live_prices(cfg) -> dict:
    """Frische Daten für den Bot nach data/live/ (Forschungsdaten bleiben unverändert)."""
    out = {}
    for t in needed_tickers(cfg):
        df = data.fetch(t, (pd.Timestamp.today() - pd.DateOffset(years=2)).strftime("%Y-%m-%d"))
        df.round(6).to_csv(settings.DIRS["live"] / f"{t}.csv")
        out[t] = df
    return out


# ------------------------------------------------------------------ Bot
class Bot:
    def __init__(self, broker, prices_fn, state_path=STATE_PATH, dry_run=False, alerts=True, cfg=None,
                 pause_file=None):
        self.b, self.prices_fn, self.path = broker, prices_fn, state_path
        self.pause_file = pause_file or risk.PAUSE_FILE
        self.dry, self.alerts = dry_run, alerts
        self.cfg = cfg or load_config()
        self.s = settings.load()

    def alert(self, msg):
        if self.alerts and not self.dry:
            notify.send(msg)

    # ---- 3 Reconcile
    def reconcile(self, st: dict, today) -> list[str]:
        notes = []
        for sid, sl in st["sleeves"].items():
            if sl["status"] == "in_trade" and sl["stop_cid"]:
                o = self.b.get_order(sl["stop_cid"])
                if o and o["status"] == "filled":
                    notes.append(f"Stop gefüllt: {sl['symbol']} {sl['shares']} @ {o['filled_avg_price']:.2f}")
                    sl.update(status="flat", shares=0, exit_date=str(pd.Timestamp(today).date()), stop_cid=None)
        if st["pending"]:
            raise Abort(f"Offene, nicht verbuchte Orders vom letzten Lauf ({len(st['pending'])}) – "
                        "Morgen-Check lief nicht?")
        actual = self.b.positions()
        exp = expected_positions(st)
        if st["runs"] == 0 and actual and not exp:
            raise Abort(f"Erster Lauf, aber das Konto hält schon Positionen {actual}. Paper-Konto leeren.")
        if actual != exp:
            raise Abort(f"Reconcile-Fehler: Broker {actual} ≠ Bot {exp}")
        return notes

    # ---- Abend
    def evening(self, asof=None) -> dict:
        asof = pd.Timestamp(asof or dt.datetime.now(NY).date())
        with Lock():
            st = load_state(self.path, self.cfg)
            if not self.b.is_trading_day(asof):
                return {"status": "kein Handelstag", "asof": asof}
            if st["last_run"] == str(asof.date()):
                return {"status": "heute schon gelaufen", "asof": asof}
            try:
                notes = self.reconcile(st, asof)
                prices = self.prices_fn(asof)
                stale = [t for t in needed_tickers(self.cfg)
                         if prices[t][prices[t].index <= asof].index[-1] != asof]
                if stale:
                    raise Abort(f"Daten nicht von heute: {stale}")
                d = decide(prices, asof, self.cfg)
                ai_note = self.ai_call(asof)
                plan = self.plan(st, d)
            except Abort as e:
                _log("runs", {"asof": asof, "status": "ABORT", "reason": str(e), "dry": self.dry})
                self.alert(f"⛔ Bot gestoppt ({asof.date()}): {e}")
                raise
            sent = [] if self.dry else self.send(plan["orders"], plan["cancels"])
            plan["state"]["last_run"] = str(asof.date())
            plan["state"]["runs"] += 1
            if not self.dry:
                save_state(plan["state"], self.path)
            rec = {"asof": asof, "status": "ok", "dry": self.dry, "core_symbol": d["core_symbol"],
                   "core_on": d["core_on"], "orders": plan["orders"], "cancels": plan["cancels"],
                   "risk": plan["risk"], "notes": notes + [ai_note], "equity": plan["equity"]}
            _log("runs", rec)
            self.alert(self.summary(rec))
            return rec

    def ai_call(self, asof) -> str:
        p = settings.DIRS["ai_calls"] / "active.json"
        if not p.exists():
            return "AI-Layer: aus, kein Call"
        return "AI-Layer: aus – gespeicherter Call nur protokolliert"

    def plan(self, st: dict, d: dict) -> dict:
        st = json.loads(json.dumps(st))                     # Kopie, erst bei Erfolg speichern
        asof = d["asof"]
        day = str(asof.date())
        eq, last_eq = self.b.equity(), self.b.last_equity()
        st["hwm"] = max(st["hwm"] or eq, eq)
        rs = risk.assess(eq, last_eq, st["hwm"], st["borrow_blocked"], self.pause_file, persist=not self.dry)
        st["borrow_blocked"] = rs.borrow_blocked
        orders, cancels, targets = [], [], {}
        tag = lambda sym, side, comp: f"{asof:%Y%m%d}-{sym}-{side}-{comp}"[:48]

        # Sleeves
        active_w = 0.0
        for sl_cfg in self.cfg["sleeves"]:
            sid, sym = sl_cfg["id"], sl_cfg["ticker"]
            sl, sig = st["sleeves"][sid], d["sleeves"][sid]
            comp = "dip" if sl_cfg["kind"] == "dip" else "brk"
            if sl["status"] == "in_trade":
                sl["hold_days"] += 1
                reason = ("exit" if sig["exit"] else
                          "time" if sig["max_hold"] and sl["hold_days"] >= sig["max_hold"] else None)
                if reason or not sl_cfg.get("enabled", True):
                    if sl["stop_cid"]:
                        cancels.append(sl["stop_cid"])
                    orders.append({"cid": tag(sym, "sell", comp), "symbol": sym, "side": "sell", "qty": sl["shares"],
                                   "price": d["closes"][sym], "component": sid, "reason": reason or "disabled"})
                    sl["status"] = "pending_exit"
                else:
                    active_w += sl["size"] or sl_cfg["weight"]
            elif (sl["status"] == "flat" and sl["exit_date"] != day and sig["entry"]
                  and sl_cfg.get("enabled", True) and rs.allow_new_sleeves):
                size = sl_cfg["weight"] * (0.5 if self.cfg.get("vol_sizing_half") and sig["vol_high"] else 1.0)
                qty = math.floor(size * eq / d["closes"][sym])
                if qty > 0:
                    orders.append({"cid": tag(sym, "buy", comp), "symbol": sym, "side": "buy", "qty": qty,
                                   "price": d["closes"][sym], "component": sid, "reason": "entry",
                                   "target_value": size * eq})
                    sl.update(status="pending_entry", size=size)
                    active_w += size
            elif sl["status"] == "flat" and sig["entry"] and not rs.allow_new_sleeves:
                rs.reasons.append(f"{sym}-Einstieg blockiert")

        # Core
        core_w = self.cfg["core"]["weight"]
        if rs.borrow_blocked:
            core_w = max(0.0, core_w - active_w)
        if d["core_on"] is not None:
            tgt_sym = d["core_symbol"]
            hold = st["core"]["holdings"]
            for sym, q in hold.items():
                if sym != tgt_sym and q:
                    orders.append({"cid": tag(sym, "sell", "core"), "symbol": sym, "side": "sell", "qty": q,
                                   "price": d["closes"][sym], "component": "core", "reason": "switch"})
            px = d["closes"][tgt_sym]
            tgt_q = math.floor(core_w * eq / px)
            cur = hold.get(tgt_sym, 0)
            delta = tgt_q - cur
            switching = any(q and s != tgt_sym for s, q in hold.items())
            if delta and (switching or cur == 0 or abs(delta * px) > 0.05 * tgt_q * px):
                orders.append({"cid": tag(tgt_sym, "buy" if delta > 0 else "sell", "core"), "symbol": tgt_sym,
                               "side": "buy" if delta > 0 else "sell", "qty": abs(delta), "price": px,
                               "component": "core", "reason": "rebalance" if cur else "enter",
                               "target_value": core_w * eq})
            targets[tgt_sym] = core_w * eq
        for sl_cfg in self.cfg["sleeves"]:
            sl = st["sleeves"][sl_cfg["id"]]
            if sl["status"] in ("in_trade", "pending_entry"):
                targets[sl_cfg["ticker"] + ":" + sl_cfg["id"]] = (sl["size"] or sl_cfg["weight"]) * eq

        errs = risk.check_orders(orders, eq, self.s["portfolio"]["max_gross"], self.s["risk"]["order_tolerance"])
        errs += risk.check_gross(targets, eq, self.s["portfolio"]["max_gross"])
        if errs:
            raise Abort("Risiko-Prüfung: " + "; ".join(errs))
        st["pending"] = [{k: o[k] for k in ("cid", "symbol", "side", "qty", "component")} for o in orders]
        return {"orders": orders, "cancels": cancels, "state": st, "equity": eq,
                "risk": {"day_change": rs.day_change, "drawdown": rs.drawdown, "reasons": rs.reasons,
                         "allow_new_sleeves": rs.allow_new_sleeves, "borrow_blocked": rs.borrow_blocked}}

    def send(self, orders, cancels) -> list:
        for cid in cancels:
            o = self.b.get_order(cid)
            if o and o["status"] in ("new", "accepted", "held"):
                self.b.cancel(o["id"])
        sent = []
        for o in orders:
            if self.b.get_order(o["cid"]):              # schon vorhanden -> nie doppelt
                continue
            self.b.submit_moo(o["symbol"], o["qty"], o["side"], o["cid"])
            _log("orders", {**o, "sent": dt.datetime.now().isoformat(timespec="seconds")})
            sent.append(o["cid"])
        return sent

    # ---- Morgen
    def morning(self, today=None) -> dict:
        today = pd.Timestamp(today or dt.datetime.now(NY).date())
        with Lock():
            st = load_state(self.path, self.cfg)
            notes, keep = [], []
            for p in st["pending"]:
                o = self.b.get_order(p["cid"])
                status = o["status"] if o else "missing"
                if status in ("accepted", "new", "pending_new", "held"):
                    keep.append(p)
                    continue
                if status != "filled":
                    notes.append(f"⚠️ Order {p['cid']} {status}")
                    if p["component"] != "core":
                        sl = st["sleeves"][p["component"]]
                        sl["status"] = "flat" if p["side"] == "buy" else "in_trade"
                    continue
                px, q = o["filled_avg_price"], o["filled_qty"]
                if p["component"] == "core":
                    h = st["core"]["holdings"]
                    h[p["symbol"]] = h.get(p["symbol"], 0) + (q if p["side"] == "buy" else -q)
                    if not h[p["symbol"]]:
                        del h[p["symbol"]]
                    notes.append(f"Core {p['side']} {q} {p['symbol']} @ {px:.2f}")
                else:
                    sl = st["sleeves"][p["component"]]
                    if p["side"] == "buy":
                        sl.update(status="in_trade", shares=q, entry_px=px, entry_date=str(today.date()),
                                  hold_days=0, stop_cid=None)
                    else:
                        sl.update(status="flat", shares=0, exit_date=str(today.date()), stop_cid=None)
                    notes.append(f"Sleeve {p['side']} {q} {p['symbol']} @ {px:.2f}")
            st["pending"] = keep
            open_ids = {o["cid"] for o in self.b.open_orders()}
            for sid, sl in st["sleeves"].items():
                if sl["status"] != "in_trade":
                    continue
                if sl["stop_cid"] in open_ids:
                    continue
                if sl["stop_cid"] and (o := self.b.get_order(sl["stop_cid"])) and o["status"] == "filled":
                    continue                                   # Reconcile verbucht das am Abend
                kind = next(s["kind"] for s in self.cfg["sleeves"] if s["id"] == sid)
                pct = self.s["risk"]["dip_stop_pct"] if kind == "dip" else self.s["risk"]["breakout_stop_pct"]
                stop = round(sl["entry_px"] * (1 - pct), 2)
                cid = f"{today:%Y%m%d}-{sl['symbol']}-stop-{kind[:3]}"[:48]
                if not self.dry and not self.b.get_order(cid):
                    self.b.submit_stop(sl["symbol"], sl["shares"], stop, cid)
                sl["stop_cid"] = cid
                notes.append(f"Stop gesetzt: {sl['symbol']} {sl['shares']} @ {stop:.2f}")
            st["last_morning"] = str(today.date())
            if not self.dry:
                save_state(st, self.path)
            rec = {"date": today, "notes": notes, "pending_left": len(keep)}
            _log("morning", rec)
            if notes:
                self.alert("☀️ Morgen-Check " + str(today.date()) + "\n" + "\n".join(notes))
            return rec

    def summary(self, r) -> str:
        lines = [f"🌙 Abend-Lauf {pd.Timestamp(r['asof']).date()}{' (DRY-RUN)' if r['dry'] else ''}",
                 f"Engine {self.cfg['core']['engine']} {'über' if r['core_on'] else 'unter'} 200-Tage-Linie "
                 f"→ Core hält morgen {r['core_symbol']}",
                 f"Equity ${r['equity']:,.0f} · Tagesänderung {r['risk']['day_change']:+.2%}"]
        for o in r["orders"]:
            lines.append(f"• {o['side'].upper()} {o['qty']} {o['symbol']} ({o['component'].split(':')[-1]}, {o['reason']})")
        if not r["orders"]:
            lines.append("• keine Orders")
        lines += [f"⚠️ {x}" for x in r["risk"]["reasons"]]
        return "\n".join(lines)


# ------------------------------------------------------------------ CLI
def flatten(broker, state_path=STATE_PATH) -> list:
    """Alles verkaufen (zum nächsten Open) + PAUSE. Stops werden storniert."""
    risk.pause("flatten: alles verkauft")
    st = load_state(state_path)
    for o in broker.open_orders():
        broker.cancel(o["id"])
    today = dt.datetime.now(NY).date()
    out = []
    for sym, q in broker.positions().items():
        cid = f"{today:%Y%m%d}-{sym}-sell-flat"[:48]
        if not broker.get_order(cid):
            broker.submit_moo(sym, q, "sell", cid)
        out.append((sym, q))
    st["pending"] = []
    st["core"]["holdings"] = {}
    for sl in st["sleeves"].values():
        sl.update(status="flat", shares=0, stop_cid=None, exit_date=str(today))
    save_state(st, state_path)
    return out


def _in_window() -> bool:
    b = settings.load()["broker"]
    now = dt.datetime.now(NY).strftime("%H:%M")
    return b["evening_run_after"] <= now <= b["evening_run_before"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Trading-Bot (nur Paper)")
    ap.add_argument("cmd", choices=["evening", "morning", "status", "pause", "resume", "flatten", "check-keys"])
    ap.add_argument("--dry-run", action="store_true", help="alles berechnen, nichts senden/speichern")
    ap.add_argument("--asof", help="als ob heute dieses Datum wäre (nur mit --dry-run oder --sim)")
    ap.add_argument("--sim", action="store_true", help="simuliertes Paper-Konto statt Alpaca")
    a = ap.parse_args(argv)
    from .broker import AlpacaBroker, SimBroker, check_keys

    if a.cmd == "check-keys":
        for k, v in check_keys().items():
            print(f"{k:20s} {'gesetzt' if v else 'FEHLT'}")
        return
    if a.cmd == "pause":
        print(risk.pause())
        return
    if a.cmd == "resume":
        print(risk.resume())
        return
    if a.cmd == "status":
        st = load_state()
        print(json.dumps({"core": st["core"], "sleeves": st["sleeves"], "last_run": st["last_run"],
                          "pause": risk.PAUSE_FILE.exists()}, indent=2, default=str))
        return

    cfg = load_config()
    if a.sim:
        prices = data.load_all(needed_tickers(cfg))
        broker = SimBroker(prices, cash=cfg["starting_cash"])
        asof = pd.Timestamp(a.asof) if a.asof else prices["SPY"].index[-1]
        broker.date = asof
        bot = Bot(broker, lambda d: prices, state_path=settings.DIRS["live"] / "state_sim.json",
                  dry_run=True, alerts=False, cfg=cfg)
        print(bot.summary(bot.evening(asof)))
        return
    broker = AlpacaBroker()
    if a.cmd == "flatten":
        print("Verkauf zum nächsten Open:", flatten(broker))
        return
    if a.asof and not a.dry_run:
        raise SystemExit("--asof nur zusammen mit --dry-run")
    if a.cmd == "evening" and not a.dry_run and not _in_window():
        raise SystemExit("Echter Abend-Lauf nur zwischen 19:05 und 23:59 New York (Alpaca nimmt MOO erst ab 19:00).")
    prices_fn = (lambda d: data.load_all(needed_tickers(cfg))) if a.asof else (lambda d: live_prices(cfg))
    bot = Bot(broker, prices_fn, dry_run=a.dry_run, cfg=cfg)
    if a.cmd == "evening":
        r = bot.evening(a.asof)
        print(bot.summary(r) if "orders" in r else r["status"])
    else:
        print(bot.morning())


if __name__ == "__main__":
    main()
