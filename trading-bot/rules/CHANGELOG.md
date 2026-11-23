# Regel-Änderungsprotokoll

Jede Änderung an Core, Sleeves oder Risiko-Limits wird hier mit Datum,
Was, Warum und dem zugehörigen Test eingetragen.

| Datum | Änderung | Grund | Test |
|---|---|---|---|
| 2026-11-13 | Projekt angelegt (Phase A) – noch keine Regeln | Architektur | `tests/test_architecture.py` |
| 2026-11-13 | Phase L: Asset-Studie, Labels (`rules/labels.json`), exakte Regel-Vorlagen (`rules/ideas.md`) | Logik vor Test | `tests/test_logic.py` |
| 2026-11-13 | Core gesetzt: QQQ über SMA200 → QQQ, sonst GLD (`rules/core.json`) | Prompt 3: Trend-Gap + bestes Safe-Asset, Nachbarn + Lock bestanden | `src/core.py`, `results/core.json` |
| 2026-11-13 | Bank: 5 Sleeves (QQQ dip/breakout, XLK dip, XLF breakout, XLY dip) | Funnel 44 → 5 | `src/sleeves.py`, `results/sleeve_funnel.json` |
| 2026-11-13 | Konto: Core + QQQ breakout + XLK dip, halbe Grösse an volatilen Tagen (`rules/config.json`) | Greedy-Auswahl Rendite/DD im Training | `src/account.py`, `results/account.json` |
| 2026-11-13 | Phase H: Bot (Alpaca Paper), Risiko-Limits, Scheduler, Telegram, Simulator | Bot handelt rules/config.json | `tests/test_bot.py` (Bot = Backtest ±0.14 %/Tag) |
| 2026-11-13 | Phase Adapt: Kill-Lines (`rules/kill_lines.json`), Entfernungsregeln, Bank/Rotation, Paper-vs-Backtest, Reviews | Strategien altern | `tests/test_adapt.py` |
| 2026-11-17 | Quartals-Auswahl per 2026-09-30: sleeve:XLI:down3_sma5, sleeve:SPY:down3_sma5, sleeve:XLY:dip_rsi10_sma5 (vorher sleeve:QQQ:brk_hi50_lo20, sleeve:XLK:dip_rsi10_sma5) | Re-Pick-Routine (Prompt 6), automatisch | results/repick.json |
| 2026-11-23 | Core-Risiko-Steuerung: Anteil = 15 % / 20-Tage-Vola (10–100 %) | Wunsch nach weniger Absturz-Tagen; Training R/DD 0.63 vs 0.48, Lock CAGR 14.5 % / DD −12.4 % (vorher 18.5 % / −15.3 %) | results/lock_log.jsonl (core-sizing:voltarget15) |
