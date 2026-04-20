"""
Monitoring and analytics module for the agent.

This module provides:
- Trade tracking and performance metrics
- Backtesting capabilities
- Market analysis and condition monitoring
- Alerting and notifications
"""

from .performance import (
    Trade,
    TradeDirection,
    TradeStatus,
    PerformanceMetrics,
    PerformanceTracker
)

from .backtesting import (
    BacktestResult,
    BacktestResultStatus,
    Backtester,
    Strategy,
    SimpleMovingAverageStrategy,
    MomentumStrategy
)

from .market_analyzer import (
    MarketCondition,
    MarketConditionData,
    VolatilityReport,
    MarketAnalyzer
)

from .alerts import (
    Alert,
    AlertPriority,
    AlertType,
    AlertManager
)

__all__ = [
    'Trade',
    'TradeDirection',
    'TradeStatus',
    'PerformanceMetrics',
    'PerformanceTracker',
    'BacktestResult',
    'BacktestResultStatus',
    'Backtester',
    'Strategy',
    'SimpleMovingAverageStrategy',
    'MomentumStrategy',
    'MarketCondition',
    'MarketConditionData',
    'VolatilityReport',
    'MarketAnalyzer',
    'Alert',
    'AlertPriority',
    'AlertType',
    'AlertManager'
]

__version__ = '1.0.0'