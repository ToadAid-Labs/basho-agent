"""
Market Data Module.

This module provides integrations with multiple market data sources:
- CEX: Binance, Coinbase
- DEX: 1inch, Jupiter

Classes:
    MarketDataSource: Base class for all data sources
    PriceData, VolumeData, TradeData: Market data types
    BinanceAPI, CoinbaseAPI: CEX data sources
    OneInch, Jupiter: DEX data sources
    MarketAggregator: Unified interface for aggregating data
"""

from .base import (
    MarketDataSource,
    PriceData,
    VolumeData,
    TradeData,
    DataSourceType,
    MarketDataError
)

from .cex import BinanceAPI, CoinbaseAPI

from .dex import OneInch, Jupiter

from .aggregator import (
    MarketAggregator,
    create_binance_aggregator,
    create_coinbase_aggregator,
    create_dex_aggregator,
    create_full_aggregator
)

__version__ = "1.0.0"
__all__ = [
    'MarketDataSource',
    'PriceData',
    'VolumeData',
    'TradeData',
    'DataSourceType',
    'MarketDataError',
    'BinanceAPI',
    'CoinbaseAPI',
    'OneInch',
    'Jupiter',
    'MarketAggregator',
    'create_binance_aggregator',
    'create_coinbase_aggregator',
    'create_dex_aggregator',
    'create_full_aggregator',
    'demo'
]