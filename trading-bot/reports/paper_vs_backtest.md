# Paper vs. Backtest (Simulation 120 Tage)

- Tage: 119 · Paper -12.18% · Backtest -13.42% · grösste Tageslücke 1.08%
- Gruppen: {'limits': 25, 'rounding': 4}
- Fazit: ✅ Paper macht, was der Backtest sagt; Lücken nur aus Fills/Rundung/Limits.

| Datum | Gruppe | Ticker | % | $ | Erklärung |
|---|---|---|---|---|---|
| 2026-05-22 | rounding | QQQ | +0.48% | 475 | QQQ: $475 bleiben wegen ganzer Aktien in Cash |
| 2026-05-26 | rounding | QQQ | +0.58% | 582 | QQQ: $582 bleiben wegen ganzer Aktien in Cash |
| 2026-06-05 | limits | XLK | +0.00% | 0 | XLK-Einstieg blockiert |
| 2026-07-17 | limits | XLK | +0.00% | 0 | XLK-Einstieg blockiert |
| 2026-07-27 | limits | XLK | +0.00% | 0 | XLK-Einstieg blockiert |
| 2026-07-28 | limits | XLK | +0.00% | 0 | XLK-Einstieg blockiert |
| 2026-07-29 | limits | XLK | +0.00% | 0 | XLK-Einstieg blockiert |
| 2026-08-19 | limits | XLK | +0.00% | 0 | XLK-Einstieg blockiert |
| 2026-08-20 | limits | XLK | +0.00% | 0 | XLK-Einstieg blockiert |
| 2026-08-24 | limits | XLK | +0.00% | 0 | XLK-Einstieg blockiert |
| 2026-09-21 | limits | QQQ | +0.00% | 0 | QQQ-Einstieg blockiert |
| 2026-09-22 | limits | QQQ | +0.00% | 0 | QQQ-Einstieg blockiert |
| 2026-10-02 | limits | QQQ | +0.00% | 0 | QQQ-Einstieg blockiert |
| 2026-10-05 | limits | QQQ | +0.00% | 0 | QQQ-Einstieg blockiert |
| 2026-10-06 | limits | QQQ | +0.00% | 0 | QQQ-Einstieg blockiert |
| 2026-10-14 | limits | XLK | +0.00% | 0 | XLK-Einstieg blockiert |
| 2026-10-15 | limits | XLK | +0.00% | 0 | XLK-Einstieg blockiert |
| 2026-10-16 | limits | XLK | +0.00% | 0 | XLK-Einstieg blockiert |
| 2026-10-30 | limits | XLK | +0.00% | 0 | XLK-Einstieg blockiert |
| 2026-11-02 | limits | XLK | +0.00% | 0 | XLK-Einstieg blockiert |
| 2026-11-05 | rounding | GLD | +0.08% | 73 | GLD: $73 bleiben wegen ganzer Aktien in Cash |
| 2026-11-11 | rounding | QQQ | +0.12% | 103 | QQQ: $103 bleiben wegen ganzer Aktien in Cash |
| 2026-09-22 | limits | QQQ | -0.60% | 0 | Backtest-Trade QQQ 2026-09-22–2026-10-19 (-3.0%) fehlt im Paper: Einstieg durch Limit blockiert |
| 2026-06-08 | limits | XLK | -0.23% | 0 | Backtest-Trade XLK 2026-06-08–2026-06-12 (-1.2%) fehlt im Paper: Einstieg durch Limit blockiert |
| 2026-07-20 | limits | XLK | +0.09% | 0 | Backtest-Trade XLK 2026-07-20–2026-07-22 (+0.4%) fehlt im Paper: Einstieg durch Limit blockiert |
| 2026-07-28 | limits | XLK | +0.71% | 0 | Backtest-Trade XLK 2026-07-28–2026-07-31 (+3.5%) fehlt im Paper: Einstieg durch Limit blockiert |
| 2026-08-20 | limits | XLK | +0.31% | 0 | Backtest-Trade XLK 2026-08-20–2026-08-27 (+1.5%) fehlt im Paper: Einstieg durch Limit blockiert |
| 2026-10-15 | limits | XLK | -0.18% | 0 | Backtest-Trade XLK 2026-10-15–2026-10-22 (-0.9%) fehlt im Paper: Einstieg durch Limit blockiert |
| 2026-11-02 | limits | XLK | -1.62% | 0 | Backtest-Trade XLK 2026-11-02–2026-11-05 (-8.1%) fehlt im Paper: Einstieg durch Limit blockiert |
