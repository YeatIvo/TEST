# Bot auf GitHub laufen lassen (ohne Laptop)

Alles geht im Browser, auch vom Handy aus. Du brauchst etwa 10 Minuten.

## 1 · Alpaca-Paper-Konto und Keys
1. Registriere dich auf https://alpaca.markets (gratis) und wähle links **Paper**.
2. Klicke auf **API Keys** und dann auf **Generate New Keys**. Lass das Fenster offen, die Keys werden nur einmal angezeigt.

## 2 · Keys bei GitHub hinterlegen (verschlüsselt)
1. Öffne https://github.com/YeatIvo/TEST/settings/secrets/actions
2. Klicke auf **New repository secret** und lege zwei Secrets an:
   - Name `ALPACA_API_KEY`, als Wert deinen Key
   - Name `ALPACA_SECRET_KEY`, als Wert dein Secret
3. Optional für Handy-Nachrichten: `TELEGRAM_BOT_TOKEN` und `TELEGRAM_CHAT_ID`
   (wie du die bekommst, steht in `SETUP.md`, Abschnitt 5).

Niemand sieht die Werte danach wieder, auch Claude nicht.

## 3 · Testen
1. Öffne https://github.com/YeatIvo/TEST/actions
2. Wähle links **Trading-Bot (Paper)**, klicke auf **Run workflow** und dann **check-keys** → **Run workflow**.
3. Nach etwa 1 Minute den Lauf öffnen. Dort sollte bei den Alpaca-Zeilen jeweils „gesetzt“ stehen.
4. Am Abend nach 01:30 Uhr Schweizer Zeit kannst du **dry-run** starten. Das zeigt, was der Bot tun würde, ohne etwas zu senden.

## 4 · Ab dann läuft es von selbst
- **Montag bis Freitag nachts** (etwa 01:20 Uhr CH): Abend-Lauf. Die Orders gelten zum nächsten Open.
- **Montag bis Freitag nachmittags** (etwa 15:50 Uhr CH): Morgen-Check, setzt die Stops.
- **Samstag**: Wochen-Review in `reports/` auf dem Branch `bot-state`.
- Was der Bot besitzt, seine Logs und Berichte liegen auf dem Branch **`bot-state`**.

## 5 · Steuern per Knopfdruck
Unter **Actions → Trading-Bot (Paper) → Run workflow** kannst du einen Befehl wählen:

| Befehl | Wirkung |
|---|---|
| `status` | was der Bot besitzt |
| `pause` / `resume` | neue Sleeves stoppen bzw. wieder erlauben (nach einem Tag mit über 5 % Verlust nötig) |
| `flatten` | alles zum nächsten Open verkaufen und PAUSE setzen |
| `review` | Bericht jetzt erstellen |
| `rotate` | Sleeve tauschen: erst ohne `--apply` prüfen, dann mit `--apply` ausführen |

Regeln änderst du nur über diese Befehle. Der Bot hält seine aktiven Regeln auf dem Branch `bot-state`.

**Hinweis:** GitHub startet geplante Läufe manchmal mit Verspätung. Deshalb gibt es mehrere Termine pro Nacht. Der Bot handelt trotzdem nur einmal pro Tag.
