"""
Portfolio Tracking Model
Tracks user portfolios, trades, and performance metrics
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, DECIMAL, Boolean
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class MarketDataRecord(Base):
    """Market data records for price history and caching"""
    __tablename__ = 'market_data_records'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    price = Column(DECIMAL(20, 8), nullable=False)
    data_source = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    data_metadata = Column(String(500))


class User(Base):
    """User model for portfolio tracking"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(50), unique=True, nullable=False)
    username = Column(String(100))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime)

    portfolios = relationship("Portfolio", back_populates="user")
    trades = relationship("Trade", back_populates="user")
    alerts = relationship("Alert", back_populates="user")


class Portfolio(Base):
    """Portfolio model for user holdings"""
    __tablename__ = 'portfolios'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    total_value = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    total_pnl = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    total_trades = Column(Integer, default=0)
    closed_trades = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="portfolios")
    holdings = relationship("Holding", back_populates="portfolio")
    performance = relationship("Performance", back_populates="portfolio")


class Holding(Base):
    """Asset holding in portfolio"""
    __tablename__ = 'holdings'

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey('portfolios.id'), nullable=False)
    symbol = Column(String(20), nullable=False)
    quantity = Column(DECIMAL(20, 8), nullable=False)
    avg_cost = Column(DECIMAL(20, 8), nullable=False)
    current_price = Column(DECIMAL(20, 8))
    pnl = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    allocation = Column(DECIMAL(5, 2), default=Decimal('0.00'))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    portfolio = relationship("Portfolio", back_populates="holdings")


class Trade(Base):
    """Individual trade record (completed or open)"""
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    portfolio_id = Column(Integer, ForeignKey('portfolios.id'), nullable=False)
    agent_id = Column(Integer)  # For backward compatibility with some modules
    symbol = Column(String(20), nullable=False)
    action = Column(String(10), nullable=False)  # 'buy' or 'sell'
    trade_type = Column(String(10))  # 'buy' or 'sell' (for compatibility)
    quantity = Column(DECIMAL(20, 8), nullable=False)
    entry_price = Column(DECIMAL(20, 8), nullable=False)
    exit_price = Column(DECIMAL(20, 8))
    price = Column(DECIMAL(20, 8))  # For compatibility
    amount = Column(DECIMAL(20, 8))  # For compatibility
    pnl = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    strategy = Column(String(100))
    status = Column(String(20), default='open')  # 'open', 'closed', 'COMPLETED', etc.
    entry_date = Column(DateTime, default=datetime.utcnow)
    exit_date = Column(DateTime)
    timestamp = Column(DateTime, default=datetime.utcnow)  # For compatibility
    entry_fee = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    exit_fee = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    notes = Column(String(500))

    user = relationship("User", back_populates="trades")
    portfolio = relationship("Portfolio")


class Performance(Base):
    """Portfolio performance metrics"""
    __tablename__ = 'performance'

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey('portfolios.id'), nullable=False)
    total_value = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    total_pnl = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    return_pct = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    buy_trades = Column(Integer, default=0)
    sell_trades = Column(Integer, default=0)
    avg_pnl = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    max_drawdown = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    portfolio = relationship("Portfolio", back_populates="performance")


class Alert(Base):
    """Trading alerts for users"""
    __tablename__ = 'alerts'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    type = Column(String(50), nullable=False)  # 'PRICE_TARGET', 'STOP_LOSS', 'PATTERN_DETECTED', etc.
    symbol = Column(String(20), nullable=False)
    message = Column(String(500), nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="alerts")


class StrategyPerformance(Base):
    """Performance metrics per trading strategy"""
    __tablename__ = 'strategy_performance'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    portfolio_id = Column(Integer, ForeignKey('portfolios.id'), nullable=False)
    strategy_name = Column(String(100), nullable=False)
    trades = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    total_pnl = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    avg_pnl = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    win_rate = Column(Float, default=0.0)
    max_pnl = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    min_pnl = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    last_updated = Column(DateTime, default=datetime.utcnow)


class VolumeStatistics(Base):
    """Trading volume statistics"""
    __tablename__ = 'volume_statistics'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    portfolio_id = Column(Integer, ForeignKey('portfolios.id'), nullable=False)
    total_trades = Column(Integer, default=0)
    buy_trades = Column(Integer, default=0)
    sell_trades = Column(Integer, default=0)
    buy_to_sell_ratio = Column(Float, default=0.0)
    avg_buy_amount = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    avg_sell_amount = Column(DECIMAL(20, 8), default=Decimal('0.00'))
    earliest_entry_date = Column(DateTime)
    latest_entry_date = Column(DateTime)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# Helper functions
def get_portfolio_summary(portfolio: Portfolio, current_prices: Dict[str, float]) -> Dict:
    """Calculate portfolio summary metrics"""
    holdings = portfolio.holdings

    total_value = Decimal('0.00')
    total_pnl = Decimal('0.00')
    allocation = {}

    for holding in holdings:
        if holding.symbol in current_prices:
            holding.current_price = Decimal(str(current_prices[holding.symbol]))
            current_value = holding.quantity * holding.current_price
            holding_value = holding.quantity * holding.current_price
            holding.allocation = float((holding_value / total_value) * 100) if total_value > 0 else 0
            total_value += holding_value
            total_pnl += holding.pnl

    if total_value > 0:
        portfolio.total_value = total_value
        portfolio.total_pnl = total_pnl
        portfolio.updated_at = datetime.now(timezone.utc)
        portfolio.performance.return_pct = float((total_pnl / (portfolio.total_value - total_pnl)) * 100) if (portfolio.total_value - total_pnl) > 0 else 0.0

    return {
        'total_value': float(total_value),
        'total_pnl': float(total_pnl),
        'return_pct': portfolio.performance.return_pct if portfolio.performance else 0.0,
        'win_rate': portfolio.performance.win_rate if portfolio.performance else 0.0,
        'total_trades': portfolio.total_trades,
        'closed_trades': portfolio.closed_trades
    }


def calculate_win_rate(trades: List[Trade]) -> float:
    """Calculate win rate from trade history"""
    if not trades:
        return 0.0

    trades_to_use = get_closed_trades(trades)

    winning_trades = sum(1 for t in trades_to_use if t.pnl > 0)
    return (winning_trades / len(trades_to_use)) * 100


def get_closed_trades(trades: List[Trade]) -> List[Trade]:
    """Return the closed trades if present, otherwise the full trade list."""
    closed_statuses = {"closed", "completed", "complete"}
    closed_trades = [
        trade for trade in trades
        if str(getattr(trade, "status", "")).lower() in closed_statuses
    ]
    return closed_trades if closed_trades else trades


def get_top_assets(portfolio: Portfolio) -> List[Dict]:
    """Get top performing assets"""
    holdings = portfolio.holdings
    current_prices = {h.symbol: float(h.current_price) for h in holdings if h.current_price}

    asset_data = []

    for holding in holdings:
        if holding.symbol in current_prices:
            pnl = float(holding.pnl)
            allocation = float(holding.allocation) if holding.allocation > 0 else 0
            pnl_pct = (pnl / (portfolio.total_value * (allocation / 100))) * 100 if allocation > 0 else 0

            asset_data.append({
                'symbol': holding.symbol,
                'quantity': float(holding.quantity),
                'allocation': allocation,
                'pnl': pnl,
                'pnl_pct': pnl_pct
            })

    # Sort by P&L percentage
    asset_data.sort(key=lambda x: x['pnl_pct'], reverse=True)

    return asset_data


def calculate_strategy_performance(user_id: int, portfolio_id: int) -> Dict[str, Dict]:
    """Calculate performance metrics per strategy"""
    from sqlalchemy.orm import sessionmaker
    from app import get_session

    session = get_session()

    trades = session.query(Trade).filter(
        Trade.user_id == user_id,
        Trade.portfolio_id == portfolio_id
    ).all()

    strategies = {}
    trades_to_use = get_closed_trades(trades)

    for trade in trades_to_use:
        strategy_name = trade.strategy or "No Strategy"
        if strategy_name not in strategies:
            strategies[strategy_name] = {
                'trades': 0,
                'wins': 0,
                'losses': 0,
                'total_pnl': Decimal('0.00'),
                'avg_pnl': Decimal('0.00')
            }

        stats = strategies[strategy_name]
        stats['trades'] += 1
        pnl = Decimal(str(getattr(trade, "pnl", 0.0) or 0.0))
        stats['total_pnl'] += pnl

        if pnl > 0:
            stats['wins'] += 1
        elif pnl < 0:
            stats['losses'] += 1

    session.close()

    for strategy_name, stats in strategies.items():
        if stats['trades'] > 0:
            stats['avg_pnl'] = stats['total_pnl'] / stats['trades']
            stats['win_rate'] = (stats['wins'] / stats['trades']) * 100
        else:
            stats['win_rate'] = 0.0

    return strategies
