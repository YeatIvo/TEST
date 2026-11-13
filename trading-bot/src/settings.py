"""Lädt config/settings.toml – die einzige Quelle für alle Einstellungen."""
from __future__ import annotations

import datetime as dt
import tomllib
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = ROOT / "config" / "settings.toml"

DIRS = {
    "data": ROOT / "data",
    "research": ROOT / "data" / "research",
    "live": ROOT / "data" / "live",
    "results": ROOT / "results",
    "reports": ROOT / "reports",
    "rules": ROOT / "rules",
    "logs": ROOT / "logs",
    "ai_calls": ROOT / "ai_calls",
    "dashboard": ROOT / "dashboard",
}


@lru_cache(maxsize=1)
def load() -> dict:
    with SETTINGS_PATH.open("rb") as f:
        return tomllib.load(f)


def window(name: str) -> tuple[dt.date, dt.date]:
    """('train'|'lock') -> (start, end) als Datum. 'today' wird aufgelöst."""
    w = load()["windows"]
    start = dt.date.fromisoformat(w[f"{name}_start"])
    end_raw = w[f"{name}_end"]
    end = dt.date.today() if end_raw == "today" else dt.date.fromisoformat(end_raw)
    return start, end


def cost_per_side(ticker: str) -> float:
    s = load()
    if ticker in s["universe"]["crypto_tickers"]:
        return s["costs"]["per_side_crypto"]
    return s["costs"]["per_side_etf"]


def tradable_tickers() -> list[str]:
    u = load()["universe"]
    return [t for t in u["study_tickers"] if t not in u["not_tradable"]]
