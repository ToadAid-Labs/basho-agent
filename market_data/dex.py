"""
DEX Aggregator integrations.

This module provides integration with decentralized exchange aggregators:
- 1inch
- Jupiter (Solana DEX)
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from .base import (
    MarketDataSource,
    PriceData,
    VolumeData,
    TradeData,
    DataSourceType,
    MarketDataError
)
import aiohttp
import json


class DexTrade:
    """Represents a DEX trade."""

    def __init__(
        self,
        trade_id: str,
        token_in: str,
        token_out: str,
        amount_in: float,
        amount_out: float,
        price: float,
        timestamp: datetime,
        side: str,
        gas_price: Optional[float] = None,
        gas_used: Optional[float] = None,
        protocol: Optional[str] = None
    ):
        self.trade_id = trade_id
        self.token_in = token_in
        self.token_out = token_out
        self.amount_in = amount_in
        self.amount_out = amount_out
        self.price = price
        self.timestamp = timestamp
        self.side = side
        self.gas_price = gas_price
        self.gas_used = gas_used
        self.protocol = protocol

    def to_dict(self) -> Dict[str, Any]:
        return {
            'trade_id': self.trade_id,
            'token_in': self.token_in,
            'token_out': self.token_out,
            'amount_in': self.amount_in,
            'amount_out': self.amount_out,
            'price': self.price,
            'timestamp': self.timestamp.isoformat(),
            'side': self.side,
            'gas_price': self.gas_price,
            'gas_used': self.gas_used,
            'protocol': self.protocol
        }


class OneInch(MarketDataSource):
    """
    1inch DEX Aggregator integration.

    Provides access to aggregated DEX liquidity across multiple exchanges.
    """

    BASE_URL = "https://api.1inch.dev"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize 1inch API client.

        Args:
            api_key: 1inch API key (required for production)
        """
        super().__init__("1inch", api_key)
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

    async def get_price(
        self,
        token_address: str,
        token_symbol: Optional[str] = None,
        quote_currency: str = "ETH"
    ) -> PriceData:
        """
        Get best price for a token.

        Args:
            token_address: Token contract address
            token_symbol: Optional token symbol
            quote_currency: Quote currency (default: ETH)

        Returns:
            PriceData object
        """
        session = await self._get_session()

        headers = {}
        if self.api_key:
            headers["Authorization"] = self.api_key

        url = f"{self.BASE_URL}/v6.0/1/quote"
        params = {
            "src": token_address,
            "dst": self._get_quote_currency_address(quote_currency),
            "slippage": 0.5  # 0.5% slippage
        }

        try:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise MarketDataError(
                        f"1inch API error: {response.status}",
                        self.name
                    )

                data = await response.json()

                # Get best price from quote
                best_price = data.get("toTokenAmountWei", 0) / float(data.get("fromTokenAmountWei", 1))

                price_data = PriceData(
                    token_address=token_address,
                    token_symbol=token_symbol or self._get_symbol_from_address(token_address),
                    price=best_price,
                    timestamp=datetime.now(),
                    data_source=self.name,
                    source_type=DataSourceType.DEX,
                    volume=data.get("estimatedBasisPoints"),  # As approximation
                    trades=data.get("numberOfTransactions")
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
            token_address: Token contract address
            token_symbol: Optional token symbol

        Returns:
            VolumeData object
        """
        session = await self._get_session()

        headers = {}
        if self.api_key:
            headers["Authorization"] = self.api_key

        url = f"{self.BASE_URL}/v6.0/1/tokens/{token_address}"

        try:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"1inch API error: {response.status}",
                        self.name
                    )

                data = await response.json()

                volume = data.get("totalVolume", {}).get("quote", 0)

                volume_data = VolumeData(
                    token_address=token_address,
                    token_symbol=token_symbol or self._get_symbol_from_address(token_address),
                    volume_24h=volume,
                    volume_1h=0,
                    volume_4h=0,
                    volume_7d=0,
                    market_cap=0,
                    fdv=0,
                    timestamp=datetime.now(),
                    data_source=self.name,
                    source_type=DataSourceType.DEX
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
            token_address: Token contract address
            limit: Number of trades to retrieve

        Returns:
            List of TradeData objects
        """
        session = await self._get_session()

        headers = {}
        if self.api_key:
            headers["Authorization"] = self.api_key

        url = f"{self.BASE_URL}/v6.0/1/trades"

        try:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"1inch API error: {response.status}",
                        self.name
                    )

                data = await response.json()

                trades = []
                for trade in data.get("trades", [])[:limit]:
                    trade_data = DexTrade(
                        trade_id=trade.get("id", ""),
                        token_in=trade.get("tokenIn", ""),
                        token_out=trade.get("tokenOut", ""),
                        amount_in=float(trade.get("amountIn", 0)),
                        amount_out=float(trade.get("amountOut", 0)),
                        price=0,
                        timestamp=datetime.fromisoformat(trade.get("timestamp", "")),
                        side=trade.get("side", "buy"),
                        gas_price=float(trade.get("gasPrice", 0)) if trade.get("gasPrice") else None,
                        gas_used=float(trade.get("gasUsed", 0)) if trade.get("gasUsed") else None,
                        protocol=trade.get("protocol", "")
                    )
                    trades.append(TradeData(
                        trade_id=trade_data.trade_id,
                        token_address=trade_data.token_in,
                        token_symbol="",
                        direction=trade_data.side,
                        amount=trade_data.amount_in,
                        price=trade_data.price,
                        timestamp=trade_data.timestamp,
                        data_source=self.name,
                        source_type=DataSourceType.DEX,
                        side=trade_data.side,
                        protocol=trade_data.protocol
                    ))

                await self.update_last_data_time()
                return trades

        except aiohttp.ClientError as e:
            raise MarketDataError(f"Network error: {str(e)}", self.name)

    async def get_best_route(
        self,
        token_in: str,
        token_out: str,
        amount: float
    ) -> Dict[str, Any]:
        """
        Get best routing for a swap.

        Args:
            token_in: Input token address
            token_out: Output token address
            amount: Amount to swap

        Returns:
            Dictionary with route information
        """
        session = await self._get_session()

        headers = {}
        if self.api_key:
            headers["Authorization"] = self.api_key

        url = f"{self.BASE_URL}/v6.0/1/routes"
        params = {
            "src": token_in,
            "dst": token_out,
            "amount": str(amount),
            "slippage": 0.5
        }

        try:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"1inch API error: {response.status}",
                        self.name
                    )

                data = await response.json()
                await self.update_last_data_time()
                return data

        except aiohttp.ClientError as e:
            raise MarketDataError(f"Network error: {str(e)}", self.name)

    # Helper methods
    def _get_quote_currency_address(self, currency: str) -> str:
        """Get token address for quote currency."""
        currency_map = {
            "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
            "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F"
        }
        return currency_map.get(currency.upper(), "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE")

    def _get_symbol_from_address(self, address: str) -> str:
        """Get token symbol from address (mock implementation)."""
        return "TOKEN"


class Jupiter(MarketDataSource):
    """
    Jupiter DEX Aggregator integration.

    Jupiter is a DEX aggregator on Solana.
    """

    BASE_URL = "https://quote-api.jup.ag/v6"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Jupiter API client.

        Args:
            api_key: Jupiter API key (optional for public endpoints)
        """
        super().__init__("Jupiter", api_key)
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

    async def get_price(
        self,
        token_address: str,
        token_symbol: Optional[str] = None,
        quote_currency: str = "SOL"
    ) -> PriceData:
        """
        Get best price for a token on Solana.

        Args:
            token_address: Token address
            token_symbol: Optional token symbol
            quote_currency: Quote currency (default: SOL)

        Returns:
            PriceData object
        """
        session = await self._get_session()

        try:
            # Get tokens for quote currency
            quote_token = await self._get_quote_token_address(quote_currency)

            # Build swap request
            url = f"{self.BASE_URL}/quote"
            params = {
                "inputMint": token_address,
                "outputMint": quote_token,
                "amount": "1000000000",  # 1 unit minimum
                "slippageBps": 50
            }

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"Jupiter API error: {response.status}",
                        self.name
                    )

                data = await response.json()
                best_price = float(data.get("inAmount", 0)) / float(data.get("outAmount", 1))

                price_data = PriceData(
                    token_address=token_address,
                    token_symbol=token_symbol or "UNKNOWN",
                    price=best_price,
                    timestamp=datetime.now(),
                    data_source=self.name,
                    source_type=DataSourceType.DEX,
                    volume=data.get("marketPriceImpactPercentage"),
                    trades=data.get("numberOfRoutes")
                )

                await self.update_last_data_time()
                return price_data

        except aiohttp.ClientError as e:
            raise MarketDataError(f"Network error: {str(e)}", self.name)

    async def get_trades(
        self,
        token_address: str,
        limit: int = 100
    ) -> List[TradeData]:
        """
        Get recent trades for a token.

        Jupiter doesn't provide a direct trades endpoint,
        so this will be a placeholder.
        """
        # Placeholder implementation
        await self.update_last_data_time()
        return []

    async def get_quote_tokens(self) -> List[Dict[str, Any]]:
        """Get list of supported quote tokens."""
        session = await self._get_session()

        try:
            async with session.get(f"{self.BASE_URL}/tokens") as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"Jupiter API error: {response.status}",
                        self.name
                    )

                data = await response.json()
                return data.get("tokens", [])

        except aiohttp.ClientError as e:
            raise MarketDataError(f"Network error: {str(e)}", self.name)

    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    # Helper methods
    async def _get_quote_token_address(self, currency: str) -> str:
        """Get token address for quote currency."""
        tokens = await self.get_quote_tokens()
        for token in tokens:
            if token.get("symbol", "").upper() == currency.upper():
                return token.get("address", "")
        return "So11111111111111111111111111111111111111112"  # SOL address

    async def get_all_tokens(self) -> List[Dict[str, Any]]:
        """Get all supported tokens."""
        session = await self._get_session()

        try:
            async with session.get(f"{self.BASE_URL}/tokens") as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"Jupiter API error: {response.status}",
                        self.name
                    )

                data = await response.json()
                return data.get("tokens", [])

        except aiohttp.ClientError as e:
            raise MarketDataError(f"Network error: {str(e)}", self.name)

    async def get_swap(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50
    ) -> Dict[str, Any]:
        """
        Get swap quote.

        Args:
            input_mint: Input token address
            output_mint: Output token address
            amount: Amount to swap
            slippage_bps: Slippage tolerance in basis points

        Returns:
            Dictionary with swap information
        """
        session = await self._get_session()

        try:
            url = f"{self.BASE_URL}/quote"
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": slippage_bps
            }

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"Jupiter API error: {response.status}",
                        self.name
                    )

                data = await response.json()
                await self.update_last_data_time()
                return data

        except aiohttp.ClientError as e:
            raise MarketDataError(f"Network error: {str(e)}", self.name)