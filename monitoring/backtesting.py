"""
Backtesting engine for strategy validation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from enum import Enum
import json
from .performance import Trade, TradeStatus


class BacktestResultStatus(Enum):
    """Status of a backtest run."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    backtest_id: str
    strategy: str
    start_date: datetime
    end_date: datetime
    status: BacktestResultStatus
    initial_capital: float
    final_capital: float
    total_return: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    total_profit: float
    total_loss: float
    metrics: Dict
    trades: List[Trade] = field(default_factory=list)
    error_message: str = ""
    execution_time: float = 0.0

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            'backtest_id': self.backtest_id,
            'strategy': self.strategy,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'status': self.status.value,
            'initial_capital': self.initial_capital,
            'final_capital': self.final_capital,
            'total_return': self.total_return,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'total_profit': self.total_profit,
            'total_loss': self.total_loss,
            'metrics': self.metrics,
            'error_message': self.error_message,
            'execution_time': self.execution_time
        }


class Backtester:
    """Backtesting engine for trading strategies."""

    def __init__(self):
        self.results: List[BacktestResult] = []

    def backtest_strategy(
        self,
        strategy: 'Strategy',
        historical_data: List[Dict],
        initial_capital: float = 10000.0,
        commission: float = 0.001
    ) -> BacktestResult:
        """
        Run a backtest on a strategy.

        Args:
            strategy: Strategy to backtest
            historical_data: Historical market data
            initial_capital: Starting capital
            commission: Trading commission rate

        Returns:
            BacktestResult with performance metrics
        """
        start_time = datetime.now()

        try:
            # Initialize strategy with historical data
            strategy.initialize(historical_data)

            # Run the backtest
            trades = strategy.run_backtest(initial_capital, commission)

            # Calculate metrics
            result = self._calculate_metrics(
                strategy.name,
                initial_capital,
                trades,
                start_time
            )

            result.status = BacktestResultStatus.SUCCESS
            result.trades = trades
            result.final_capital = initial_capital + sum(t.profit_loss for t in trades)

            return result

        except Exception as e:
            return BacktestResult(
                backtest_id=self._generate_id(),
                strategy=strategy.name,
                start_date=datetime.now(),
                end_date=datetime.now(),
                status=BacktestResultStatus.FAILED,
                initial_capital=initial_capital,
                final_capital=initial_capital,
                total_return=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                total_profit=0.0,
                total_loss=0.0,
                metrics={},
                error_message=str(e),
                execution_time=(datetime.now() - start_time).total_seconds()
            )

    def _calculate_metrics(
        self,
        strategy_name: str,
        initial_capital: float,
        trades: List[Trade],
        start_time: datetime
    ) -> BacktestResult:
        """Calculate performance metrics from trades."""
        from .performance import PerformanceMetrics

        metrics = PerformanceMetrics()
        for trade in trades:
            metrics.add_trade(trade)

        winning_trades = [t for t in trades if t.profit_loss > 0]
        losing_trades = [t for t in trades if t.profit_loss < 0]

        total_profit = sum(t.profit_loss for t in winning_trades)
        total_loss = sum(t.profit_loss for t in losing_trades)

        final_capital = initial_capital + total_profit

        return BacktestResult(
            backtest_id=self._generate_id(),
            strategy=strategy_name,
            start_date=start_time,
            end_date=datetime.now(),
            status=BacktestResultStatus.SUCCESS,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=((final_capital - initial_capital) / initial_capital) * 100,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=(len(winning_trades) / len(trades)) * 100 if trades else 0.0,
            sharpe_ratio=metrics.get_sharpe_ratio(),
            max_drawdown=metrics.get_max_drawdown(),
            total_profit=total_profit,
            total_loss=total_loss,
            metrics=metrics.get_metrics(),
            execution_time=(datetime.now() - start_time).total_seconds()
        )

    def _generate_id(self) -> str:
        """Generate unique backtest ID."""
        import uuid
        return f"backtest_{uuid.uuid4().hex[:8]}"

    def get_results(self, strategy_name: Optional[str] = None) -> List[BacktestResult]:
        """Get backtest results."""
        if strategy_name:
            return [r for r in self.results if r.strategy == strategy_name]
        return self.results

    def get_best_result(self, metric: str = 'total_return') -> Optional[BacktestResult]:
        """Get best performing backtest result."""
        if not self.results:
            return None
        return max(self.results, key=lambda r: getattr(r, metric, 0))

    def get_worst_result(self, metric: str = 'total_return') -> Optional[BacktestResult]:
        """Get worst performing backtest result."""
        if not self.results:
            return None
        return min(self.results, key=lambda r: getattr(r, metric, 0))

    def export_result(self, result: BacktestResult, filename: str):
        """Export backtest result to JSON file."""
        with open(filename, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)

    def clear_results(self):
        """Clear all backtest results."""
        self.results.clear()


class Strategy:
    """Base strategy class for backtesting."""

    def __init__(self, name: str):
        self.name = name
        self.data = []

    def initialize(self, data: List[Dict]):
        """Initialize strategy with data."""
        self.data = data

    def run_backtest(self, initial_capital: float, commission: float) -> List[Trade]:
        """Run backtest and return trades."""
        raise NotImplementedError

    def generate_signals(self, index: int) -> Optional[bool]:
        """Generate trading signals."""
        raise NotImplementedError

    def get_historical_data(self) -> List[Dict]:
        """Get historical data."""
        return self.data


class SimpleMovingAverageStrategy(Strategy):
    """Simple moving average crossover strategy."""

    def __init__(self, short_period: int = 10, long_period: int = 30):
        super().__init__("SMA Crossover")
        self.short_period = short_period
        self.long_period = long_period

    def generate_signals(self, index: int) -> Optional[bool]:
        """Generate buy/sell signals."""
        if index < self.long_period:
            return None

        short_ma = sum(self.data[index - i]['close'] for i in range(self.short_period)) / self.short_period
        long_ma = sum(self.data[index - i]['close'] for i in range(self.long_period)) / self.long_period

        prev_short_ma = sum(self.data[index - 1 - i]['close'] for i in range(self.short_period)) / self.short_period
        prev_long_ma = sum(self.data[index - 1 - i]['close'] for i in range(self.long_period)) / self.long_period

        if prev_short_ma <= prev_long_ma and short_ma > long_ma:
            return True  # Buy signal
        elif prev_short_ma >= prev_long_ma and short_ma < long_ma:
            return False  # Sell signal

        return None

    def run_backtest(self, initial_capital: float, commission: float) -> List[Trade]:
        """Run backtest."""
        trades = []
        capital = initial_capital
        position = 0
        current_price = 0

        for i in range(len(self.data)):
            signal = self.generate_signals(i)
            data_point = self.data[i]

            if signal is True and position == 0:  # Buy
                current_price = data_point['close']
                position = capital / current_price
                capital = 0
                trades.append(Trade(
                    trade_id=f"buy_{i}",
                    direction='buy',
                    token_address=data_point.get('token_address', ''),
                    amount=position,
                    price=current_price,
                    timestamp=data_point.get('timestamp', datetime.now()),
                    status=TradeStatus.CLOSED
                ))

            elif signal is False and position > 0:  # Sell
                current_price = data_point['close']
                capital = position * current_price
                position = 0
                trades.append(Trade(
                    trade_id=f"sell_{i}",
                    direction='sell',
                    token_address=data_point.get('token_address', ''),
                    amount=current_price,  # Use price as amount proxy
                    price=current_price,
                    timestamp=data_point.get('timestamp', datetime.now()),
                    status=TradeStatus.CLOSED
                ))

        # Close any open position
        if position > 0:
            trades.append(Trade(
                trade_id=f"final_sell_{i}",
                direction='sell',
                token_address=self.data[-1].get('token_address', ''),
                amount=capital,
                price=self.data[-1]['close'],
                timestamp=self.data[-1].get('timestamp', datetime.now()),
                status=TradeStatus.CLOSED
            ))

        return trades


class MomentumStrategy(Strategy):
    """Momentum-based trading strategy."""

    def __init__(self, period: int = 20):
        super().__init__("Momentum")
        self.period = period

    def generate_signals(self, index: int) -> Optional[bool]:
        """Generate signals based on momentum."""
        if index < self.period:
            return None

        current_price = self.data[index]['close']
        start_price = self.data[index - self.period]['close']

        momentum = (current_price - start_price) / start_price

        if momentum > 0.05:  # Strong uptrend
            return True  # Buy
        elif momentum < -0.05:  # Strong downtrend
            return False  # Sell

        return None

    def run_backtest(self, initial_capital: float, commission: float) -> List[Trade]:
        """Run backtest."""
        trades = []
        capital = initial_capital
        position = 0

        for i in range(len(self.data)):
            signal = self.generate_signals(i)
            data_point = self.data[i]

            if signal is True and position == 0:
                current_price = data_point['close']
                position = capital / current_price
                capital = 0
                trades.append(Trade(
                    trade_id=f"buy_{i}",
                    direction='buy',
                    token_address=data_point.get('token_address', ''),
                    amount=position,
                    price=current_price,
                    timestamp=data_point.get('timestamp', datetime.now()),
                    status=TradeStatus.CLOSED
                ))

            elif signal is False and position > 0:
                current_price = data_point['close']
                capital = position * current_price
                position = 0
                trades.append(Trade(
                    trade_id=f"sell_{i}",
                    direction='sell',
                    token_address=data_point.get('token_address', ''),
                    amount=current_price,
                    price=current_price,
                    timestamp=data_point.get('timestamp', datetime.now()),
                    status=TradeStatus.CLOSED
                ))

        # Close position at end
        if position > 0:
            trades.append(Trade(
                trade_id=f"final_sell_{i}",
                direction='sell',
                token_address=self.data[-1].get('token_address', ''),
                amount=capital,
                price=self.data[-1]['close'],
                timestamp=self.data[-1].get('timestamp', datetime.now()),
                status=TradeStatus.CLOSED
            ))

        return trades