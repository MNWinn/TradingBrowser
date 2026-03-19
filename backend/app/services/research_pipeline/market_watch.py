"""
Market Watch System for TradingBrowser.

Provides 24/7 market monitoring with:
- Price movement alerts
- Volume spike detection
- News event triggers
- Market open/close scheduling
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

import httpx
import redis.asyncio as redis

from app.core.config import settings
from app.services.market_data import get_quote_snapshot, get_bars_snapshot, configured_live_data

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    """Types of market alerts."""
    PRICE_CHANGE = "price_change"
    PRICE_THRESHOLD = "price_threshold"
    VOLUME_SPIKE = "volume_spike"
    NEWS_EVENT = "news_event"
    MARKET_OPEN = "market_open"
    MARKET_CLOSE = "market_close"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PriceAlert:
    """Price-based alert configuration."""
    ticker: str
    alert_type: AlertType
    threshold: float
    condition: str  # "above", "below", "change_pct_above", "change_pct_below"
    severity: AlertSeverity = AlertSeverity.MEDIUM
    triggered: bool = False
    last_triggered: Optional[datetime] = None
    cooldown_minutes: int = 15
    
    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "alert_type": self.alert_type.value,
            "threshold": self.threshold,
            "condition": self.condition,
            "severity": self.severity.value,
            "triggered": self.triggered,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "cooldown_minutes": self.cooldown_minutes,
        }


@dataclass
class VolumeAlert:
    """Volume-based alert configuration."""
    ticker: str
    multiplier: float  # e.g., 2.0 for 2x average volume
    lookback_periods: int = 20
    severity: AlertSeverity = AlertSeverity.MEDIUM
    triggered: bool = False
    last_triggered: Optional[datetime] = None
    cooldown_minutes: int = 30
    
    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "multiplier": self.multiplier,
            "lookback_periods": self.lookback_periods,
            "severity": self.severity.value,
            "triggered": self.triggered,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "cooldown_minutes": self.cooldown_minutes,
        }


@dataclass
class MarketAlert:
    """Represents a triggered market alert."""
    alert_id: str
    ticker: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    data: dict
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    
    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "ticker": self.ticker,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
        }


class MarketWatch:
    """
    24/7 Market Watch System.
    
    Monitors market data continuously and triggers alerts for:
    - Price movements beyond thresholds
    - Volume spikes
    - News events
    - Market open/close times
    """
    
    # Redis key prefixes
    ALERT_CONFIG_KEY = "marketwatch:alert:{ticker}:{alert_type}"
    ALERT_HISTORY_KEY = "marketwatch:alerts:history"
    PRICE_CACHE_KEY = "marketwatch:price_cache:{ticker}"
    VOLUME_CACHE_KEY = "marketwatch:volume_cache:{ticker}"
    WATCHLIST_KEY = "marketwatch:watchlist"
    
    # Market hours (US Eastern Time)
    MARKET_OPEN_TIME = time(9, 30)
    MARKET_CLOSE_TIME = time(16, 0)
    PRE_MARKET_OPEN = time(4, 0)
    AFTER_HOURS_CLOSE = time(20, 0)
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        self._redis: Optional[redis.Redis] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._monitor_task: Optional[asyncio.Task] = None
        self._market_hours_task: Optional[asyncio.Task] = None
        self._subscribers: list[Callable[[MarketAlert], Coroutine]] = []
        self._price_alerts: dict[str, PriceAlert] = {}
        self._volume_alerts: dict[str, VolumeAlert] = {}
        self._watchlist: set[str] = set()
        self._price_history: dict[str, list[dict]] = {}
        self._volume_history: dict[str, list[int]] = {}
        
    @property
    def redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    async def initialize(self) -> None:
        """Initialize the market watch system."""
        await self.redis.ping()
        self._running = True
        
        # Load saved alerts and watchlist
        await self._load_configuration()
        
        # Start monitoring tasks
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        self._market_hours_task = asyncio.create_task(self._market_hours_loop())
        
        logger.info(f"MarketWatch initialized with {len(self._watchlist)} tickers on watchlist")
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the market watch."""
        self._running = False
        self._shutdown_event.set()
        
        for task in [self._monitor_task, self._market_hours_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Save configuration
        await self._save_configuration()
        
        logger.info("MarketWatch shutdown complete")
    
    async def add_to_watchlist(self, ticker: str) -> None:
        """Add a ticker to the watchlist."""
        ticker = ticker.upper()
        self._watchlist.add(ticker)
        await self.redis.sadd(self.WATCHLIST_KEY, ticker)
        logger.info(f"Added {ticker} to watchlist")
    
    async def remove_from_watchlist(self, ticker: str) -> None:
        """Remove a ticker from the watchlist."""
        ticker = ticker.upper()
        self._watchlist.discard(ticker)
        await self.redis.srem(self.WATCHLIST_KEY, ticker)
        logger.info(f"Removed {ticker} from watchlist")
    
    async def get_watchlist(self) -> list[str]:
        """Get the current watchlist."""
        return list(self._watchlist)
    
    async def add_price_alert(
        self,
        ticker: str,
        alert_type: AlertType,
        threshold: float,
        condition: str,
        severity: AlertSeverity = AlertSeverity.MEDIUM,
        cooldown_minutes: int = 15,
    ) -> PriceAlert:
        """
        Add a price-based alert.
        
        Args:
            ticker: Stock ticker symbol
            alert_type: Type of price alert
            threshold: Price threshold value
            condition: "above", "below", "change_pct_above", "change_pct_below"
            severity: Alert severity level
            cooldown_minutes: Minutes between repeat alerts
        """
        ticker = ticker.upper()
        alert = PriceAlert(
            ticker=ticker,
            alert_type=alert_type,
            threshold=threshold,
            condition=condition,
            severity=severity,
            cooldown_minutes=cooldown_minutes,
        )
        
        key = f"{ticker}:{alert_type.value}"
        self._price_alerts[key] = alert
        
        await self.redis.setex(
            self.ALERT_CONFIG_KEY.format(ticker=ticker, alert_type=alert_type.value),
            86400 * 30,  # 30 day TTL
            json.dumps(alert.to_dict())
        )
        
        logger.info(f"Added price alert for {ticker}: {condition} {threshold}")
        return alert
    
    async def add_volume_alert(
        self,
        ticker: str,
        multiplier: float = 2.0,
        lookback_periods: int = 20,
        severity: AlertSeverity = AlertSeverity.MEDIUM,
        cooldown_minutes: int = 30,
    ) -> VolumeAlert:
        """
        Add a volume spike alert.
        
        Args:
            ticker: Stock ticker symbol
            multiplier: Volume multiplier threshold (e.g., 2.0 for 2x average)
            lookback_periods: Number of periods for volume average
            severity: Alert severity level
            cooldown_minutes: Minutes between repeat alerts
        """
        ticker = ticker.upper()
        alert = VolumeAlert(
            ticker=ticker,
            multiplier=multiplier,
            lookback_periods=lookback_periods,
            severity=severity,
            cooldown_minutes=cooldown_minutes,
        )
        
        key = f"{ticker}:volume"
        self._volume_alerts[key] = alert
        
        await self.redis.setex(
            self.ALERT_CONFIG_KEY.format(ticker=ticker, alert_type="volume"),
            86400 * 30,
            json.dumps(alert.to_dict())
        )
        
        logger.info(f"Added volume alert for {ticker}: {multiplier}x average")
        return alert
    
    async def remove_alert(self, ticker: str, alert_type: str) -> bool:
        """Remove an alert."""
        ticker = ticker.upper()
        key = f"{ticker}:{alert_type}"
        
        if key in self._price_alerts:
            del self._price_alerts[key]
        elif key in self._volume_alerts:
            del self._volume_alerts[key]
        else:
            return False
        
        await self.redis.delete(
            self.ALERT_CONFIG_KEY.format(ticker=ticker, alert_type=alert_type)
        )
        
        logger.info(f"Removed {alert_type} alert for {ticker}")
        return True
    
    async def subscribe(self, callback: Callable[[MarketAlert], Coroutine]) -> None:
        """Subscribe to market alerts."""
        self._subscribers.append(callback)
    
    async def unsubscribe(self, callback: Callable[[MarketAlert], Coroutine]) -> None:
        """Unsubscribe from market alerts."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    async def get_active_alerts(self) -> dict:
        """Get all active alert configurations."""
        return {
            "price_alerts": {k: v.to_dict() for k, v in self._price_alerts.items()},
            "volume_alerts": {k: v.to_dict() for k, v in self._volume_alerts.items()},
        }
    
    async def get_alert_history(
        self,
        ticker: Optional[str] = None,
        alert_type: Optional[AlertType] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get historical alerts."""
        alerts = await self.redis.lrange(self.ALERT_HISTORY_KEY, 0, limit - 1)
        result = []
        
        for alert_json in alerts:
            alert = json.loads(alert_json)
            if ticker and alert["ticker"] != ticker.upper():
                continue
            if alert_type and alert["alert_type"] != alert_type.value:
                continue
            result.append(alert)
        
        return result
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop for price and volume alerts."""
        while self._running:
            try:
                await self._check_price_alerts()
                await self._check_volume_alerts()
                
                # Wait before next check
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=30  # Check every 30 seconds
                )
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.exception(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _check_price_alerts(self) -> None:
        """Check all price alerts."""
        for key, alert in self._price_alerts.items():
            try:
                # Check cooldown
                if alert.last_triggered:
                    minutes_since = (datetime.now(timezone.utc) - alert.last_triggered).total_seconds() / 60
                    if minutes_since < alert.cooldown_minutes:
                        continue
                
                # Get current price
                quote = get_quote_snapshot(alert.ticker)
                current_price = quote.get("price", 0)
                change_pct = quote.get("change_pct", 0)
                
                # Get previous price for change calculation
                prev_price_data = await self.redis.get(self.PRICE_CACHE_KEY.format(ticker=alert.ticker))
                prev_price = json.loads(prev_price_data)["price"] if prev_price_data else current_price
                
                # Check condition
                triggered = False
                if alert.condition == "above" and current_price > alert.threshold:
                    triggered = True
                    message = f"{alert.ticker} price ${current_price:.2f} above threshold ${alert.threshold:.2f}"
                elif alert.condition == "below" and current_price < alert.threshold:
                    triggered = True
                    message = f"{alert.ticker} price ${current_price:.2f} below threshold ${alert.threshold:.2f}"
                elif alert.condition == "change_pct_above" and change_pct > alert.threshold:
                    triggered = True
                    message = f"{alert.ticker} up {change_pct:.2f}% (threshold: {alert.threshold:.2f}%)"
                elif alert.condition == "change_pct_below" and change_pct < alert.threshold:
                    triggered = True
                    message = f"{alert.ticker} down {abs(change_pct):.2f}% (threshold: {alert.threshold:.2f}%)"
                
                if triggered:
                    await self._trigger_alert(
                        ticker=alert.ticker,
                        alert_type=alert.alert_type,
                        severity=alert.severity,
                        message=message,
                        data={
                            "price": current_price,
                            "change_pct": change_pct,
                            "previous_price": prev_price,
                            "threshold": alert.threshold,
                            "condition": alert.condition,
                        }
                    )
                    alert.last_triggered = datetime.now(timezone.utc)
                
                # Update price cache
                await self.redis.setex(
                    self.PRICE_CACHE_KEY.format(ticker=alert.ticker),
                    3600,
                    json.dumps({"price": current_price, "timestamp": datetime.now(timezone.utc).isoformat()})
                )
                
            except Exception as e:
                logger.error(f"Error checking price alert for {alert.ticker}: {e}")
    
    async def _check_volume_alerts(self) -> None:
        """Check all volume alerts."""
        for key, alert in self._volume_alerts.items():
            try:
                # Check cooldown
                if alert.last_triggered:
                    minutes_since = (datetime.now(timezone.utc) - alert.last_triggered).total_seconds() / 60
                    if minutes_since < alert.cooldown_minutes:
                        continue
                
                # Get current volume
                quote = get_quote_snapshot(alert.ticker)
                current_volume = quote.get("volume", 0)
                
                # Get volume history
                volume_key = self.VOLUME_CACHE_KEY.format(ticker=alert.ticker)
                volume_history_json = await self.redis.get(volume_key)
                volume_history = json.loads(volume_history_json) if volume_history_json else []
                
                # Add current volume
                volume_history.append({
                    "volume": current_volume,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                
                # Keep only lookback periods
                volume_history = volume_history[-alert.lookback_periods:]
                
                # Calculate average
                if len(volume_history) >= alert.lookback_periods // 2:
                    volumes = [v["volume"] for v in volume_history[:-1]]  # Exclude current
                    avg_volume = sum(volumes) / len(volumes) if volumes else 1
                    
                    if avg_volume > 0 and current_volume > avg_volume * alert.multiplier:
                        await self._trigger_alert(
                            ticker=alert.ticker,
                            alert_type=AlertType.VOLUME_SPIKE,
                            severity=alert.severity,
                            message=f"{alert.ticker} volume spike: {current_volume:,} ({current_volume/avg_volume:.1f}x average)",
                            data={
                                "current_volume": current_volume,
                                "average_volume": avg_volume,
                                "multiplier": current_volume / avg_volume,
                                "threshold_multiplier": alert.multiplier,
                            }
                        )
                        alert.last_triggered = datetime.now(timezone.utc)
                
                # Update volume cache
                await self.redis.setex(volume_key, 86400, json.dumps(volume_history))
                
            except Exception as e:
                logger.error(f"Error checking volume alert for {alert.ticker}: {e}")
    
    async def _market_hours_loop(self) -> None:
        """Monitor market hours and trigger open/close alerts."""
        market_open_sent = False
        market_close_sent = False
        
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                
                # Convert to Eastern Time (simplified - assumes ET)
                # In production, use proper timezone handling
                et_hour = (now.hour - 5) % 24  # EST is UTC-5
                et_minute = now.minute
                
                # Market open (9:30 AM ET)
                if et_hour == 9 and et_minute == 30 and not market_open_sent:
                    await self._trigger_alert(
                        ticker="MARKET",
                        alert_type=AlertType.MARKET_OPEN,
                        severity=AlertSeverity.MEDIUM,
                        message="US Equity Markets Open",
                        data={"time": "09:30 ET", "exchanges": ["NYSE", "NASDAQ"]}
                    )
                    market_open_sent = True
                    market_close_sent = False
                
                # Market close (4:00 PM ET)
                elif et_hour == 16 and et_minute == 0 and not market_close_sent:
                    await self._trigger_alert(
                        ticker="MARKET",
                        alert_type=AlertType.MARKET_CLOSE,
                        severity=AlertSeverity.MEDIUM,
                        message="US Equity Markets Close",
                        data={"time": "16:00 ET", "exchanges": ["NYSE", "NASDAQ"]}
                    )
                    market_close_sent = True
                    market_open_sent = False
                
                # Reset flags after hours
                if et_hour == 17:  # 5 PM ET
                    market_open_sent = False
                    market_close_sent = False
                
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=60  # Check every minute
                )
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in market hours loop: {e}")
                await asyncio.sleep(60)
    
    async def _trigger_alert(
        self,
        ticker: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        data: dict,
    ) -> None:
        """Trigger a market alert."""
        import uuid
        
        alert = MarketAlert(
            alert_id=f"alert-{uuid.uuid4().hex[:12]}",
            ticker=ticker,
            alert_type=alert_type,
            severity=severity,
            message=message,
            data=data,
        )
        
        # Save to history
        await self.redis.lpush(self.ALERT_HISTORY_KEY, json.dumps(alert.to_dict()))
        await self.redis.ltrim(self.ALERT_HISTORY_KEY, 0, 999)  # Keep last 1000
        
        # Publish to Redis
        await self.redis.publish("marketwatch:alerts", json.dumps(alert.to_dict()))
        
        # Notify subscribers
        for callback in self._subscribers:
            try:
                await callback(alert)
            except Exception as e:
                logger.error(f"Error notifying alert subscriber: {e}")
        
        logger.info(f"Market alert triggered: {message}")
    
    async def _load_configuration(self) -> None:
        """Load saved configuration from Redis."""
        # Load watchlist
        watchlist = await self.redis.smembers(self.WATCHLIST_KEY)
        self._watchlist = set(watchlist) if watchlist else set()
        
        # Load price alerts
        pattern = self.ALERT_CONFIG_KEY.format(ticker="*", alert_type="*")
        keys = await self.redis.keys(pattern.replace("{ticker}", "*").replace("{alert_type}", "*"))
        
        for key in keys:
            try:
                data = await self.redis.get(key)
                if data:
                    config = json.loads(data)
                    ticker = config["ticker"]
                    alert_type = config["alert_type"]
                    
                    if alert_type == "volume":
                        alert = VolumeAlert(
                            ticker=ticker,
                            multiplier=config["multiplier"],
                            lookback_periods=config.get("lookback_periods", 20),
                            severity=AlertSeverity(config.get("severity", "medium")),
                            cooldown_minutes=config.get("cooldown_minutes", 30),
                        )
                        self._volume_alerts[f"{ticker}:volume"] = alert
                    else:
                        alert = PriceAlert(
                            ticker=ticker,
                            alert_type=AlertType(alert_type),
                            threshold=config["threshold"],
                            condition=config["condition"],
                            severity=AlertSeverity(config.get("severity", "medium")),
                            cooldown_minutes=config.get("cooldown_minutes", 15),
                        )
                        self._price_alerts[f"{ticker}:{alert_type}"] = alert
            except Exception as e:
                logger.error(f"Error loading alert config from {key}: {e}")
    
    async def _save_configuration(self) -> None:
        """Save configuration to Redis."""
        # Watchlist is already saved on add/remove
        # Alerts are already saved on add/remove
        pass


# Global market watch instance
_market_watch: Optional[MarketWatch] = None


async def get_market_watch() -> MarketWatch:
    """Get or create the global market watch."""
    global _market_watch
    if _market_watch is None:
        _market_watch = MarketWatch()
        await _market_watch.initialize()
    return _market_watch


async def shutdown_market_watch() -> None:
    """Shutdown the global market watch."""
    global _market_watch
    if _market_watch:
        await _market_watch.shutdown()
        _market_watch = None
