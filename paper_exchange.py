"""
Paper exchange: in-memory ledger that simulates fills without touching any
real exchange. Stop-loss / take-profit exits are pure price comparisons --
condition-triggered code, never a model decision.
"""
from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass
class PaperPosition:
    id: str
    symbol: str
    side: str          # buy / sell
    entry_price: float
    amount_usd: float
    stop_loss_price: float
    take_profit_price: float


@dataclass
class PaperExchange:
    balance: float
    open_position: Optional[PaperPosition] = None
    closed_trades: list = field(default_factory=list)

    def execute(self, decision, side: str, symbol: str, current_price: float) -> Optional[PaperPosition]:
        """Open a position using the RiskDecision's approved amount. One position at a time."""
        if self.open_position is not None:
            return None
        pos = PaperPosition(
            id=str(uuid.uuid4())[:8],
            symbol=symbol,
            side=side,
            entry_price=current_price,
            amount_usd=decision.approved_amount_usd,
            stop_loss_price=decision.stop_loss_price,
            take_profit_price=decision.take_profit_price,
        )
        self.open_position = pos
        return pos

    def check_exit(self, current_price: float) -> Optional[dict]:
        """Close the open position if SL/TP is hit; returns the trade record."""
        pos = self.open_position
        if pos is None:
            return None

        hit_sl = (
            (pos.side == "buy" and current_price <= pos.stop_loss_price)
            or (pos.side == "sell" and current_price >= pos.stop_loss_price)
        )
        hit_tp = (
            (pos.side == "buy" and current_price >= pos.take_profit_price)
            or (pos.side == "sell" and current_price <= pos.take_profit_price)
        )
        if not (hit_sl or hit_tp):
            return None

        exit_price = current_price
        if pos.side == "buy":
            pnl = (exit_price - pos.entry_price) / pos.entry_price * pos.amount_usd
        else:
            pnl = (pos.entry_price - exit_price) / pos.entry_price * pos.amount_usd

        self.balance += pnl
        result = {
            "position_id": pos.id,
            "side": pos.side,
            "entry": pos.entry_price,
            "exit": exit_price,
            "pnl": round(pnl, 2),
            "reason": "stop_loss" if hit_sl else "take_profit",
        }
        self.closed_trades.append(result)
        self.open_position = None
        return result
