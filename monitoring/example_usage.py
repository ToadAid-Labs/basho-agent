#!/usr/bin/env python3
"""
Example usage of the monitoring module.

This script demonstrates:
1. Trade tracking and performance metrics
2. Backtesting with different strategies
3. Market analysis and condition monitoring
4. Alert generation and management
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from monitoring import (
    Trade,
    TradeStatus,
    TradeDirection,
    PerformanceTracker,
    PerformanceMetrics,
    Backtester,
    SimpleMovingAverageStrategy,
    MomentumStrategy,
    MarketAnalyzer,
    MarketCondition,
    Alert,
    AlertPriority,
    AlertType,
    AlertManager
)


def example_trade_tracking():
    """Example: Tracking trades and calculating performance."""
    print("\n" + "=" * 60)
    print("Example 1: Trade Tracking")
    print("=" * 60)

    # Create a performance tracker
    tracker = PerformanceTracker()

    # Add some trades
    trades = [
        Trade('trade_1', TradeDirection.BUY, '0xTokenA', 1.0, 100.0, datetime.now(), TradeStatus.CLOSED, profit_loss=20.0),
        Trade('trade_2', TradeDirection.BUY, '0xTokenB', 0.5, 200.0, datetime.now(), TradeStatus.CLOSED, profit_loss=-15.0),
        Trade('trade_3', TradeDirection.BUY, '0xTokenC', 2.0, 50.0, datetime.now(), TradeStatus.CLOSED, profit_loss=30.0),
        Trade('trade_4', TradeDirection.BUY, '0xTokenD', 1.5, 80.0, datetime.now(), TradeStatus.CLOSED, profit_loss=-10.0),
        Trade('trade_5', TradeDirection.BUY, '0xTokenE', 0.8, 150.0, datetime.now(), TradeStatus.CLOSED, profit_loss=25.0),
    ]

    for trade in trades:
        tracker.add_trade(trade)

    # Get performance metrics
    metrics = tracker.get_metrics()

    print(f"Total Trades: {metrics['total_trades']}")
    print(f"Winning Trades: {metrics['winning_trades']}")
    print(f"Losing Trades: {metrics['losing_trades']}")
    print(f"Win Rate: {metrics['win_rate']:.2f}%")
    print(f"Total Profit: ${metrics['total_profit']:.2f}")
    print(f"Total Loss: ${metrics['total_loss']:.2f}")
    print(f"Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {metrics['max_drawdown']:.2f}")


def example_backtesting():
    """Example: Backtesting trading strategies."""
    print("\n" + "=" * 60)
    print("Example 2: Backtesting")
    print("=" * 60)

    # Create mock historical data
    historical_data = []
    base_price = 100.0
    for i in range(200):
        # Generate realistic price movements
        trend = 0.0005 if i % 50 < 25 else -0.0005
        price = base_price * (1 + trend * i + random.uniform(-0.02, 0.02))
        historical_data.append({
            'timestamp': f'2024-01-01T{i:02d}:00:00',
            'close': price,
            'volume': 1000000 * (1 + random.uniform(-0.3, 0.3)),
            'token_address': '0xExampleToken'
        })

    # Test different strategies
    strategies = [
        ('SMA Crossover', SimpleMovingAverageStrategy(short_period=10, long_period=30)),
        ('Momentum', MomentumStrategy(period=20))
    ]

    backtester = Backtester()

    for strategy_name, strategy in strategies:
        print(f"\nBacktesting {strategy_name}...")
        result = backtester.backtest_strategy(
            strategy=strategy,
            historical_data=historical_data,
            initial_capital=10000.0
        )

        print(f"  Strategy: {strategy_name}")
        print(f"  Initial: ${result.initial_capital:,.2f}")
        print(f"  Final: ${result.final_capital:,.2f}")
        print(f"  Return: {result.total_return:.2f}%")
        print(f"  Trades: {result.total_trades}")
        print(f"  Win Rate: {result.win_rate:.2f}%")
        print(f"  Sharpe: {result.sharpe_ratio:.2f}")

    # Get best result
    best = backtester.get_best_result()
    print(f"\nBest performing: {best.strategy} with {best.total_return:.2f}% return")


def example_market_analysis():
    """Example: Analyzing market conditions."""
    print("\n" + "=" * 60)
    print("Example 3: Market Analysis")
    print("=" * 60)

    analyzer = MarketAnalyzer()

    # Create mock price data
    price_data = []
    base_price = 100.0

    for i in range(100):
        # Simulate different market conditions
        if i % 3 == 0:
            # Volatile period
            change = random.uniform(-0.05, 0.05)
        elif i % 3 == 1:
            # Bullish period
            change = random.uniform(0.01, 0.03)
        else:
            # Bearish period
            change = random.uniform(-0.03, -0.01)

        price = base_price * (1 + change * i)
        price_data.append({
            'close': price,
            'volume': 1000000 * (1 + random.uniform(-0.2, 0.5))
        })

    # Analyze market
    condition = analyzer.analyze_market(price_data)

    print(f"Current Market Condition: {condition.condition.value}")
    print(f"Confidence: {condition.confidence:.2%}")
    print(f"Volatility: {condition.volatility:.2%}")
    print(f"Sentiment: {condition.sentiment_score:.2%}")
    print(f"Volume: {condition.volume:.2%}")

    # Get recommendations
    recommendations = analyzer._generate_recommendations(
        condition.volatility,
        "increasing" if condition.volatility > 0.1 else "decreasing"
    )
    print(f"\nRecommendations: {len(recommendations)}")
    for i, rec in enumerate(recommendations, 1):
        print(f"  {i}. {rec}")

    # Generate volatility report
    report = analyzer.generate_volatility_report(price_data)
    print(f"\nVolatility Report:")
    print(f"  Average: {report.avg_volatility:.2f}%")
    print(f"  Max: {report.max_volatility:.2f}%")
    print(f"  Trend: {report.trend}")


def example_alerts():
    """Example: Creating and managing alerts."""
    print("\n" + "=" * 60)
    print("Example 4: Alerts")
    print("=" * 60)

    alert_manager = AlertManager()

    # Create different types of alerts
    alerts = [
        Alert(
            'high_volatility',
            'Market volatility has exceeded threshold',
            AlertPriority.HIGH,
            AlertType.RISK
        ),
        Alert(
            'new_high',
            'Price has reached all-time high',
            AlertPriority.MEDIUM,
            AlertType.MARKET
        ),
        Alert(
            'trade_alert',
            'Large trade executed',
            AlertPriority.LOW,
            AlertType.TRADE
        ),
        Alert(
            'performance',
            'Performance target reached',
            AlertPriority.MEDIUM,
            AlertType.METRIC
        )
    ]

    for alert in alerts:
        alert_manager.add_alert(alert)

    # Get alerts
    print(f"Total alerts: {len(alert_manager.get_all_alerts())}")
    print(f"High priority: {len(alert_manager.get_alerts_by_priority(AlertPriority.HIGH))}")
    print(f"Unresolved: {len(alert_manager.get_unresolved_alerts())}")

    # Get alerts by type
    risk_alerts = alert_manager.get_alerts_by_type(AlertType.RISK)
    if risk_alerts:
        print(f"\nRisk Alerts:")
        for alert in risk_alerts:
            print(f"  [{alert.priority.value}] {alert.title}: {alert.message}")


def main():
    """Run all examples."""
    import random  # Imported here for the backtesting example

    print("=" * 60)
    print("Monitoring Module Examples")
    print("=" * 60)

    try:
        example_trade_tracking()
        example_backtesting()
        example_market_analysis()
        example_alerts()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Example failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()