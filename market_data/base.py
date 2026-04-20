"""
Base classes for market data sources.

This module defines the abstract interfaces and base implementations
for all market data sources.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
import json


class DataSourceType(Enum):
    """Type of data source."""
    DEX = "dex"
    CEX = "cex"
    ONCHAIN = "onchain"
    SENTIMENT = "sentiment"
    TECHNICAL = "technical"


class MarketDataError(Exception):
    """Base exception for market data errors."""
    def __init__(self, message: str, source: Optional[str] = None):
        self.source = source
        super().__init__(f"{message} (from {source})" if source else message)


class MarketData(ABC):
    """Base class for all market data."""

    @property
    @abstractmethod
    def timestamp(self) -> datetime:
        """Timestamp of when data was retrieved."""
        pass

    @property
    @abstractmethod
    def data_source(self) -> str:
        """Name of the data source."""
        pass

    @property
    @abstractmethod
    def source_type(self) -> DataSourceType:
        """Type of data source."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'data_source': self.data_source,
            'source_type': self.source_type.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create from dictionary."""
        raise NotImplementedError()


class PriceData(MarketData):
    """Price data from market sources."""

    def __init__(
        self,
        token_address: str,
        token_symbol: str,
        price: float,
        timestamp: datetime,
        data_source: str,
        source_type: DataSourceType,
        ohlc: Optional[Dict[str, float]] = None,
        high: Optional[float] = None,
        low: Optional[float] = None,
        close: Optional[float] = None,
        volume: Optional[float] = None,
        trades: Optional[int] = None
    ):
        self._timestamp = timestamp
        self._data_source = data_source
        self._source_type = source_type

        self.token_address = token_address
        self.token_symbol = token_symbol
        self.price = price
        self.ohlc = ohlc or {}
        self.high = high
        self.low = low
        self.volume = volume
        self.trades = trades

    @property
    def timestamp(self) -> datetime:
        return self._timestamp

    @property
    def data_source(self) -> str:
        return self._data_source

    @property
    def source_type(self) -> DataSourceType:
        return self._source_type

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'token_address': self.token_address,
            'token_symbol': self.token_symbol,
            'price': self.price,
            'ohlc': self.ohlc,
            'high': self.high,
            'low': self.low,
            'volume': self.volume,
            'trades': self.trades
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(
            token_address=data['token_address'],
            token_symbol=data['token_symbol'],
            price=data['price'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            data_source=data['data_source'],
            source_type=DataSourceType(data['source_type']),
            ohlc=data.get('ohlc'),
            high=data.get('high'),
            low=data.get('low'),
            volume=data.get('volume'),
            trades=data.get('trades')
        )


class VolumeData(MarketData):
    """Volume data from market sources."""

    def __init__(
        self,
        token_address: str,
        token_symbol: str,
        volume_24h: float,
        timestamp: datetime,
        data_source: str,
        source_type: DataSourceType,
        volume_1h: Optional[float] = None,
        volume_4h: Optional[float] = None,
        volume_7d: Optional[float] = None,
        market_cap: Optional[float] = None,
        fdv: Optional[float] = None
    ):
        self._timestamp = timestamp
        self._data_source = data_source
        self._source_type = source_type

        self.token_address = token_address
        self.token_symbol = token_symbol
        self.volume_24h = volume_24h
        self.volume_1h = volume_1h
        self.volume_4h = volume_4h
        self.volume_7d = volume_7d
        self.market_cap = market_cap
        self.fdv = fdv

    @property
    def timestamp(self) -> datetime:
        return self._timestamp

    @property
    def data_source(self) -> str:
        return self._data_source

    @property
    def source_type(self) -> DataSourceType:
        return self._source_type

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'token_address': self.token_address,
            'token_symbol': self.token_symbol,
            'volume_24h': self.volume_24h,
            'volume_1h': self.volume_1h,
            'volume_4h': self.volume_4h,
            'volume_7d': self.volume_7d,
            'market_cap': self.market_cap,
            'fdv': self.fdv
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(
            token_address=data['token_address'],
            token_symbol=data['token_symbol'],
            volume_24h=data['volume_24h'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            data_source=data['data_source'],
            source_type=DataSourceType(data['source_type']),
            volume_1h=data.get('volume_1h'),
            volume_4h=data.get('volume_4h'),
            volume_7d=data.get('volume_7d'),
            market_cap=data.get('market_cap'),
            fdv=data.get('fdv')
        )


class TradeData(MarketData):
    """Trade execution data."""

    def __init__(
        self,
        trade_id: str,
        token_address: str,
        token_symbol: str,
        direction: str,
        amount: float,
        price: float,
        timestamp: datetime,
        data_source: str,
        source_type: DataSourceType,
        side: str = None,
        slippage: Optional[float] = None,
        protocol: Optional[str] = None
    ):
        self._timestamp = timestamp
        self._data_source = data_source
        self._source_type = source_type

        self.trade_id = trade_id
        self.token_address = token_address
        self.token_symbol = token_symbol
        self.direction = direction
        self.amount = amount
        self.price = price
        self.side = side or ('buy' if direction == 'buy' else 'sell')
        self.slippage = slippage
        self.protocol = protocol

    @property
    def timestamp(self) -> datetime:
        return self._timestamp

    @property
    def data_source(self) -> str:
        return self._data_source

    @property
    def source_type(self) -> DataSourceType:
        return self._source_type

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'trade_id': self.trade_id,
            'token_address': self.token_address,
            'token_symbol': self.token_symbol,
            'direction': self.direction,
            'amount': self.amount,
            'price': self.price,
            'side': self.side,
            'slippage': self.slippage,
            'protocol': self.protocol
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(
            trade_id=data['trade_id'],
            token_address=data['token_address'],
            token_symbol=data['token_symbol'],
            direction=data['direction'],
            amount=data['amount'],
            price=data['price'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            data_source=data['data_source'],
            source_type=DataSourceType(data['source_type']),
            side=data.get('side'),
            slippage=data.get('slippage'),
            protocol=data.get('protocol')
        )


class MarketDataSource(ABC):
    """Abstract base class for market data sources."""

    def __init__(self, name: str, api_key: Optional[str] = None):
        """
        Initialize data source.

        Args:
            name: Name of the data source
            api_key: Optional API key for authentication
        """
        self.name = name
        self.api_key = api_key
        self._last_data_time = None

    @abstractmethod
    async def get_price(
        self,
        token_address: str,
        token_symbol: Optional[str] = None
    ) -> PriceData:
        """Get current price for a token."""
        pass

    @abstractmethod
    async def get_prices(
        self,
        token_addresses: List[str]
    ) -> List[PriceData]:
        """Get prices for multiple tokens."""
        pass

    @abstractmethod
    async def get_volume(
        self,
        token_address: str,
        token_symbol: Optional[str] = None
    ) -> VolumeData:
        """Get 24h volume for a token."""
        pass

    @abstractmethod
    async def get_trades(
        self,
        token_address: str,
        limit: int = 100
    ) -> List[TradeData]:
        """Get recent trades for a token."""
        pass

    @property
    def last_data_time(self) -> Optional[datetime]:
        """When was data last fetched?"""
        return self._last_data_time

    async def update_last_data_time(self):
        """Update the last data fetch timestamp."""
        self._last_data_time = datetime.now()

    async def is_data_fresh(
        self,
        max_age: timedelta = timedelta(minutes=5)
    ) -> bool:
        """Check if data is fresh enough to use."""
        if self._last_data_time is None:
            return False
        return datetime.now() - self._last_data_time < max_age

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'api_key_provided': self.api_key is not None,
            'last_data_time': self._last_data_time.isoformat() if self._last_data_time else None
        }