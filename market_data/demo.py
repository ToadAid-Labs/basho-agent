"""
Demo script showing how to use the Market Data module.

This demonstrates:
1. Basic usage of PriceData, VolumeData, TradeData
2. Using CEX APIs (Binance, Coinbase)
3. Using DEX APIs (1inch, Jupiter)
4. Aggregating data from multiple sources
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_data import (
    MarketAggregator,
    create_binance_aggregator,
    create_full_aggregator,
    PriceData,
    VolumeData,
    TradeData
)


async def demo_basic_data_types():
    """Demo basic data type usage."""
    print("=" * 60)
    print("DEMO 1: Basic Data Types")
    print("=" * 60)

    # Create sample data
    price = PriceData(
        token_address="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",  # UNI
        token_symbol="UNI",
        price=6.52,
        timestamp=datetime.now(),
        data_source="Demo",
        source_type="CEX",
        volume=1000000
    )

    volume = VolumeData(
        token_address="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        token_symbol="UNI",
        volume_24h=12500000,
        volume_1h=500000,
        volume_4h=2000000,
        volume_7d=87500000,
        market_cap=4000000000,
        fdv=4500000000,
        timestamp=datetime.now(),
        data_source="Demo",
        source_type="CEX"
    )

    print(f"\nPrice Data:")
    print(f"  Token: {price.token_symbol}")
    print(f"  Address: {price.token_address}")
    print(f"  Price: ${price.price:.2f}")
    print(f"  Volume: {price.volume:,.2f}")
    print(f"  Source: {price.data_source}")

    print(f"\nVolume Data:")
    print(f"  Token: {volume.token_symbol}")
    print(f"  Address: {volume.token_address}")
    print(f"  24h Volume: {volume.volume_24h:,.2f}")
    print(f"  7d Volume: {volume.volume_7d:,.2f}")
    print(f"  Market Cap: ${volume.market_cap:,.2f}")


async def demo_binance():
    """Demo Binance API usage."""
    print("\n" + "=" * 60)
    print("DEMO 2: Binance API")
    print("=" * 60)

    aggregator = create_binance_aggregator()
    aggregator.add_source(BinanceAPI())

    try:
        # Get price for ETH
        print("\nFetching ETH price from Binance...")
        price = await aggregator.get_price("ETH", "ETH")
        print(f"  ETH Price: ${price.price:.2f}")
        print(f"  Timestamp: {price.timestamp}")
        print(f"  Source: {price.data_source}")

        # Get volume for SOL
        print("\nFetching SOL 24h volume from Binance...")
        volume = await aggregator.get_volume("SOL", "SOL")
        print(f"  SOL Volume: ${volume.volume_24h:,.2f}")

        # Get recent trades
        print("\nFetching recent trades for BTC...")
        trades = await aggregator.get_trades("BTC", limit=5)
        print(f"  Trade Count: {len(trades)}")
        if trades:
            trade = trades[0]
            print(f"  Sample Trade:")
            print(f"    Price: ${trade.price:.2f}")
            print(f"    Amount: {trade.amount}")
            print(f"    Side: {trade.direction}")

    except Exception as e:
        print(f"Error: {e}")


async def demo_coinbase():
    """Demo Coinbase API usage."""
    print("\n" + "=" * 60)
    print("DEMO 3: Coinbase API")
    print("=" * 60)

    aggregator = create_coinbase_aggregator()
    aggregator.add_source(CoinbaseAPI())

    try:
        # Get price for BTC
        print("\nFetching BTC price from Coinbase...")
        price = await aggregator.get_price("BTC", "BTC")
        print(f"  BTC Price: ${price.price:.2f}")
        print(f"  Source: {price.data_source}")

    except Exception as e:
        print(f"Error: {e}")


async def demo_aggregator():
    """Demo MarketAggregator usage."""
    print("\n" + "=" * 60)
    print("DEMO 4: Market Aggregator")
    print("=" * 60)

    # Create aggregator with all sources
    aggregator = create_full_aggregator(
        binance_key=None,
        coinbase_key=None,
        oneinch_key=None,
        jupiter_key=None
    )

    try:
        # Get price from best source
        print("\nFetching price for ETH from best available source...")
        price = await aggregator.get_price("ETH", "ETH")
        print(f"  Token: {price.token_symbol}")
        print(f"  Price: ${price.price:.2f}")
        print(f"  Source: {price.data_source}")

        # Get volume from best source
        print("\nFetching volume for SOL from best available source...")
        volume = await aggregator.get_volume("SOL", "SOL")
        print(f"  Token: {volume.token_symbol}")
        print(f"  24h Volume: ${volume.volume_24h:,.2f}")
        print(f"  Source: {volume.data_source}")

        # Get prices for multiple tokens
        print("\nFetching prices for multiple tokens...")
        tokens = ["ETH", "BTC", "SOL", "MATIC"]
        prices = await aggregator.get_prices(tokens)
        print("\nPrice Summary:")
        for address, p in prices.items():
            print(f"  {p.token_symbol}: ${p.price:.2f} ({p.data_source})")

    except Exception as e:
        print(f"Error: {e}")


async def demo_multi_source_comparison():
    """Demo comparing multiple sources."""
    print("\n" + "=" * 60)
    print("DEMO 5: Multi-Source Comparison")
    print("=" * 60)

    aggregator = create_full_aggregator(
        binance_key=None,
        coinbase_key=None
    )

    try:
        # Get prices from all sources
        print("\nFetching prices for ETH from all sources...")
        multi_price = await aggregator.get_multi_source_price("ETH", "ETH")

        print("\nPrice Comparison:")
        print(f"{'Source':<15} {'Price':<15}")
        print("-" * 35)
        for source, price in multi_price.items():
            print(f"{source:<15} ${price.price:.4f}")

        # Get best source
        print("\nFetching best source for volume...")
        best = await aggregator.get_best_source("BTC", metric="volume")
        print(f"\nBest Volume Source:")
        print(f"  Source: {best['best_source']}")
        print(f"  Volume: ${best['volume']:,.2f}")

    except Exception as e:
        print(f"Error: {e}")


async def demo_error_handling():
    """Demo error handling."""
    print("\n" + "=" * 60)
    print("DEMO 6: Error Handling")
    print("=" * 60)

    aggregator = MarketAggregator()

    try:
        # Try to get price from uninitialized aggregator
        print("\nTrying to get price from uninitialized aggregator...")
        price = await aggregator.get_price("ETH", "ETH")
        print(f"Price: {price.price}")
    except Exception as e:
        print(f"Expected Error: {e}")


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("Market Data Module Demo")
    print("=" * 60)

    await demo_basic_data_types()
    await demo_error_handling()
    await demo_aggregator()

    # Uncomment to run live API demos:
    # await demo_binance()
    # await demo_coinbase()
    # await demo_multi_source_comparison()

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
