"""Risiko-Limits (Prompt 8 + 8B). Sie ändern nie eine Regel – sie können den Bot
nur WENIGER tun lassen.

  * PAUSE-Datei      -> keine neuen Sleeve-Trades, kein neues Leihen. Core + Exits laufen weiter.
  * Tagesverlust >3 % -> heute Abend keine neuen Sleeve-Trades (löst sich am Folgetag).
  * Tagesverlust >5 % -> Bot legt PAUSE an und meldet sich; erst "resume" hebt sie auf.
  * Leih-Stopp       -> Drawdown vom Hoch schlimmer als der schlimmste Backtest-DD:
                        kein Margin mehr, neue Sleeves werden aus dem Core finanziert.
                        Wieder frei, wenn der DD unter die Hälfte davon fällt.
  * Order-Prüfung    -> keine Order > 105 % ihres Ziels, Summe der Ziele <= max_gross.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from . import settings

PAUSE_FILE = settings.ROOT / "PAUSE"


def worst_backtest_dd() -> float:
    p = settings.DIRS["results"] / "account.json"
    if p.exists():
        return abs(json.loads(p.read_text())["all"]["maxdd"])
    return 0.30


@dataclass
class RiskState:
    paused: bool
    day_block: bool
    bad_day: bool
    borrow_blocked: bool
    day_change: float
    drawdown: float
    reasons: list

    @property
    def allow_new_sleeves(self) -> bool:
        return not (self.paused or self.day_block or self.bad_day)


def assess(equity: float, last_equity: float, hwm: float, borrow_blocked_before: bool,
           pause_file=None, persist: bool = True) -> RiskState:
    pause_file = pause_file or PAUSE_FILE
    r = settings.load()["risk"]
    change = equity / last_equity - 1 if last_equity else 0.0
    dd = equity / hwm - 1 if hwm else 0.0
    worst = worst_backtest_dd()
    reasons = []
    bad = change <= -r["bad_day_pause_pct"]
    if bad and persist and not pause_file.exists():
        pause_file.write_text(f"Automatisch: Tagesverlust {change:.1%}. 'resume' zum Aufheben.\n")
        reasons.append(f"Tagesverlust {change:.1%} > {r['bad_day_pause_pct']:.0%}: PAUSE angelegt")
    day_block = change <= -r["daily_loss_block_pct"]
    if day_block:
        reasons.append(f"Tagesverlust {change:.1%}: heute keine neuen Sleeve-Trades")
    if borrow_blocked_before:
        borrow = abs(dd) > worst / 2
    else:
        borrow = abs(dd) > worst
    if borrow:
        reasons.append(f"Drawdown {dd:.1%} (schlimmster Backtest {worst:.1%}): kein Margin")
    paused = pause_file.exists() or (bad and not persist)
    if paused:
        reasons.append("PAUSE aktiv: keine neuen Sleeves, kein neues Leihen")
    return RiskState(paused, day_block, bad, borrow, change, dd, reasons)


def check_orders(orders: list[dict], equity: float, max_gross: float, tolerance: float) -> list[str]:
    """orders: {symbol, qty, side, price, target_value}. Gibt Fehler zurück (leer = ok)."""
    errs = []
    for o in orders:
        val = o["qty"] * o["price"]
        if o["side"] == "buy" and o.get("target_value") is not None and val > o["target_value"] * tolerance + 1e-6:
            errs.append(f"{o['symbol']}: Order ${val:,.0f} > {tolerance:.0%} des Ziels ${o['target_value']:,.0f}")
    return errs


def check_gross(target_values: dict, equity: float, max_gross: float) -> list[str]:
    gross = sum(abs(v) for v in target_values.values()) / equity if equity else 0
    return [f"Ziel-Exposure {gross:.0%} > Maximum {max_gross:.0%}"] if gross > max_gross + 1e-6 else []


def pause(reason: str = "manuell") -> str:
    PAUSE_FILE.write_text(f"{reason}\n")
    return "PAUSE angelegt: ab dem nächsten Abend-Lauf keine neuen Sleeve-Trades, kein neues Leihen."


def resume() -> str:
    if PAUSE_FILE.exists():
        PAUSE_FILE.unlink()
        return "PAUSE aufgehoben: der nächste Abend-Lauf handelt wieder normal."
    return "Es war keine PAUSE aktiv."
