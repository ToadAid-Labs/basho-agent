"""
Price Action Module Tests and Demo

Demonstrates usage of pattern recognition and price action analyzer modules
"""

__test__ = False

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

try:
    import matplotlib.pyplot as plt
except ModuleNotFoundError:  # pragma: no cover - optional demo dependency
    plt = None

# Import the modules
try:
    from backend.pattern_recognition import *
    from backend.price_action import PriceActionAnalyzer, PriceActionStrategy
except ModuleNotFoundError as exc:  # pragma: no cover - optional demo dependency
    raise unittest.SkipTest(f"Skipping price action demo: {exc}")


def generate_mock_data(days: int = 100, start_price: float = 100.0) -> pd.DataFrame:
    """
    Generate mock OHLCV data for testing

    Args:
        days: Number of days of data to generate
        start_price: Starting price

    Returns:
        DataFrame with OHLCV data
    """
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

    # Generate price data with random walk
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, days)
    prices = start_price * np.cumprod(1 + returns)

    # Generate OHLCV data
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, days)),
        'high': prices * (1 + np.random.uniform(0, 0.02, days)),
        'low': prices * (1 + np.random.uniform(-0.02, 0, days)),
        'close': prices,
        'volume': np.random.randint(100000, 1000000, days)
    })

    df.set_index('timestamp', inplace=True)

    return df


def test_pattern_recognition():
    """Test pattern recognition module"""
    print("=" * 60)
    print("Testing Pattern Recognition Module")
    print("=" * 60)

    # Generate test data
    df = generate_mock_data(days=100, start_price=100.0)

    # Initialize analyzer
    recognizer = MarketPatternDetector()

    # Test pattern detection
    patterns = recognizer.detect_patterns(df, lookback=20)

    print(f"\nDetected {len(patterns)} patterns:")
    for pattern in patterns:
        print(f"  - {pattern['type']}: {pattern['confidence']:.2f} "
              f"({pattern['description']})")

    # Get pattern analysis
    analysis = recognizer.analyze_patterns(df)
    print(f"\nPattern Analysis:")
    print(f"  Bullish patterns: {analysis['bullish_count']}")
    print(f"  Bearish patterns: {analysis['bearish_count']}")
    print(f"  Neutral patterns: {analysis['neutral_count']}")

def test_price_action_analyzer():
    """Test price action analyzer module"""
    print("\n" + "=" * 60)
    print("Testing Price Action Analyzer Module")
    print("=" * 60)

    # Generate test data
    df = generate_mock_data(days=100, start_price=100.0)

    # Initialize analyzer
    analyzer = PriceActionAnalyzer(lookback_period=50, volatility_window=20)

    # Comprehensive analysis
    analysis = analyzer.analyze_price_action(df)

    print(f"\nComprehensive Analysis:")
    print(f"  Trend: {analysis['trend']}")
    print(f"  Momentum: {analysis['momentum']:.2f}%")
    print(f"  Volatility: {analysis['volatility']:.2f}%")
    print(f"  RSI: {analysis['rsi']:.2f}")

    print(f"\nSupport Levels: {analysis['support_levels']}")
    print(f"Resistance Levels: {analysis['resistance_levels']}")

    print(f"\nBreakout: {analysis['breakout']['type'] if analysis['breakout']['breakout'] else 'None'} "
          f"({analysis['breakout']['strength']:.2f}% if present)")

    print(f"\nReversal: {analysis['reversal']['type'] if analysis['reversal']['reversal'] else 'None'} "
          f"({analysis['reversal']['strength']:.2f}% if present)")

    # Trading signals
    signals = analyzer.get_trading_signals(df)
    print(f"\nTrading Signals: {len(signals)} signals generated")

    for signal in signals:
        print(f"  - {signal['signal']}: {signal['reason']} "
              f"(confidence: {signal['confidence']:.2f})")

def test_strategy():
    """Test price action strategy module"""
    print("\n" + "=" * 60)
    print("Testing Price Action Strategy")
    print("=" * 60)

    # Generate test data
    df = generate_mock_data(days=100, start_price=100.0)

    # Initialize strategy
    analyzer = PriceActionAnalyzer()
    strategy = PriceActionStrategy(analyzer)

    # Generate entry signals
    entry_signals = strategy.generate_entry_signals(df)
    print(f"\nEntry Signals: {len(entry_signals)} signals generated")

    for signal in entry_signals:
        print(f"  - {signal['type']}: {signal['reason']}")
        print(f"    Price: {signal['price']:.2f}, Target: {signal['target']:.2f}, "
              f"Stop Loss: {signal['stop_loss']:.2f}")
        print(f"    Confidence: {signal['confidence']:.2f}")

    # Generate exit signals
    exit_signals = strategy.generate_exit_signals(df)
    print(f"\nExit Signals: {len(exit_signals)} signals generated")

    for signal in exit_signals:
        print(f"  - {signal['type']}: {signal['reason']} "
              f"(confidence: {signal['confidence']:.2f})")

def visual_analysis(df: pd.DataFrame, analyzer: PriceActionAnalyzer):
    """Visualize price action analysis"""
    if plt is None:
        print("\nMatplotlib is not installed; skipping visualization.")
        return

    print("\n" + "=" * 60)
    print("Generating Visualization")
    print("=" * 60)

    # Create figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

    # Price chart
    ax1.plot(df.index, df['close'], label='Price', linewidth=2)
    ax1.set_title('Price Chart')
    ax1.set_ylabel('Price')
    ax1.grid(True, alpha=0.3)

    # Add support and resistance levels
    analysis = analyzer.analyze_price_action(df)
    if analysis['support_levels']:
        for level in analysis['support_levels']:
            ax1.axhline(y=level, color='g', linestyle='--', alpha=0.5, label='Support')

    if analysis['resistance_levels']:
        for level in analysis['resistance_levels']:
            ax1.axhline(y=level, color='r', linestyle='--', alpha=0.5, label='Resistance')

    ax1.legend()

    # RSI chart
    ax2.plot(df.index, analyzer.get_rsi(df), label='RSI', linewidth=2)
    ax2.axhline(y=70, color='r', linestyle='--', alpha=0.5, label='Overbought')
    ax2.axhline(y=30, color='g', linestyle='--', alpha=0.5, label='Oversold')
    ax2.set_title('RSI Indicator')
    ax2.set_ylabel('RSI')
    ax2.set_ylim(0, 100)
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    plt.tight_layout()
    output_path = Path(__file__).resolve().parent / 'price_action_analysis.png'
    plt.savefig(output_path, dpi=100)
    print("\nVisualization saved to: price_action_analysis.png")
    plt.close()


def main():
    """Run all tests and demos"""
    print("\n" + "=" * 60)
    print("Price Action Analysis Module Demo")
    print("=" * 60)

    # Test pattern recognition
    df1, recognizer = test_pattern_recognition()

    # Test price action analyzer
    df2, analyzer = test_price_action_analyzer()

    # Test strategy
    df3, strategy = test_strategy()

    # Generate visualization
    visual_analysis(df2, analyzer)

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
