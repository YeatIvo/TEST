"""Scheduler-Einstieg (Prompt 9). Wird mehrmals pro Tag gestartet (GitHub Actions oder
Computer-Scheduler) und entscheidet anhand der New-York-Zeit und des Alpaca-Börsenkalenders selbst.

Robust gegen verspätete Starts (GitHub verschiebt geplante Läufe teils um Stunden):
  * Morgen-Check: an einem Handelstag ab Open + 5 Min., einmal pro Tag.
  * Abend-Lauf für die letzte abgeschlossene Sitzung S: ab Schluss(S) + 15 Min. bis
    Open(nächster Handelstag) − 15 Min. (Alpaca nimmt Market-on-Open-Orders bis 09:28 NY an).
    Ein Lauf am Freitag kann also bis Montagmorgen nachgeholt werden – die Order gilt
    trotzdem zum nächsten Open, genau wie im Backtest.
  * Alarm, wenn der Abend-Lauf weniger als 75 Min. vor dem nächsten Open noch fehlt.
"""
from __future__ import annotations

import datetime as dt
import traceback
from dataclasses import dataclass

from . import notify, settings
from .bot import NY, Abort, Bot, live_prices, load_config, load_state
from .broker import AlpacaBroker

LOG = settings.DIRS["logs"] / "scheduler.log"
EVENING_DELAY = dt.timedelta(minutes=15)
OPG_CUTOFF = dt.timedelta(minutes=15)
MORNING_DELAY = dt.timedelta(minutes=5)
LATE_ALERT = dt.timedelta(minutes=75)


@dataclass(frozen=True)
class Session:
    date: dt.date
    open: dt.datetime     # NY, zeitzonenbewusst
    close: dt.datetime


def log(msg):
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{dt.datetime.now(NY).isoformat(timespec='seconds')} {msg}\n")


def _ny(t: dt.datetime) -> dt.datetime:
    return t.replace(tzinfo=NY) if t.tzinfo is None else t.astimezone(NY)


def sessions(broker, now: dt.datetime) -> list[Session]:
    from alpaca.trading.requests import GetCalendarRequest
    cal = broker.c.get_calendar(GetCalendarRequest(start=now.date() - dt.timedelta(days=10),
                                                   end=now.date() + dt.timedelta(days=10)))
    return sorted((Session(c.date, _ny(c.open), _ny(c.close)) for c in cal), key=lambda s: s.date)


def plan(now: dt.datetime, sess: list[Session], last_run: str | None, last_morning: str | None) -> list[tuple]:
    """Reine Funktion: welche Schritte sind jetzt fällig? -> [("morning", d), ("evening", d), ("late", d)]"""
    actions = []
    today = next((s for s in sess if s.date == now.date()), None)
    if today and now >= today.open + MORNING_DELAY and last_morning != str(today.date):
        actions.append(("morning", today.date))
    closed = [s for s in sess if s.close + EVENING_DELAY <= now]
    if closed:
        s = closed[-1]
        nxt = next((x for x in sess if x.date > s.date), None)
        if last_run != str(s.date) and (nxt is None or now <= nxt.open - OPG_CUTOFF):
            actions.append(("evening", s.date))
            if nxt and now >= nxt.open - LATE_ALERT:
                actions.append(("late", s.date))
    return actions


def main():
    now = dt.datetime.now(NY)
    st = load_state()
    try:
        broker = AlpacaBroker()
        acts = plan(now, sessions(broker, now), st.get("last_run"), st.get("last_morning"))
        if not acts:
            log("nichts zu tun")
            return
        cfg = load_config()
        bot = Bot(broker, lambda d: live_prices(cfg), cfg=cfg)
        for kind, d in acts:
            if kind == "late":
                notify.send(f"⏰ Abend-Lauf für {d} wird knapp (Open bald) – wird jetzt versucht.")
            elif kind == "morning":
                log(f"Morgen-Check {d}: {bot.morning(d)}")
            else:
                r = bot.evening(d)
                log(f"Abend-Lauf {d}: {r.get('status')} Orders={len(r.get('orders', []))}")
    except Abort as e:
        log(f"STOPP: {e}")
    except Exception as e:
        log("FEHLER: " + "".join(traceback.format_exception_only(type(e), e)).strip())
        notify.send(f"❌ Bot-Fehler {now.date()}: {e}")
        raise


if __name__ == "__main__":
    main()
