"""
MiroFish Cache - Redis-based caching layer for MiroFish assessments.

Provides:
- Redis-based caching with configurable TTL
- TTL management per ticker/timeframe
- Cache invalidation strategies
- Fallback to fresh data
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """Cache invalidation strategies."""
    TTL_ONLY = "ttl_only"                    # Only use TTL expiration
    MARKET_HOURS = "market_hours"            # Invalidate at market open/close
    VOLATILITY_BASED = "volatility_based"    # Shorter TTL for volatile tickers
    EVENT_DRIVEN = "event_driven"            # Invalidate on market events
    HYBRID = "hybrid"                        # Combine multiple strategies


@dataclass
class CacheConfig:
    """Configuration for cache behavior."""
    default_ttl_seconds: int = 300           # 5 minutes default
    short_ttl_seconds: int = 60              # 1 minute for volatile
    long_ttl_seconds: int = 1800             # 30 minutes for stable
    focus_ticker_ttl_seconds: int = 120      # 2 minutes for focus tickers
    enable_compression: bool = True
    max_key_length: int = 200
    namespace: str = "mirofish"
    
    # Strategy settings
    volatility_threshold: float = 0.02       # 2% move = volatile
    pre_market_ttl_multiplier: float = 0.5
    after_hours_ttl_multiplier: float = 2.0


@dataclass
class CacheEntry:
    """A cached MiroFish assessment entry."""
    data: dict[str, Any]
    cached_at: datetime
    expires_at: datetime
    ticker: str
    timeframe: str
    lens: str
    cache_key: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> dict:
        return {
            "data": self.data,
            "cached_at": self.cached_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "ticker": self.ticker,
            "timeframe": self.timeframe,
            "lens": self.lens,
            "cache_key": self.cache_key,
            "metadata": self.metadata,
        }


class MiroFishCache:
    """
    Redis-based caching layer for MiroFish assessments.
    
    Features:
    - Configurable TTL per ticker/timeframe combination
    - Multiple invalidation strategies
    - Automatic fallback to fresh data
    - Compression for large payloads
    - Cache warming and pre-fetching
    """

    _instance: MiroFishCache | None = None
    _redis: redis.Redis | None = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: CacheConfig | None = None):
        if hasattr(self, '_initialized'):
            return
        
        self.config = config or CacheConfig()
        self._initialized = True
        self._local_cache: dict[str, CacheEntry] = {}  # In-memory fallback
        self._stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "fallbacks": 0,
        }

    async def _get_redis(self) -> redis.Redis | None:
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                return None
        return self._redis

    def _generate_key(
        self,
        ticker: str,
        timeframe: str,
        lens: str,
        extra_params: dict | None = None,
    ) -> str:
        """Generate a cache key for the given parameters."""
        key_parts = [
            self.config.namespace,
            ticker.upper(),
            timeframe,
            lens,
        ]
        
        if extra_params:
            param_str = json.dumps(extra_params, sort_keys=True)
            param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
            key_parts.append(param_hash)
        
        key = ":".join(key_parts)
        
        if len(key) > self.config.max_key_length:
            key_hash = hashlib.md5(key.encode()).hexdigest()[:16]
            key = f"{self.config.namespace}:{ticker.upper()}:{key_hash}"
        
        return key

    def _calculate_ttl(
        self,
        ticker: str,
        timeframe: str,
        is_focus: bool = False,
        volatility: float | None = None,
    ) -> int:
        """
        Calculate appropriate TTL based on context.
        
        Args:
            ticker: Stock symbol
            timeframe: Analysis timeframe
            is_focus: Whether this is a focus ticker
            volatility: Recent volatility (if known)
        """
        # Base TTL
        if is_focus:
            ttl = self.config.focus_ticker_ttl_seconds
        elif timeframe in ("1m", "5m"):
            ttl = self.config.short_ttl_seconds
        elif timeframe in ("1d", "1w"):
            ttl = self.config.long_ttl_seconds
        else:
            ttl = self.config.default_ttl_seconds

        # Adjust for volatility
        if volatility and volatility > self.config.volatility_threshold:
            ttl = int(ttl * 0.5)  # Shorter TTL for volatile tickers

        # Market hours adjustment (simplified - could integrate with market calendar)
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        # US market hours: 9:30 - 16:00 ET (approx 14:30 - 21:00 UTC)
        is_market_hours = 14 <= hour <= 21
        
        if not is_market_hours:
            ttl = int(ttl * self.config.after_hours_ttl_multiplier)

        return max(ttl, 30)  # Minimum 30 seconds

    async def get(
        self,
        ticker: str,
        timeframe: str,
        lens: str,
        extra_params: dict | None = None,
    ) -> CacheEntry | None:
        """
        Retrieve cached assessment if available and not expired.
        
        Returns None if not found or expired.
        """
        cache_key = self._generate_key(ticker, timeframe, lens, extra_params)
        
        # Try Redis first
        redis_client = await self._get_redis()
        if redis_client:
            try:
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    self._stats["hits"] += 1
                    data = json.loads(cached_data)
                    return CacheEntry(
                        data=data["data"],
                        cached_at=datetime.fromisoformat(data["cached_at"]),
                        expires_at=datetime.fromisoformat(data["expires_at"]),
                        ticker=data["ticker"],
                        timeframe=data["timeframe"],
                        lens=data["lens"],
                        cache_key=cache_key,
                        metadata=data.get("metadata", {}),
                    )
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
                self._stats["errors"] += 1

        # Fallback to local cache
        if cache_key in self._local_cache:
            entry = self._local_cache[cache_key]
            if not entry.is_expired():
                self._stats["hits"] += 1
                return entry
            else:
                del self._local_cache[cache_key]

        self._stats["misses"] += 1
        return None

    async def set(
        self,
        ticker: str,
        timeframe: str,
        lens: str,
        data: dict[str, Any],
        ttl_seconds: int | None = None,
        extra_params: dict | None = None,
        is_focus: bool = False,
        volatility: float | None = None,
        metadata: dict | None = None,
    ) -> bool:
        """
        Cache an assessment result.
        
        Returns True if successfully cached.
        """
        cache_key = self._generate_key(ticker, timeframe, lens, extra_params)
        
        if ttl_seconds is None:
            ttl_seconds = self._calculate_ttl(ticker, timeframe, is_focus, volatility)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        entry = CacheEntry(
            data=data,
            cached_at=now,
            expires_at=expires_at,
            ticker=ticker.upper(),
            timeframe=timeframe,
            lens=lens,
            cache_key=cache_key,
            metadata=metadata or {},
        )

        # Store in local cache
        self._local_cache[cache_key] = entry

        # Store in Redis
        redis_client = await self._get_redis()
        if redis_client:
            try:
                cache_data = {
                    "data": data,
                    "cached_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "ticker": ticker.upper(),
                    "timeframe": timeframe,
                    "lens": lens,
                    "metadata": metadata or {},
                }
                await redis_client.setex(
                    cache_key,
                    ttl_seconds,
                    json.dumps(cache_data, default=str),
                )
                return True
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
                self._stats["errors"] += 1

        return True  # Still cached locally

    async def get_or_fetch(
        self,
        ticker: str,
        timeframe: str,
        lens: str,
        fetch_func: Callable[[], dict[str, Any]],
        extra_params: dict | None = None,
        is_focus: bool = False,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        Get from cache or fetch fresh data.
        
        This is the main method for cached data retrieval.
        
        Args:
            ticker: Stock symbol
            timeframe: Analysis timeframe
            lens: Analysis lens
            fetch_func: Function to call if cache miss
            extra_params: Additional parameters for cache key
            is_focus: Whether this is a focus ticker
            force_refresh: Skip cache and fetch fresh
            
        Returns:
            Assessment data (from cache or fresh)
        """
        # Check cache unless forcing refresh
        if not force_refresh:
            cached = await self.get(ticker, timeframe, lens, extra_params)
            if cached:
                return {
                    **cached.data,
                    "_cache": {
                        "hit": True,
                        "cached_at": cached.cached_at.isoformat(),
                        "expires_at": cached.expires_at.isoformat(),
                    },
                }

        # Fetch fresh data
        try:
            fresh_data = await fetch_func()
            
            # Cache the result
            await self.set(
                ticker=ticker,
                timeframe=timeframe,
                lens=lens,
                data=fresh_data,
                extra_params=extra_params,
                is_focus=is_focus,
                metadata={"fetched_at": datetime.now(timezone.utc).isoformat()},
            )
            
            return {
                **fresh_data,
                "_cache": {
                    "hit": False,
                    "fresh": True,
                },
            }
        except Exception as e:
            logger.error(f"Fetch failed for {ticker}/{timeframe}/{lens}: {e}")
            self._stats["errors"] += 1
            
            # Try to return stale cache as fallback
            cached = await self.get(ticker, timeframe, lens, extra_params)
            if cached:
                self._stats["fallbacks"] += 1
                return {
                    **cached.data,
                    "_cache": {
                        "hit": True,
                        "stale": True,
                        "cached_at": cached.cached_at.isoformat(),
                    },
                    "_error": str(e),
                }
            
            raise

    async def invalidate(
        self,
        ticker: str | None = None,
        timeframe: str | None = None,
        lens: str | None = None,
    ) -> int:
        """
        Invalidate cached entries matching the criteria.
        
        Returns number of entries invalidated.
        """
        pattern = f"{self.config.namespace}:"
        
        if ticker:
            pattern += f"{ticker.upper()}:"
            if timeframe:
                pattern += f"{timeframe}:"
                if lens:
                    pattern += f"{lens}"
                    pattern += "*"
                else:
                    pattern += "*"
            else:
                pattern += "*"
        else:
            pattern += "*"

        count = 0

        # Clear local cache
        keys_to_remove = [
            k for k in self._local_cache.keys()
            if k.startswith(pattern.rstrip("*"))
        ]
        for key in keys_to_remove:
            del self._local_cache[key]
            count += 1

        # Clear Redis
        redis_client = await self._get_redis()
        if redis_client:
            try:
                cursor = 0
                while True:
                    cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
                    if keys:
                        await redis_client.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning(f"Redis invalidation failed: {e}")

        return count

    async def invalidate_ticker(self, ticker: str) -> int:
        """Invalidate all cached entries for a ticker."""
        return await self.invalidate(ticker=ticker)

    async def invalidate_timeframe(self, timeframe: str) -> int:
        """Invalidate all cached entries for a timeframe across all tickers."""
        count = 0
        
        # Local cache
        keys_to_remove = [
            k for k in self._local_cache.keys()
            if f":{timeframe}:" in k
        ]
        for key in keys_to_remove:
            del self._local_cache[key]
            count += 1

        # Redis - scan and delete
        redis_client = await self._get_redis()
        if redis_client:
            try:
                cursor = 0
                pattern = f"{self.config.namespace}:*:{timeframe}:*"
                while True:
                    cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
                    if keys:
                        await redis_client.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning(f"Redis timeframe invalidation failed: {e}")

        return count

    async def warm_cache(
        self,
        tickers: list[str],
        timeframes: list[str],
        lenses: list[str],
        fetch_func: Callable[[str, str, str], dict[str, Any]],
    ) -> dict:
        """
        Pre-warm cache with assessments for given tickers/timeframes/lenses.
        
        Returns dict with success/failure counts.
        """
        results = {"success": 0, "failed": 0, "errors": []}

        for ticker in tickers:
            for timeframe in timeframes:
                for lens in lenses:
                    try:
                        data = await fetch_func(ticker, timeframe, lens)
                        await self.set(ticker, timeframe, lens, data)
                        results["success"] += 1
                    except Exception as e:
                        results["failed"] += 1
                        results["errors"].append(f"{ticker}/{timeframe}/{lens}: {str(e)}")

        return results

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0

        redis_info = {}
        redis_client = await self._get_redis()
        if redis_client:
            try:
                info = await redis_client.info("memory")
                redis_info = {
                    "used_memory_human": info.get("used_memory_human", "unknown"),
                    "connected": True,
                }
            except Exception as e:
                redis_info = {"connected": False, "error": str(e)}

        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "errors": self._stats["errors"],
            "fallbacks": self._stats["fallbacks"],
            "hit_rate": round(hit_rate, 4),
            "local_cache_size": len(self._local_cache),
            "redis": redis_info,
        }

    async def clear_all(self) -> int:
        """Clear all cached entries."""
        count = len(self._local_cache)
        self._local_cache.clear()

        redis_client = await self._get_redis()
        if redis_client:
            try:
                pattern = f"{self.config.namespace}:*"
                cursor = 0
                while True:
                    cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
                    if keys:
                        await redis_client.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning(f"Redis clear failed: {e}")

        return count


# Convenience functions for external use
_cache: MiroFishCache | None = None


def get_cache() -> MiroFishCache:
    """Get or create the singleton cache instance."""
    global _cache
    if _cache is None:
        _cache = MiroFishCache()
    return _cache


async def cached_assessment(
    ticker: str,
    timeframe: str,
    lens: str,
    fetch_func: Callable[[], dict[str, Any]],
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Convenience function to get cached or fresh assessment.
    
    Usage:
        result = await cached_assessment(
            ticker="AAPL",
            timeframe="5m",
            lens="technical",
            fetch_func=lambda: mirofish_predict({...}),
        )
    """
    cache = get_cache()
    return await cache.get_or_fetch(
        ticker=ticker,
        timeframe=timeframe,
        lens=lens,
        fetch_func=fetch_func,
        force_refresh=force_refresh,
    )


async def invalidate_ticker_cache(ticker: str) -> int:
    """Invalidate all cache entries for a ticker."""
    cache = get_cache()
    return await cache.invalidate_ticker(ticker)


async def get_cache_stats() -> dict:
    """Get cache statistics."""
    cache = get_cache()
    return await cache.get_stats()
