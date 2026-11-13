---
name: trading-review
description: Wöchentliche Review des Paper-Trading-Bots (jeden Samstag). Erstellt Wochen-/Monats-/Quartalsbericht, prüft Paper gegen Backtest, repariert Code-Fehler, ändert aber NIE Regeln. Nutzen bei "review", "Wochenbericht", "wie lief der Bot", oder als geplante Aufgabe samstags.
---

# Trading-Review (nur Paper)

Arbeite im Ordner `trading-bot/`, aktiviere `.venv`. Lies zuerst `CLAUDE.md` und `rules/removal_rules.md`.

1. `python -m src.compare --alpaca` ausführen (Paper vs. Backtest). Ohne Keys: `python -m src.compare --sim`.
2. `python -m src.review` ausführen. Es entscheidet selbst, ob Wochen-, Monats- oder Quartalsteil fällig ist.
3. Den neuen Bericht `reports/<datum>-review.md` lesen.
4. **Code-Fehler** (Bot tat nicht, was die Regeln sagen, oder ist abgestürzt): beheben, `python -m pytest -q`
   ausführen, mit klarer Nachricht committen.
5. **Nie** Regeln ändern (`rules/config.json`, `rules/core.json`, Limits). Ideen für Regeländerungen kommen ans Ende des
   Berichts unter „Ideen für später“. Sie müssen erst durch die Gates aus Phase P (`src/sleeves.py`).
6. Quartalsvorschläge **nur vorschlagen**. Den `rotate … --apply`-Befehl erst nach einem ausdrücklichen JA des
   Menschen ausführen.
7. Antworte mit 3–5 Zeilen: Kontostand, Auffälligkeiten, offene Entscheidungen.

Niemals `.env` öffnen, ausgeben oder committen.
