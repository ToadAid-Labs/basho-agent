"""
API client module for interacting with cryptocurrency exchanges.

This module provides:
- Binance API client
- Coinbase API client
- Generic exchange API client
- Market data fetching
- Trade execution (paper trading)
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from decimal import Decimal
import time

from backend.config import settings
from backend.redis import get_redis_manager, get_price, set_price
from backend.database import get_db_manager, MarketDataRecord


class ExchangeAPIError(Exception):
    """Base exception for exchange API errors."""
    pass


class APIClient:
    """Base API client."""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """Initialize API client."""
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = aiohttp.ClientSession()

    async def close(self):
        """Close session."""
        await self.session.close()

    async def _request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request."""
        try:
            async with self.session.request(method, url, **kwargs) as response:
                data = await response.json()
                if response.status >= 400:
                    raise ExchangeAPIError(f"API error: {response.status} - {data}")
                return data
        except aiohttp.ClientError as e:
            raise ExchangeAPIError(f"Request error: {e}")


class BinanceClient(APIClient):
    """Binance API client."""

    BASE_URL = "https://api.binance.com/api/v3"

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """Initialize Binance client."""
        super().__init__(api_key, api_secret)

    async def get_ticker_price(self, symbol: str = "BTCUSDT") -> Optional[Decimal]:
        """Get current ticker price."""
        try:
            url = f"{self.BASE_URL}/ticker/price?symbol={symbol}"
            data = await self._request("GET", url)

            price = Decimal(data["price"])
            await set_price(symbol.split("USDT")[0], price, "binance")
            return price
        except ExchangeAPIError as e:
            print(f"Binance price error: {e}")
            return None

    async def get_multiple_ticker_prices(self, symbols: List[str]) -> Dict[str, Decimal]:
        """Get prices for multiple symbols."""
        prices = {}
        tasks = [self.get_ticker_price(f"{symbol}USDT") for symbol in symbols]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for symbol, result in zip(symbols, results):
                if isinstance(result, Decimal):
                    prices[symbol] = result
        except Exception as e:
            print(f"Multiple price error: {e}")

        return prices

    async def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100):
        """Get historical klines (candlestick data)."""
        try:
            url = f"{self.BASE_URL}/klines"
            params = {
                "symbol": symbol + "USDT",
                "interval": interval,
                "limit": limit
            }

            data = await self._request("GET", url, params=params)

            klines = []
            for k in data:
                klines.append({
                    "timestamp": datetime.fromtimestamp(k[0] / 1000),
                    "open": Decimal(k[1]),
                    "high": Decimal(k[2]),
                    "low": Decimal(k[3]),
                    "close": Decimal(k[4]),
                    "volume": Decimal(k[5]),
                })

            return klines
        except ExchangeAPIError as e:
            print(f"Binance klines error: {e}")
            return []

    async def get_orderbook(self, symbol: str, limit: int = 5):
        """Get order book."""
        try:
            url = f"{self.BASE_URL}/depth"
            params = {
                "symbol": symbol + "USDT",
                "limit": limit
            }

            data = await self._request("GET", url, params=params)

            return {
                "bids": [{"price": Decimal(b[0]), "quantity": Decimal(b[1])} for b in data["bids"]],
                "asks": [{"price": Decimal(a[0]), "quantity": Decimal(a[1])} for a in data["asks"]],
            }
        except ExchangeAPIError as e:
            print(f"Binance orderbook error: {e}")
            return {"bids": [], "asks": []}

    async def get_balance(self) -> Optional[Decimal]:
        """Get account balance (requires auth)."""
        if not self.api_key or not self.api_secret:
            print("Binance API key and secret required for balance")
            return None

        try:
            url = f"{self.BASE_URL}/account"
            headers = {
                "X-MBX-APIKEY": self.api_key
            }

            data = await self._request("GET", url, headers=headers)

            # Get USDT balance
            for asset in data["balances"]:
                if asset["asset"] == "USDT" and Decimal(asset["free"]) > 0:
                    return Decimal(asset["free"])

            return Decimal("0.00")
        except ExchangeAPIError as e:
            print(f"Binance balance error: {e}")
            return None

    async def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get detailed account information."""
        if not self.api_key or not self.api_secret:
            print("Binance API key and secret required")
            return None

        try:
            url = f"{self.BASE_URL}/account"
            headers = {
                "X-MBX-APIKEY": self.api_key
            }

            data = await self._request("GET", url, headers=headers)
            return data
        except ExchangeAPIError as e:
            print(f"Binance account error: {e}")
            return None


class CoinbaseClient(APIClient):
    """Coinbase API client."""

    BASE_URL = "https://api.coinbase.com/v2"

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """Initialize Coinbase client."""
        super().__init__(api_key, api_secret)

    async def get_spot_price(self, base_currency: str = "BTC", quote_currency: str = "USD") -> Optional[Decimal]:
        """Get spot price."""
        try:
            symbol = f"{base_currency}-{quote_currency}"
            url = f"{self.BASE_URL}/prices/{symbol}/spot"

            data = await self._request("GET", url)

            price = Decimal(data["data"]["amount"])
            await set_price(base_currency, price, "coinbase")
            return price
        except ExchangeAPIError as e:
            print(f"Coinbase price error: {e}")
            return None

    async def get_crypto_price(self, crypto_currency: str) -> Optional[Decimal]:
        """Get crypto price in USD."""
        return await self.get_spot_price(crypto_currency, "USD")

    async def get_crypto_prices(self, currencies: List[str]) -> Dict[str, Decimal]:
        """Get prices for multiple cryptocurrencies."""
        prices = {}
        tasks = [self.get_crypto_price(currency) for currency in currencies]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for currency, result in zip(currencies, results):
                if isinstance(result, Decimal):
                    prices[currency] = result
        except Exception as e:
            print(f"Multiple crypto price error: {e}")

        return prices

    async def get_account_balance(self) -> Optional[Decimal]:
        """Get account balance in USD."""
        if not self.api_key or not self.api_secret:
            print("Coinbase API key and secret required for balance")
            return None

        try:
            url = f"{self.BASE_URL}/wallet/balance"
            headers = {
                "CB-ACCESS-KEY": self.api_key,
                "CB-ACCESS-SIGN": self.api_secret,
                "CB-ACCESS-TIMESTAMP": str(int(time.time())),
            }

            data = await self._request("GET", url, headers=headers)

            total_balance = Decimal("0.00")
            for balance in data["data"]:
                total_balance += Decimal(balance["amount"])

            return total_balance
        except ExchangeAPIError as e:
            print(f"Coinbase balance error: {e}")
            return None


class PaperTradingClient:
    """Paper trading client for simulation."""

    def __init__(self, initial_capital: Decimal = Decimal("10000.00")):
        """Initialize paper trading client."""
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.open_trades: List[Dict[str, Any]] = []
        self.closed_trades: List[Dict[str, Any]] = []

    async def get_current_capital(self) -> Decimal:
        """Get current capital."""
        return self.capital

    async def open_position(
        self,
        symbol: str,
        action: str,
        quantity: Decimal,
        entry_price: Decimal,
        strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """Open a new position."""
        if action.lower() not in ["buy", "sell"]:
            raise ValueError("Action must be 'buy' or 'sell'")

        if symbol in self.positions and action.lower() == "buy":
            raise ValueError("Already have an open position for this symbol")

        position_value = quantity * entry_price

        if action.lower() == "buy" and position_value > self.capital:
            raise ValueError("Insufficient capital")

        position = {
            "id": len(self.positions) + 1,
            "symbol": symbol,
            "action": action.lower(),
            "quantity": quantity,
            "entry_price": entry_price,
            "current_price": entry_price,
            "strategy": strategy,
            "entry_time": datetime.now(timezone.utc),
        }

        if action.lower() == "buy":
            self.capital -= position_value
        else:
            # Short position (simplified)
            self.capital += position_value

        self.positions[symbol] = position
        self.open_trades.append(position)

        return position

    async def update_positions(self, current_prices: Dict[str, Decimal]):
        """Update current prices of open positions."""
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                position["current_price"] = current_prices[symbol]

    async def close_position(self, symbol: str, exit_price: Decimal) -> Dict[str, Any]:
        """Close an open position."""
        if symbol not in self.positions:
            raise ValueError(f"No open position for {symbol}")

        position = self.positions[symbol]
        exit_value = position["quantity"] * exit_price

        # Calculate P&L
        if position["action"] == "buy":
            pnl = exit_value - (position["quantity"] * position["entry_price"])
        else:
            pnl = (position["quantity"] * position["entry_price"]) - exit_value

        position["exit_price"] = exit_price
        position["exit_time"] = datetime.now(timezone.utc)
        position["pnl"] = pnl

        self.capital += exit_value
        self.closed_trades.append(position)

        del self.positions[symbol]

        return position

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        return list(self.positions.values())

    async def get_closed_trades(self) -> List[Dict[str, Any]]:
        """Get all closed trades."""
        return self.closed_trades

    async def get_portfolio_value(self, current_prices: Dict[str, Decimal]) -> Decimal:
        """Get total portfolio value."""
        # Add current capital to value of all positions
        portfolio_value = self.capital

        for symbol, position in self.positions.items():
            if symbol in current_prices:
                portfolio_value += position["quantity"] * current_prices[symbol]

        return portfolio_value

    async def get_total_pnl(self) -> Decimal:
        """Get total P&L from closed trades."""
        total_pnl = Decimal("0.00")
        for trade in self.closed_trades:
            if trade.get("pnl"):
                total_pnl += trade["pnl"]
        return total_pnl


# Global API clients
binance_client = None
coinbase_client = None


async def get_binance_client() -> BinanceClient:
    """Get Binance API client."""
    global binance_client
    if binance_client is None:
        binance_client = BinanceClient(
            api_key=settings.binance_api_key,
            api_secret=settings.binance_api_secret
        )
    return binance_client


async def get_coinbase_client() -> CoinbaseClient:
    """Get Coinbase API client."""
    global coinbase_client
    if coinbase_client is None:
        coinbase_client = CoinbaseClient(
            api_key=settings.coinbase_api_key,
            api_secret=settings.coinbase_api_secret
        )
    return coinbase_client


# Market data service
async def fetch_market_data(symbols: List[str]) -> Dict[str, Decimal]:
    """Fetch market data for multiple symbols."""
    prices = {}

    # Try Redis cache first
    cache = get_redis_manager()
    for symbol in symbols:
        cached = await cache.get_price_cache(symbol, "binance")
        if cached:
            prices[symbol] = Decimal(cached["price"])
            continue

        # Fetch from Binance
        try:
            client = await get_binance_client()
            price = await client.get_ticker_price(f"{symbol}USDT")
            if price:
                prices[symbol] = price
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")

    return prices
