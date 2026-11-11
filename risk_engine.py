"""
Deterministic risk engine. Every trade decision passes through here AFTER the
LLM proposal and BEFORE execution. All limits come from config.py constants,
never from the model. Any failed check = rejected. No exceptions, no overrides.
"""
from dataclasses import dataclass

from config import (
    MAX_CONSECUTIVE_LOSSES,
    MAX_DAILY_DRAWDOWN,
    MAX_ORDER_USD,
    MAX_POSITION_PCT,
    STOP_LOSS_PCT,
    TAKE_PROFIT_PCT,
)


@dataclass
class RiskState:
    equity: float
    peak_equity: float
    day_start_equity: float
    consecutive_losses: int = 0
    trading_enabled: bool = True


@dataclass
class TradeRequest:
    side: str          # buy / sell / hold
    symbol: str
    price: float       # current market price, used for sizing & paper fills
    stop_loss_pct: float = STOP_LOSS_PCT
    take_profit_pct: float = TAKE_PROFIT_PCT


@dataclass
class RiskDecision:
    allowed: bool
    reason: str = ""
    approved_amount_usd: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0


class RiskEngine:
    def __init__(self, state: RiskState):
        self.state = state

    def evaluate(self, req: TradeRequest) -> RiskDecision:
        # 0. hold passes straight through (no execution needed)
        if req.side == "hold":
            return RiskDecision(allowed=True, reason="hold, no execution needed")

        # 1. Kill switch
        if not self.state.trading_enabled:
            return RiskDecision(allowed=False, reason="trading disabled (kill switch)")

        # 2. Consecutive-loss circuit breaker
        if self.state.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            return RiskDecision(
                allowed=False,
                reason=f"consecutive losses {self.state.consecutive_losses} >= {MAX_CONSECUTIVE_LOSSES}",
            )

        # 3. Intraday drawdown circuit breaker
        day_dd = (self.state.day_start_equity - self.state.equity) / self.state.day_start_equity
        if day_dd >= MAX_DAILY_DRAWDOWN:
            return RiskDecision(
                allowed=False,
                reason=f"daily drawdown {day_dd:.2%} >= {MAX_DAILY_DRAWDOWN:.2%}",
            )

        # 4. Position sizing: min(equity % cap, per-order USD cap) -- code-decided, not model-decided
        by_pct = self.state.equity * MAX_POSITION_PCT
        amount_usd = min(by_pct, MAX_ORDER_USD)

        if amount_usd <= 0:
            return RiskDecision(allowed=False, reason="computed amount <= 0")

        # 5. Stop-loss / take-profit prices attached at entry, in code
        if req.side == "buy":
            sl = req.price * (1 - req.stop_loss_pct)
            tp = req.price * (1 + req.take_profit_pct)
        else:  # sell
            sl = req.price * (1 + req.stop_loss_pct)
            tp = req.price * (1 - req.take_profit_pct)

        return RiskDecision(
            allowed=True,
            reason=f"approved: {amount_usd:.2f} USD at {req.price}",
            approved_amount_usd=amount_usd,
            stop_loss_price=sl,
            take_profit_price=tp,
        )

    def on_trade_closed(self, pnl: float):
        """Update risk state after each closed trade."""
        self.state.equity += pnl
        self.state.peak_equity = max(self.state.peak_equity, self.state.equity)
        if pnl < 0:
            self.state.consecutive_losses += 1
        else:
            self.state.consecutive_losses = 0
        if self.state.equity <= 0:
            self.state.trading_enabled = False
