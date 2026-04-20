"""
Market Data Aggregator.

This module provides a unified interface for aggregating market data from
multiple sources (CEX and DEX).
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
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


class MarketAggregator:
    """
    Aggregates market data from multiple sources.

    Provides unified access to CEX and DEX price/volume/trade data.
    """

    def __init__(self):
        """Initialize the market data aggregator."""
        self.sources: Dict[str, MarketDataSource] = {}
        self._initialized = False

    def add_source(self, source: MarketDataSource):
        """
        Add a market data source.

        Args:
            source: Market data source instance
        """
        self.sources[source.name] = source
        self._initialized = True

    def get_price(
        self,
        token_address: str,
        token_symbol: Optional[str] = None,
        sources: Optional[List[str]] = None
    ) -> PriceData:
        """
        Get price from the best available source.

        Args:
            token_address: Token contract/address
            token_symbol: Token symbol
            sources: Optional list of source names to query

        Returns:
            PriceData object
        """
        if not self._initialized:
            raise MarketDataError("No sources initialized", "Aggregator")

        # Filter sources if specified
        available_sources = [
            (name, source)
            for name, source in self.sources.items()
            if sources is None or name in sources
        ]

        if not available_sources:
            raise MarketDataError("No available sources", "Aggregator")

        # Try each source until we get a successful price
        for name, source in available_sources:
            try:
                price_data = source.get_price(token_address, token_symbol)
                price_data.data_source = name
                return price_data
            except Exception as e:
                print(f"Error from {name}: {e}")
                continue

        raise MarketDataError("Could not get price from any source", "Aggregator")

    def get_prices(
        self,
        token_addresses: List[str],
        token_symbols: Optional[List[str]] = None,
        sources: Optional[List[str]] = None
    ) -> Dict[str, PriceData]:
        """
        Get prices for multiple tokens.

        Args:
            token_addresses: List of token addresses
            token_symbols: Optional list of token symbols (same order as addresses)
            sources: Optional list of source names to query

        Returns:
            Dictionary mapping token addresses to PriceData
        """
        prices = {}
        symbols = token_symbols or [None] * len(token_addresses)

        for address, symbol in zip(token_addresses, symbols):
            try:
                price = self.get_price(address, symbol, sources)
                prices[address] = price
            except Exception as e:
                print(f"Error getting price for {address}: {e}")

        return prices

    def get_volume(
        self,
        token_address: str,
        token_symbol: Optional[str] = None,
        sources: Optional[List[str]] = None
    ) -> VolumeData:
        """
        Get volume from the best available source.

        Args:
            token_address: Token contract/address
            token_symbol: Token symbol
            sources: Optional list of source names to query

        Returns:
            VolumeData object
        """
        if not self._initialized:
            raise MarketDataError("No sources initialized", "Aggregator")

        # Filter sources if specified
        available_sources = [
            (name, source)
            for name, source in self.sources.items()
            if sources is None or name in sources
        ]

        if not available_sources:
            raise MarketDataError("No available sources", "Aggregator")

        # Try each source until we get a successful volume
        for name, source in available_sources:
            try:
                volume_data = source.get_volume(token_address, token_symbol)
                volume_data.data_source = name
                return volume_data
            except Exception as e:
                print(f"Error from {name}: {e}")
                continue

        raise MarketDataError("Could not get volume from any source", "Aggregator")

    def get_trades(
        self,
        token_address: str,
        limit: int = 100,
        sources: Optional[List[str]] = None
    ) -> List[TradeData]:
        """
        Get trades from the best available source.

        Args:
            token_address: Token contract/address
            limit: Number of trades to retrieve
            sources: Optional list of source names to query

        Returns:
            List of TradeData objects
        """
        if not self._initialized:
            raise MarketDataError("No sources initialized", "Aggregator")

        # Filter sources if specified
        available_sources = [
            (name, source)
            for name, source in self.sources.items()
            if sources is None or name in sources
        ]

        if not available_sources:
            raise MarketDataError("No available sources", "Aggregator")

        # Try each source until we get a successful trades list
        for name, source in available_sources:
            try:
                trades = source.get_trades(token_address, limit)
                trades_data = []
                for trade in trades:
                    trade.data_source = name
                    trades_data.append(trade)
                return trades_data
            except Exception as e:
                print(f"Error from {name}: {e}")
                continue

        return []

    def get_multi_source_price(
        self,
        token_address: str,
        token_symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get price from all sources.

        Args:
            token_address: Token contract/address
            token_symbol: Token symbol

        Returns:
            Dictionary mapping source names to PriceData
        """
        prices = {}

        for name, source in self.sources.items():
            try:
                price_data = source.get_price(token_address, token_symbol)
                price_data.data_source = name
                prices[name] = price_data
            except Exception as e:
                print(f"Error from {name}: {e}")
                continue

        return prices

    def get_price_trend(
        self,
        token_address: str,
        token_symbol: Optional[str] = None,
        lookback_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get price trend data.

        Args:
            token_address: Token contract/address
            token_symbol: Token symbol
            lookback_hours: How far back to look

        Returns:
            List of price trend dictionaries
        """
        trend = []

        for name, source in self.sources.items():
            try:
                if hasattr(source, 'get_ohlcv'):
                    ohlcv = source.get_ohlcv(token_address, limit=lookback_hours * 4)

                    for candle in ohlcv:
                        trend.append({
                            'source': name,
                            'timestamp': datetime.fromtimestamp(int(candle[0]) / 1000),
                            'open': float(candle[1]),
                            'high': float(candle[2]),
                            'low': float(candle[3]),
                            'close': float(candle[4]),
                            'volume': float(candle[5])
                        })
            except Exception as e:
                print(f"Error getting trend from {name}: {e}")
                continue

        return trend

    def get_liquidity(
        self,
        token_address: str,
        token_symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get liquidity information from all sources.

        Args:
            token_address: Token contract/address
            token_symbol: Token symbol

        Returns:
            Dictionary with liquidity from each source
        """
        liquidity = {}

        for name, source in self.sources.items():
            try:
                if hasattr(source, 'get_volume'):
                    volume_data = source.get_volume(token_address, token_symbol)
                    liquidity[name] = {
                        'volume': volume_data.volume_24h,
                        'token_symbol': volume_data.token_symbol,
                        'timestamp': volume_data.timestamp
                    }
            except Exception as e:
                print(f"Error getting liquidity from {name}: {e}")
                continue

        return liquidity

    def get_best_source(
        self,
        token_address: str,
        metric: str = 'volume',
        token_symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get the best performing source for a metric.

        Args:
            token_address: Token contract/address
            metric: Metric to compare ('volume', 'trades')
            token_symbol: Token symbol

        Returns:
            Dictionary with best source information
        """
        if metric == 'volume':
            volumes = self.get_multi_source_price(token_address, token_symbol)
            best_source = max(volumes.items(), key=lambda x: x[1].volume)
            return {
                'best_source': best_source[0],
                'volume': best_source[1].volume,
                'other_sources': {
                    name: data.volume
                    for name, data in volumes.items()
                    if name != best_source[0]
                }
            }
        elif metric == 'trades':
            trade_counts = {}
            for name, source in self.sources.items():
                try:
                    trades = source.get_trades(token_address, limit=100)
                    trade_counts[name] = len(trades)
                except Exception as e:
                    trade_counts[name] = 0
            best_source = max(trade_counts.items(), key=lambda x: x[1])
            return {
                'best_source': best_source[0],
                'trade_count': best_source[1],
                'other_sources': trade_counts
            }
        else:
            raise ValueError(f"Unknown metric: {metric}")

    def get_all_tokens(self) -> Dict[str, List[str]]:
        """
        Get list of tokens from all sources.

        Returns:
            Dictionary mapping source names to token lists
        """
        tokens = {}

        for name, source in self.sources.items():
            try:
                if hasattr(source, 'get_all_tokens'):
                    token_list = source.get_all_tokens()
                    tokens[name] = [
                        token.get('symbol', '') if isinstance(token, dict) else token
                        for token in token_list
                    ]
            except Exception as e:
                print(f"Error getting tokens from {name}: {e}")
                tokens[name] = []

        return tokens


# Convenience functions
def create_binance_aggregator(api_key: Optional[str] = None, api_secret: Optional[str] = None) -> MarketAggregator:
    """Create an aggregator with Binance source."""
    aggregator = MarketAggregator()
    aggregator.add_source(BinanceAPI(api_key, api_secret))
    return aggregator


def create_coinbase_aggregator(api_key: Optional[str] = None, api_secret: Optional[str] = None) -> MarketAggregator:
    """Create an aggregator with Coinbase source."""
    aggregator = MarketAggregator()
    aggregator.add_source(CoinbaseAPI(api_key, api_secret))
    return aggregator


def create_dex_aggregator(api_key: Optional[str] = None) -> MarketAggregator:
    """Create an aggregator with DEX sources."""
    aggregator = MarketAggregator()
    aggregator.add_source(OneInch(api_key))
    aggregator.add_source(Jupiter(api_key))
    return aggregator


def create_full_aggregator(
    binance_key: Optional[str] = None,
    binance_secret: Optional[str] = None,
    coinbase_key: Optional[str] = None,
    coinbase_secret: Optional[str] = None,
    oneinch_key: Optional[str] = None,
    jupiter_key: Optional[str] = None
) -> MarketAggregator:
    """Create a full aggregator with all sources."""
    aggregator = MarketAggregator()

    if binance_key or binance_secret:
        aggregator.add_source(BinanceAPI(binance_key, binance_secret))

    if coinbase_key or coinbase_secret:
        aggregator.add_source(CoinbaseAPI(coinbase_key, coinbase_secret))

    if oneinch_key or jupiter_key:
        aggregator.add_source(OneInch(oneinch_key))
        aggregator.add_source(Jupiter(jupiter_key))

    return aggregator