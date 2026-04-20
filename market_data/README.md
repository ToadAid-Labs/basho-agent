# Market Data Module

A comprehensive Python module for fetching and aggregating market data from multiple cryptocurrency exchanges and decentralized exchanges.

## Features

- **Unified Interface**: Single API for multiple data sources
- **Multiple Data Types**: Price, Volume, Trade data
- **CEX Integration**: Binance, Coinbase
- **DEX Integration**: 1inch, Jupiter
- **Data Aggregation**: Compare and aggregate data from multiple sources
- **Error Handling**: Robust error handling with retries

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

### Basic Usage

```python
import asyncio
from market_data import create_full_aggregator

async def main():
    # Create aggregator with all sources
    aggregator = create_full_aggregator()

    # Get price for a token
    price = await aggregator.get_price("ETH", "ETH")
    print(f"ETH Price: ${price.price:.2f}")

    # Get volume for a token
    volume = await aggregator.get_volume("SOL", "SOL")
    print(f"SOL 24h Volume: ${volume.volume_24h:,.2f}")

    # Get recent trades
    trades = await aggregator.get_trades("BTC", limit=10)
    print(f"Trade Count: {len(trades)}")

asyncio.run(main())
```

### Data Types

#### PriceData

```python
from market_data import PriceData

price = PriceData(
    token_address="0x...",
    token_symbol="ETH",
    price=1850.25,
    volume=5000000,
    timestamp=datetime.now(),
    data_source="Binance",
    source_type="CEX"
)
```

#### VolumeData

```python
from market_data import VolumeData

volume = VolumeData(
    token_address="0x...",
    token_symbol="ETH",
    volume_24h=12500000,
    volume_1h=500000,
    volume_4h=2000000,
    volume_7d=87500000,
    market_cap=4000000000,
    fdv=4500000000,
    timestamp=datetime.now(),
    data_source="Binance",
    source_type="CEX"
)
```

#### TradeData

```python
from market_data import TradeData

trade = TradeData(
    token_address="0x...",
    token_symbol="ETH",
    price=1850.25,
    amount=1.5,
    direction="buy",  # or "sell"
    timestamp=datetime.now(),
    data_source="Binance",
    source_type="CEX"
)
```

### Using Specific Sources

```python
import asyncio
from market_data import BinanceAPI, CoinbaseAPI, MarketAggregator

async def main():
    # Create separate aggregators for specific sources
    binance = MarketAggregator()
    binance.add_source(BinanceAPI())

    coinbase = MarketAggregator()
    coinbase.add_source(CoinbaseAPI())

    # Get prices from each source
    binance_price = await binance.get_price("BTC", "BTC")
    coinbase_price = await coinbase.get_price("BTC", "BTC")

asyncio.run(main())
```

### Aggregating Data

```python
import asyncio
from market_data import MarketAggregator

async def main():
    aggregator = MarketAggregator()

    # Add multiple sources
    from market_data import BinanceAPI, CoinbaseAPI, OneInch, Jupiter
    aggregator.add_source(BinanceAPI())
    aggregator.add_source(CoinbaseAPI())
    aggregator.add_source(OneInch())
    aggregator.add_source(Jupiter())

    # Get price from best source
    price = await aggregator.get_price("ETH", "ETH")

    # Get prices from all sources
    multi_price = await aggregator.get_multi_source_price("ETH", "ETH")
    for source, data in multi_price.items():
        print(f"{source}: ${data.price}")

    # Compare sources
    best = await aggregator.get_best_source("BTC", metric="volume")
    print(f"Best volume source: {best['best_source']}")

asyncio.run(main())
```

### Demo

Run the demo script:

```bash
python -m market_data.demo
```

## API Reference

### MarketAggregator

The main class for aggregating data from multiple sources.

#### Methods

- `get_price(token_address, token_symbol=None)` - Get price from best source
- `get_prices(token_addresses, token_symbols=None)` - Get prices for multiple tokens
- `get_volume(token_address, token_symbol=None)` - Get volume from best source
- `get_trades(token_address, limit=100)` - Get recent trades
- `get_multi_source_price(token_address, token_symbol=None)` - Get price from all sources
- `get_price_trend(token_address, lookback_hours=24)` - Get historical price data
- `get_liquidity(token_address, token_symbol=None)` - Get liquidity info
- `get_best_source(token_address, metric='volume')` - Get best performing source
- `get_all_tokens()` - Get list of tokens from all sources

### Convenience Functions

- `create_binance_aggregator()` - Create aggregator with Binance only
- `create_coinbase_aggregator()` - Create aggregator with Coinbase only
- `create_dex_aggregator()` - Create aggregator with DEX sources
- `create_full_aggregator()` - Create aggregator with all sources

## Configuration

### API Keys

Some exchanges require API keys for higher rate limits:

```python
from market_data import BinanceAPI

# For Binance
api_key = "your_api_key"
api_secret = "your_api_secret"
binance = BinanceAPI(api_key, api_secret)
```

## Error Handling

The module uses custom exceptions:

- `MarketDataError` - Base exception for market data errors

```python
try:
    price = await aggregator.get_price("UNKNOWN_TOKEN")
except MarketDataError as e:
    print(f"Error: {e}")
```

## Architecture

```
market_data/
├── __init__.py       # Module exports
├── base.py          # Base classes and data types
├── cex.py           # CEX API implementations
├── dex.py           # DEX API implementations
├── aggregator.py    # Data aggregation logic
├── demo.py          # Example usage
└── requirements.txt # Python dependencies
```

## Data Sources

### CEX
- **Binance**: Leading crypto exchange
- **Coinbase**: Major US-based exchange

### DEX
- **1inch**: Decentralized exchange aggregator
- **Jupiter**: Solana DEX aggregator

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.