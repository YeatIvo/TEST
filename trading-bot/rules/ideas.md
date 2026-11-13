# Exakte Regeln (Phase L)

Eine Idee ist erst testbar, wenn alle **7 Teile** ausgefüllt sind:
Markt · Setup · Filter · Einstieg · Ausstieg · Stop · Grösse.
Alle Signale werden am Tagesschluss berechnet und zum **nächsten Open** ausgeführt.

## Core – Trend-Schalter (Engine vs. sicheres Asset)
| Teil | Regel |
|---|---|
| Markt | Engine = Kandidat mit grösstem Trend-Gap (`engine_candidates`); Safe = bestes Asset an den Downtrend-Tagen der Engine mit Korrelation < 0.5 (`safe_candidates`) – wird in Phase P bestimmt |
| Setup | Engine-Schlusskurs vs. 200-Tage-Schnitt |
| Filter | – (optional später: Marktfilter VIX/Breite, AI-Layer) |
| Einstieg | Schluss > SMA200 → am nächsten Open Engine halten |
| Ausstieg | Schluss < SMA200 → am nächsten Open in Safe wechseln |
| Stop | keiner (Rotation, immer investiert) |
| Grösse | 100 % des Kontos |

## Sleeve-Typ 1 – Dip-Buy (passt zu Label `snaps_back`)
| Teil | Regel |
|---|---|
| Markt | jeder handelbare Ticker mit Label „springt zurück“ |
| Setup | RSI(2) < 10 |
| Filter | Schluss > SMA200 (Uptrend) |
| Einstieg | nächster Open |
| Ausstieg | Schluss > SMA5 **oder** 10 Handelstage im Trade (was zuerst kommt) → nächster Open |
| Stop | 8 % unter Einstand, liegt beim Broker |
| Grösse | 20 % des Kontos (Slot), im Test zusätzlich 10 % an volatilen Tagen |

Nachbarn: RSI < 5 / < 15; Ausstieg über SMA3 / SMA10.

## Sleeve-Typ 2 – Breakout (passt zu Label `keeps_going`)
| Teil | Regel |
|---|---|
| Markt | jeder handelbare Ticker mit Label „läuft weiter“ |
| Setup | neues 50-Tage-Schlusshoch |
| Filter | Schluss > SMA200 |
| Einstieg | nächster Open |
| Ausstieg | Schluss = 20-Tage-Tief **oder** Schluss < SMA200 → nächster Open |
| Stop | 10 % unter Einstand, liegt beim Broker |
| Grösse | 20 % des Kontos (Slot) |

Nachbarn: 20-Tage- / 100-Tage-Hoch.

## Strategie ↔ Asset-Matrix
| Label | Breakout | Dip-Buy | Sicheres Asset (Core) |
|---|---|---|---|
| läuft weiter | ✅ | – | – |
| springt zurück | – | ✅ | – |
| hält bei Aktien-Crash / tiefe Korrelation | – | – | ✅ |

Nur passende Paare werden in Phase P getestet.
