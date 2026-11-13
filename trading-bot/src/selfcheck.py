"""Phase P / Schritt 1 – den Backtester selbst testen, bevor wir ihm glauben.

Pass-Bereiche sind VOR dem Lauf festgelegt:
  1. Eingepflanzter Vorteil (+1 % pro Trade, Kosten 0.1 % Rundreise)
     -> Ø Trade muss zwischen +0.6 % und +1.2 % liegen.
  2. Reines Rauschen (kein Vorteil) -> Ø Trade zwischen -0.3 % und +0.1 %.
  3. Schummel-Signal (kennt den morgigen Kurs) -> Guard MUSS abbrechen.
  4. Echte Signale (Trend-Schalter SPY, Dip/Breakout QQQ) -> Guard darf NICHT abbrechen.
"""
from __future__ import annotations

import html
import json

import numpy as np
import pandas as pd

from . import backtest as bt
from . import data, settings, signals

EDGE_RANGE = (0.006, 0.012)
NOISE_RANGE = (-0.003, 0.001)
COST = 0.0005


def fake_prices(n: int = 3000, edge: float = 0.0, flag_rate: float = 0.2, seed: int = 42):
    rng = np.random.default_rng(seed)
    flags = rng.random(n) < flag_rate
    flags[-3:] = False
    step = rng.normal(0.0003, 0.01, n)          # Open(k) -> Open(k+1)
    bumped = np.zeros(n, bool)
    for t in np.where(flags)[0]:
        bumped[t + 1] = True                     # Open(t+1) -> Open(t+2) bekommt +edge
    step = step + edge * bumped
    o = 100 * np.cumprod(np.r_[1, 1 + step[:-1]])
    c = o * (1 + rng.normal(0, 0.003, n))
    idx = pd.bdate_range("2000-01-03", periods=n)
    df = pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.002, "low": np.minimum(o, c) * 0.998,
                       "close": c, "volume": 1e6}, index=idx)
    return df, pd.Series(flags, idx)


def run_trade_test(edge: float) -> dict:
    df, flags = fake_prices(edge=edge)
    res = bt.simulate_trades(df, flags, pd.Series(True, index=df.index), cost=COST)
    return {"trades": len(res.trades), "avg_trade": float(res.trades["ret"].mean())}


def run() -> dict:
    out = {}
    e = run_trade_test(0.01)
    e["pass"] = EDGE_RANGE[0] <= e["avg_trade"] <= EDGE_RANGE[1]
    out["planted_edge"] = e
    nz = run_trade_test(0.0)
    nz["pass"] = NOISE_RANGE[0] <= nz["avg_trade"] <= NOISE_RANGE[1]
    out["pure_noise"] = nz

    df, _ = fake_prices()
    try:
        bt.guard(lambda d: d["close"].shift(-1) > d["close"], df)
        out["cheat_caught"] = {"pass": False, "msg": "Guard hat NICHT angeschlagen"}
    except bt.LookAheadError as ex:
        out["cheat_caught"] = {"pass": True, "msg": str(ex)}

    real = {}
    spy, qqq = data.load_research("SPY"), data.load_research("QQQ")
    checks = {
        "trend_switch SPY": (lambda d: signals.trend_switch(d["close"]), spy),
        "dip entry QQQ": (signals.BASE_SLEEVES["dip"].entry, qqq),
        "dip exit QQQ": (signals.BASE_SLEEVES["dip"].exit, qqq),
        "breakout entry QQQ": (signals.BASE_SLEEVES["breakout"].entry, qqq),
        "breakout exit QQQ": (signals.BASE_SLEEVES["breakout"].exit, qqq),
    }
    for name, (fn, d) in checks.items():
        try:
            bt.guard(fn, d)
            real[name] = True
        except bt.LookAheadError:
            real[name] = False
    out["real_signals_clean"] = {"pass": all(real.values()), "detail": real}
    out["all_pass"] = all(v["pass"] for k, v in out.items() if isinstance(v, dict))
    (settings.DIRS["results"] / "selfcheck.json").write_text(json.dumps(out, indent=2))
    write_panel(out)
    return out


def write_panel(o: dict) -> None:
    ok = lambda b: '<b class="good">PASS</b>' if b else '<b class="bad">FAIL</b>'
    rows = [
        ("Eingepflanzter Vorteil +1 %", f"Ø Trade {o['planted_edge']['avg_trade']*100:.2f} % "
         f"({o['planted_edge']['trades']} Trades)", "0.60 – 1.20 %", o["planted_edge"]["pass"]),
        ("Reines Rauschen", f"Ø Trade {o['pure_noise']['avg_trade']*100:.2f} % "
         f"({o['pure_noise']['trades']} Trades)", "−0.30 – +0.10 %", o["pure_noise"]["pass"]),
        ("Schummel-Signal (kennt morgen)", html.escape(o["cheat_caught"]["msg"][:90]),
         "Guard bricht ab", o["cheat_caught"]["pass"]),
        ("Echte Signale (5 Stück)", ", ".join(k for k, v in o["real_signals_clean"]["detail"].items() if v),
         "Guard bricht nicht ab", o["real_signals_clean"]["pass"]),
    ]
    tr = "".join(f"<tr><td>{a}</td><td style='white-space:normal'>{b}</td><td>{c}</td><td>{ok(d)}</td></tr>"
                 for a, b, c, d in rows)
    p = settings.DIRS["dashboard"] / "panels"
    p.mkdir(exist_ok=True)
    (p / "20_selfcheck.html").write_text(
        f"<section><h2>Phase P · Backtester-Selbsttest</h2><p class='sub'>Fantasiepreise mit bekannter "
        f"Antwort. Erst wenn alles PASS ist, glauben wir dem Backtester.</p><table><tr><th>Test</th>"
        f"<th>Ergebnis</th><th>Erwartet</th><th></th></tr>{tr}</table></section>")


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: (v if k != "cheat_caught" else v["pass"]) for k, v in r.items()}, indent=1))
