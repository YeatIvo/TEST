"""Scheduler-Logik: verspätete Starts dürfen keinen Abend-Lauf verpassen."""
import datetime as dt

from src.bot import NY
from src.tick import Session, plan


def S(y, m, d, o=(9, 30), c=(16, 0)):
    return Session(dt.date(y, m, d), dt.datetime(y, m, d, *o, tzinfo=NY), dt.datetime(y, m, d, *c, tzinfo=NY))


# Do 12.11., Fr 13.11., Mo 16.11.2026
CAL = [S(2026, 11, 12), S(2026, 11, 13), S(2026, 11, 16)]
T = lambda m, d, h, mi=0: dt.datetime(2026, m, d, h, mi, tzinfo=NY)


def test_friday_evening_normal():
    assert plan(T(11, 13, 19, 20), CAL, "2026-11-12", "2026-11-13") == [("evening", dt.date(2026, 11, 13))]


def test_friday_run_delayed_into_saturday_still_runs():
    """Der Fehler vom 13.11.: GitHub startete erst Samstag 01:25 NY."""
    assert plan(T(11, 14, 1, 25), CAL, "2026-11-12", "2026-11-13") == [("evening", dt.date(2026, 11, 13))]


def test_friday_run_can_be_caught_up_monday_morning_with_alarm():
    acts = plan(T(11, 16, 8, 30), CAL, "2026-11-12", "2026-11-13")
    assert ("evening", dt.date(2026, 11, 13)) in acts and ("late", dt.date(2026, 11, 13)) in acts


def test_too_late_after_cutoff():
    assert plan(T(11, 16, 9, 20), CAL, "2026-11-12", "2026-11-13") == []


def test_already_ran_nothing_to_do():
    assert plan(T(11, 14, 3, 0), CAL, "2026-11-13", "2026-11-13") == []


def test_morning_check_then_evening_same_tick_if_delayed():
    acts = plan(T(11, 13, 20, 0), CAL, "2026-11-12", "2026-11-12")
    assert acts == [("morning", dt.date(2026, 11, 13)), ("evening", dt.date(2026, 11, 13))]


def test_no_opg_orders_before_19h():
    """Regression 17.11.: Lauf um 17:36 NY -> Alpaca lehnt OPG-Orders vor 19:00 ab."""
    assert plan(T(11, 13, 17, 36), CAL, "2026-11-12", "2026-11-12") == [("morning", dt.date(2026, 11, 13))]
    assert plan(T(11, 13, 19, 6), CAL, "2026-11-12", "2026-11-13") == [("evening", dt.date(2026, 11, 13))]


def test_no_evening_during_session():
    assert plan(T(11, 13, 12, 0), CAL, "2026-11-12", "2026-11-13") == []


def test_early_close_day():
    cal = [S(2026, 11, 25), S(2026, 11, 27, c=(13, 0)), S(2026, 11, 30)]
    assert plan(T(11, 27, 13, 30), cal, "2026-11-25", "2026-11-27") == []          # erst ab 19:05
    assert plan(T(11, 27, 19, 30), cal, "2026-11-25", "2026-11-27") == [("evening", dt.date(2026, 11, 27))]
