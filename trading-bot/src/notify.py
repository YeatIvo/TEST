"""Alerts ans Handy über Telegram (optional). Ohne Keys wird nur ins Log geschrieben."""
from __future__ import annotations

import datetime as dt
import os

from . import settings
from .broker import check_keys

LOG = settings.DIRS["logs"] / "alerts.log"


def send(text: str, practice: bool = False) -> bool:
    if practice:
        text = "PRACTICE · " + text
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {text}\n")
    flags = check_keys()
    if not (flags["TELEGRAM_BOT_TOKEN"] and flags["TELEGRAM_CHAT_ID"]):
        return False
    import requests
    try:
        r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                          json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text[:4000]}, timeout=15)
        return r.ok
    except Exception:
        return False


if __name__ == "__main__":
    ok = send("Test vom Trading-Bot: Handy-Alerts sind eingerichtet.")
    print("Telegram gesendet" if ok else "Telegram nicht konfiguriert – nur ins Log geschrieben (logs/alerts.log)")
