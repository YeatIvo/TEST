"""Signal-Datei: jede Regel steht hier genau EINMAL.
Backtest UND Live-Bot lesen von hier – so handelt der Bot exakt, was getestet wurde.
Alle Funktionen nutzen nur Daten bis einschliesslich Tag t.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .indicators import ema, rsi, sma


# ------------------------------------------------------------------ Core
def trend_switch(close: pd.Series, kind: str = "sma", n: int = 200, fast: int = 50) -> pd.Series:
    """True = Engine halten, False = sicheres Asset. NaN in der Anlaufphase.
    kind: 'sma' (Schluss > SMA n), 'ema' (Schluss > EMA n), 'cross' (SMA fast > SMA n)."""
    if kind == "sma":
        m = sma(close, n)
        out = close > m
    elif kind == "ema":
        m = ema(close, n)
        out = close > m
    elif kind == "cross":
        m = sma(close, n)
        out = sma(close, fast) > m
    else:
        raise ValueError(kind)
    return out.where(m.notna())


CORE_NEIGHBORS = [
    ("sma", 100), ("sma", 150), ("sma", 250), ("ema", 200), ("cross", 200),
]


# ------------------------------------------------------------------ Sleeves
@dataclass(frozen=True)
class SleeveRule:
    kind: str                 # 'dip' | 'breakout'
    a: int                    # dip: RSI-Schwelle | breakout: Hoch-Fenster
    b: int                    # dip: SMA-Ausstieg | breakout: Tief-Fenster
    trend: int = 200

    @property
    def name(self) -> str:
        return (f"dip_rsi{self.a}_sma{self.b}" if self.kind == "dip"
                else f"brk_hi{self.a}_lo{self.b}")

    def entry(self, df: pd.DataFrame) -> pd.Series:
        c = df["close"]
        m = sma(c, self.trend)
        up = c > m
        if self.kind == "dip":
            sig = (rsi(c, 2) < self.a) & up
        else:
            sig = (c >= c.rolling(self.a, min_periods=self.a).max()) & up
        return sig.where(m.notna(), False).astype(bool)

    def exit(self, df: pd.DataFrame) -> pd.Series:
        c = df["close"]
        if self.kind == "dip":
            return (c > sma(c, self.b)).fillna(False)
        low = c <= c.rolling(self.b, min_periods=self.b).min()
        return (low | (c < sma(c, self.trend))).fillna(False)

    @property
    def max_hold(self) -> int | None:
        return 10 if self.kind == "dip" else None

    def stop_pct(self, s: dict) -> float:
        return s["risk"]["dip_stop_pct"] if self.kind == "dip" else s["risk"]["breakout_stop_pct"]

    def neighbors(self) -> list["SleeveRule"]:
        if self.kind == "dip":
            return [SleeveRule("dip", 5, self.b), SleeveRule("dip", 15, self.b),
                    SleeveRule("dip", self.a, 3), SleeveRule("dip", self.a, 10)]
        return [SleeveRule("breakout", 20, self.b), SleeveRule("breakout", 100, self.b)]


BASE_SLEEVES = {"dip": SleeveRule("dip", 10, 5), "breakout": SleeveRule("breakout", 50, 20)}
FITS = {"dip": "snaps_back", "breakout": "keeps_going"}


def rule_from_dict(d: dict) -> SleeveRule:
    return SleeveRule(d["kind"], int(d["a"]), int(d["b"]), int(d.get("trend", 200)))


def rule_to_dict(r: SleeveRule) -> dict:
    return {"kind": r.kind, "a": r.a, "b": r.b, "trend": r.trend}
