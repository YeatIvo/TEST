# Trading-System (ALPHA-Framework, nur Paper-Trading)

Eigenständiges Python-Projekt neben der Website im Hauptordner.

| Phase | Inhalt | Status |
|---|---|---|
| **A** Architecture | Ordner, Hausregeln, Settings, `.env.example`, Python-Umgebung | ✅ |
| **L** Logic | Daten, Asset-Studie, Regime, exakte Regeln | ✅ |
| **P** Proof | Backtester + Selbsttest, Core, Sleeves, Konto, Re-Pick | ✅ |
| **H** Harness | Alpaca-Paper-Bot, Risiko-Limits, Scheduler, Telegram | ⏳ |
| **A** Adapt | Paper vs. Backtest, Kill-Lines, Bench/Rotation, Reviews | ⏳ |

## Ordner
```
config/     settings.toml – ALLE Einstellungen (Ticker, Fenster, Kosten, Risiko)
data/       research/ = eingefrorene Forschungsdaten, live/ = Bot-Daten
src/        Code (Signale, Backtester, Bot)
rules/      aktive Core/Sleeve-Regeln + CHANGELOG.md
results/    jede getestete Idee, auch die durchgefallenen
reports/    Wochen-/Monats-/Quartalsberichte
logs/       Bot-Läufe, Orders, Scheduler
ai_calls/   gespeicherte, versiegelte AI-Calls (optional)
dashboard/  index.html
tests/      pytest
```

## Setup
```bash
cd trading-bot
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m src.fingerprint
python -m pytest -q
```

Keys: `cp .env.example .env` und die Werte **selbst** eintippen. `.env` wird nie committet.
