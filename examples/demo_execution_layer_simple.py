"""
Simple Demo Script for Execution Layer
Demonstrates core features of the Execution Layer module
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


def main():
    """Run the execution layer demo"""
    print("\n" + "=" * 60)
    print("EXECUTION LAYER DEMO")
    print("=" * 60)

    token_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

    # Create mock dependencies
    mock_market_analyzer = Mock()
    mock_market_analyzer.get_current_price = Mock(return_value=2800.00)
    mock_market_analyzer.get_current_gas_price = Mock(return_value=20.0)
    mock_market_analyzer.get_token_price = Mock(return_value=1.00)

    mock_trust_wallet = Mock()
    mock_trust_wallet.get_balance = Mock(return_value=1000.00)
    mock_trust_wallet.get_token_balance = Mock(return_value=1000.00)
    mock_trust_wallet.estimate_gas = Mock(return_value=150000)
    mock_trust_wallet.get_nonce = Mock(return_value=42)

    # Initialize execution layer
    execution_layer = ExecutionLayer(
        trust_wallet=mock_trust_wallet,
        market_analyzer=mock_market_analyzer,
        slippage_config=SlippageConfig(
            max_slippage_pct=0.02,
            min_price_impact_pct=0.01
        )
    )

    print("\n" + "=" * 60)
    print("DEMO 1: Basic Execution")
    print("=" * 60)

    print("✅ Execution layer initialized")
    print(f"   Network: {Network.ETHEREUM.value}")
    print(f"   Strategy: {ExecutionStrategy.BEST_PRICE.value}")
    print(f"   Max Slippage: 2.0%")
    print(f"   Min Price Impact: 1.0%")

    print("\n" + "=" * 60)
    print("DEMO 2: Transaction Queuing")
    print("=" * 60)

    # Queue multiple transactions
    for i in range(3):
        result = execution_layer.execute_trade(
            token_address=token_address,
            amount=1.0,
            strategy=ExecutionStrategy.BEST_PRICE,
            network=Network.ETHEREUM,
            slippage_tolerance=0.02
        )
        if result.transaction:
            print(f"✓ Queued transaction {i+1}: {result.transaction.tx_id[:8]}...")

    # Check queue status
    queue_status = execution_layer.get_queue_status()
    print(f"\n📊 Queue Status: {queue_status}")

    print("\n" + "=" * 60)
    print("DEMO 3: Slippage Protection")
    print("=" * 60)

    # Test with different slippage tolerances
    for slippage in [0.005, 0.01, 0.02, 0.05]:
        result = execution_layer.execute_trade(
            token_address=token_address,
            amount=1.0,
            strategy=ExecutionStrategy.BEST_PRICE,
            network=Network.ETHEREUM,
            slippage_tolerance=slippage
        )
        status = "✓" if result.success else "✗"
        print(f"{status} Slippage {slippage*100:.1f}%: {result.message}")

    print("\n" + "=" * 60)
    print("DEMO 4: Performance Metrics")
    print("=" * 60)

    # Print execution statistics
    metrics = execution_layer.get_metrics()
    print(f"📈 Total Executions: {metrics['total_executions']}")
    print(f"   Successful: {metrics['successful_executions']}")
    print(f"   Failed: {metrics['failed_executions']}")
    print(f"   Success Rate: {metrics['success_rate']:.2f}%")
    print(f"   Avg Execution Time: {metrics['avg_execution_time']:.2f}s")
    print(f"   Avg Slippage: {metrics['avg_slippage']:.2f}%")
    print(f"   Avg Gas Cost: ${metrics['avg_gas_cost']:.4f}")

    print("\n" + "=" * 60)
    print("DEMO 5: Network Status")
    print("=" * 60)

    # Get network status
    networks = [Network.ETHEREUM, Network.BSC]
    for network in networks:
        try:
            gas_price = mock_market_analyzer.get_current_gas_price(network)
            eth_price = mock_market_analyzer.get_current_price()
            print(f"🪙 {network.value}:")
            print(f"   Gas Price: {gas_price} gwei")
            print(f"   ETH Price: ${eth_price:.2f}")
        except Exception as e:
            print(f"🪙 {network.value}: Error - {str(e)}")

    print("\n" + "=" * 60)
    print("DEMO 6: Transaction Cleanup")
    print("=" * 60)

    # Create some old transactions
    for i in range(3):
        result = execution_layer.execute_trade(
            token_address=token_address,
            amount=1.0,
            strategy=ExecutionStrategy.BEST_PRICE,
            network=Network.ETHEREUM,
            slippage_tolerance=0.02
        )
        if result.transaction:
            result.transaction.created_at = datetime.datetime.now() - datetime.timedelta(hours=2)

    print(f"📊 Transactions before cleanup: {len(execution_layer.executed_transactions)}")

    # Clean up old transactions (older than 1 hour)
    execution_layer.cleanup_old_transactions(hours_old=1)
    print(f"📊 Transactions after cleanup: {len(execution_layer.executed_transactions)}")

    print("\n" + "=" * 60)
    print("EXECUTION LAYER DEMO COMPLETE!")
    print("=" * 60)

    # Final status
    final_status = execution_layer.print_status()
    print("\n" + final_status)


if __name__ == "__main__":
    main()