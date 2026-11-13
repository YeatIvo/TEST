"""Indikatoren + Regime. Alles nutzt nur Daten bis einschliesslich Tag t."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 2) -> pd.Series:
    """Wilder-RSI (0–100). RSI(2) < 10 = zwei harte Abwärtstage."""
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(dn != 0, 100.0)


def trend_up(close: pd.Series, n: int = 200) -> pd.Series:
    """Regime 1: True = Kurs über seinem n-Tage-Schnitt (Uptrend). NaN in der Anlaufphase."""
    m = sma(close, n)
    return (close > m).where(m.notna())


def realized_vol(close: pd.Series, n: int = 20) -> pd.Series:
    return close.pct_change().rolling(n, min_periods=n).std() * np.sqrt(252)


def vol_high(close: pd.Series, n: int = 20, lookback: int = 252) -> pd.Series:
    """Regime 2: True = heutige 20-Tage-Vola über ihrem 1-Jahres-Median (volatil)."""
    v = realized_vol(close, n)
    med = v.rolling(lookback, min_periods=lookback // 2).median()
    return (v > med).where(med.notna())
