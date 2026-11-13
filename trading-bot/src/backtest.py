"""Phase P – Backtester.

Grundregeln (aus den Hausregeln):
  * Signal am Schluss von Tag t  ->  Ausführung zum Open von Tag t+1.
  * Kosten pro Seite auf jeden gehandelten Betrag.
  * Stops liegen beim Broker: Fällt das Tief unter den Stop, wird zum Stop
    verkauft; eröffnet der Kurs schon darunter (Gap), zum Open.
  * `guard()` prüft, dass ein Signal nie in die Zukunft schaut.
  * `lock_once()` sorgt dafür, dass ein Lock-Test pro Idee nur EINMAL läuft.

Zwei Simulatoren:
  simulate_trades  – eine Regel auf einem Ticker (Sleeves), Rendite je Slot.
  simulate_weights – Zielgewichte über mehrere Ticker (Core-Rotation).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from . import settings


class LookAheadError(RuntimeError):
    pass


# ------------------------------------------------------------------ Trades
@dataclass
class TradeResult:
    daily: pd.Series                 # Tagesrendite des Slots (0 wenn flach)
    in_trade: pd.Series              # True an Tagen mit Position (Close)
    trades: pd.DataFrame = field(default_factory=pd.DataFrame)


def simulate_trades(df: pd.DataFrame, entry: pd.Series, exit_sig: pd.Series | None,
                    cost: float, stop_pct: float | None = None, max_hold: int | None = None,
                    allowed: pd.Series | None = None) -> TradeResult:
    """Simuliert eine Long-Regel. entry/exit_sig: bool je Tag (am Schluss bekannt).

    allowed: optional bool je Tag – Einstiege nur, wenn True; endet `allowed`,
    wird zum nächsten Open verkauft (für Quartals-Re-Pick).
    """
    idx = df.index
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    ent = entry.reindex(idx).fillna(False).to_numpy(bool)
    ext = (exit_sig.reindex(idx).fillna(False).to_numpy(bool) if exit_sig is not None
           else np.zeros(len(idx), bool))
    alw = (allowed.reindex(idx).fillna(False).to_numpy(bool) if allowed is not None
           else np.ones(len(idx), bool))
    n = len(idx)
    r = np.zeros(n)
    held = np.zeros(n, bool)
    trades = []
    pos = pend_in = pend_out = False
    entry_px = stop = 0.0
    entry_i = hold = 0

    for j in range(0, n):
        exited_today = False
        if j == 0:
            pass                                      # Tag 0: nur Entscheidung am Schluss
        elif pend_in:                                 # Kauf zum Open
            pos, pend_in = True, False
            entry_px, entry_i, hold = o[j], j, 0
            stop = entry_px * (1 - stop_pct) if stop_pct else -np.inf
            if l[j] <= stop:                          # Stop am Einstiegstag
                px = stop
                r[j] = px / entry_px - 1 - 2 * cost
                trades.append((idx[entry_i], idx[j], entry_px, px, "stop"))
                pos, exited_today = False, True
            else:
                r[j] = (1 - cost) * c[j] / entry_px - 1
        elif pos and pend_out:                        # Verkauf zum Open
            px = o[j]
            r[j] = (1 - cost) * px / c[j - 1] - 1
            trades.append((idx[entry_i], idx[j], entry_px, px, reason))
            pos = pend_out = False
            exited_today = True
        elif pos:
            if o[j] <= stop:                          # Gap unter Stop
                r[j] = (1 - cost) * o[j] / c[j - 1] - 1
                trades.append((idx[entry_i], idx[j], entry_px, o[j], "stop"))
                pos, exited_today = False, True
            elif l[j] <= stop:
                r[j] = (1 - cost) * stop / c[j - 1] - 1
                trades.append((idx[entry_i], idx[j], entry_px, stop, "stop"))
                pos, exited_today = False, True
            else:
                r[j] = c[j] / c[j - 1] - 1

        # ---- Entscheidungen am Schluss von Tag j (wirken am Open j+1)
        if pos:
            held[j] = True
            hold += 1
            if not alw[j] or (j + 1 < n and not alw[j + 1]):
                pend_out, reason = True, "deselected"
            elif ext[j]:
                pend_out, reason = True, "exit"
            elif max_hold and hold >= max_hold:
                pend_out, reason = True, "time"
        elif not exited_today and ent[j] and j + 1 < n and alw[j + 1]:
            pend_in = True

    tr = pd.DataFrame(trades, columns=["entry_date", "exit_date", "entry_px", "exit_px", "reason"])
    if len(tr):
        tr["ret"] = tr["exit_px"] / tr["entry_px"] * (1 - cost) ** 2 - 1
    return TradeResult(pd.Series(r, idx), pd.Series(held, idx), tr)


# ------------------------------------------------------------------ Gewichte
def simulate_weights(prices: dict[str, pd.DataFrame], weights: pd.DataFrame,
                     costs: dict[str, float]) -> pd.Series:
    """weights: Zielgewicht je Ticker am Schluss von Tag t -> gehalten ab Open t+1."""
    idx = weights.index
    w = weights.fillna(0.0)
    held = w.shift(1).fillna(0.0)         # ab Open heute gültig
    prev = held.shift(1).fillna(0.0)      # bis Open heute gültig
    night = pd.Series(0.0, index=idx)   # Gestern-Schluss -> heute-Open, alte Gewichte
    trade = pd.Series(0.0, index=idx)   # Umschichtung zum Open (Kosten)
    day = pd.Series(0.0, index=idx)     # Open -> Schluss, neue Gewichte
    for t in w.columns:
        p = prices[t].reindex(idx)
        o, c = p["open"], p["close"]
        night += prev[t] * (o / c.shift(1) - 1).fillna(0)
        day += held[t] * (c / o - 1).fillna(0)
        trade += costs[t] * (held[t] - prev[t]).abs()
    return (1 + night) * (1 - trade) * (1 + day) - 1


# ------------------------------------------------------------------ Kennzahlen
def equity(daily: pd.Series, start: float = 1.0) -> pd.Series:
    return start * (1 + daily).cumprod()


def max_drawdown(eq: pd.Series) -> float:
    return float((eq / eq.cummax() - 1).min())


def metrics(daily: pd.Series, trades: pd.DataFrame | None = None, days: int = 252) -> dict:
    daily = daily.dropna()
    if daily.empty:
        return {"cagr": np.nan, "maxdd": np.nan, "ret_dd": np.nan, "total": np.nan}
    eq = equity(daily)
    years = len(daily) / days
    total = eq.iloc[-1] - 1
    cagr = eq.iloc[-1] ** (1 / years) - 1 if eq.iloc[-1] > 0 else -1.0
    dd = max_drawdown(eq)
    sd = daily.std()
    m = {"total": total, "cagr": cagr, "maxdd": dd,
         "ret_dd": cagr / abs(dd) if dd < 0 else np.nan,
         "sharpe": daily.mean() / sd * np.sqrt(days) if sd > 0 else np.nan}
    if trades is not None:
        tr = trades["ret"] if len(trades) else pd.Series(dtype=float)
        gains, losses = tr[tr > 0].sum(), -tr[tr < 0].sum()
        m.update(trades=int(len(tr)), win_rate=float((tr > 0).mean()) if len(tr) else np.nan,
                 avg_trade=float(tr.mean()) if len(tr) else np.nan,
                 profit_factor=float(gains / losses) if losses > 0 else (np.inf if gains > 0 else np.nan))
    return m


def window_slice(s: pd.Series, name: str | tuple) -> pd.Series:
    a, b = settings.window(name) if isinstance(name, str) else name
    return s[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]


def trades_in(tr: pd.DataFrame, name: str | tuple) -> pd.DataFrame:
    """Nur Trades, die komplett im Fenster liegen (kein Blick über das Fensterende)."""
    if tr.empty:
        return tr
    a, b = settings.window(name) if isinstance(name, str) else name
    return tr[(tr["entry_date"] >= pd.Timestamp(a)) & (tr["exit_date"] <= pd.Timestamp(b))]


# ------------------------------------------------------------------ Guards
def guard(signal_fn: Callable[[pd.DataFrame], pd.Series], df: pd.DataFrame,
          n_checks: int = 30, seed: int = 7, min_history: int = 260) -> None:
    """Schneidet die Daten an n zufälligen Tagen ab und rechnet das Signal neu.
    Weicht das Signal an diesem Tag ab, hat es Zukunftsdaten benutzt."""
    full = signal_fn(df)
    rng = np.random.default_rng(seed)
    cuts = rng.choice(np.arange(min_history, len(df) - 1), size=min(n_checks, len(df) - min_history - 1),
                      replace=False)
    for k in sorted(cuts):
        part = signal_fn(df.iloc[: k + 1])
        a, b = full.iloc[k], part.iloc[-1]
        if not ((pd.isna(a) and pd.isna(b)) or a == b):
            raise LookAheadError(f"Signal am {df.index[k].date()} ändert sich, wenn die Zukunft fehlt "
                                 f"({a} vs. {b})")


def lock_once(idea_id: str, run: Callable[[], dict]) -> dict:
    """Führt den Lock-Test einer Idee genau einmal aus und speichert das Resultat.
    Ein zweiter Aufruf liefert das gespeicherte Resultat – er rechnet NICHT neu."""
    path = settings.DIRS["results"] / "lock_log.jsonl"
    if path.exists():
        for ln in path.read_text().splitlines():
            rec = json.loads(ln)
            if rec["idea"] == idea_id:
                return rec["result"]
    res = run()
    clean = {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in res.items()}
    with path.open("a") as f:
        f.write(json.dumps({"idea": idea_id, "run": pd.Timestamp.now().isoformat(timespec="seconds"),
                            "result": clean}) + "\n")
    return clean
