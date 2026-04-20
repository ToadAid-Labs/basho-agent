"""
Performance tracking and metrics calculation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import statistics
from enum import Enum


class TradeDirection(Enum):
    """Direction of a trade."""
    BUY = "buy"
    SELL = "sell"


class TradeStatus(Enum):
    """Status of a trade."""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"
    CLOSED = "closed"


@dataclass
class Trade:
    """Represents a trade execution."""
    trade_id: str
    direction: TradeDirection
    token_address: str
    amount: float
    price: float
    timestamp: datetime = field(default_factory=datetime.now)
    status: TradeStatus = TradeStatus.PENDING
    gas_cost: float = 0.0
    actual_amount: float = 0.0
    actual_price: float = 0.0
    profit_loss: float = 0.0
    profit_loss_percent: float = 0.0
    slippage: float = 0.0
    error_message: str = ""

    def __post_init__(self):
        """Calculate profit/loss if both buy and sell are known."""
        if self.status == TradeStatus.CLOSED and self.actual_price > 0:
            if self.direction == TradeDirection.BUY:
                total_cost = self.amount * self.price + self.gas_cost
                total_value = self.actual_amount * self.actual_price
                self.profit_loss = total_value - total_cost
                if total_cost > 0:
                    self.profit_loss_percent = (self.profit_loss / total_cost) * 100
            elif self.direction == TradeDirection.SELL:
                total_revenue = self.amount * self.price - self.gas_cost
                total_cost = self.actual_amount * self.actual_price
                self.profit_loss = total_revenue - total_cost
                if total_cost > 0:
                    self.profit_loss_percent = (self.profit_loss / total_cost) * 100


class PerformanceMetrics:
    """Calculates and tracks performance metrics."""

    def __init__(self):
        self.trades: List[Trade] = []
        self.start_date: Optional[datetime] = None
        self.end_date: Optional[datetime] = None
        self.initial_capital: float = 10000.0
        self.current_capital: float = 10000.0

    def add_trade(self, trade: Trade):
        """Add a trade to the tracker."""
        if not self.start_date:
            self.start_date = trade.timestamp
        self.end_date = trade.timestamp
        self.trades.append(trade)

    def get_total_trades(self) -> int:
        """Get total number of trades."""
        return len(self.trades)

    def get_closed_trades(self) -> List[Trade]:
        """Get all closed trades."""
        return [t for t in self.trades if t.status == TradeStatus.CLOSED]

    def get_win_rate(self) -> float:
        """Get win rate (closed trades that are profitable)."""
        closed_trades = self.get_closed_trades()
        if not closed_trades:
            return 0.0

        winning_trades = [t for t in closed_trades if t.profit_loss > 0]
        return (len(winning_trades) / len(closed_trades)) * 100

    def get_avg_profit(self) -> float:
        """Get average profit of closed trades."""
        closed_trades = self.get_closed_trades()
        if not closed_trades:
            return 0.0

        profits = [t.profit_loss for t in closed_trades]
        return statistics.mean(profits)

    def get_avg_loss(self) -> float:
        """Get average loss of closed trades."""
        closed_trades = [t for t in self.get_closed_trades() if t.profit_loss < 0]
        if not closed_trades:
            return 0.0

        losses = [t.profit_loss for t in closed_trades]
        return statistics.mean(losses)

    def get_profit_factor(self) -> float:
        """Get profit factor from closed trades."""
        closed_trades = self.get_closed_trades()
        if not closed_trades:
            return 0.0

        gross_profit = sum(t.profit_loss for t in closed_trades if t.profit_loss > 0)
        gross_loss = abs(sum(t.profit_loss for t in closed_trades if t.profit_loss < 0))

        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0

        return gross_profit / gross_loss

    def get_sharpe_ratio(self, risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio."""
        closed_trades = self.get_closed_trades()
        if len(closed_trades) < 2:
            return 0.0

        returns = [t.profit_loss_percent / 100 for t in closed_trades]
        if not returns:
            return 0.0

        if len(returns) > 1:
            mean_return = statistics.mean(returns)
            std_return = statistics.stdev(returns)
            if std_return == 0:
                return 0.0
            return (mean_return - risk_free_rate) / std_return
        return returns[0]

    def get_max_drawdown(self) -> float:
        """Calculate maximum drawdown."""
        if not self.trades:
            return 0.0

        capital = [self.initial_capital]
        for i in range(1, len(self.trades) + 1):
            cumulative_pnl = sum(t.profit_loss for t in self.trades[:i])
            capital.append(self.initial_capital + cumulative_pnl)

        max_drawdown = 0.0
        peak = capital[0]

        for c in capital[1:]:
            if c > peak:
                peak = c
            drawdown = (peak - c) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return max_drawdown * 100

    def get_total_return(self) -> float:
        """Get total return percentage."""
        if not self.trades:
            return 0.0

        total_pnl = sum(t.profit_loss for t in self.trades)
        return (total_pnl / self.initial_capital) * 100

    def get_total_gas_cost(self) -> float:
        """Get total gas cost."""
        return sum(t.gas_cost for t in self.trades)

    def get_avg_execution_time(self) -> float:
        """Get average execution time."""
        if not self.trades:
            return 0.0
        return statistics.mean([t.actual_price if hasattr(t, 'actual_price') else 0 for t in self.trades])

    def get_best_trade(self) -> Optional[Trade]:
        """Get best performing trade."""
        closed_trades = self.get_closed_trades()
        if not closed_trades:
            return None
        return max(closed_trades, key=lambda t: t.profit_loss)

    def get_worst_trade(self) -> Optional[Trade]:
        """Get worst performing trade."""
        closed_trades = self.get_closed_trades()
        if not closed_trades:
            return None
        return min(closed_trades, key=lambda t: t.profit_loss)

    def get_trades_by_token(self, token_address: str) -> List[Trade]:
        """Get trades for specific token."""
        return [t for t in self.trades if t.token_address == token_address]

    def get_metrics(self) -> dict:
        """Get comprehensive metrics."""
        closed_trades = self.get_closed_trades()

        return {
            'total_trades': self.get_total_trades(),
            'closed_trades': len(closed_trades),
            'open_trades': sum(1 for t in self.trades if t.status == TradeStatus.OPEN),
            'win_rate': self.get_win_rate(),
            'avg_profit': self.get_avg_profit(),
            'avg_loss': self.get_avg_loss(),
            'sharpe_ratio': self.get_sharpe_ratio(),
            'max_drawdown': self.get_max_drawdown(),
            'total_return': self.get_total_return(),
            'total_gas_cost': self.get_total_gas_cost(),
            'avg_execution_time': self.get_avg_execution_time(),
            'best_trade': self.get_best_trade().to_dict() if self.get_best_trade() else None,
            'worst_trade': self.get_worst_trade().to_dict() if self.get_worst_trade() else None,
            'time_period': {
                'start': self.start_date.isoformat() if self.start_date else None,
                'end': self.end_date.isoformat() if self.end_date else None
            }
        }

    def clear_trades(self):
        """Clear all trades."""
        self.trades.clear()
        self.start_date = None
        self.end_date = None
        self.initial_capital = 10000.0
        self.current_capital = 10000.0

    def export_metrics(self, filename: str):
        """Export metrics to JSON file."""
        with open(filename, 'w') as f:
            import json
            json.dump(self.get_metrics(), f, indent=2)


class PerformanceTracker:
    """Main performance tracking interface."""

    def __init__(self):
        self.metrics = PerformanceMetrics()

    def track_trade(self, trade: Trade):
        """Track a trade."""
        self.metrics.add_trade(trade)

    def get_metrics(self) -> dict:
        """Get current metrics."""
        return self.metrics.get_metrics()

    def reset(self):
        """Reset all metrics."""
        self.metrics.clear_trades()

    def export(self, filename: str):
        """Export metrics to file."""
        self.metrics.export_metrics(filename)
