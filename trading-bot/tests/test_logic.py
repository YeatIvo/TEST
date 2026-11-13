"""Phase L: Daten, Indikatoren und Studie prüfen."""
import json

import numpy as np
import pandas as pd
import pytest

from src import data, settings, study
from src.indicators import rsi, sma, trend_up, vol_high

HAVE_DATA = (settings.DIRS["research"] / "manifest.json").exists()


def test_rsi_bounds_and_extremes():
    up = pd.Series(np.arange(1, 50, dtype=float))
    assert rsi(up, 2).dropna().iloc[-1] == pytest.approx(100)
    dn = pd.Series(np.arange(50, 1, -1, dtype=float))
    assert rsi(dn, 2).dropna().iloc[-1] < 1
    rnd = pd.Series(np.random.default_rng(0).normal(0, 1, 500).cumsum() + 100)
    r = rsi(rnd, 2).dropna()
    assert r.between(0, 100).all()


def test_indicators_use_only_past():
    """Indikator am Tag t darf sich nicht ändern, wenn die Zukunft abgeschnitten wird."""
    s = pd.Series(np.random.default_rng(1).normal(0, 1, 600).cumsum() + 100)
    for f in (lambda x: sma(x, 200), lambda x: rsi(x, 2), lambda x: trend_up(x),
              lambda x: vol_high(x)):
        full = f(s)
        cut = f(s.iloc[:400])
        pd.testing.assert_series_equal(full.iloc[:400], cut, check_names=False)


def test_fwd_never_crosses_window():
    idx = pd.bdate_range("2024-12-01", periods=40)
    c = pd.Series(np.linspace(100, 140, 40), index=idx)
    f = study._fwd(c, 5, pd.Timestamp("2024-12-31"))
    last_valid = f.dropna().index.max()
    assert idx[idx.get_loc(last_valid) + 5] <= pd.Timestamp("2024-12-31")


@pytest.mark.skipif(not HAVE_DATA, reason="Forschungsdaten fehlen (python -m src.data)")
def test_research_data_frozen_and_clean():
    m = data.manifest()
    assert set(m["tickers"]) == set(settings.load()["universe"]["study_tickers"])
    for t in m["tickers"]:
        df = data.load_research(t)
        assert df.index.is_monotonic_increasing and not df.index.duplicated().any()
        assert (df["close"] > 0).all()
        assert df.index[0] <= pd.Timestamp("2020-01-10")


@pytest.mark.skipif(not HAVE_DATA, reason="Forschungsdaten fehlen")
def test_labels_written():
    labels = json.loads((settings.DIRS["rules"] / "labels.json").read_text())
    assert len(labels) == 24
    assert all(set(v) <= set(study.LABEL_DE) for v in labels.values())
