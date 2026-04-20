"""
Trading Strategies Demo
=====================

Demonstrates how to use the various trading strategies in the trading bot.
"""

import os
from tools.trust import TrustWalletAgent
from tools.market_data import MarketDataAnalyzer
from trading_strategies import (
    StrategyManager,
    StrategyType
)


def main():
    """Main demo function"""

    print("=" * 60)
    print("🤖 TRADING STRATEGIES DEMO")
    print("=" * 60)
    print()

    # Initialize agents
    print("1️⃣  Initializing agents...")
    print("-" * 60)

    trust_wallet = TrustWalletAgent(
        access_id=os.getenv('TWAK_ACCESS_ID'),
        hmac_secret=os.getenv('TWAK_HMAC_SECRET')
    )

    market_analyzer = MarketDataAnalyzer()

    strategy_manager = StrategyManager(trust_wallet, market_analyzer)

    print("✅ Agents initialized successfully!")
    print()

    # Show available strategies
    print("2️⃣  Available Trading Strategies:")
    print("-" * 60)

    strategies = strategy_manager.get_available_strategies()
    for i, strategy in enumerate(strategies, 1):
        print(f"{i}. {strategy['name']}")
        print(f"   Type: {strategy['type']}")
        print(f"   Description: {strategy['description']}")
        print()

    print("3️⃣  Strategy Demonstration:")
    print("-" * 60)
    print()

    # Demo DCA Strategy
    print("Demo 1: DCA Strategy (Dollar Cost Averaging)")
    print("-" * 60)

    # Example: USDC address on BSC
    # You'd typically use a specific token address for your chosen chain
    demo_token = "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"  # USDC-BSC

    print(f"Token: {demo_token}")
    print(f"Strategy: Buy $100 every 7 days")
    print()

    dca_result = strategy_manager.execute_strategy(
        StrategyType.DCA,
        token_address=demo_token,
        amount=100.0,
        interval_days=7
    )

    print("Result:")
    print(f"  Success: {dca_result.get('success', False)}")
    print(f"  Message: {dca_result.get('message', 'N/A')}")
    if 'tokens_bought' in dca_result:
        print(f"  Tokens Bought: {dca_result.get('tokens_bought', 0):.6f}")
    print(f"  Investment: ${dca_result.get('investment', 0):.2f}")
    print(f"  Next Purchase: {dca_result.get('next_purchase_date', 'N/A')}")
    print()

    # Demo Momentum Strategy
    print("Demo 2: Momentum Strategy (Trend Following)")
    print("-" * 60)

    print(f"Token: {demo_token}")
    print(f"Strategy: Ride trends, lookback 7 days")
    print()

    momentum_result = strategy_manager.execute_strategy(
        StrategyType.MOMENTUM,
        token_address=demo_token,
        portfolio_value=1000.0,
        lookback_days=7
    )

    print("Result:")
    print(f"  Signal: {momentum_result.get('signal', 'N/A')}")
    print(f"  Confidence: {momentum_result.get('confidence', 0):.2%}")
    print(f"  Reason: {momentum_result.get('reason', 'N/A')}")
    print(f"  Average Change: {momentum_result.get('avg_change', 0):.2f}%")
    print()

    # Demo Mean Reversion Strategy
    print("Demo 3: Mean Reversion Strategy")
    print("-" * 60)

    print(f"Token: {demo_token}")
    print(f"Strategy: Buy low, sell high, lookback 14 days")
    print()

    mean_reversion_result = strategy_manager.execute_strategy(
        StrategyType.MEAN_REVERSION,
        token_address=demo_token,
        lookback_days=14,
        deviation_threshold=3.0
    )

    print("Result:")
    print(f"  Signal: {mean_reversion_result.get('signal', 'N/A')}")
    print(f"  Confidence: {mean_reversion_result.get('confidence', 0):.2%}")
    print(f"  Reason: {mean_reversion_result.get('reason', 'N/A')}")
    print(f"  Current Price: ${mean_reversion_result.get('current_price', 0):.2f}")
    print(f"  Average Price: ${mean_reversion_result.get('avg_price', 0):.2f}")
    print(f"  Deviation: {mean_reversion_result.get('deviation', 0):.2f}%")
    print()

    # Demo Arbitrage Strategy
    print("Demo 4: Arbitrage Strategy")
    print("-" * 60)

    print(f"Token: {demo_token}")
    print(f"Strategy: Find price differences, min profit 1%")
    print()

    arbitrage_result = strategy_manager.execute_strategy(
        StrategyType.ARBITRAGE,
        token_address=demo_token,
        min_profit_pct=1.0
    )

    print("Result:")
    print(f"  Signal: {arbitrage_result.get('signal', 'N/A')}")
    print(f"  Buy Price: ${arbitrage_result.get('buy_price', 0):.6f}")
    print(f"  Sell Price: ${arbitrage_result.get('sell_price', 0):.6f}")
    print(f"  Potential Profit: {arbitrage_result.get('potential_profit', 0):.2f}%")
    print(f"  Action: {arbitrage_result.get('action', 'N/A')}")
    print()

    # Demo Swing Strategy
    print("Demo 5: Swing Trading Strategy")
    print("-" * 60)

    print(f"Token: {demo_token}")
    print(f"Strategy: Capture medium-term moves, hold 5 days")
    print()

    swing_result = strategy_manager.execute_strategy(
        StrategyType.SWING,
        token_address=demo_token,
        lookback_days=14,
        hold_period_days=5
    )

    print("Result:")
    print(f"  Signal: {swing_result.get('signal', 'N/A')}")
    print(f"  Confidence: {swing_result.get('confidence', 0):.2%}")
    print(f"  Reason: {swing_result.get('reason', 'N/A')}")
    print(f"  Current Price: ${swing_result.get('current_price', 0):.2f}")
    print(f"  RSI: {swing_result.get('rsi', 0):.1f}")
    print()

    # Demo Portfolio Rebalance
    print("Demo 6: Portfolio Rebalancing Strategy")
    print("-" * 60)

    target_allocation = {
        "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d": 40.0,  # USDC
        "0x55d398326f99059fF775485246999027B3197955": 30.0,  # USDT-BSC
        "0xE592427A0AEce92De3Edee1F18E0157C05861564": 20.0,  # BUSD-BSC
        "0x2170Ed0880ac9A7588bD10F801F6288Bd85f019E": 10.0,  # WBNB-BSC
    }

    print(f"Target Allocation: {target_allocation}")
    print(f"Drift Threshold: 5%")
    print()

    rebalance_result = strategy_manager.execute_strategy(
        StrategyType.REBALANCE,
        target_allocation=target_allocation,
        threshold_pct=5.0
    )

    print("Result:")
    print(f"  Success: {rebalance_result.get('success', False)}")
    print(f"  Total Trades: {rebalance_result.get('total_trades', 0)}")
    print(f"  Message: {rebalance_result.get('message', 'N/A')}")
    print()

    # Summary
    print("=" * 60)
    print("✅ DEMO COMPLETE!")
    print("=" * 60)
    print()
    print("📝 Notes:")
    print("  • These are demo executions for demonstration purposes")
    print("  • In production, always test strategies with paper trading first")
    print("  • Consider risk management and stop-loss levels")
    print("  • Start with small amounts for live trading")
    print("  • Monitor strategy performance and adjust parameters")
    print()


if __name__ == "__main__":
    main()