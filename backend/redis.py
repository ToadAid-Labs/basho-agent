"""
Redis module for caching and session management.

This module provides:
- Redis connection management
- Session storage
- Cache utilities
"""

import json
import asyncio
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.config import settings
from backend.database import get_db_manager


class RedisManager:
    """Manager for Redis operations."""

    def __init__(self):
        """Initialize Redis manager."""
        self._redis = None
        self._initialized = False

    def initialize(self):
        """Initialize Redis connection."""
        if self._initialized:
            return

        try:
            import redis
            self._redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
            self._initialized = True
        except Exception as e:
            print(f"Redis initialization error: {e}")
            print("Redis will be unavailable - operations will use database only")
            self._initialized = False

    def get_redis(self):
        """Get Redis client instance."""
        if not self._initialized:
            self.initialize()
        return self._redis

    def is_available(self) -> bool:
        """Check if Redis is available."""
        try:
            return self._initialized and self._redis is not None
        except:
            return False

    async def get(self, key: str) -> Optional[str]:
        """Get value from Redis."""
        try:
            redis_client = self.get_redis()
            if not redis_client:
                return None
            return redis_client.get(key)
        except Exception as e:
            print(f"Redis get error: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in Redis."""
        try:
            redis_client = self.get_redis()
            if not redis_client:
                return

            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            if ttl:
                redis_client.setex(key, ttl, value)
            else:
                redis_client.set(key, value)
        except Exception as e:
            print(f"Redis set error: {e}")

    async def delete(self, key: str):
        """Delete key from Redis."""
        try:
            redis_client = self.get_redis()
            if not redis_client:
                return
            redis_client.delete(key)
        except Exception as e:
            print(f"Redis delete error: {e}")

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        try:
            redis_client = self.get_redis()
            if not redis_client:
                return False
            return bool(redis_client.exists(key))
        except Exception as e:
            print(f"Redis exists error: {e}")
            return False

    async def expire(self, key: str, ttl: int):
        """Set TTL for a key."""
        try:
            redis_client = self.get_redis()
            if not redis_client:
                return
            redis_client.expire(key, ttl)
        except Exception as e:
            print(f"Redis expire error: {e}")

    # Session methods
    async def create_session(self, session_id: str, data: Dict[str, Any], ttl: int = 3600):
        """Create a new session."""
        await self.set(f"session:{session_id}", data, ttl)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        value = await self.get(f"session:{session_id}")
        if value:
            return json.loads(value)
        return None

    async def update_session(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None):
        """Update session data."""
        ttl = ttl or await self.get_ttl(f"session:{session_id}")
        await self.set(f"session:{session_id}", data, ttl)

    async def delete_session(self, session_id: str):
        """Delete a session."""
        await self.delete(f"session:{session_id}")

    async def get_ttl(self, key: str) -> Optional[int]:
        """Get time-to-live for a key."""
        try:
            redis_client = self.get_redis()
            if not redis_client:
                return None
            return redis_client.ttl(key)
        except Exception as e:
            print(f"Redis TTL error: {e}")
            return None

    # Cache methods
    async def cache_get(self, key: str) -> Optional[Any]:
        """Get from cache."""
        return await self.get(key)

    async def cache_set(self, key: str, value: Any, ttl: int = 3600):
        """Set in cache."""
        await self.set(key, value, ttl)

    async def cache_delete(self, key: str):
        """Delete from cache."""
        await self.delete(key)

    # Specialized methods
    async def set_price_cache(self, symbol: str, price: Decimal, data_source: str, ttl: int = 60):
        """Cache price data."""
        key = f"price:{symbol}:{data_source}"
        await self.set(key, {"price": str(price), "timestamp": datetime.now(timezone.utc).isoformat()}, ttl)

    async def get_price_cache(self, symbol: str, data_source: str) -> Optional[Dict[str, Any]]:
        """Get cached price data."""
        key = f"price:{symbol}:{data_source}"
        return await self.get(key)

    async def set_trend_cache(self, symbol: str, trend_data: Dict[str, Any], ttl: int = 3600):
        """Cache trend data."""
        key = f"trend:{symbol}"
        await self.set(key, trend_data, ttl)

    async def get_trend_cache(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached trend data."""
        key = f"trend:{symbol}"
        return await self.get(key)

    async def set_active_agents(self, user_id: int, agent_ids: List[int]):
        """Cache active agent IDs for a user."""
        key = f"active_agents:{user_id}"
        await self.set(key, agent_ids, ttl=86400)  # 24 hours

    async def get_active_agents(self, user_id: int) -> Optional[List[int]]:
        """Get cached active agent IDs for a user."""
        key = f"active_agents:{user_id}"
        return await self.get(key)

    async def invalidate_user_cache(self, user_id: int):
        """Invalidate all user-related cache."""
        pattern = f"user:*:{user_id}"
        try:
            redis_client = self.get_redis()
            if not redis_client:
                return

            # In production, you'd want a more specific pattern matching
            # For now, we'll just delete the active_agents cache
            await self.delete(f"active_agents:{user_id}")
        except Exception as e:
            print(f"Cache invalidation error: {e}")


# Global redis manager instance
_redis_manager = None


def get_redis_manager() -> RedisManager:
    """Get global Redis manager instance."""
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = RedisManager()
    return _redis_manager


# Async version
async def get_async_redis() -> Optional[RedisManager]:
    """Get Redis manager (async wrapper)."""
    return get_redis_manager() if get_redis_manager().is_available() else None


# Helper functions
async def get_price(symbol: str, data_source: str = "binance") -> Optional[Decimal]:
    """Get current price with cache."""
    cache = get_redis_manager()
    cached = await cache.get_price_cache(symbol, data_source)
    if cached:
        return Decimal(cached["price"])

    # If cache miss, fetch from database
    db = get_db_manager()
    session = db.get_session()
    try:
        from sqlalchemy import desc
        record = session.query(MarketDataRecord).filter(
            MarketDataRecord.symbol == symbol,
            MarketDataRecord.data_source == data_source
        ).order_by(desc(MarketDataRecord.timestamp)).first()

        if record:
            price = Decimal(record.price)
            # Update cache
            await cache.set_price_cache(symbol, price, data_source, ttl=60)
            return price
    finally:
        session.close()

    return None


async def set_price(symbol: str, price: Decimal, data_source: str = "binance"):
    """Set price in database and cache."""
    db = get_db_manager()
    session = db.get_session()
    try:
        from sqlalchemy import or_
        record = session.query(MarketDataRecord).filter(
            MarketDataRecord.symbol == symbol,
            MarketDataRecord.data_source == data_source
        ).first()

        if record:
            record.price = price
            record.timestamp = datetime.now(timezone.utc)
        else:
            record = MarketDataRecord(
                symbol=symbol,
                price=price,
                data_source=data_source,
                timestamp=datetime.now(timezone.utc),
            )
            session.add(record)

        session.commit()

        # Update cache
        cache = get_redis_manager()
        await cache.set_price_cache(symbol, price, data_source, ttl=60)
    finally:
        session.close()
