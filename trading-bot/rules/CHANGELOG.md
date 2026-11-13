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
