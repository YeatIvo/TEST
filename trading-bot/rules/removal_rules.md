# Wann ein Sleeve rausfliegt (vorher festgelegt; nur du änderst diese Datei)

1. **Kill-Line:** Der Live-Drawdown des Sleeves ist grösser als **2×** sein schlimmster getesteter Drawdown
   (`rules/kill_lines.json`). Der Bot schaltet ihn dann selbst ab, verkauft zum nächsten Open, trägt das ins CHANGELOG ein
   und meldet sich.
2. **Re-Pick:** Die Quartals-Routine (`src/repick.py`) wählt ihn nicht mehr. Claude schlägt einen Tausch gegen einen
   Bank-Sleeve vor. **Du** sagst ja oder nein.
3. **Verhalten:** Nach mindestens 3 Monaten live handelt er weniger als halb so oft oder mehr als doppelt so oft
   wie im Test. Er bekommt dann den Status `review`, und **du** entscheidest.

**Core:** Ist der Konto-Drawdown grösser als 1.5× der schlimmste Core-Drawdown, gibt es einen Alarm und keine neuen Sleeves.
Den Core selbst ändert nur der Mensch.

**Nie** ein Grund: eine schlechte Woche oder ein schlechter Monat.
