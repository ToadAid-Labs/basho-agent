"""
Demo Script for Execution Layer
Demonstrates all features of the Execution Layer module
"""

import time
import datetime
from unittest.mock import Mock

from execution_layer import (
    ExecutionLayer,
    ExecutionStrategy,
    Network,
    DEX,
    SlippageConfig,
    TransactionStatus
)

# Create mock market analyzer
mock_market_analyzer = Mock()
mock_market_analyzer.get_current_price = Mock(return_value=2800.00)  # Mock ETH price in USD
mock_market_analyzer.get_current_gas_price = Mock(return_value=20.0)  # Mock gas price in gwei (numeric)
mock_market_analyzer.get_token_price = Mock(return_value=1.00)  # Mock stablecoin price in USD
mock_market_analyzer.get_market_data = Mock(return_value={
    'ETH_price': 2800.00,
    'WETH_price': 2800.00,
    'USDT_price': 1.00,
    'USDC_price': 1.00,
    'gas_price': 20.0
})

# Create mock trust wallet
mock_trust_wallet = Mock()
mock_trust_wallet.get_balance = Mock(return_value=1000.00)  # Mock balance
mock_trust_wallet.get_token_balance = Mock(return_value=1000.00)  # Mock token balance
mock_trust_wallet.estimate_gas = Mock(return_value=150000)  # Mock gas estimate
mock_trust_wallet.get_nonce = Mock(return_value=42)  # Mock nonce

# Initialize execution layer
execution_layer = ExecutionLayer(
    trust_wallet=mock_trust_wallet,
    market_analyzer=mock_market_analyzer,
    slippage_config=SlippageConfig(
        max_slippage_pct=0.02,  # 2%
        min_price_impact_pct=0.01  # 1%
    )
)


def demo_basic_execution():
    """Demo 1: Basic trade execution"""
    print("\n" + "=" * 60)
    print("DEMO 1: Basic Trade Execution")
    print("=" * 60)

    # Example token (WETH on Ethereum)
    token_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

    # Execute trade with different strategies
    strategies = [
        ExecutionStrategy.BEST_PRICE,
        ExecutionStrategy.LOWEST_SLIPPAGE,
        ExecutionStrategy.FASTEST_GAS
    ]

    for strategy in strategies:
        print(f"\n📝 Executing trade with {strategy.value} strategy...")
        result = execution_layer.execute_trade(
            token_address=token_address,
            amount=1.0,  # 1 WETH
            strategy=strategy,
            network=Network.ETHEREUM,
            slippage_tolerance=0.015
        )

        print(f"   Success: {result.success}")
        print(f"   Transaction ID: {result.tx_id}")
        print(f"   Amount: {result.actual_amount} WETH")
        print(f"   Slippage: {result.actual_slippage * 100:.2f}%")
        print(f"   Gas Used: {result.gas_used}")
        print(f"   Cost: ${result.cost:.4f}")
        print(f"   Message: {result.message}")
        print(f"   Time: {result.execution_time:.2f}s")

    print("\n✅ Basic execution demo complete!")


def demo_transaction_queueing():
    """Demo 2: Transaction queuing"""
    print("\n" + "=" * 60)
    print("DEMO 2: Transaction Queuing")
    print("=" * 60)

    token_addresses = [
        "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
        "0x0BFD5BDB57BbE5c4667F4C3D7fd8Bd8c48A2A845",  # USDT
        "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"   # USDC
    ]

    # Add multiple transactions to queue
    for i, token_address in enumerate(token_addresses):
        tx_id = execution_layer.queue_transaction(
            token_address=token_address,
            amount=10.0 * (i + 1),
            dex=DEX.UNISWAP_V2,
            network=Network.ETHEREUM,
            priority=i,  # Lower priority number = higher priority
            slippage=0.015
        )
        print(f"✓ Queued transaction {i + 1}: {tx_id[:8]}...")

    print(f"\n📊 Queue Status: {execution_layer.get_queue_status()}")

    # Process queue
    print("\n🔄 Processing queue...")
    results = execution_layer.process_queue(max_transactions=2)

    for result in results:
        print(f"   Transaction {result.tx_id[:8]}...: {'✅ Success' if result.success else '❌ Failed'}")

    print(f"\n📊 Queue Status: {execution_layer.get_queue_status()}")

    print("\n✅ Queuing demo complete!")


def demo_cancellation():
    """Demo 3: Transaction cancellation"""
    print("\n" + "=" * 60)
    print("DEMO 3: Transaction Cancellation")
    print("=" * 60)

    token_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

    # Queue a transaction
    tx_id = execution_layer.queue_transaction(
        token_address=token_address,
        amount=5.0,
        dex=DEX.UNISWAP_V2,
        network=Network.ETHEREUM,
        slippage=0.015
    )
    print(f"✓ Queued transaction: {tx_id[:8]}...")

    # Cancel it
    print(f"\n🔄 Cancelling transaction {tx_id[:8]}...")
    success = execution_layer.cancel_transaction(tx_id)
    print(f"   Cancelled: {success}")

    # Check status
    tx = execution_layer.get_transaction_status(tx_id)
    if tx:
        print(f"   Status: {tx.status.value}")

    print("\n✅ Cancellation demo complete!")


def demo_slippage_protection():
    """Demo 4: Slippage protection"""
    print("\n" + "=" * 60)
    print("DEMO 4: Slippage Protection")
    print("=" * 60)

    token_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

    # Test with different slippage tolerances
    slippage_settings = [0.005, 0.015, 0.03]  # 0.5%, 1.5%, 3%

    for slippage in slippage_settings:
        print(f"\n📝 Executing with {slippage * 100:.2f}% slippage tolerance...")
        result = execution_layer.execute_trade(
            token_address=token_address,
            amount=1.0,
            strategy=ExecutionStrategy.BEST_PRICE,
            network=Network.ETHEREUM,
            slippage_tolerance=slippage
        )

        if result.success:
            print(f"   Slippage: {result.actual_slippage * 100:.2f}%")
            print(f"   Message: {result.message}")
        else:
            print(f"   Blocked due to slippage")
            if result.transaction:
                print(f"   Error: {result.transaction.error_message}")

    print("\n✅ Slippage protection demo complete!")


def demo_multi_dex_routing():
    """Demo 5: Multi-DEX routing"""
    print("\n" + "=" * 60)
    print("DEMO 5: Multi-DEX Routing")
    print("=" * 60)

    token_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

    # Test routing across different DEXs
    dexes = [DEX.UNISWAP_V2, DEX.PANCAKESWAP, DEX.SUSHISWAP, DEX.QUICKSWAP]

    for dex in dexes:
        print(f"\n📝 Executing on {dex.value}...")
        result = execution_layer.execute_trade(
            token_address=token_address,
            amount=1.0,
            strategy=ExecutionStrategy.BEST_PRICE,
            network=Network.ETHEREUM,
            slippage_tolerance=0.02
        )

        if result.success:
            print(f"   DEX: {result.transaction.dex.value}")
            print(f"   Amount: {result.actual_amount} WETH")
            print(f"   Slippage: {result.actual_slippage * 100:.2f}%")
        else:
            print(f"   Failed: {result.transaction.error_message}")

    print("\n✅ Multi-DEX routing demo complete!")


def demo_gas_optimization():
    """Demo 6: Gas optimization"""
    print("\n" + "=" * 60)
    print("DEMO 6: Gas Optimization")
    print("=" * 60)

    # Optimize for different networks and DEXs
    test_cases = [
        (Network.ETHEREUM, DEX.UNISWAP_V2),
        (Network.BSC, DEX.PANCAKESWAP),
        (Network.ARBITRUM, DEX.UNISWAP_V3),
        (Network.POLYGON, DEX.QUICKSWAP)
    ]

    for network, dex in test_cases:
        recommendations = execution_layer.optimize_gas(network, dex)

        print(f"\n🪙 {network.value} - {dex.value}:")
        print(f"   Current Gas Price: {recommendations['current_gas_price_gwei']:.2f} gwei")
        print(f"   Recommended: {recommendations['recommended_gas_price_gwei']:.2f} gwei")
        print(f"   Gas Multiplier: {recommendations['gas_multiplier']:.2f}x")
        print(f"   Estimated Cost: ${recommendations['estimated_cost_eth']:.4f}")

    print("\n✅ Gas optimization demo complete!")


def demo_flash_loan_arbitrage():
    """Demo 7: Flash loan arbitrage"""
    print("\n" + "=" * 60)
    print("DEMO 7: Flash Loan Arbitrage")
    print("=" * 60)

    # Create flash loan request
    loan_request = {
        'token': 'WETH',
        'amount': 1000.0,
        'dex': DEX.UNISWAP_V2,
        'strategy': ExecutionStrategy.BEST_PRICE,
        'arbitrage_path': [
            '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
            '0x0BFD5BDB57BbE5c4667F4C3D7fd8Bd8c48A2A845',  # USDT
            '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'   # Back to WETH
        ],
        'gas_limit': 300000,
        'max_slippage': 0.005
    }

    print(f"⚡ Flash Loan Parameters:")
    print(f"   Token: {loan_request['token']}")
    print(f"   Amount: {loan_request['amount']} {loan_request['token']}")
    print(f"   DEX: {loan_request['dex'].value}")
    print(f"   Path: {' → '.join(loan_request['arbitrage_path'][:2])} → {loan_request['arbitrage_path'][-1]}")
    print(f"   Max Slippage: {loan_request['max_slippage'] * 100:.2f}%")

    # Note: This requires actual market data and trust wallet integration
    print(f"\n📝 Executing flash loan arbitrage...")
    print(f"   (This would execute in a real scenario with market data)")

    print("\n✅ Flash loan arbitrage demo complete!")


def demo_performance_metrics():
    """Demo 8: Performance metrics"""
    print("\n" + "=" * 60)
    print("DEMO 8: Performance Metrics")
    print("=" * 60)

    # Simulate some executions
    token_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

    for i in range(5):
        result = execution_layer.execute_trade(
            token_address=token_address,
            amount=1.0 + i * 0.1,
            strategy=ExecutionStrategy.BEST_PRICE,
            network=Network.ETHEREUM,
            slippage_tolerance=0.02
        )

    # Get and display metrics
    metrics = execution_layer.get_execution_metrics()

    print(f"\n📈 Execution Metrics:")
    print(f"   Total Executions: {metrics['total_executions']}")
    print(f"   Successful: {metrics['successful_executions']}")
    print(f"   Failed: {metrics['failed_executions']}")
    print(f"   Success Rate: {(metrics['successful_executions'] / max(metrics['total_executions'], 1) * 100):.2f}%")
    print(f"   Avg Execution Time: {metrics['avg_execution_time']:.2f}s")
    print(f"   Avg Slippage: {metrics['avg_slippage'] * 100:.2f}%")
    print(f"   Avg Gas Cost: ${metrics['avg_gas_cost']:.4f}")

    execution_layer.print_status()

    print("\n✅ Performance metrics demo complete!")


def demo_cleanup():
    """Demo 9: Transaction cleanup"""
    print("\n" + "=" * 60)
    print("DEMO 9: Transaction Cleanup")
    print("=" * 60)

    # Create some old transactions
    token_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

    for i in range(3):
        result = execution_layer.execute_trade(
            token_address=token_address,
            amount=1.0,
            strategy=ExecutionStrategy.BEST_PRICE,
            network=Network.ETHEREUM,
            slippage_tolerance=0.02
        )

        if result.transaction:
            # Set timestamp to simulate old transactions
            result.transaction.created_at = datetime.datetime.now() - datetime.timedelta(hours=2)  # 2 hours ago

    print(f"📊 Transactions before cleanup: {len(execution_layer.executed_transactions)}")

    # Clean up expired transactions (1 hour old in demo)
    cleaned = execution_layer.cleanup_expired_transactions(max_age_hours=0.0)
    print(f"🧹 Cleaned up {cleaned} expired transactions")

    print(f"📊 Transactions after cleanup: {len(execution_layer.executed_transactions)}")

    print("\n✅ Cleanup demo complete!")


def run_all_demos():
    """Run all demos"""
    print("\n" + "=" * 60)
    print("EXECUTION LAYER DEMOS")
    print("=" * 60)

    demos = [
        ("Basic Trade Execution", demo_basic_execution),
        ("Transaction Queuing", demo_transaction_queueing),
        ("Transaction Cancellation", demo_cancellation),
        ("Slippage Protection", demo_slippage_protection),
        ("Multi-DEX Routing", demo_multi_dex_routing),
        ("Gas Optimization", demo_gas_optimization),
        ("Flash Loan Arbitrage", demo_flash_loan_arbitrage),
        ("Performance Metrics", demo_performance_metrics),
        ("Transaction Cleanup", demo_cleanup)
    ]

    for name, demo_func in demos:
        print(f"\n{'=' * 60}")
        print(f"Running: {name}")
        print(f"{'=' * 60}")

        try:
            demo_func()
            time.sleep(1)  # Brief pause between demos
        except Exception as e:
            print(f"❌ Demo failed: {str(e)}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("✅ ALL DEMOS COMPLETE!")
    print("=" * 60)

    # Final status
    execution_layer.print_status()


if __name__ == "__main__":
    run_all_demos()