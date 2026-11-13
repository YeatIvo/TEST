# Trading-System (ALPHA-Framework) – Hausregeln

Diese Datei liest der Assistent zu Beginn jeder Sitzung, bevor er etwas tut.
Sie gilt für JEDEN späteren Schritt. `AGENTS.md` ist eine identische Kopie
(für Codex/andere Agenten).

## Meine Einstellungen
Alle Einstellungen (Bar-Grösse, Ticker, Zeitfenster, Kosten, Kapital, Risiko)
stehen in **`config/settings.toml`** – nirgends sonst. Kein Skript darf Ticker,
Daten oder Kosten fest einprogrammieren; alles wird von dort gelesen
(`src/settings.py`).

## Sicherheit (nicht verhandelbar)
1. **Nur Paper-Trading.** Der Bot verweigert jeden Lauf, wenn `ALPACA_PAPER`
   nicht `true` ist oder `broker.paper_only = false`. Das Live-Konto bleibt gesperrt.
2. **`.env` wird niemals geöffnet, gelesen, ausgegeben, geloggt oder committet.**
   Keys tippt der Mensch selbst in `.env`. Code darf nur prüfen, *ob* ein Key
   gesetzt ist (ja/nein), nie den Wert anzeigen. Niemals im Chat nach Keys fragen.
3. Nur `.env.example` (ohne Werte) gehört ins Repo.

## Daten
- Quelle: Yahoo Finance via `yfinance`, Tagesbalken, **bereinigt** (Splits/Dividenden).
- Forschungsdaten werden einmal geladen und in `data/research/` gespeichert;
  jeder Test liest diese gespeicherte Kopie. Der Bot schreibt seine eigenen
  Daten nach `data/live/` – Forschungsresultate ändern sich dadurch nie.

## Zeitfenster & Tests
- Training **2022-01-01 – 2024-12-31**: alle Entscheidungen (Assets, Regeln, Parameter).
- Lock-Test **2025-01-01 – heute**: wird pro Idee **genau einmal** gelaufen und
  ehrlich berichtet. Fällt eine Idee durch, wird sie verworfen – **nie** nachjustiert.
- Signal am Tagesschluss -> Ausführung zum **nächsten Open** (keine Look-Ahead-Fills).
- Kosten immer drin: 0.05 % pro Seite (ETF), 0.25 % (Krypto). Stresstest mit 2x Kosten.
- Bewertung: **Rendite pro Drawdown** (CAGR / Max-Drawdown) ist die Hauptkennzahl,
  dazu Anzahl Trades, Profit-Faktor, Nachbar-Parameter.
- Pass-Kriterien werden **vor** dem Lauf festgeschrieben, nie danach.

## System-Aufbau
Daten -> Regime -> Core + Sleeves -> Risiko -> Orders (Broker) -> Log/Alerts/Dashboard.
Backtest und Bot lesen **dieselbe** Signal-Datei (`src/signals.py`) und dieselbe
Regel-Datei (`rules/`).
- **Core**: langfristige Rotation (Engine vs. sicheres Asset), 100 % investiert.
- **Sleeves**: kurzfristige Regeln (Dip-Buy, Breakout …), je 20 %, max. 3,
  dürfen auf Margin laufen; werden regelmässig ersetzt.
- **AI-Layer** (optional): darf nur den Core zeitlich begrenzt übersteuern,
  nie Sleeves, nie Orders platzieren, nie Regeln ändern.

## Arbeitsweise
- Ein Modul pro Schritt. Jeder Schritt endet mit einer Prüfung (Tabelle/Chart/Test)
  und einer Zeile Fazit.
- **Keine Regeländerung wegen kurzfristiger Resultate** (schlechte Woche/Monat).
  Jede Änderung ist eine neue Idee und durchläuft die Gates erneut.
- Jede getestete Idee wird geloggt – auch die, die durchfallen (`results/`).
- Änderungen an `rules/` werden in `rules/CHANGELOG.md` mit Datum, Grund und Test notiert.
- Nach Settings-Änderungen den Fingerprint neu erzeugen (`python -m src.fingerprint`).
