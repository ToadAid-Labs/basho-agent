"""
CEX API integrations.

This module provides integration with centralized exchange APIs:
- Binance
- Coinbase
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from .base import (
    MarketDataSource,
    PriceData,
    VolumeData,
    TradeData,
    DataSourceType,
    MarketDataError
)
import aiohttp


class BinanceAPI(MarketDataSource):
    """
    Binance Exchange API integration.

    Provides access to Binance spot market data.
    """

    BASE_URL = "https://api.binance.com"

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize Binance API client.

        Args:
            api_key: Binance API key (optional for public endpoints)
            api_secret: Binance API secret (optional for private endpoints)
        """
        super().__init__("Binance", api_key)
        self.api_secret = api_secret
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create async HTTP session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    def _get_symbol(self, token_address: str, token_symbol: Optional[str] = None) -> str:
        """Get Binance symbol from token info."""
        # Map common tokens to Binance symbols
        token_map = {
            "BTC": "BTCUSDT",
            "ETH": "ETHUSDT",
            "SOL": "SOLUSDT",
            "USDT": "USDTUSDT",
            "USDC": "USDCUSDT",
            "BNB": "BNBUSDT",
            "MATIC": "MATICUSDT",
            "ADA": "ADAUSDT",
            "XRP": "XRPUSDT",
            "DOGE": "DOGEUSDT",
            "AVAX": "AVAXUSDT",
            "LINK": "LINKUSDT",
            "UNI": "UNIUSDT"
        }

        symbol = token_symbol or token_address
        return token_map.get(symbol.upper(), f"{symbol.upper()}USDT")

    async def get_price(
        self,
        token_address: str,
        token_symbol: Optional[str] = None
    ) -> PriceData:
        """
        Get current price for a token.

        Args:
            token_address: Token address (for mapping to symbol)
            token_symbol: Token symbol

        Returns:
            PriceData object
        """
        session = await self._get_session()
        symbol = self._get_symbol(token_address, token_symbol)

        try:
            async with session.get(f"{self.BASE_URL}/api/v3/ticker/price") as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"Binance API error: {response.status}",
                        self.name
                    )

                data = await response.json()

                # Find our symbol in the response
                ticker_data = None
                for ticker in data:
                    if ticker.get("symbol") == symbol:
                        ticker_data = ticker
                        break

                if not ticker_data:
                    raise MarketDataError(
                        f"Symbol {symbol} not found on Binance",
                        self.name
                    )

                price_data = PriceData(
                    token_address=token_address,
                    token_symbol=token_symbol or symbol.replace("USDT", "").replace("USDC", ""),
                    price=float(ticker_data.get("price", 0)),
                    timestamp=datetime.fromtimestamp(
                        int(ticker_data.get("time", 0)) / 1000
                    ),
                    data_source=self.name,
                    source_type=DataSourceType.CEX,
                    high=float(ticker_data.get("highPrice", 0)),
                    low=float(ticker_data.get("lowPrice", 0)),
                    volume=float(ticker_data.get("quoteVolume", 0))
                )

                await self.update_last_data_time()
                return price_data

        except aiohttp.ClientError as e:
            raise MarketDataError(f"Network error: {str(e)}", self.name)

    async def get_prices(
        self,
        token_addresses: List[str]
    ) -> List[PriceData]:
        """Get prices for multiple tokens."""
        prices = []
        for token_address in token_addresses:
            try:
                price = await self.get_price(token_address)
                prices.append(price)
            except Exception as e:
                print(f"Error getting price for {token_address}: {e}")
        return prices

    async def get_volume(
        self,
        token_address: str,
        token_symbol: Optional[str] = None
    ) -> VolumeData:
        """
        Get 24h volume for a token.

        Args:
            token_address: Token address
            token_symbol: Token symbol

        Returns:
            VolumeData object
        """
        session = await self._get_session()
        symbol = self._get_symbol(token_address, token_symbol)

        try:
            async with session.get(f"{self.BASE_URL}/api/v3/ticker/24hr") as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"Binance API error: {response.status}",
                        self.name
                    )

                data = await response.json()

                # Find our symbol in the response
                ticker_data = None
                for ticker in data:
                    if ticker.get("symbol") == symbol:
                        ticker_data = ticker
                        break

                if not ticker_data:
                    raise MarketDataError(
                        f"Symbol {symbol} not found on Binance",
                        self.name
                    )

                volume_data = VolumeData(
                    token_address=token_address,
                    token_symbol=token_symbol or symbol.replace("USDT", "").replace("USDC", ""),
                    volume_24h=float(ticker_data.get("quoteVolume", 0)),
                    volume_1h=0,
                    volume_4h=0,
                    volume_7d=0,
                    market_cap=0,
                    fdv=0,
                    timestamp=datetime.now(),
                    data_source=self.name,
                    source_type=DataSourceType.CEX
                )

                await self.update_last_data_time()
                return volume_data

        except aiohttp.ClientError as e:
            raise MarketDataError(f"Network error: {str(e)}", self.name)

    async def get_trades(
        self,
        token_address: str,
        limit: int = 100
    ) -> List[TradeData]:
        """
        Get recent trades for a token.

        Args:
            token_address: Token address
            limit: Number of trades to retrieve

        Returns:
            List of TradeData objects
        """
        session = await self._get_session()
        symbol = self._get_symbol(token_address)

        try:
            async with session.get(f"{self.BASE_URL}/api/v3/aggTrades?symbol={symbol}&limit={limit}") as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"Binance API error: {response.status}",
                        self.name
                    )

                data = await response.json()

                trades = []
                for trade in data:
                    trade_data = TradeData(
                        trade_id=str(trade.get("a", "")),
                        token_address=token_address,
                        token_symbol=symbol.replace("USDT", ""),
                        direction=trade.get("m", "buy").lower(),
                        amount=float(trade.get("q", 0)),
                        price=float(trade.get("p", 0)),
                        timestamp=datetime.fromtimestamp(
                            int(trade.get("T", 0)) / 1000
                        ),
                        data_source=self.name,
                        source_type=DataSourceType.CEX,
                        side=trade.get("m", "buy").lower(),
                        slippage=None,
                        protocol="Binance"
                    )
                    trades.append(trade_data)

                await self.update_last_data_time()
                return trades

        except aiohttp.ClientError as e:
            raise MarketDataError(f"Network error: {str(e)}", self.name)

    async def get_ohlcv(
        self,
        token_address: str,
        interval: str = "1h",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get OHLCV data for a token.

        Args:
            token_address: Token address
            interval: Time interval (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles

        Returns:
            List of OHLCV dictionaries
        """
        session = await self._get_session()
        symbol = self._get_symbol(token_address)

        try:
            url = f"{self.BASE_URL}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
            async with session.get(url) as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"Binance API error: {response.status}",
                        self.name
                    )

                data = await response.json()
                await self.update_last_data_time()
                return data

        except aiohttp.ClientError as e:
            raise MarketDataError(f"Network error: {str(e)}", self.name)


class CoinbaseAPI(MarketDataSource):
    """
    Coinbase Exchange API integration.

    Provides access to Coinbase spot market data.
    """

    BASE_URL = "https://api.coinbase.com/v2"

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize Coinbase API client.

        Args:
            api_key: Coinbase API key (optional for public endpoints)
            api_secret: Coinbase API secret (optional for private endpoints)
        """
        super().__init__("Coinbase", api_key)
        self.api_secret = api_secret
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create async HTTP session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    def _get_product(self, token_address: str, token_symbol: Optional[str] = None) -> str:
        """Get Coinbase product ID from token info."""
        # Map common tokens to Coinbase product IDs
        token_map = {
            "BTC": "BTC-USD",
            "ETH": "ETH-USD",
            "SOL": "SOL-USD",
            "USDT": "USDT-USD",
            "USDC": "USDC-USD",
            "MATIC": "MATIC-USD",
            "ADA": "ADA-USD",
            "XRP": "XRP-USD",
            "DOGE": "DOGE-USD",
            "AVAX": "AVAX-USD",
            "LINK": "LINK-USD",
            "UNI": "UNI-USD"
        }

        product = token_symbol or token_address
        return token_map.get(product.upper(), f"{product.upper()}-USD")

    async def get_price(
        self,
        token_address: str,
        token_symbol: Optional[str] = None
    ) -> PriceData:
        """
        Get current price for a token.

        Args:
            token_address: Token address (for mapping to product)
            token_symbol: Token symbol

        Returns:
            PriceData object
        """
        session = await self._get_session()
        product = self._get_product(token_address, token_symbol)

        try:
            async with session.get(f"{self.BASE_URL}/products/{product}/price") as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"Coinbase API error: {response.status}",
                        self.name
                    )

                data = await response.json()
                price_data = data.get("data", {}).get("amount", "0")

                price_data_obj = PriceData(
                    token_address=token_address,
                    token_symbol=token_symbol or product.replace("-USD", ""),
                    price=float(price_data),
                    timestamp=datetime.now(),
                    data_source=self.name,
                    source_type=DataSourceType.CEX
                )

                await self.update_last_data_time()
                return price_data_obj

        except aiohttp.ClientError as e:
            raise MarketDataError(f"Network error: {str(e)}", self.name)

    async def get_prices(
        self,
        token_addresses: List[str]
    ) -> List[PriceData]:
        """Get prices for multiple tokens."""
        prices = []
        for token_address in token_addresses:
            try:
                price = await self.get_price(token_address)
                prices.append(price)
            except Exception as e:
                print(f"Error getting price for {token_address}: {e}")
        return prices

    async def get_volume(
        self,
        token_address: str,
        token_symbol: Optional[str] = None
    ) -> VolumeData:
        """
        Get 24h volume for a token.

        Args:
            token_address: Token address
            token_symbol: Token symbol

        Returns:
            VolumeData object
        """
        session = await self._get_session()
        product = self._get_product(token_address, token_symbol)

        try:
            async with session.get(f"{self.BASE_URL}/products/{product}/stats") as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"Coinbase API error: {response.status}",
                        self.name
                    )

                data = await response.json()
                stats = data.get("data", {})

                volume_data = VolumeData(
                    token_address=token_address,
                    token_symbol=token_symbol or product.replace("-USD", ""),
                    volume_24h=float(stats.get("volume_24h", 0)),
                    volume_1h=0,
                    volume_4h=0,
                    volume_7d=0,
                    market_cap=0,
                    fdv=0,
                    timestamp=datetime.now(),
                    data_source=self.name,
                    source_type=DataSourceType.CEX
                )

                await self.update_last_data_time()
                return volume_data

        except aiohttp.ClientError as e:
            raise MarketDataError(f"Network error: {str(e)}", self.name)

    async def get_trades(
        self,
        token_address: str,
        limit: int = 100
    ) -> List[TradeData]:
        """
        Get recent trades for a token.

        Args:
            token_address: Token address
            limit: Number of trades to retrieve

        Returns:
            List of TradeData objects
        """
        session = await self._get_session()
        product = self._get_product(token_address)

        try:
            async with session.get(f"{self.BASE_URL}/products/{product}/trades?limit={limit}") as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"Coinbase API error: {response.status}",
                        self.name
                    )

                data = await response.json()
                trades_data = data.get("data", [])

                trades = []
                for trade in trades_data:
                    trade_data = TradeData(
                        trade_id=trade.get("trade_id", ""),
                        token_address=token_address,
                        token_symbol=product.replace("-USD", ""),
                        direction=trade.get("side", "buy").lower(),
                        amount=float(trade.get("size", 0)),
                        price=float(trade.get("price", 0)),
                        timestamp=datetime.fromisoformat(trade.get("created_at", "")),
                        data_source=self.name,
                        source_type=DataSourceType.CEX,
                        side=trade.get("side", "buy").lower(),
                        slippage=None,
                        protocol="Coinbase"
                    )
                    trades.append(trade_data)

                await self.update_last_data_time()
                return trades

        except aiohttp.ClientError as e:
            raise MarketDataError(f"Network error: {str(e)}", self.name)

    async def get_ohlcv(
        self,
        token_address: str,
        interval: str = "1h",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get OHLCV data for a token.

        Args:
            token_address: Token address
            interval: Time interval (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles

        Returns:
            List of OHLCV dictionaries
        """
        session = await self._get_session()
        product = self._get_product(token_address)

        try:
            url = f"{self.BASE_URL}/products/{product}/candles"
            params = {
                "granularity": self._convert_interval(interval),
                "count": limit
            }
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"Coinbase API error: {response.status}",
                        self.name
                    )

                data = await response.json()
                await self.update_last_data_time()
                return data

        except aiohttp.ClientError as e:
            raise MarketDataError(f"Network error: {str(e)}", self.name)

    # Helper methods
    def _convert_interval(self, interval: str) -> str:
        """Convert standard interval to Coinbase granularity."""
        mapping = {
            "1m": "60",
            "5m": "300",
            "15m": "900",
            "1h": "3600",
            "4h": "14400",
            "1d": "86400"
        }
        return mapping.get(interval, "3600")