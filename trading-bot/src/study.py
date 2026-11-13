"""Phase L – Asset-Studie: wie bewegt sich jedes Asset? (nur Trainingsfenster)

Fragen pro Ticker:
  1. Läuft es nach einem neuen Hoch weiter?          -> Label keeps_going
  2. Springt es nach einem schnellen Einbruch zurück? -> Label snaps_back
  3. Bewegt es sich mit Aktien (SPY)?                 -> Label moves_with_stocks
  4. Was tut es, wenn Aktien fallen?                  -> Label holds_up
  5. Wie gross sind seine Schwankungen?               -> Label wild
  + Trend-Gap (Uptrend- vs. Downtrend-Tage) und Ruhig- vs. Volatil-Tage.

Feste Schwellen (vor dem Lauf festgelegt):
  keeps_going: neues 50-Tage-Schlusshoch über der 200-Tage-Linie, >= 6 Ereignisse
               (Mindestabstand 20 Tage), Ø 20-Tage-Rendite danach > normale Ø 20-Tage-Rendite
  snaps_back : RSI(2) < 10 über der 200-Tage-Linie, >= 12 Ereignisse (Abstand 5 Tage),
               Ø 5-Tage-Rendite danach > normale Ø 5-Tage-Rendite
  moves_with_stocks: Korrelation täglicher Renditen mit SPY >= 0.6
  holds_up   : Ø Rendite an Tagen mit SPY < -1 % ist >= 0
  wild       : annualisierte Vola > 30 %
Vorwärtsrenditen enden spätestens am letzten Trainingstag -> kein Blick ins Lock-Fenster.
"""
from __future__ import annotations

import html
import json

import numpy as np
import pandas as pd

from . import data, fingerprint, settings
from .indicators import rsi, trend_up, vol_high

GROUPS = {
    "Breite Aktien-Indizes": ["SPY", "QQQ", "IWM", "DIA"],
    "Sektoren": ["XLK", "XLF", "XLY", "XLE", "XLV", "XLI", "XLP", "XLU", "XLB", "XLRE", "XLC"],
    "Anleihen & Cash": ["SHY", "IEF", "TLT", "BIL"],
    "Rohstoffe": ["GLD", "SLV"],
    "International": ["EFA", "EEM"],
    "Krypto": ["BTC-USD"],
}
LABEL_DE = {
    "keeps_going": "läuft weiter", "snaps_back": "springt zurück",
    "moves_with_stocks": "geht mit Aktien", "holds_up": "hält bei Aktien-Crash",
    "wild": "sehr volatil",
}


def _events(mask: pd.Series, spacing: int) -> list[pd.Timestamp]:
    out, last = [], None
    idx = mask.index
    pos = {d: i for i, d in enumerate(idx)}
    for d in idx[mask.fillna(False).astype(bool).values]:
        if last is None or pos[d] - pos[last] >= spacing:
            out.append(d)
            last = d
    return out


def _fwd(c: pd.Series, h: int, end: pd.Timestamp) -> pd.Series:
    """h-Tage-Vorwärtsrendite, nur wenn Tag t+h <= end (kein Look-Ahead ins Lock-Fenster)."""
    f = c.shift(-h) / c - 1
    end_dates = pd.Series(c.index, index=c.index).shift(-h)
    return f.where(end_dates <= end)


def study_ticker(t: str, df: pd.DataFrame, spy_ret: pd.Series, spy_up: pd.Series,
                 win: tuple | None = None) -> dict:
    s = settings.load()
    tr_s, tr_e = (pd.Timestamp(x) for x in (win or settings.window("train")))
    c = df["close"]
    up = trend_up(c, s["regime"]["trend_ma_days"])
    vh = vol_high(c, s["regime"]["vol_window_days"], s["regime"]["vol_lookback_days"])
    r_next = c.pct_change().shift(-1)  # Rendite von t nach t+1 (Regime bekannt bei t)
    in_tr = (c.index >= tr_s) & (c.index <= tr_e)

    # 1) läuft weiter?
    f20 = _fwd(c, 20, tr_e)
    hi50 = c >= c.rolling(50, min_periods=50).max()
    ev_m = _events((hi50 & (up == True)) & in_tr & f20.notna(), 20)
    mom_after = f20.loc[ev_m].mean() if ev_m else np.nan
    mom_base = f20[in_tr].mean()

    # 2) springt zurück?
    f5 = _fwd(c, 5, tr_e)
    r2 = rsi(c, 2)
    dip = (r2 < 10) & in_tr & f5.notna()
    ev_s = _events(dip & (up == True), 5)
    ev_s_below = _events(dip & (up == False), 5)
    snap_after = f5.loc[ev_s].mean() if ev_s else np.nan
    snap_below = f5.loc[ev_s_below].mean() if ev_s_below else np.nan
    snap_base = f5[in_tr].mean()
    snap_hit = (f5.loc[ev_s] > 0).mean() if ev_s else np.nan

    # 3+4) Beziehung zu Aktien
    ret = c.pct_change()
    j = pd.concat([ret, spy_ret], axis=1, keys=["a", "spy"]).dropna()
    j = j[(j.index >= tr_s) & (j.index <= tr_e)]
    corr = j["a"].corr(j["spy"])
    on_spy_drop = j.loc[j["spy"] < -0.01, "a"].mean()
    spy_dn = spy_up.reindex(j.index) == False
    on_spy_downtrend_ann = j.loc[spy_dn, "a"].mean() * 252 if spy_dn.any() else np.nan

    # 5) Schwankung, Trend-Gap, Ruhig vs. Volatil
    rt = ret[in_tr]
    days = 365 if t in s["universe"]["crypto_tickers"] else 252
    vol = rt.std() * np.sqrt(days)
    rn = r_next[in_tr & r_next.notna()]
    upm = up.reindex(rn.index)
    gap_up = rn[upm == True].mean() * days
    gap_dn = rn[upm == False].mean() * days
    vhm = vh.reindex(rn.index)
    calm_move = rn[vhm == False].abs().mean()
    wild_move = rn[vhm == True].abs().mean()
    total = (c[in_tr].iloc[-1] / c[in_tr].iloc[0]) ** (days / in_tr.sum()) - 1

    labels = []
    if len(ev_m) >= 6 and mom_after > mom_base:
        labels.append("keeps_going")
    if len(ev_s) >= 12 and snap_after > snap_base:
        labels.append("snaps_back")
    if t != "SPY" and corr >= 0.6:
        labels.append("moves_with_stocks")
    if on_spy_drop >= 0:
        labels.append("holds_up")
    if vol > 0.30:
        labels.append("wild")

    return dict(
        ticker=t, cagr_train=total, vol=vol, corr_spy=corr,
        n_high=len(ev_m), fwd20_after_high=mom_after, fwd20_normal=mom_base,
        n_dip=len(ev_s), fwd5_after_dip=snap_after, fwd5_normal=snap_base, dip_hit=snap_hit,
        n_dip_below=len(ev_s_below), fwd5_after_dip_below=snap_below,
        on_spy_drop_day=on_spy_drop, on_spy_downtrend_ann=on_spy_downtrend_ann,
        trend_up_ann=gap_up, trend_dn_ann=gap_dn, trend_gap=gap_up - gap_dn,
        calm_move=calm_move, wild_move=wild_move, labels=labels,
    )


def plain_line(r: dict) -> str:
    bits = []
    if "keeps_going" in r["labels"]:
        bits.append("läuft nach neuen Hochs weiter (Trend/Momentum)")
    if "snaps_back" in r["labels"]:
        bits.append("springt nach schnellen Dips zurück (Mean Reversion)")
    if "holds_up" in r["labels"]:
        bits.append("hält sich, wenn Aktien fallen")
    elif "moves_with_stocks" in r["labels"]:
        bits.append("fällt mit Aktien")
    if "wild" in r["labels"]:
        bits.append("schwankt stark")
    if not bits:
        bits.append("kein klares Muster im Training")
    gap = r["trend_gap"]
    bits.append(f"Trend-Gap {gap*100:+.0f} %/J")
    return "; ".join(bits) + "."


def correlation(all_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    tr_s, tr_e = settings.window("train")
    rets = pd.DataFrame({t: d["close"].pct_change() for t, d in all_data.items()})
    stock_days = all_data["SPY"].index
    rets = rets.reindex(stock_days)
    rets = rets[(rets.index >= pd.Timestamp(tr_s)) & (rets.index <= pd.Timestamp(tr_e))]
    return rets.corr()


def run() -> tuple[pd.DataFrame, pd.DataFrame]:
    all_data = data.load_all()
    spy = all_data["SPY"]["close"]
    spy_ret, spy_up = spy.pct_change(), trend_up(spy, settings.load()["regime"]["trend_ma_days"])
    rows = [study_ticker(t, d, spy_ret, spy_up) for t, d in all_data.items()]
    df = pd.DataFrame(rows).set_index("ticker")
    df["summary"] = [plain_line(r) for r in rows]
    corr = correlation(all_data)

    res = settings.DIRS["results"]
    df.assign(labels=df["labels"].map(",".join)).to_csv(res / "asset_study.csv", float_format="%.5f")
    corr.to_csv(res / "correlation_train.csv", float_format="%.3f")
    (settings.DIRS["rules"] / "labels.json").write_text(json.dumps(
        {t: r["labels"] for t, r in zip(df.index, rows)}, indent=2))
    write_panel(df, corr)
    return df, corr


# ---------------------------------------------------------------- Dashboard
def _pct(x, d=1):
    return "–" if pd.isna(x) else f"{x*100:.{d}f} %"


def _heat(v: float) -> str:
    if pd.isna(v):
        return ""
    col = "31,122,77" if v >= 0 else "179,38,30"
    return f"background:rgba({col},{min(abs(v),1)*0.85:.2f})"


def _bars(items: list[tuple[str, float]], title: str) -> str:
    w, rowh, lab = 560, 20, 70
    vmax = max(abs(v) for _, v in items) or 1
    mid = lab + (w - lab) / 2
    h = rowh * len(items) + 10
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(title)}">']
    out.append(f'<line x1="{mid}" y1="0" x2="{mid}" y2="{h}" stroke="currentColor" opacity=".3"/>')
    for i, (name, v) in enumerate(items):
        y = i * rowh + 4
        bw = abs(v) / vmax * (w - lab) / 2 - 40
        x = mid if v >= 0 else mid - bw
        color = "var(--good)" if v >= 0 else "var(--bad)"
        out.append(f'<text x="0" y="{y+12}" font-size="11" fill="currentColor">{name}</text>')
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(bw,1):.1f}" height="{rowh-6}" fill="{color}" rx="2"/>')
        tx = x + bw + 4 if v >= 0 else x - 4
        anchor = "start" if v >= 0 else "end"
        out.append(f'<text x="{tx:.1f}" y="{y+11}" font-size="10" text-anchor="{anchor}" '
                   f'fill="currentColor">{v*100:+.0f}%</text>')
    out.append("</svg>")
    return "".join(out)


def write_panel(df: pd.DataFrame, corr: pd.DataFrame) -> None:
    rows = []
    for g, ts in GROUPS.items():
        rows.append(f'<tr><th colspan="7" style="padding-top:14px">{g}</th></tr>')
        for t in ts:
            r = df.loc[t]
            tags = "".join(f'<span class="tag">{LABEL_DE[l]}</span>' for l in r["labels"]) or "–"
            rows.append(
                f"<tr><td><b>{t}</b></td><td>{tags}</td><td>{_pct(r.cagr_train)}</td>"
                f"<td>{_pct(r.vol,0)}</td><td>{r.corr_spy:.2f}</td><td>{_pct(r.trend_gap,0)}</td>"
                f'<td style="white-space:normal;min-width:260px">{html.escape(r.summary)}</td></tr>')
    tbl = ("<table><tr><th>Ticker</th><th>Labels</th><th>CAGR Training</th><th>Vola</th>"
           "<th>Korr. SPY</th><th>Trend-Gap</th><th>Klartext</th></tr>" + "".join(rows) + "</table>")

    order = [t for ts in GROUPS.values() for t in ts]
    c = corr.loc[order, order]
    head = "".join(f'<th style="writing-mode:vertical-rl;font-size:.7rem">{t}</th>' for t in order)
    body = "".join(
        f'<tr><th style="font-size:.75rem">{a}</th>' + "".join(
            f'<td title="{a}/{b} {c.loc[a,b]:.2f}" style="{_heat(c.loc[a,b])};padding:2px 3px;'
            f'font-size:.65rem;text-align:center">{c.loc[a,b]:.1f}</td>' for b in order) + "</tr>"
        for a in order)
    heat = f"<table style='width:auto'><tr><th></th>{head}</tr>{body}</table>"

    gap_items = sorted(((t, df.loc[t, "trend_gap"]) for t in order if t != "BIL"),
                       key=lambda x: -x[1])
    dip_rows = "".join(
        f"<tr><td>{t}</td><td>{int(df.loc[t,'n_dip'])}</td><td>{_pct(df.loc[t,'fwd5_after_dip'],2)}</td>"
        f"<td>{int(df.loc[t,'n_dip_below'])}</td><td>{_pct(df.loc[t,'fwd5_after_dip_below'],2)}</td>"
        f"<td>{_pct(df.loc[t,'fwd5_normal'],2)}</td></tr>"
        for t in ["SPY", "QQQ", "IWM", "DIA", "XLK", "GLD"])
    calm_rows = "".join(
        f"<tr><td>{t}</td><td>{_pct(df.loc[t,'calm_move'],2)}</td><td>{_pct(df.loc[t,'wild_move'],2)}</td>"
        f"<td>{df.loc[t,'wild_move']/df.loc[t,'calm_move']:.1f}×</td></tr>"
        for t in ["SPY", "QQQ", "IWM", "GLD", "TLT", "BTC-USD"])

    fp = fingerprint.line().replace("FINGERPRINT A", "FINGERPRINT L") + \
        f" | labels={sum(len(x) for x in df['labels'])} keeps_going={sum('keeps_going' in x for x in df['labels'])}" \
        f" snaps_back={sum('snaps_back' in x for x in df['labels'])}"
    html_out = f"""
<section><h2>Phase L · Asset-Studie (Training 2022–2024)</h2>
<p class="sub">Welche Strategie passt zu welchem Asset? Labels entscheiden später, welche Sleeves überhaupt getestet werden.</p>
{tbl}<p class="fp mono">{html.escape(fp)}</p></section>
<section><h2>Regime 1 · Gleicher Dip über vs. unter der 200-Tage-Linie</h2>
<p class="sub">RSI(2) &lt; 10, durchschnittliche Rendite der nächsten 5 Tage.</p>
<table><tr><th>Ticker</th><th>Dips über Linie</th><th>Ø 5T danach</th><th>Dips unter Linie</th><th>Ø 5T danach</th><th>normale 5T</th></tr>{dip_rows}</table></section>
<section><h2>Trend-Gap · Rendite/Jahr an Uptrend- minus Downtrend-Tagen</h2>
<p class="sub">Grosser Gap = ein Trend-Schalter (über/unter 200-Tage-Linie) hilft am meisten → Engine-Kandidat für den Core.</p>
{_bars(gap_items, "Trend-Gap pro Ticker")}</section>
<section><h2>Regime 2 · Ruhige vs. volatile Tage</h2>
<p class="sub">Durchschnittliche Tagesbewegung. An volatilen Tagen wird später die Sleeve-Grösse halbiert getestet.</p>
<table><tr><th>Ticker</th><th>ruhig</th><th>volatil</th><th>Faktor</th></tr>{calm_rows}</table></section>
<section><h2>Korrelation (tägliche Renditen, Training)</h2>
<p class="sub">Grün = bewegen sich zusammen, Rot = gegenläufig. Für den Core suchen wir eine Engine und ein sicheres Asset mit tiefer Korrelation.</p>
{heat}</section>"""
    p = settings.DIRS["dashboard"] / "panels"
    p.mkdir(exist_ok=True)
    (p / "10_asset_study.html").write_text(html_out)


if __name__ == "__main__":
    df, _ = run()
    pd.set_option("display.width", 200)
    print(df[["labels", "cagr_train", "vol", "corr_spy", "n_high", "n_dip", "trend_gap"]]
          .round(3).to_string())
