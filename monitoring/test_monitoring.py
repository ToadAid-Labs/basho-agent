#!/usr/bin/env python3
"""
Test script for monitoring module.
"""

__test__ = False

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitoring import (
    Trade,
    TradeStatus,
    PerformanceMetrics,
    MarketCondition,
    Backtester,
    SimpleMovingAverageStrategy,
    MarketAnalyzer
)


def test_performance_metrics():
    """Test performance metrics tracking."""
    print("Testing Performance Metrics...")
    metrics = PerformanceMetrics()

    # Add sample trades
    for i in range(10):
        metrics.add_trade(Trade(
            trade_id=f"trade_{i}",
            direction='buy',
            token_address=f"0x{i}",
            amount=1.0,
            price=100 + i * 0.1,
            status=TradeStatus.CLOSED
        ))

    print(f"  Total trades: {metrics.get_total_trades()}")
    print(f"  Win rate: {metrics.get_win_rate():.2f}%")
    print(f"  Sharpe ratio: {metrics.get_sharpe_ratio():.2f}")
    print(f"  Max drawdown: {metrics.get_max_drawdown():.2f}")
    print(f"  Profit factor: {metrics.get_profit_factor():.2f}")


def test_backtesting():
    """Test backtesting functionality."""
    print("\nTesting Backtesting...")
    backtester = Backtester()

    # Create mock historical data
    historical_data = []
    base_price = 100.0
    for i in range(100):
        price = base_price * (1 + (i % 20 - 10) * 0.05)
        historical_data.append({
            'timestamp': f'2024-01-01T{i}:00:00',
            'close': price,
            'volume': 100000 * (1 + (i % 10) * 0.1),
            'token_address': '0x123456789'
        })

    # Test SMA strategy
    strategy = SimpleMovingAverageStrategy(short_period=10, long_period=30)
    result = backtester.backtest_strategy(
        strategy=strategy,
        historical_data=historical_data,
        initial_capital=10000.0
    )

    print(f"  Strategy: {strategy.name}")
    print(f"  Initial capital: ${result.initial_capital:,.2f}")
    print(f"  Final capital: ${result.final_capital:,.2f}")
    print(f"  Total return: {result.total_return:.2f}%")
    print(f"  Total trades: {result.total_trades}")
    print(f"  Win rate: {result.win_rate:.2f}%")
    print(f"  Sharpe ratio: {result.sharpe_ratio:.2f}")


def test_market_analyzer():
    """Test market analyzer."""
    print("\nTesting Market Analyzer...")
    analyzer = MarketAnalyzer()

    # Create mock price data
    price_data = []
    base_price = 100.0
    for i in range(50):
        price = base_price * (1 + (i % 25) * 0.04 - (i % 10) * 0.02)
        price_data.append({
            'close': price,
            'volume': 1000000 * (1 + (i % 5) * 0.2)
        })

    # Analyze market
    condition = analyzer.analyze_market(price_data)

    print(f"  Current condition: {condition.condition.value}")
    print(f"  Confidence: {condition.confidence:.2%}")
    print(f"  Volatility: {condition.volatility:.2%}")
    print(f"  Sentiment: {condition.sentiment_score:.2%}")

    # Generate report
    report = analyzer.generate_volatility_report(price_data)
    print(f"\n  Volatility Report:")
    print(f"    Average: {report.avg_volatility:.2f}%")
    print(f"    Trend: {report.trend}")
    print(f"    Recommendations: {len(report.recommendations)}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Monitoring Module Test Suite")
    print("=" * 60)

    try:
        test_performance_metrics()
        test_backtesting()
        test_market_analyzer()

        print("\n" + "=" * 60)
        print("All tests passed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
