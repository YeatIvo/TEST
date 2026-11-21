# Paper vs. Backtest (Alpaca Paper)

- Tage: 10 · Paper -8.73% · Backtest -14.41% · grösste Tageslücke 2.93%
- Gruppen: {'rules': 6, 'rounding': 3, 'fills': 1, 'limits': 1}
- Fazit: ⚠️ Unerklärte Lücken (rules) – Bot tut etwas, das die Regeln nicht sagen. Prüfen!

| Datum | Gruppe | Ticker | % | $ | Erklärung |
|---|---|---|---|---|---|
| 2026-11-16 | fills | GLD | -0.03% | 31 | GLD buy gefüllt zu 354.02 statt Open 354.13 |
| 2026-11-13 | rounding | GLD | +0.14% | 139 | GLD: $139 bleiben wegen ganzer Aktien in Cash |
| 2026-11-17 | rounding | SPY | +0.30% | 298 | SPY: $298 bleiben wegen ganzer Aktien in Cash |
| 2026-11-17 | rounding | XLY | +0.10% | 101 | XLY: $101 bleiben wegen ganzer Aktien in Cash |
| 2026-11-18 | limits | SPY | +0.00% | 0 | SPY-Einstieg blockiert |
| 2026-11-10 | rules |  | +2.71% | 0 | 2026-11-10: Paper +0.03% vs. Backtest -2.68% – unerklärt |
| 2026-11-11 | rules |  | +1.13% | 0 | 2026-11-11: Paper -0.01% vs. Backtest -1.13% – unerklärt |
| 2026-11-12 | rules |  | +1.13% | 0 | 2026-11-12: Paper +0.09% vs. Backtest -1.04% – unerklärt |
| 2026-11-13 | rules |  | +1.18% | 0 | 2026-11-13: Paper -0.02% vs. Backtest -1.20% – unerklärt |
| 2026-11-19 | rules |  | -1.25% | 0 | 2026-11-19: Paper -3.19% vs. Backtest -1.94% – unerklärt |
| 2026-11-20 | rules |  | +2.29% | 0 | 2026-11-20: Paper -1.75% vs. Backtest -4.04% – unerklärt |
