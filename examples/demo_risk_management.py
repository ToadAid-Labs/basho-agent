"""
Demo script for Risk Management Module

Demonstrates all risk management features:
- Position sizing
- Stop-loss and take-profit
- Portfolio diversification
- Daily loss limits
- Maximum drawdown protection
- Risk-reward ratio tracking
"""

import os
from decimal import Decimal
from datetime import datetime

from tools.trust import TrustWalletAgent
from tools.market_data import MarketDataAnalyzer
from risk_management import RiskManager, RiskLevel, Position


def main():
    """Run risk management demo"""

    print("\n" + "=" * 70)
    print("🛡️ RISK MANAGEMENT MODULE DEMO")
    print("=" * 70 + "\n")

    # Initialize Trust Wallet and Market Data
    access_id = os.getenv('TWAK_ACCESS_ID')
    hmac_secret = os.getenv('TWAK_HMAC_SECRET')

    if not access_id or not hmac_secret:
        print("❌ Error: TWAK_ACCESS_ID and TWAK_HMAC_SECRET not found in .env")
        print("Please ensure your .env file contains the required credentials.")
        return

    try:
        trust_wallet = TrustWalletAgent(access_id, hmac_secret)
        market_analyzer = MarketDataAnalyzer()
        risk_manager = RiskManager(trust_wallet, market_analyzer)

        # Set risk level
        print("1️⃣ Setting Risk Level")
        print("-" * 70)
        risk_manager.set_risk_level(RiskLevel.MEDIUM)
        print(f"✓ Risk level set to: {risk_manager.config.risk_level.value}")
        print(f"  - Max Daily Loss: {risk_manager.config.max_daily_loss_pct}%")
        print(f"  - Max Drawdown: {risk_manager.config.max_drawdown_pct}%")
        print(f"  - Risk per Trade: {risk_manager.config.risk_per_trade_pct}%")
        print(f"  - Max Position Size: {risk_manager.config.max_position_size_pct}%")
        print(f"  - Min Risk-Reward: {risk_manager.config.min_risk_reward_ratio}")
        print()

        # Get wallet balance
        print("2️⃣ Portfolio Overview")
        print("-" * 70)
        balance = trust_wallet.get_wallet_balance()
        print(f"✓ Wallet Balance: ${balance:.2f}")
        metrics = risk_manager.get_current_metrics()
        print(f"✓ Total Portfolio Value: ${metrics.total_portfolio_value:.2f}")
        print(f"✓ Active Positions: {len(risk_manager.active_positions)}")
        print(f"✓ Daily PnL: ${metrics.daily_pnl:.2f} ({metrics.daily_pnl_pct:.2f}%)")
        print()

        # Open a position with DCA
        print("3️⃣ Opening Positions (Simulated)")
        print("-" * 70)

        # Position 1: USDC
        token1 = "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"  # USDC-BSC
        price1 = trust_wallet.get_current_price(token1) or 1.0

        print(f"\n📈 Opening Position 1: USDC")
        print(f"  Token: {token1}")
        print(f"  Entry Price: ${price1:.6f}")

        # Validate entry
        is_valid, message, params = risk_manager.validate_entry(
            token1, price1, 100.0,  # Target position size
            stop_loss_pct=3.0,
            take_profit_pct=6.0,
            risk_reward_ratio=2.0
        )

        if is_valid:
            print(f"✓ {message}")
            print(f"  Stop Loss: ${params['stop_loss_price']:.6f}")
            print(f"  Take Profit: ${params['take_profit_price']:.6f}")
            print(f"  Risk: ${params['risk_amount']:.2f}")
            print(f"  Potential Profit: ${params['potential_profit']:.2f}")
            print(f"  Risk-Reward Ratio: {params['risk_reward_ratio']:.2f}")

            # Open position
            result = risk_manager.open_position(
                token1, price1, 100.0,
                stop_loss_pct=3.0,
                take_profit_pct=6.0
            )

            if result['success']:
                print(f"✓ Position opened successfully!")
                print(f"  Position Size: {result['position']['position_size']:.6f} tokens")
            else:
                print(f"✗ {result['message']}")
        else:
            print(f"✗ {message}")

        # Position 2: USDT
        token2 = "0x55d398326f99059fF775485246999027B3197955"  # USDT-BSC
        price2 = trust_wallet.get_current_price(token2) or 1.0

        print(f"\n📈 Opening Position 2: USDT")
        print(f"  Token: {token2}")
        print(f"  Entry Price: ${price2:.6f}")

        is_valid, message, params = risk_manager.validate_entry(
            token2, price2, 75.0,  # Target position size
            stop_loss_pct=2.5,
            take_profit_pct=5.0
        )

        if is_valid:
            print(f"✓ {message}")
            print(f"  Stop Loss: ${params['stop_loss_price']:.6f}")
            print(f"  Take Profit: ${params['take_profit_price']:.6f}")

            # Open position
            result = risk_manager.open_position(
                token2, price2, 75.0,
                stop_loss_pct=2.5,
                take_profit_pct=5.0
            )

            if result['success']:
                print(f"✓ Position opened successfully!")
                print(f"  Position Size: {result['position']['position_size']:.6f} tokens")
            else:
                print(f"✗ {result['message']}")
        else:
            print(f"✗ {message}")

        # Check if can open new position
        print("\n4️⃣ Position Management")
        print("-" * 70)
        can_open, message = risk_manager.can_open_new_position()
        print(f"✓ Can open new position: {'✅ Yes' if can_open else '❌ No'}")
        print(f"  Reason: {message}")
        print()

        # Check and manage positions
        print("5️⃣ Managing Active Positions")
        print("-" * 70)
        management = risk_manager.check_and_manage_positions()

        print(f"✓ Active positions: {len(risk_manager.active_positions)}")
        print(f"✓ Updated positions: {len(management['updated_positions'])}")
        print(f"✓ Closed positions: {len(management['closed_positions'])}")

        if management['warnings']:
            print(f"\n⚠️ Warnings:")
            for warning in management['warnings']:
                print(f"  - {warning}")
        print()

        # Get diversification score
        print("6️⃣ Portfolio Diversification")
        print("-" * 70)
        diversification = risk_manager.get_diversification_score()

        print(f"✓ Active Positions: {diversification['active_positions']}")
        print(f"✓ Total Value: ${diversification['total_value']:.2f}")
        print(f"✓ Diversification Score: {diversification['diversification_score']:.2f}/100")

        print(f"\n  Allocations:")
        for token, allocation in diversification['allocations'].items():
            print(f"    - {token[:10]}...: {allocation:.2f}%")

        print(f"\n✓ Max Allocation: {diversification['max_allocation']:.2f}%")
        print(f"✓ Is Diversified: {'✅ Yes' if diversification['is_diversified'] else '❌ No'}")
        print(f"  Required: < {risk_manager.config.max_portfolio_concentration}%")
        print()

        # Get all positions
        print("7️⃣ All Active Positions")
        print("-" * 70)
        positions = risk_manager.get_all_positions()

        for i, position in enumerate(positions, 1):
            print(f"\n  Position {i}:")
            print(f"    Token: {position['token_address']}")
            print(f"    Entry Price: ${position['entry_price']:.6f}")
            print(f"    Amount: {position['amount']:.6f}")
            print(f"    Stop Loss: ${position['stop_loss']:.6f}")
            print(f"    Take Profit: ${position['take_profit']:.6f}")
            print(f"    Position Value: ${position['position_value']:.2f}")
        print()

        # Risk metrics
        print("8️⃣ Risk Metrics")
        print("-" * 70)
        metrics = risk_manager.get_current_metrics()

        print(f"\n📊 Portfolio Metrics:")
        print(f"    Total Value: ${metrics.total_portfolio_value:.2f}")
        print(f"    Daily PnL: ${metrics.daily_pnl:.2f} ({metrics.daily_pnl_pct:.2f}%)")
        print(f"    Max Drawdown: {metrics.max_drawdown:.2f}%")

        print(f"\n📈 Trade Statistics:")
        print(f"    Total Trades: {metrics.total_trades}")
        print(f"    Winning: {metrics.winning_trades}")
        print(f"    Losing: {metrics.losing_trades}")
        print(f"    Win Rate: {metrics.win_rate:.2f}%")
        print(f"    Avg Risk-Reward: {metrics.average_risk_reward:.2f}")
        print()

        # Print full status
        print("9️⃣ Full Status Report")
        print("-" * 70)
        risk_manager.print_status()

        # Try different risk levels
        print("🔟 Testing Different Risk Levels")
        print("-" * 70)

        for level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]:
            print(f"\n{level.value.upper()} Risk Level:")
            print(f"  - Max Daily Loss: {level.value}.config.max_daily_loss_pct}%")
            print(f"  - Max Drawdown: {level.value}.config.max_drawdown_pct}%")
            print(f"  - Risk per Trade: {level.value}.config.risk_per_trade_pct}%")
            print(f"  - Max Position Size: {level.value}.config.max_position_size_pct}%")
            print(f"  - Min Risk-Reward: {level.value}.config.min_risk_reward_ratio}")
            print()

        print("✅ Demo completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()