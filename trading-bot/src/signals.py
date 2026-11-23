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


def core_size(close: pd.Series, vol_target: float | None, window: int = 20, min_w: float = 0.1) -> pd.Series:
    """Risiko-Steuerung: Anteil des Kontos im Core-Asset = Vola-Ziel / 20-Tage-Vola, begrenzt auf
    [min_w, 1]. Ohne vol_target immer 1.0. Getestet: Ziel 15 % (Training R/DD 0.63 statt 0.48)."""
    if not vol_target:
        return pd.Series(1.0, index=close.index)
    vol = close.pct_change().rolling(window, min_periods=window).std() * (252 ** 0.5)
    return (vol_target / vol).clip(min_w, 1.0)


CORE_NEIGHBORS = [
    ("sma", 100), ("sma", 150), ("sma", 250), ("ema", 200), ("cross", 200),
]


# ------------------------------------------------------------------ Sleeves
# Sleeve-Typen. "snaps" = Mean-Reversion (passt zu Label snaps_back),
# "trend" = Momentum (passt zu keeps_going). dip/breakout aus dem Video, ibs/down3/mom
# sind zusätzliche Ideen (Prompt 4B) und müssen dieselben Gates bestehen.
KINDS = {
    "dip":      {"family": "snaps", "fits": "snaps_back"},   # RSI(2) < a, raus über SMA b / 10 Tage
    "ibs":      {"family": "snaps", "fits": "snaps_back"},   # Schluss im unteren a % der Tagesspanne, raus über Vortageshoch / b Tage
    "down3":    {"family": "snaps", "fits": "snaps_back"},   # a tiefere Schlusskurse in Folge, raus über SMA b / 10 Tage
    "breakout": {"family": "trend", "fits": "keeps_going"},  # neues a-Tage-Hoch, raus bei b-Tage-Tief / unter SMA200
    "mom":      {"family": "trend", "fits": "keeps_going"},  # Schluss erobert SMA a zurück (SMA a > SMA200), raus unter SMA b
}


@dataclass(frozen=True)
class SleeveRule:
    kind: str
    a: int
    b: int
    trend: int = 200

    @property
    def family(self) -> str:
        return KINDS[self.kind]["family"]

    @property
    def name(self) -> str:
        return {"dip": f"dip_rsi{self.a}_sma{self.b}", "breakout": f"brk_hi{self.a}_lo{self.b}",
                "ibs": f"ibs{self.a}_h{self.b}", "down3": f"down{self.a}_sma{self.b}",
                "mom": f"mom{self.a}_x{self.b}"}[self.kind]

    def entry(self, df: pd.DataFrame) -> pd.Series:
        c = df["close"]
        m = sma(c, self.trend)
        up = c > m
        if self.kind == "dip":
            sig = (rsi(c, 2) < self.a) & up
        elif self.kind == "breakout":
            sig = (c >= c.rolling(self.a, min_periods=self.a).max()) & up
        elif self.kind == "ibs":
            rng = (df["high"] - df["low"]).replace(0, float("nan"))
            sig = ((c - df["low"]) / rng < self.a / 100) & up
        elif self.kind == "down3":
            lower = (c < c.shift(1)).astype(int)
            sig = (lower.rolling(self.a, min_periods=self.a).sum() == self.a) & up
        else:  # mom
            f = sma(c, self.a)
            sig = (c > f) & (c.shift(1) <= f.shift(1)) & (f > m)
        return sig.where(m.notna(), False).fillna(False).astype(bool)

    def exit(self, df: pd.DataFrame) -> pd.Series:
        c = df["close"]
        if self.kind in ("dip", "down3"):
            return (c > sma(c, self.b)).fillna(False)
        if self.kind == "ibs":
            return (c > df["high"].shift(1)).fillna(False)
        if self.kind == "breakout":
            low = c <= c.rolling(self.b, min_periods=self.b).min()
            return (low | (c < sma(c, self.trend))).fillna(False)
        return (c < sma(c, self.b)).fillna(False)  # mom

    @property
    def max_hold(self) -> int | None:
        return {"dip": 10, "down3": 10, "ibs": self.b}.get(self.kind)

    def stop_pct(self, s: dict) -> float:
        return s["risk"]["dip_stop_pct"] if self.family == "snaps" else s["risk"]["breakout_stop_pct"]

    def neighbors(self) -> list["SleeveRule"]:
        k, a, b = self.kind, self.a, self.b
        if k == "dip":
            return [SleeveRule(k, 5, b), SleeveRule(k, 15, b), SleeveRule(k, a, 3), SleeveRule(k, a, 10)]
        if k == "breakout":
            return [SleeveRule(k, 20, b), SleeveRule(k, 100, b)]
        if k == "ibs":
            return [SleeveRule(k, 10, b), SleeveRule(k, 30, b), SleeveRule(k, a, 3), SleeveRule(k, a, 8)]
        if k == "down3":
            return [SleeveRule(k, 2, b), SleeveRule(k, 4, b), SleeveRule(k, a, 3), SleeveRule(k, a, 10)]
        return [SleeveRule(k, 10, b), SleeveRule(k, 30, b), SleeveRule(k, a, 30), SleeveRule(k, a, 100)]


BASE_SLEEVES = {"dip": SleeveRule("dip", 10, 5), "breakout": SleeveRule("breakout", 50, 20),
                "ibs": SleeveRule("ibs", 20, 5), "down3": SleeveRule("down3", 3, 5),
                "mom": SleeveRule("mom", 20, 50)}
FITS = {k: v["fits"] for k, v in KINDS.items()}
KIND_DE = {"dip": "Dip-Buy (RSI)", "breakout": "Breakout", "ibs": "Schwacher Schluss (IBS)",
           "down3": "3 Tage runter", "mom": "Trend-Rückeroberung"}


def rule_from_dict(d: dict) -> SleeveRule:
    return SleeveRule(d["kind"], int(d["a"]), int(d["b"]), int(d.get("trend", 200)))


def rule_to_dict(r: SleeveRule) -> dict:
    return {"kind": r.kind, "a": r.a, "b": r.b, "trend": r.trend}
