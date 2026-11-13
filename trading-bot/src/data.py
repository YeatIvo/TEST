"""Daten: lädt Tagesbalken einmal und friert sie in data/research/ ein.

Jeder Backtest liest diese eingefrorene Kopie (`load_research`). Der Bot
benutzt später `download(..., dest='live')`, damit sich Forschungsresultate
nie verändern.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pandas as pd

from . import settings

COLS = ["open", "high", "low", "close", "volume"]


def _fname(ticker: str) -> str:
    return ticker.replace("^", "_").replace("/", "_") + ".csv"


def fetch(ticker: str, start: str, end: str | None = None) -> pd.DataFrame:
    s = settings.load()["data"]
    if s["source"] == "files":
        return read_csv(settings.DIRS["research"] / _fname(ticker))
    import yfinance as yf

    df = yf.download(ticker, start=start, end=end, interval=s["bar_size"],
                     auto_adjust=s["adjusted"], progress=False, threads=False)
    if df.empty:
        raise RuntimeError(f"Keine Daten für {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[COLS]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df.index.name = "date"
    return df.dropna(subset=["open", "close"])


def read_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    return df[COLS]


def freeze_research() -> dict:
    """Lädt alle Studien-Ticker und schreibt sie + Manifest nach data/research/."""
    s = settings.load()
    out = settings.DIRS["research"]
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"downloaded": dt.date.today().isoformat(), "tickers": {}}
    for t in s["universe"]["study_tickers"]:
        df = fetch(t, s["data"]["history_start"])
        # unvollständigen heutigen Balken nie einfrieren
        df = df[df.index.date < dt.date.today()]
        p = out / _fname(t)
        df.round(6).to_csv(p)
        manifest["tickers"][t] = {
            "rows": len(df), "first": str(df.index[0].date()), "last": str(df.index[-1].date()),
            "sha": hashlib.sha256(p.read_bytes()).hexdigest()[:10],
        }
        print(f"  {t:8s} {len(df):5d} Zeilen  {df.index[0].date()} .. {df.index[-1].date()}")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def manifest() -> dict:
    return json.loads((settings.DIRS["research"] / "manifest.json").read_text())


def research_end() -> dt.date:
    """Letztes Datum der eingefrorenen Daten = Ende des Lock-Fensters."""
    return min(dt.date.fromisoformat(v["last"]) for k, v in manifest()["tickers"].items()
               if k not in settings.load()["universe"]["crypto_tickers"])


def load_research(ticker: str) -> pd.DataFrame:
    return read_csv(settings.DIRS["research"] / _fname(ticker))


def load_all(tickers: list[str] | None = None) -> dict[str, pd.DataFrame]:
    tickers = tickers or settings.load()["universe"]["study_tickers"]
    return {t: load_research(t) for t in tickers}


if __name__ == "__main__":
    print("Lade Forschungsdaten …")
    freeze_research()
