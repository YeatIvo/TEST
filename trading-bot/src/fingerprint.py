"""Fingerprint: eine Zeile, die zeigt, ob dein Setup identisch zur Referenz ist.

Gleiche Settings -> gleicher Hash. Ändert sich ein Ticker, ein Fenster oder
ein Kostensatz, ändert sich der Hash. Spätere Phasen hängen ihre eigenen
Kennzahlen (z. B. Anzahl Datenzeilen) an.
"""
from __future__ import annotations

import hashlib
import json

from . import settings


def settings_hash() -> str:
    canon = json.dumps(settings.load(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:10]


def line() -> str:
    s = settings.load()
    w = s["windows"]
    u = s["universe"]
    return (
        f"FINGERPRINT A | settings={settings_hash()} | bar={s['data']['bar_size']} "
        f"| tickers={len(u['study_tickers'])} tradable={len(settings.tradable_tickers())} "
        f"| train={w['train_start']}..{w['train_end']} lock={w['lock_start']}..{w['lock_end']} "
        f"| cash={s['portfolio']['starting_cash']:.0f} cost={s['costs']['per_side_etf']}"
    )


if __name__ == "__main__":
    print(line())
