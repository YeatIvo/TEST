"""Broker-Schicht. Nur dieser Teil ist broker-spezifisch.

  AlpacaBroker – echtes Alpaca-PAPER-Konto (verweigert alles andere).
  SimBroker    – simuliertes Paper-Konto auf historischen Daten (Tests, Simulation).

Gemeinsame Schnittstelle:
  is_trading_day(d) · equity() · last_equity() · positions() -> {sym: qty}
  submit_moo(sym, qty, side, cid) · submit_stop(sym, qty, stop, cid)
  get_order(cid) -> dict|None · open_orders() · cancel(order_id)
"""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field

import pandas as pd

from . import settings


class BrokerSafetyError(RuntimeError):
    pass


# ------------------------------------------------------------------ Alpaca (Paper)
def _env_flags() -> dict:
    """Lädt .env in die Umgebung und meldet NUR, ob Werte gesetzt sind – nie die Werte."""
    try:
        from dotenv import load_dotenv
        load_dotenv(settings.ROOT / ".env", override=False)
    except ImportError:
        pass
    keys = ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_PAPER", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    return {k: bool(os.environ.get(k)) for k in keys}


def check_keys() -> dict:
    flags = _env_flags()
    flags["paper_mode"] = os.environ.get("ALPACA_PAPER", "").strip().lower() == "true"
    return flags


class AlpacaBroker:
    name = "alpaca-paper"

    def __init__(self):
        flags = check_keys()
        if not settings.load()["broker"]["paper_only"] or not flags["paper_mode"]:
            raise BrokerSafetyError("Nur Paper erlaubt: ALPACA_PAPER=true und broker.paper_only=true nötig.")
        if not (flags["ALPACA_API_KEY"] and flags["ALPACA_SECRET_KEY"]):
            raise BrokerSafetyError("Alpaca-Keys fehlen in .env (Werte selbst eintragen).")
        from alpaca.trading.client import TradingClient
        self.c = TradingClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"], paper=True)
        url = getattr(self.c, "_base_url", None)
        url = str(getattr(url, "value", url) or "")
        if not url.startswith("https://paper-api.alpaca.markets"):
            raise BrokerSafetyError(f"Client zeigt nicht auf die Paper-API ({url}).")

    def is_trading_day(self, d: dt.date) -> bool:
        from alpaca.trading.requests import GetCalendarRequest
        cal = self.c.get_calendar(GetCalendarRequest(start=d, end=d))
        return any(x.date == d for x in cal)

    def account(self):
        return self.c.get_account()

    def equity(self) -> float:
        return float(self.account().equity)

    def last_equity(self) -> float:
        return float(self.account().last_equity)

    def margin_allowed(self) -> bool:
        return float(self.account().multiplier) > 1

    def positions(self) -> dict[str, int]:
        return {p.symbol: int(float(p.qty)) for p in self.c.get_all_positions()}

    def submit_moo(self, sym, qty, side, cid):
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest
        return self.c.submit_order(MarketOrderRequest(
            symbol=sym, qty=qty, side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.OPG, client_order_id=cid))

    def submit_stop(self, sym, qty, stop, cid):
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import StopOrderRequest
        return self.c.submit_order(StopOrderRequest(
            symbol=sym, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.GTC,
            stop_price=round(stop, 2), client_order_id=cid))

    def get_order(self, cid) -> dict | None:
        try:
            o = self.c.get_order_by_client_id(cid)
        except Exception:
            return None
        return {"id": str(o.id), "cid": cid, "symbol": o.symbol, "side": str(o.side.value),
                "qty": int(float(o.qty)), "status": str(o.status.value),
                "filled_qty": int(float(o.filled_qty or 0)),
                "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
                "type": str(o.order_type.value)}

    def open_orders(self) -> list[dict]:
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest
        return [{"id": str(o.id), "cid": o.client_order_id, "symbol": o.symbol, "type": str(o.order_type.value),
                 "qty": int(float(o.qty)), "side": str(o.side.value)}
                for o in self.c.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))]

    def cancel(self, order_id):
        self.c.cancel_order_by_id(order_id)


# ------------------------------------------------------------------ Simulation
@dataclass
class SimBroker:
    """Paper-Konto auf historischen Kursen. Market-on-Open füllt zum nächsten Open,
    Stops füllen zum Stop (oder Open bei Gap). Ganze Aktien, Margin erlaubt."""
    prices: dict[str, pd.DataFrame]
    cash: float = 100000.0
    date: pd.Timestamp | None = None
    pos: dict = field(default_factory=dict)
    orders: dict = field(default_factory=dict)
    _prev_equity: float | None = None
    margin_rate: float = 0.065
    name: str = "sim-paper"

    def calendar(self):
        return self.prices["SPY"].index

    def is_trading_day(self, d) -> bool:
        return pd.Timestamp(d) in self.calendar()

    def _close(self, sym, d=None):
        return float(self.prices[sym].loc[d or self.date, "close"])

    def equity(self) -> float:
        return self.cash + sum(q * self._close(s) for s, q in self.pos.items() if q)

    def last_equity(self) -> float:
        return self._prev_equity if self._prev_equity is not None else self.equity()

    def margin_allowed(self) -> bool:
        return True

    def positions(self):
        return {s: q for s, q in self.pos.items() if q}

    def _add(self, sym, qty, side, cid, typ, stop=None):
        if cid in self.orders:
            raise ValueError(f"client_order_id doppelt: {cid}")
        self.orders[cid] = {"id": cid, "cid": cid, "symbol": sym, "side": side, "qty": int(qty), "type": typ,
                            "stop": stop, "status": "accepted" if typ == "market" else "new",
                            "filled_qty": 0, "filled_avg_price": None, "placed": self.date}
        return self.orders[cid]

    def submit_moo(self, sym, qty, side, cid):
        return self._add(sym, qty, side, cid, "market")

    def submit_stop(self, sym, qty, stop, cid):
        if qty > self.pos.get(sym, 0) - self._reserved(sym):
            raise ValueError(f"Stop {sym} {qty} > verfügbare Aktien")
        return self._add(sym, qty, "sell", cid, "stop", stop)

    def _reserved(self, sym):
        return sum(o["qty"] for o in self.orders.values()
                   if o["symbol"] == sym and o["type"] == "stop" and o["status"] == "new")

    def get_order(self, cid):
        return dict(self.orders[cid]) if cid in self.orders else None

    def open_orders(self):
        return [dict(o) for o in self.orders.values() if o["status"] in ("new", "accepted")]

    def cancel(self, order_id):
        if self.orders[order_id]["status"] in ("new", "accepted"):
            self.orders[order_id]["status"] = "canceled"

    def _fill(self, o, px, cost):
        q = o["qty"] if o["side"] == "buy" else -o["qty"]
        self.pos[o["symbol"]] = self.pos.get(o["symbol"], 0) + q
        self.cash -= q * px + abs(q) * px * cost
        o.update(status="filled", filled_qty=o["qty"], filled_avg_price=px, filled_on=self.date)

    def open_session(self, d):
        """Neuer Handelstag: Zinsen, offene Stops mit Gap, dann MOO-Fills zum Open."""
        if self.date is not None:
            self._prev_equity = self.equity()
        d = pd.Timestamp(d)
        if self.cash < 0 and self.date is not None:
            self.cash -= -self.cash * self.margin_rate / 252
        self.date = d
        for o in list(self.orders.values()):
            if o["type"] == "market" and o["status"] == "accepted":
                self._fill(o, float(self.prices[o["symbol"]].loc[d, "open"]), settings.cost_per_side(o["symbol"]))

    def run_stops(self):
        """Stops im Tagesverlauf (nach dem Morgen-Check)."""
        d = self.date
        for o in list(self.orders.values()):
            if o["type"] == "stop" and o["status"] == "new":
                bar = self.prices[o["symbol"]].loc[d]
                if bar["open"] <= o["stop"]:
                    self._fill(o, float(bar["open"]), settings.cost_per_side(o["symbol"]))
                elif bar["low"] <= o["stop"]:
                    self._fill(o, float(o["stop"]), settings.cost_per_side(o["symbol"]))
