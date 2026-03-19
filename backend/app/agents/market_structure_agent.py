"""
Market Structure Agent

Analyzes price action, volatility, trend, momentum, and volume.
Detects regime changes (trending, ranging, volatile).
Classifies market environments.

Outputs:
- Regime labels
- Technical state
- Structure confidence
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import numpy as np

from .base_agent import BaseAgent, AgentState
from .message_bus import MessageType, AgentMessage


class MarketRegime(Enum):
    """Market regime classifications."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"


@dataclass
class TechnicalState:
    """Current technical state of a market."""
    ticker: str
    timestamp: datetime
    
    # Price action
    current_price: float
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    
    # Trend metrics
    trend_direction: str  # up, down, sideways
    trend_strength: float  # 0.0 to 1.0
    trend_duration_bars: int
    
    # Volatility
    volatility_regime: str  # low, normal, high, extreme
    atr_14: float
    atr_percent: float
    bollinger_width: float
    
    # Momentum
    rsi_14: float
    macd_line: float
    macd_signal: float
    macd_histogram: float
    
    # Volume
    volume_regime: str  # low, normal, high, climactic
    volume_sma_ratio: float
    obv_trend: str  # rising, falling, neutral
    
    # Structure
    support_levels: List[float]
    resistance_levels: List[float]
    pivot_highs: List[Tuple[int, float]]  # (bars_ago, price)
    pivot_lows: List[Tuple[int, float]]
    
    # Regime
    regime: MarketRegime
    regime_confidence: float
    regime_stability: float  # How long regime has persisted
    
    # Overall
    structure_score: float  # -1.0 to 1.0 (bearish to bullish)
    structure_confidence: float


class MarketStructureAgent(BaseAgent):
    """
    Agent for analyzing market structure and detecting regime changes.
    """
    
    def __init__(self, message_bus=None, config=None):
        super().__init__("market_structure", message_bus, config)
        
        # Configuration
        self.lookback_periods = config.get("lookback_periods", 100) if config else 100
        self.regime_threshold = config.get("regime_threshold", 0.6) if config else 0.6
        
        # State cache
        self._technical_states: Dict[str, TechnicalState] = {}
        self._price_history: Dict[str, List[Dict]] = {}
        self._regime_history: Dict[str, List[Tuple[datetime, MarketRegime]]] = {}
        
        # Register handlers
        self.register_handler(MessageType.PRICE_ACTION_ALERT, self._handle_price_alert)
        
    async def on_start(self):
        """Start periodic analysis."""
        asyncio.create_task(self._analysis_loop())
        
    async def _analysis_loop(self):
        """Periodic market structure analysis."""
        while self._running and self.state.value == "RUNNING":
            try:
                for ticker in list(self._price_history.keys()):
                    await self._analyze_ticker(ticker)

                await asyncio.sleep(60)  # Analyze every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.agent_id}] Analysis loop error: {e}")
                await asyncio.sleep(60)
                
    async def _handle_price_alert(self, message: AgentMessage):
        """Handle price action alerts."""
        ticker = message.payload.get("ticker")
        price_data = message.payload.get("price_data")
        
        if ticker and price_data:
            await self._update_price_history(ticker, price_data)
            
    async def _update_price_history(self, ticker: str, price_data: Dict):
        """Update price history for a ticker."""
        if ticker not in self._price_history:
            self._price_history[ticker] = []
            
        self._price_history[ticker].append({
            "timestamp": datetime.utcnow(),
            **price_data
        })
        
        # Keep only recent history
        max_history = self.lookback_periods * 2
        if len(self._price_history[ticker]) > max_history:
            self._price_history[ticker] = self._price_history[ticker][-max_history:]
            
    async def _analyze_ticker(self, ticker: str) -> TechnicalState:
        """Analyze market structure for a ticker."""
        if ticker not in self._price_history or len(self._price_history[ticker]) < 20:
            return None
            
        prices = self._price_history[ticker]
        
        # Calculate indicators
        closes = [p["close"] for p in prices]
        highs = [p["high"] for p in prices]
        lows = [p["low"] for p in prices]
        volumes = [p.get("volume", 0) for p in prices]
        
        # Current values
        current = prices[-1]
        
        # Trend analysis
        trend_direction, trend_strength = self._calculate_trend(closes)
        trend_duration = self._calculate_trend_duration(closes, trend_direction)
        
        # Volatility
        atr = self._calculate_atr(highs, lows, closes, 14)
        atr_percent = (atr / closes[-1]) * 100 if closes[-1] > 0 else 0
        volatility_regime = self._classify_volatility(atr_percent)
        bb_width = self._calculate_bollinger_width(closes, 20)
        
        # Momentum
        rsi = self._calculate_rsi(closes, 14)
        macd_line, macd_signal, macd_hist = self._calculate_macd(closes)
        
        # Volume
        volume_regime, volume_ratio = self._analyze_volume(volumes)
        obv_trend = self._calculate_obv_trend(closes, volumes)
        
        # Structure
        supports, resistances = self._find_support_resistance(highs, lows, closes)
        pivot_highs, pivot_lows = self._find_pivots(highs, lows)
        
        # Regime detection
        regime, regime_confidence = self._detect_regime(
            closes, trend_direction, trend_strength, 
            volatility_regime, volume_regime
        )
        
        # Calculate stability
        stability = self._calculate_regime_stability(ticker, regime)
        
        # Structure score
        structure_score = self._calculate_structure_score(
            trend_direction, trend_strength, rsi, macd_hist, regime
        )
        
        state = TechnicalState(
            ticker=ticker,
            timestamp=datetime.utcnow(),
            current_price=closes[-1],
            open_price=current.get("open", closes[-1]),
            high_price=current.get("high", highs[-1]),
            low_price=current.get("low", lows[-1]),
            close_price=closes[-1],
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            trend_duration_bars=trend_duration,
            volatility_regime=volatility_regime,
            atr_14=atr,
            atr_percent=atr_percent,
            bollinger_width=bb_width,
            rsi_14=rsi,
            macd_line=macd_line,
            macd_signal=macd_signal,
            macd_histogram=macd_hist,
            volume_regime=volume_regime,
            volume_sma_ratio=volume_ratio,
            obv_trend=obv_trend,
            support_levels=supports,
            resistance_levels=resistances,
            pivot_highs=pivot_highs,
            pivot_lows=pivot_lows,
            regime=regime,
            regime_confidence=regime_confidence,
            regime_stability=stability,
            structure_score=structure_score,
            structure_confidence=min(0.95, 0.5 + trend_strength * 0.5)
        )
        
        self._technical_states[ticker] = state
        
        # Track regime history
        if ticker not in self._regime_history:
            self._regime_history[ticker] = []
        self._regime_history[ticker].append((datetime.utcnow(), regime))
        
        # Publish update
        await self._publish_structure_update(state)
        
        # Check for regime change
        if len(self._regime_history[ticker]) > 1:
            prev_regime = self._regime_history[ticker][-2][1]
            if prev_regime != regime:
                await self._publish_regime_change(ticker, prev_regime, regime, regime_confidence)
                
        return state
        
    def _calculate_trend(self, closes: List[float]) -> Tuple[str, float]:
        """Calculate trend direction and strength."""
        if len(closes) < 20:
            return "sideways", 0.0
            
        # Use EMA slopes
        ema_9 = self._calculate_ema(closes, 9)
        ema_21 = self._calculate_ema(closes, 21)
        
        if len(ema_9) < 2 or len(ema_21) < 2:
            return "sideways", 0.0
            
        # Trend direction
        if ema_9[-1] > ema_21[-1] and ema_9[-2] > ema_21[-2]:
            direction = "up"
        elif ema_9[-1] < ema_21[-1] and ema_9[-2] < ema_21[-2]:
            direction = "down"
        else:
            direction = "sideways"
            
        # Trend strength (ADX-like calculation)
        price_change = abs(closes[-1] - closes[-20]) / closes[-20] if closes[-20] > 0 else 0
        strength = min(1.0, price_change * 10)  # Scale to 0-1
        
        return direction, strength
        
    def _calculate_trend_duration(self, closes: List[float], direction: str) -> int:
        """Calculate how long the current trend has persisted."""
        if len(closes) < 2:
            return 0
            
        duration = 0
        if direction == "up":
            for i in range(len(closes) - 1, 0, -1):
                if closes[i] > closes[i-1]:
                    duration += 1
                else:
                    break
        elif direction == "down":
            for i in range(len(closes) - 1, 0, -1):
                if closes[i] < closes[i-1]:
                    duration += 1
                else:
                    break
        else:
            for i in range(len(closes) - 1, 0, -1):
                if abs(closes[i] - closes[i-1]) / closes[i-1] < 0.001:
                    duration += 1
                else:
                    break
                    
        return duration
        
    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int) -> float:
        """Calculate Average True Range."""
        if len(closes) < period + 1:
            return 0.0
            
        tr_values = []
        for i in range(1, len(closes)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i-1])
            tr3 = abs(lows[i] - closes[i-1])
            tr_values.append(max(tr1, tr2, tr3))
            
        return np.mean(tr_values[-period:]) if tr_values else 0.0
        
    def _classify_volatility(self, atr_percent: float) -> str:
        """Classify volatility regime."""
        if atr_percent < 0.5:
            return "low"
        elif atr_percent < 1.5:
            return "normal"
        elif atr_percent < 3.0:
            return "high"
        else:
            return "extreme"
            
    def _calculate_bollinger_width(self, closes: List[float], period: int) -> float:
        """Calculate Bollinger Band width."""
        if len(closes) < period:
            return 0.0
            
        sma = np.mean(closes[-period:])
        std = np.std(closes[-period:])
        
        upper = sma + 2 * std
        lower = sma - 2 * std
        
        return (upper - lower) / sma if sma > 0 else 0.0
        
    def _calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        """Calculate RSI."""
        if len(closes) < period + 1:
            return 50.0
            
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
            
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
        
    def _calculate_macd(self, closes: List[float]) -> Tuple[float, float, float]:
        """Calculate MACD."""
        if len(closes) < 26:
            return 0.0, 0.0, 0.0
            
        ema_12 = self._calculate_ema(closes, 12)
        ema_26 = self._calculate_ema(closes, 26)
        
        if len(ema_12) < 1 or len(ema_26) < 1:
            return 0.0, 0.0, 0.0
            
        macd_line = ema_12[-1] - ema_26[-1]
        
        # Signal line (9-period EMA of MACD)
        macd_history = [ema_12[i] - ema_26[i] for i in range(min(len(ema_12), len(ema_26)))]
        signal_line = self._calculate_ema(macd_history, 9)[-1] if len(macd_history) >= 9 else 0.0
        
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
        
    def _calculate_ema(self, values: List[float], period: int) -> List[float]:
        """Calculate EMA."""
        if len(values) < period:
            return values
            
        multiplier = 2 / (period + 1)
        ema = [np.mean(values[:period])]
        
        for price in values[period:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
            
        return ema
        
    def _analyze_volume(self, volumes: List[float]) -> Tuple[str, float]:
        """Analyze volume regime."""
        if len(volumes) < 20:
            return "normal", 1.0
            
        current_vol = volumes[-1]
        avg_vol = np.mean(volumes[-20:])
        ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
        
        if ratio < 0.5:
            return "low", ratio
        elif ratio < 1.5:
            return "normal", ratio
        elif ratio < 3.0:
            return "high", ratio
        else:
            return "climactic", ratio
            
    def _calculate_obv_trend(self, closes: List[float], volumes: List[float]) -> str:
        """Calculate OBV trend."""
        if len(closes) < 2 or len(volumes) < 2:
            return "neutral"
            
        obv = [0]
        for i in range(1, len(closes)):
            if closes[i] > closes[i-1]:
                obv.append(obv[-1] + volumes[i])
            elif closes[i] < closes[i-1]:
                obv.append(obv[-1] - volumes[i])
            else:
                obv.append(obv[-1])
                
        # Check trend of OBV
        if len(obv) >= 10:
            recent = obv[-10:]
            if all(recent[i] <= recent[i+1] for i in range(len(recent)-1)):
                return "rising"
            elif all(recent[i] >= recent[i+1] for i in range(len(recent)-1)):
                return "falling"
                
        return "neutral"
        
    def _find_support_resistance(self, highs: List[float], lows: List[float], closes: List[float]) -> Tuple[List[float], List[float]]:
        """Find support and resistance levels."""
        if len(closes) < 20:
            return [], []
            
        # Simple pivot-based approach
        window = 5
        supports = []
        resistances = []
        
        for i in range(window, len(lows) - window):
            # Support: local minimum
            if all(lows[i] <= lows[i-j] for j in range(1, window+1)) and \
               all(lows[i] <= lows[i+j] for j in range(1, window+1)):
                supports.append(lows[i])
                
        for i in range(window, len(highs) - window):
            # Resistance: local maximum
            if all(highs[i] >= highs[i-j] for j in range(1, window+1)) and \
               all(highs[i] >= highs[i+j] for j in range(1, window+1)):
                resistances.append(highs[i])
                
        # Cluster levels
        supports = self._cluster_levels(supports, threshold=0.02)
        resistances = self._cluster_levels(resistances, threshold=0.02)
        
        return supports[-5:], resistances[-5:]  # Keep last 5
        
    def _cluster_levels(self, levels: List[float], threshold: float = 0.02) -> List[float]:
        """Cluster similar price levels."""
        if not levels:
            return []
            
        clusters = []
        for level in levels:
            found = False
            for cluster in clusters:
                if abs(level - np.mean(cluster)) / np.mean(cluster) < threshold:
                    cluster.append(level)
                    found = True
                    break
            if not found:
                clusters.append([level])
                
        return [np.mean(cluster) for cluster in clusters]
        
    def _find_pivots(self, highs: List[float], lows: List[float]) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """Find pivot highs and lows."""
        window = 3
        pivot_highs = []
        pivot_lows = []
        
        for i in range(window, len(highs) - window):
            if all(highs[i] >= highs[i-j] for j in range(1, window+1)) and \
               all(highs[i] >= highs[i+j] for j in range(1, window+1)):
                pivot_highs.append((len(highs) - i - 1, highs[i]))
                
        for i in range(window, len(lows) - window):
            if all(lows[i] <= lows[i-j] for j in range(1, window+1)) and \
               all(lows[i] <= lows[i+j] for j in range(1, window+1)):
                pivot_lows.append((len(lows) - i - 1, lows[i]))
                
        return pivot_highs[:5], pivot_lows[:5]  # Keep last 5
        
    def _detect_regime(
        self, 
        closes: List[float], 
        trend_direction: str, 
        trend_strength: float,
        volatility_regime: str,
        volume_regime: str
    ) -> Tuple[MarketRegime, float]:
        """Detect current market regime."""
        
        # Calculate price range
        price_range = (max(closes[-20:]) - min(closes[-20:])) / np.mean(closes[-20:]) if closes else 0
        
        # Volatile regime
        if volatility_regime == "extreme":
            if trend_direction == "up":
                return MarketRegime.BREAKOUT, 0.8
            elif trend_direction == "down":
                return MarketRegime.REVERSAL, 0.8
            else:
                return MarketRegime.VOLATILE, 0.9
                
        # Trending regime
        if trend_strength > 0.6:
            if trend_direction == "up":
                # Check for distribution at highs
                if volume_regime == "climactic":
                    return MarketRegime.DISTRIBUTION, 0.7
                return MarketRegime.TRENDING_UP, trend_strength
            elif trend_direction == "down":
                # Check for accumulation at lows
                if volume_regime == "climactic":
                    return MarketRegime.ACCUMULATION, 0.7
                return MarketRegime.TRENDING_DOWN, trend_strength
                
        # Ranging regime
        if price_range < 0.03:  # 3% range
            return MarketRegime.RANGING, 0.8
            
        # Low volatility
        if volatility_regime == "low":
            return MarketRegime.LOW_VOLATILITY, 0.7
            
        # Default
        return MarketRegime.RANGING, 0.5
        
    def _calculate_regime_stability(self, ticker: str, current_regime: MarketRegime) -> float:
        """Calculate how stable the current regime is."""
        if ticker not in self._regime_history or len(self._regime_history[ticker]) < 2:
            return 0.0
            
        # Count consecutive same regimes
        count = 0
        for ts, regime in reversed(self._regime_history[ticker]):
            if regime == current_regime:
                count += 1
            else:
                break
                
        return min(1.0, count / 20)  # Max at 20 periods
        
    def _calculate_structure_score(
        self,
        trend_direction: str,
        trend_strength: float,
        rsi: float,
        macd_hist: float,
        regime: MarketRegime
    ) -> float:
        """Calculate overall structure score (-1.0 to 1.0)."""
        score = 0.0
        
        # Trend contribution
        if trend_direction == "up":
            score += trend_strength * 0.4
        elif trend_direction == "down":
            score -= trend_strength * 0.4
            
        # RSI contribution
        if rsi > 70:
            score -= 0.1  # Overbought
        elif rsi < 30:
            score += 0.1  # Oversold
        elif rsi > 50:
            score += (rsi - 50) / 500
        else:
            score -= (50 - rsi) / 500
            
        # MACD contribution
        score += macd_hist * 0.2
        
        # Regime contribution
        regime_scores = {
            MarketRegime.TRENDING_UP: 0.3,
            MarketRegime.TRENDING_DOWN: -0.3,
            MarketRegime.BREAKOUT: 0.4,
            MarketRegime.REVERSAL: -0.4,
            MarketRegime.ACCUMULATION: 0.1,
            MarketRegime.DISTRIBUTION: -0.1,
        }
        score += regime_scores.get(regime, 0.0)
        
        return max(-1.0, min(1.0, score))
        
    async def _publish_structure_update(self, state: TechnicalState):
        """Publish market structure update."""
        await self.send_message(
            MessageType.MARKET_STRUCTURE_UPDATE,
            {
                "ticker": state.ticker,
                "timestamp": state.timestamp.isoformat(),
                "current_price": state.current_price,
                "trend_direction": state.trend_direction,
                "trend_strength": state.trend_strength,
                "volatility_regime": state.volatility_regime,
                "volume_regime": state.volume_regime,
                "rsi": state.rsi_14,
                "macd_histogram": state.macd_histogram,
                "regime": state.regime.value,
                "regime_confidence": state.regime_confidence,
                "structure_score": state.structure_score,
                "structure_confidence": state.structure_confidence,
                "support_levels": state.support_levels,
                "resistance_levels": state.resistance_levels,
            }
        )
        
    async def _publish_regime_change(
        self, 
        ticker: str, 
        old_regime: MarketRegime, 
        new_regime: MarketRegime,
        confidence: float
    ):
        """Publish regime change alert."""
        await self.send_message(
            MessageType.REGIME_CHANGE,
            {
                "ticker": ticker,
                "timestamp": datetime.utcnow().isoformat(),
                "old_regime": old_regime.value,
                "new_regime": new_regime.value,
                "confidence": confidence,
                "significance": "high" if confidence > 0.8 else "medium" if confidence > 0.6 else "low",
            },
            priority=2  # High priority
        )
        
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task assignment."""
        task_type = task.get("type")
        ticker = task.get("ticker")
        
        if task_type == "analyze":
            if ticker:
                state = await self._analyze_ticker(ticker)
                return {
                    "ticker": ticker,
                    "state": self._state_to_dict(state) if state else None
                }
            else:
                # Analyze all tracked tickers
                results = {}
                for t in self._price_history.keys():
                    state = await self._analyze_ticker(t)
                    results[t] = self._state_to_dict(state) if state else None
                return results
                
        elif task_type == "get_state":
            state = self._technical_states.get(ticker)
            return {
                "ticker": ticker,
                "state": self._state_to_dict(state) if state else None
            }
            
        elif task_type == "get_regime_history":
            history = self._regime_history.get(ticker, [])
            return {
                "ticker": ticker,
                "history": [
                    {"timestamp": ts.isoformat(), "regime": r.value}
                    for ts, r in history[-50:]
                ]
            }
            
        return {"error": f"Unknown task type: {task_type}"}
        
    def _state_to_dict(self, state: TechnicalState) -> Dict[str, Any]:
        """Convert TechnicalState to dictionary."""
        if not state:
            return None
        return {
            "ticker": state.ticker,
            "timestamp": state.timestamp.isoformat(),
            "current_price": state.current_price,
            "trend_direction": state.trend_direction,
            "trend_strength": state.trend_strength,
            "volatility_regime": state.volatility_regime,
            "volume_regime": state.volume_regime,
            "rsi_14": state.rsi_14,
            "macd_histogram": state.macd_histogram,
            "regime": state.regime.value,
            "regime_confidence": state.regime_confidence,
            "structure_score": state.structure_score,
            "structure_confidence": state.structure_confidence,
            "support_levels": state.support_levels,
            "resistance_levels": state.resistance_levels,
        }
        
    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        status = super().get_status()
        status.update({
            "tracked_tickers": list(self._price_history.keys()),
            "cached_states": list(self._technical_states.keys()),
            "regime_history_count": {t: len(h) for t, h in self._regime_history.items()},
        })
        return status


import asyncio
