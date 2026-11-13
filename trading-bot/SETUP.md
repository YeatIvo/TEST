# Bot auf deinem Computer einrichten (nur Paper-Trading)

Der Bot muss auf **deinem** Computer laufen, denn dort laufen der Scheduler und deine `.env`.
Du brauchst etwa 20 Minuten.

## 1 · Projekt holen
```bash
git clone https://github.com/YeatIvo/TEST.git
cd TEST
git checkout claude/zealous-fermat-4yzkvx
cd trading-bot
```

## 2 · Python-Umgebung
Du brauchst Python 3.11 oder neuer.
```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.data                  # Forschungsdaten laden
python -m pytest -q                 # alle Tests müssen grün sein
```
Ergebnisse und Regeln (`rules/`, `results/`) liegen schon im Repo. Wer alles neu rechnen will, startet
`python -m src.study`, dann `src.selfcheck`, `src.core`, `src.sleeves`, `src.account` und `src.repick`.
Lock-Tests laufen dabei **nicht** neu, sie stehen in `results/lock_log.jsonl`.

## 3 · Alpaca-Paper-Konto
1. Konto eröffnen auf https://alpaca.markets (gratis) und links **Paper** wählen.
2. **API Keys → Generate New Keys** klicken. Key und Secret sofort kopieren, sie werden nur einmal angezeigt.
3. Die Vorlage kopieren und die Werte **selbst** eintragen (nie in einen Chat einfügen):
   ```bash
   cp .env.example .env
   ```
   Öffne `.env` in einem Editor und trage `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` und `ALPACA_PAPER=true` ein.
4. Prüfen, ohne dass Werte angezeigt werden:
   ```bash
   python -m src.bot check-keys
   ```
5. Das Paper-Konto muss vor dem ersten Lauf **leer** sein (keine Positionen), sonst stoppt der Bot.

## 4 · Probelauf ohne Orders
```bash
python -m src.bot evening --dry-run --asof 2026-11-12
```
Zeigt, was der Bot an diesem Tag tun würde. Es wird nichts gesendet und nichts gespeichert.

## 5 · Telegram (optional)
1. In Telegram **@BotFather** öffnen, `/newbot` senden, einen Namen wählen (er muss auf `bot` enden) und den **Token** kopieren.
2. Deinem neuen Bot „hallo“ schreiben.
3. Im Browser `https://api.telegram.org/bot<TOKEN>/getUpdates` öffnen und dort die `"chat":{"id": …}` kopieren.
4. Beides in `.env` eintragen: `TELEGRAM_BOT_TOKEN` und `TELEGRAM_CHAT_ID`.
5. Testen:
   ```bash
   python -m src.notify
   ```

## 6 · Scheduler (alle 30 Minuten)
Das Skript `src/tick.py` entscheidet selbst nach New-York-Zeit: Morgen-Check ab 09:35, Abend-Lauf ab 19:05.

- **macOS:** In `scheduler/com.tradingbot.tick.plist` `PFAD` ersetzen, dann:
  ```bash
  cp scheduler/com.tradingbot.tick.plist ~/Library/LaunchAgents/
  ```
  ```bash
  launchctl load ~/Library/LaunchAgents/com.tradingbot.tick.plist
  ```
- **Windows** (PowerShell im Ordner `trading-bot`):
  ```bash
  powershell -ExecutionPolicy Bypass -File scheduler\install_windows.ps1
  ```
- **Linux:** Die Zeile aus `scheduler/crontab.txt` mit `crontab -e` einfügen.

**Computer wach halten**, mindestens von 09:30–10:00 und 19:00–23:30 Uhr New-York-Zeit
(in der Schweiz etwa 15:30–16:00 und 01:00–05:30):
- macOS: Systemeinstellungen → Batterie/Energie → „Ruhezustand verhindern, wenn Netzteil angeschlossen“.
  Alternativ im Terminal `caffeinate -s`.
- Windows: Einstellungen → System → Energie → Bildschirm und Standby → „Nie“, wenn am Netz.

Die Logs liegen in `logs/scheduler.log`, `logs/runs.jsonl` und `logs/orders.jsonl`.

## 7 · Steuern in einfachen Worten
| Befehl | Wirkung |
|---|---|
| `python -m src.bot pause` | keine neuen Sleeve-Trades, kein neues Leihen; Core und Exits laufen weiter |
| `python -m src.bot resume` | PAUSE aufheben (nötig nach einem Tagesverlust von mehr als 5 %) |
| `python -m src.bot flatten` | alles zum nächsten Open verkaufen und PAUSE setzen |
| `python -m src.bot status` | was der Bot zu besitzen glaubt |

## Wichtig
- Für dieses Projekt ist **nur Paper** erlaubt. Der Code verweigert jedes Live-Konto.
- Nach einem Tag mit mehr als 5 % Verlust pausiert der Bot von selbst neue Sleeves, bis du `resume` sagst.
- Eine Regel wird **nie** wegen einer schlechten Woche geändert (siehe `CLAUDE.md`).

## 8 · Wöchentliche Routine (etwa 10 Minuten am Samstag)
Automatisch: Richte in der Claude-Desktop-App eine **geplante Aufgabe** ein, jeden Samstag um 10:00, Ordner `trading-bot`,
Text: „Führe den Skill trading-review aus“. Der Skill liegt in `.claude/skills/trading-review/`.
Ohne Claude geht es auch so:
```bash
python -m src.compare --alpaca
```
```bash
python -m src.review
```

Was der Review macht:
- **Jeden Samstag:** Wochenbericht in `reports/<datum>-review.md`. Die ersten Zeilen kommen per Telegram.
- **Erster Samstag im Monat:** Status jedes Sleeves (keep / watch / review / out).
- **Erster Samstag nach Quartalsende:** Re-Pick-Vorschlag. Es wird **nichts** geändert, bis du JA sagst.
  Dann führst du den angezeigten Befehl aus, zum Beispiel:
  ```bash
  python -m src.adapt rotate <live-id> <bank-id> --apply
  ```

Was du selbst tust:
1. Den Bericht lesen, vor allem Fehler und verpasste Läufe.
2. Die Alerts auf dem Handy anschauen. Ein verpasster Lauf bedeutet meist, dass der Computer geschlafen hat.
3. Prüfen, wie weit jeder Sleeve von seiner Kill-Line entfernt ist.
4. Bei Quartalsvorschlägen JA oder NEIN sagen.

Erst nach mehreren Wochen bis Monaten, in denen Paper und Backtest übereinstimmen, über echtes Geld nachdenken.
Diesen Schritt automatisiert dieses Projekt bewusst **nicht**.
