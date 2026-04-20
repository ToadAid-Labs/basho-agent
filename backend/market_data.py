"""
Market data module for fetching and aggregating cryptocurrency prices.

This module provides interfaces for fetching market data from various sources
and aggregating results.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

# Database imports
try:
    from backend.database import SessionLocal
    from backend.models import MarketDataRecord as MarketDataRecordModel
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    SessionLocal = None
    MarketDataRecordModel = None


@dataclass
class PriceData:
    """Price data for a symbol."""

    symbol: str
    price: Decimal
    data_source: str
    volume: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "price": float(self.price),
            "data_source": self.data_source,
            "volume": float(self.volume) if self.volume else None,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PriceTrend:
    """Price trend data for a symbol."""

    symbol: str
    start_price: Decimal
    end_price: Decimal
    current_price: Decimal
    high: Decimal
    low: Decimal
    change_24h: Decimal
    change_percent: Decimal
    period_hours: int
    data_points: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "start_price": float(self.start_price),
            "end_price": float(self.end_price),
            "current_price": float(self.current_price),
            "high": float(self.high),
            "low": float(self.low),
            "change_24h": float(self.change_24h),
            "change_percent": float(self.change_percent),
            "period_hours": self.period_hours,
            "data_points": self.data_points,
        }


class DataSource(ABC):
    """Abstract base class for data sources."""

    @abstractmethod
    async def fetch_price(self, symbol: str, currency: str = "USD") -> Optional[PriceData]:
        """Fetch current price for a symbol."""
        pass

    @abstractmethod
    async def fetch_price_trend(self, symbol: str, hours: int = 24) -> Optional[PriceTrend]:
        """Fetch price trend for a symbol."""
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """Get data source name."""
        pass


class BinanceAPI(DataSource):
    """Binance API data source."""

    BASE_URL = "https://api.binance.com/api/v3"

    async def fetch_price(self, symbol: str, currency: str = "USD") -> Optional[PriceData]:
        """Fetch current price from Binance."""
        try:
            pair = f"{symbol.upper()}{currency.upper()}"
            url = f"{self.BASE_URL}/ticker/price?symbol={pair}"

            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = Decimal(data.get("price", 0))

                        # Store in database
                        await self._store_price(symbol, price, "binance")

                        return PriceData(
                            symbol=symbol,
                            price=price,
                            data_source="binance",
                            volume=None,
                        )

        except Exception as e:
            print(f"Binance price fetch error: {e}")
            return None

    async def fetch_price_trend(self, symbol: str, hours: int = 24) -> Optional[PriceTrend]:
        """Fetch price trend from Binance."""
        try:
            pair = f"{symbol.upper()}USDT"
            url = f"{self.BASE_URL}/klines?symbol={pair}&interval=1h&limit={hours}"

            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        klines = await response.json()

                        if not klines:
                            return None

                        data_points = []
                        for k in klines:
                            timestamp = datetime.fromtimestamp(k[0] / 1000)
                            open_price = Decimal(k[1])
                            high = Decimal(k[2])
                            low = Decimal(k[3])
                            close = Decimal(k[4])
                            volume = Decimal(k[5])

                            data_points.append({
                                "timestamp": timestamp.isoformat(),
                                "open": float(open_price),
                                "high": float(high),
                                "low": float(low),
                                "close": float(close),
                                "volume": float(volume),
                            })

                        start_price = Decimal(klines[0][1])
                        end_price = Decimal(klines[-1][4])
                        current_price = end_price
                        high = max(Decimal(k[2]) for k in klines)
                        low = min(Decimal(k[3]) for k in klines)

                        change_24h = end_price - start_price
                        change_percent = (change_24h / start_price * 100) if start_price else 0

                        trend = PriceTrend(
                            symbol=symbol,
                            start_price=start_price,
                            end_price=end_price,
                            current_price=current_price,
                            high=high,
                            low=low,
                            change_24h=change_24h,
                            change_percent=change_percent,
                            period_hours=hours,
                            data_points=data_points,
                        )

                        return trend

        except Exception as e:
            print(f"Binance trend fetch error: {e}")
            return None

    def get_source_name(self) -> str:
        """Get data source name."""
        return "Binance"

    async def _store_price(self, symbol: str, price: Decimal, source: str):
        """Store price in database."""
        if not DB_AVAILABLE or not SessionLocal:
            return

        session = SessionLocal()
        try:
            record = session.query(MarketDataRecordModel).filter(
                MarketDataRecordModel.symbol == symbol,
                MarketDataRecordModel.data_source == source
            ).first()

            if record:
                record.price = price
                record.timestamp = datetime.now(timezone.utc)
            else:
                record = MarketDataRecordModel(
                    symbol=symbol,
                    price=price,
                    data_source=source,
                    timestamp=datetime.now(timezone.utc),
                )
                session.add(record)

            session.commit()
        except Exception as e:
            print(f"Error storing price: {e}")
            session.rollback()
        finally:
            session.close()


class CoinbaseAPI(DataSource):
    """Coinbase API data source."""

    BASE_URL = "https://api.coinbase.com/v2"

    async def fetch_price(self, symbol: str, currency: str = "USD") -> Optional[PriceData]:
        """Fetch current price from Coinbase."""
        try:
            pair = f"{symbol.upper()}-{currency.upper()}"
            url = f"{self.BASE_URL}/prices/{pair}/buy"

            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = Decimal(data.get("data", {}).get("amount", 0))

                        await self._store_price(symbol, price, "coinbase")

                        return PriceData(
                            symbol=symbol,
                            price=price,
                            data_source="coinbase",
                            volume=None,
                        )

        except Exception as e:
            print(f"Coinbase price fetch error: {e}")
            return None

    async def fetch_price_trend(self, symbol: str, hours: int = 24) -> Optional[PriceTrend]:
        """Fetch price trend from Coinbase."""
        try:
            pair = f"{symbol.upper()}-USD"
            url = f"{self.BASE_URL}/prices/{pair}/spot"

            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        current_price = Decimal(data.get("data", {}).get("amount", 0))

                        # Get historical data
                        start_date = datetime.now(timezone.utc) - timedelta(hours=hours)
                        url = f"{self.BASE_URL}/currencies/{symbol.upper()}/historical"

                        async with session.get(url) as resp:
                            if resp.status == 200:
                                hist_data = await resp.json()

                                data_points = []
                                for item in hist_data.get("data", {}).get("history", []):
                                    timestamp = datetime.strptime(item.get("time", ""), "%Y-%m-%dT%H:%M:%SZ")
                                    price = Decimal(item.get("price", 0))

                                    data_points.append({
                                        "timestamp": timestamp.isoformat(),
                                        "price": float(price),
                                    })

                                # Sort by timestamp
                                data_points.sort(key=lambda x: x["timestamp"])

                                start_price = Decimal(data_points[0]["price"]) if data_points else current_price
                                high = max(Decimal(p["price"]) for p in data_points) if data_points else current_price
                                low = min(Decimal(p["price"]) for p in data_points) if data_points else current_price

                                change_24h = current_price - start_price
                                change_percent = (change_24h / start_price * 100) if start_price else 0

                                trend = PriceTrend(
                                    symbol=symbol,
                                    start_price=start_price,
                                    end_price=current_price,
                                    current_price=current_price,
                                    high=high,
                                    low=low,
                                    change_24h=change_24h,
                                    change_percent=change_percent,
                                    period_hours=hours,
                                    data_points=data_points,
                                )

                                return trend

        except Exception as e:
            print(f"Coinbase trend fetch error: {e}")
            return None

    def get_source_name(self) -> str:
        """Get data source name."""
        return "Coinbase"

    async def _store_price(self, symbol: str, price: Decimal, source: str):
        """Store price in database."""
        if not DB_AVAILABLE or not SessionLocal:
            return

        session = SessionLocal()
        try:
            record = session.query(MarketDataRecordModel).filter(
                MarketDataRecordModel.symbol == symbol,
                MarketDataRecordModel.data_source == source
            ).first()

            if record:
                record.price = price
                record.timestamp = datetime.now(timezone.utc)
            else:
                record = MarketDataRecordModel(
                    symbol=symbol,
                    price=price,
                    data_source=source,
                    timestamp=datetime.now(timezone.utc),
                )
                session.add(record)

            session.commit()
        except Exception as e:
            print(f"Error storing price: {e}")
            session.rollback()
        finally:
            session.close()


class MarketAggregator:
    """Aggregates multiple data sources."""

    def __init__(self):
        self._sources: List[DataSource] = []

    def add_source(self, source: DataSource):
        """Add a data source."""
        self._sources.append(source)

    async def get_price(self, symbol: str, currency: str = "USD") -> Optional[PriceData]:
        """Get price from all sources and return best result."""
        tasks = [source.fetch_price(symbol, currency) for source in self._sources]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = [r for r in results if not isinstance(r, Exception) and r is not None]

        return valid_results[0] if valid_results else None

    async def get_price_trend(self, symbol: str, hours: int = 24) -> Optional[PriceTrend]:
        """Get price trend from all sources and return best result."""
        tasks = [source.fetch_price_trend(symbol, hours) for source in self._sources]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = [r for r in results if not isinstance(r, Exception) and r is not None]

        return valid_results[0] if valid_results else None

    def get_available_sources(self) -> List[str]:
        """Get list of available data sources."""
        return [source.get_source_name() for source in self._sources]

    async def aggregate_data(self, symbol: str, hours: int = 24) -> Dict[str, Any]:
        """Aggregate data from all sources."""
        price = await self.get_price(symbol)
        trend = await self.get_price_trend(symbol, hours)

        return {
            "symbol": symbol,
            "price": price.to_dict() if price else None,
            "trend": trend.to_dict() if trend else None,
            "sources": self.get_available_sources(),
        }

    async def multi_symbol(self, symbols: List[str]) -> Dict[str, Any]:
        """Get prices for multiple symbols."""
        results = {}

        for symbol in symbols:
            price = await self.get_price(symbol)
            if price:
                results[symbol] = price.to_dict()

        return {
            "symbols": list(results.keys()),
            "data": results,
        }


# Global aggregator instance
market_aggregator = MarketAggregator()
initialized = False

# Market data symbols to fetch
TRADING_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT", "MATIC", "LINK"]


def init_market_data():
    """Initialize market data module with default sources."""
    market_aggregator.add_source(BinanceAPI())
    market_aggregator.add_source(CoinbaseAPI())


def ensure_market_data_initialized():
    """Ensure market data is initialized."""
    global initialized
    if not initialized:
        init_market_data()
        initialized = True


def get_current_prices() -> Dict[str, float]:
    """
    Get current prices for trading symbols.

    Fetches prices from configured market data sources and returns them as a dictionary.
    """
    ensure_market_data_initialized()

    prices = {}

    try:
        # Check if there's already an event loop running
        try:
            loop = asyncio.get_running_loop()
            running_loop = True
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            running_loop = False

        # Fetch prices for all trading symbols
        for symbol in TRADING_SYMBOLS:
            if running_loop:
                # If loop is running, we can't use run_until_complete
                # This is a fallback for when this is called from an async context
                # though usually get_current_prices is intended for sync contexts
                import nest_asyncio
                nest_asyncio.apply()

            price_data = loop.run_until_complete(market_aggregator.get_price(symbol))

            if price_data:
                prices[symbol] = float(price_data.price)

    except Exception as e:
        print(f"Error fetching current prices: {e}")

    for symbol in TRADING_SYMBOLS:
        if symbol not in prices:
            fallback_price = _get_trust_wallet_price(symbol)
            if fallback_price:
                prices[symbol] = fallback_price

    return prices


def _get_trust_wallet_price(symbol: str) -> Optional[float]:
    chain_by_symbol = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "BNB": "bsc",
        "MATIC": "polygon",
    }
    chain = chain_by_symbol.get(symbol.upper(), "ethereum")
    try:
        from tools.trust import trust_get_token_price

        raw = trust_get_token_price(token_symbol=symbol.upper(), chain=chain)
        data = json.loads(raw)
        price = data.get("priceUsd") or data.get("price")
        return float(price) if price is not None else None
    except Exception:
        return None
