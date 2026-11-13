"""Scheduler-Einstieg (Prompt 9). Dein Computer startet dieses Skript alle 30 Minuten.
Es entscheidet anhand der New-York-Zeit selbst, was zu tun ist – Zeitzone und
Sommerzeit deines Computers spielen keine Rolle.

  09:35–15:30 NY, Handelstag, Morgen-Check heute noch nicht gelaufen -> Morgen-Check
  ab 19:05 NY,   Handelstag, Abend-Lauf heute noch nicht gelaufen    -> Abend-Lauf
  ab 23:30 NY,   Abend-Lauf fehlt                                     -> Alarm "verpasster Lauf"
"""
from __future__ import annotations

import datetime as dt
import traceback

from . import notify, settings
from .bot import NY, Abort, Bot, live_prices, load_config, load_state
from .broker import AlpacaBroker

LOG = settings.DIRS["logs"] / "scheduler.log"


def log(msg):
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{dt.datetime.now(NY).isoformat(timespec='seconds')} {msg}\n")


def main():
    now = dt.datetime.now(NY)
    hm, today = now.strftime("%H:%M"), now.date()
    st = load_state()
    try:
        broker = AlpacaBroker()
        if not broker.is_trading_day(today):
            log("kein Handelstag")
            return
        cfg = load_config()
        bot = Bot(broker, lambda d: live_prices(cfg), cfg=cfg)
        if "09:35" <= hm <= "15:30" and st.get("last_morning") != str(today):
            log(f"Morgen-Check: {bot.morning(today)}")
        elif hm >= settings.load()["broker"]["evening_run_after"] and st.get("last_run") != str(today):
            missed_flag = settings.DIRS["logs"] / f"missed-{today}"
            if hm >= "23:30" and not missed_flag.exists():
                missed_flag.write_text("1")
                notify.send(f"⏰ Abend-Lauf {today} hat bis 23:30 NY nicht geklappt – Computer wach/online?")
            r = bot.evening(today)
            log(f"Abend-Lauf: {r.get('status')} Orders={len(r.get('orders', []))}")
        else:
            log("nichts zu tun")
    except Abort as e:
        log(f"STOPP: {e}")
    except Exception as e:
        log("FEHLER: " + "".join(traceback.format_exception_only(type(e), e)).strip())
        notify.send(f"❌ Bot-Fehler {today}: {e}")


if __name__ == "__main__":
    main()
