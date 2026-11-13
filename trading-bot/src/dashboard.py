"""Baut dashboard/index.html aus den Panels, die die einzelnen Phasen ablegen.

Jede Phase schreibt ein HTML-Fragment nach dashboard/panels/<NN>_<name>.html.
Dieses Skript setzt sie in Reihenfolge zusammen. So bleibt jede Phase
unabhängig und das Dashboard immer vollständig.
"""
from __future__ import annotations

import datetime as dt
import html

from . import fingerprint, settings

PANELS = settings.DIRS["dashboard"] / "panels"

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--ink:#1b1d1f;--muted:#5f6670;--line:#e3e3df;
--good:#1f7a4d;--bad:#b3261e;--accent:#2b5fab;--warn:#a86400}
@media (prefers-color-scheme: dark){:root{--bg:#141516;--card:#1d1f21;--ink:#ececea;
--muted:#a3a8ae;--line:#2e3134;--good:#4cc38a;--bad:#ff8a80;--accent:#82a8ff;--warn:#f2b45c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.15rem;margin:0 0 12px}
.sub{color:var(--muted);margin:0 0 24px}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:20px;margin:0 0 20px;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--muted);font-weight:600;font-size:.85rem}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.85rem}
.tag{display:inline-block;padding:1px 8px;border-radius:99px;font-size:.78rem;
border:1px solid var(--line);margin-right:4px}
.good{color:var(--good)}.bad{color:var(--bad)}.warn{color:var(--warn)}
.fp{background:var(--bg);padding:10px;border-radius:6px;word-break:break-all;white-space:normal}
svg{max-width:100%;height:auto}
"""


def build() -> str:
    PANELS.mkdir(parents=True, exist_ok=True)
    parts = [p.read_text() for p in sorted(PANELS.glob("*.html"))]
    if not parts:
        parts = ["<section><h2>Noch leer</h2><p>Phase A ist fertig. "
                 "Die nächsten Phasen fügen hier ihre Panels hinzu.</p></section>"]
    s = settings.load()
    head = f"""<section><h2>Architektur (Phase A)</h2>
<table><tr><th>Bar-Grösse</th><td>{s['data']['bar_size']}</td></tr>
<tr><th>Training</th><td>{s['windows']['train_start']} – {s['windows']['train_end']}</td></tr>
<tr><th>Lock-Test</th><td>{s['windows']['lock_start']} – {s['windows']['lock_end']}</td></tr>
<tr><th>Startkapital</th><td>${s['portfolio']['starting_cash']:,.0f}</td></tr>
<tr><th>Kosten</th><td>{s['costs']['per_side_etf']*100:.2f} % pro Seite (ETF), {s['costs']['per_side_crypto']*100:.2f} % (Krypto)</td></tr>
<tr><th>Broker</th><td>{s['broker']['name']} – <b>nur Paper</b></td></tr>
<tr><th>Ticker</th><td style="white-space:normal">{', '.join(s['universe']['study_tickers'])}</td></tr></table>
<p class="fp mono">{html.escape(fingerprint.line())}</p></section>"""
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trading-System Dashboard</title><style>{CSS}</style></head><body><main>
<h1>Trading-System</h1><p class="sub">ALPHA-Framework · nur Paper-Trading · erzeugt {now}</p>
{''.join(parts)}{head}</main></body></html>"""


def write() -> None:
    out = settings.DIRS["dashboard"] / "index.html"
    out.write_text(build())
    print(f"Dashboard geschrieben: {out}")


if __name__ == "__main__":
    write()
