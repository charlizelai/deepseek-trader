"""
Main loop: market snapshot -> DeepSeek trade intent -> RiskEngine veto -> paper execution.
ccxt is used READ-ONLY (public market data); no real orders are ever placed here.

Fail-closed: if any data source / API call fails, the round is skipped --
the model never trades on stale or reconstructed data.
"""
import logging
import signal
import time
from datetime import datetime, timezone

import ccxt

from config import INITIAL_BALANCE, LOOP_INTERVAL, SYMBOL
from llm_proposal import get_trade_intent
from paper_exchange import PaperExchange
from risk_engine import RiskEngine, RiskState, TradeRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("trader")


def fetch_snapshot(exchange, limit=20):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe="1m", limit=limit)
    closes = [c[4] for c in ohlcv]
    return {
        "symbol": SYMBOL,
        "recent_closes": closes,
        "last_price": closes[-1],
        "change_pct_5": (closes[-1] - closes[-5]) / closes[-5] * 100 if len(closes) >= 5 else 0.0,
    }


def maybe_reset_day(state):
    """Reset the intraday drawdown reference at 00:00 UTC."""
    today = datetime.now(timezone.utc).date()
    if getattr(state, "_day", None) != today:
        state._day = today
        state.day_start_equity = state.equity
        log.info("New UTC day %s: daily drawdown reference reset to %.2f", today, state.equity)


def main():
    exchange = ccxt.binance({"enableRateLimit": True})  # read-only, no API keys attached
    exchange.load_markets()
    log.info("INIT balance=%.2f symbol=%s interval=%ds", INITIAL_BALANCE, SYMBOL, LOOP_INTERVAL)

    state = RiskState(
        equity=INITIAL_BALANCE,
        peak_equity=INITIAL_BALANCE,
        day_start_equity=INITIAL_BALANCE,
    )
    engine = RiskEngine(state)
    paper = PaperExchange(balance=INITIAL_BALANCE)

    running = True

    def _stop(_sig, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    while running:
        try:
            maybe_reset_day(state)

            # 1) refresh price/snapshot FIRST -- never decide on stale data
            snapshot = fetch_snapshot(exchange)
            price = snapshot["last_price"]

            # 2) check open position against SL/TP
            exit_result = paper.check_exit(price)
            if exit_result:
                engine.on_trade_closed(exit_result["pnl"])
                log.info("EXIT %s | equity=%.2f", exit_result, state.equity)

            # 3) one position at a time: no new intents while open
            if paper.open_position is not None:
                pos = paper.open_position
                log.info(
                    "HOLD open entry=%.2f SL=%.2f TP=%.2f price=%.2f",
                    pos.entry_price, pos.stop_loss_price, pos.take_profit_price, price,
                )
                time.sleep(LOOP_INTERVAL)
                continue

            # 4) DeepSeek proposal (structured TradeIntent only)
            intent = get_trade_intent(snapshot)
            log.info("INTENT %s", intent)

            # 5) hard risk gate -- code holds the veto
            req = TradeRequest(side=intent["side"], symbol=intent["symbol"], price=price)
            decision = engine.evaluate(req)
            log.info("RISK allowed=%s reason=%s", decision.allowed, decision.reason)

            if decision.allowed and intent["side"] != "hold":
                pos = paper.execute(decision, intent["side"], SYMBOL, price)
                if pos:
                    log.info(
                        "OPEN %s %.2f USD @ %.2f SL=%.2f TP=%.2f",
                        pos.side, pos.amount_usd, pos.entry_price,
                        pos.stop_loss_price, pos.take_profit_price,
                    )

        except Exception as e:  # fail-closed: skip round, never trade on missing data
            log.error("ERROR %s -- skipping round", e)
            time.sleep(LOOP_INTERVAL)
            continue

        time.sleep(LOOP_INTERVAL)

    log.info("Shutdown. equity=%.2f closed_trades=%d", state.equity, len(paper.closed_trades))


if __name__ == "__main__":
    main()
