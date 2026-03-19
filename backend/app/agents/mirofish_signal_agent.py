"""
MiroFish Signal Agent

Ingests MiroFish predictive outputs and transforms them into structured signals.
Tracks strength, direction, and confidence changes over time.

Outputs:
- Directional bias
- Confidence score
- Predictive features
- Disagreement flags
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np

from .base_agent import BaseAgent
from .message_bus import MessageType, AgentMessage


class SignalDirection(Enum):
    """Direction of the signal."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    CONFLICTED = "conflicted"


@dataclass
class MiroFishSignal:
    """Structured MiroFish signal."""
    ticker: str
    timestamp: datetime
    
    # Core signal
    direction: SignalDirection
    confidence: float  # 0.0 to 1.0
    strength: float  # 0.0 to 1.0 (magnitude of prediction)
    
    # Source data
    raw_prediction: Dict[str, Any]
    scenario_summary: str
    catalyst_summary: str
    risk_flags: List[str]
    
    # Features
    predictive_features: Dict[str, float]
    feature_importance: Dict[str, float]
    
    # Context
    timeframe: str
    prediction_horizon: str
    
    # Change tracking
    confidence_change: float  # Change from previous signal
    direction_change: bool  # True if direction flipped
    
    # Disagreement detection
    internal_disagreement: float  # 0.0 to 1.0
    model_consensus: float  # 0.0 to 1.0
    
    # Metadata
    signal_id: str = field(default_factory=lambda: f"mfs_{datetime.utcnow().timestamp()}")
    version: str = "1.0"


@dataclass
class SignalHistory:
    """History of signals for a ticker."""
    ticker: str
    signals: List[MiroFishSignal] = field(default_factory=list)
    
    def add_signal(self, signal: MiroFishSignal):
        """Add a signal to history."""
        self.signals.append(signal)
        # Keep last 100 signals
        if len(self.signals) > 100:
            self.signals = self.signals[-100:]
            
    def get_recent_signals(self, n: int = 10) -> List[MiroFishSignal]:
        """Get n most recent signals."""
        return self.signals[-n:]
        
    def get_trend(self, lookback: int = 5) -> Dict[str, Any]:
        """Analyze signal trend."""
        recent = self.signals[-lookback:]
        if not recent:
            return {"trend": "unknown", "confidence_trend": 0.0}
            
        confidences = [s.confidence for s in recent]
        directions = [s.direction for s in recent]
        
        # Confidence trend
        if len(confidences) >= 2:
            confidence_slope = np.polyfit(range(len(confidences)), confidences, 1)[0]
        else:
            confidence_slope = 0.0
            
        # Direction consistency
        direction_counts = {}
        for d in directions:
            direction_counts[d] = direction_counts.get(d, 0) + 1
        most_common = max(direction_counts.items(), key=lambda x: x[1])
        consistency = most_common[1] / len(directions)
        
        return {
            "trend": "strengthening" if confidence_slope > 0.05 else "weakening" if confidence_slope < -0.05 else "stable",
            "confidence_trend": confidence_slope,
            "dominant_direction": most_common[0].value,
            "direction_consistency": consistency,
            "avg_confidence": np.mean(confidences),
            "confidence_volatility": np.std(confidences) if len(confidences) > 1 else 0.0,
        }


class MiroFishSignalAgent(BaseAgent):
    """
    Agent for ingesting and processing MiroFish predictive signals.
    """
    
    def __init__(self, message_bus=None, config=None):
        super().__init__("mirofish_signal", message_bus, config)
        
        # Configuration
        self.min_confidence_threshold = config.get("min_confidence", 0.5) if config else 0.5
        self.disagreement_threshold = config.get("disagreement_threshold", 0.3) if config else 0.3
        
        # State
        self._signal_history: Dict[str, SignalHistory] = {}
        self._current_signals: Dict[str, MiroFishSignal] = {}
        
        # MiroFish service reference (will be set externally)
        self._mirofish_service = None
        
        # Register handlers
        self.register_handler(MessageType.MIROFISH_PREDICTION, self._handle_prediction)
        
    def set_mirofish_service(self, service):
        """Set the MiroFish service for fetching predictions."""
        self._mirofish_service = service
        
    async def on_start(self):
        """Start periodic signal fetching."""
        asyncio.create_task(self._fetch_loop())
        
    async def _fetch_loop(self):
        """Periodically fetch MiroFish predictions."""
        while self._running and self.state.value == "RUNNING":
            try:
                # Fetch for tracked tickers
                for ticker in list(self._signal_history.keys()):
                    await self._fetch_prediction(ticker)

                await asyncio.sleep(30)  # Fetch every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.agent_id}] Fetch loop error: {e}")
                await asyncio.sleep(30)
                
    async def _fetch_prediction(self, ticker: str):
        """Fetch MiroFish prediction for a ticker."""
        if not self._mirofish_service:
            return
            
        try:
            # Call MiroFish service
            prediction = await self._mirofish_service.get_prediction(ticker)
            
            if prediction:
                await self._process_prediction(ticker, prediction)
                
        except Exception as e:
            print(f"[{self.agent_id}] Error fetching prediction for {ticker}: {e}")
            
    async def _handle_prediction(self, message: AgentMessage):
        """Handle incoming MiroFish prediction."""
        ticker = message.payload.get("ticker")
        prediction = message.payload.get("prediction")
        
        if ticker and prediction:
            await self._process_prediction(ticker, prediction)
            
    async def _process_prediction(self, ticker: str, raw_prediction: Dict[str, Any]):
        """Process a raw MiroFish prediction into a structured signal."""
        
        # Extract core data
        bias = raw_prediction.get("directional_bias", "NEUTRAL")
        confidence = raw_prediction.get("confidence", 0.5)
        
        # Transform to SignalDirection
        direction = self._parse_direction(bias)
        
        # Calculate strength based on confidence and magnitude
        strength = self._calculate_strength(raw_prediction)
        
        # Extract predictive features
        features = self._extract_features(raw_prediction)
        feature_importance = self._calculate_feature_importance(features)
        
        # Calculate changes from previous signal
        prev_signal = self._current_signals.get(ticker)
        confidence_change = 0.0
        direction_change = False
        
        if prev_signal:
            confidence_change = confidence - prev_signal.confidence
            direction_change = direction != prev_signal.direction
            
        # Detect internal disagreement
        internal_disagreement = self._detect_disagreement(raw_prediction)
        model_consensus = self._calculate_model_consensus(raw_prediction)
        
        signal = MiroFishSignal(
            ticker=ticker,
            timestamp=datetime.utcnow(),
            direction=direction,
            confidence=confidence,
            strength=strength,
            raw_prediction=raw_prediction,
            scenario_summary=raw_prediction.get("scenario_summary", ""),
            catalyst_summary=raw_prediction.get("catalyst_summary", ""),
            risk_flags=raw_prediction.get("risk_flags", []),
            predictive_features=features,
            feature_importance=feature_importance,
            timeframe=raw_prediction.get("timeframe", "5m"),
            prediction_horizon=raw_prediction.get("horizon", "short_term"),
            confidence_change=confidence_change,
            direction_change=direction_change,
            internal_disagreement=internal_disagreement,
            model_consensus=model_consensus,
        )
        
        # Update state
        self._current_signals[ticker] = signal
        
        if ticker not in self._signal_history:
            self._signal_history[ticker] = SignalHistory(ticker)
        self._signal_history[ticker].add_signal(signal)
        
        # Publish signal update
        await self._publish_signal_update(signal)
        
        # Check for significant changes
        if direction_change and confidence > 0.6:
            await self._publish_direction_change(signal, prev_signal)
            
        if abs(confidence_change) > 0.2:
            await self._publish_confidence_alert(signal, confidence_change)
            
    def _parse_direction(self, bias: str) -> SignalDirection:
        """Parse MiroFish bias into SignalDirection."""
        bias_upper = bias.upper()
        if bias_upper == "BULLISH":
            return SignalDirection.BULLISH
        elif bias_upper == "BEARISH":
            return SignalDirection.BEARISH
        elif bias_upper == "NEUTRAL":
            return SignalDirection.NEUTRAL
        else:
            return SignalDirection.CONFLICTED
            
    def _calculate_strength(self, prediction: Dict[str, Any]) -> float:
        """Calculate signal strength from prediction."""
        confidence = prediction.get("confidence", 0.5)
        
        # Adjust based on scenario confidence
        scenarios = prediction.get("scenarios", [])
        if scenarios and len(scenarios) > 0:
            top_scenario_conf = scenarios[0].get("probability", 0.5)
            confidence = (confidence + top_scenario_conf) / 2
            
        # Adjust based on catalyst strength
        catalysts = prediction.get("catalysts", [])
        catalyst_strength = 0.5
        if catalysts:
            catalyst_strength = np.mean([c.get("strength", 0.5) for c in catalysts])
            
        # Combine factors
        strength = (confidence * 0.6) + (catalyst_strength * 0.4)
        return min(1.0, max(0.0, strength))
        
    def _extract_features(self, prediction: Dict[str, Any]) -> Dict[str, float]:
        """Extract predictive features from prediction."""
        features = {}
        
        # Scenario probabilities
        scenarios = prediction.get("scenarios", [])
        for i, scenario in enumerate(scenarios[:3]):
            features[f"scenario_{i}_prob"] = scenario.get("probability", 0.0)
            
        # Catalyst strengths
        catalysts = prediction.get("catalysts", [])
        for i, catalyst in enumerate(catalysts[:3]):
            features[f"catalyst_{i}_strength"] = catalyst.get("strength", 0.0)
            
        # Risk factors
        risks = prediction.get("risk_factors", [])
        features["risk_count"] = float(len(risks))
        features["risk_severity"] = np.mean([r.get("severity", 0.0) for r in risks]) if risks else 0.0
        
        # Model agreement
        model_votes = prediction.get("model_votes", {})
        if model_votes:
            total_votes = sum(model_votes.values())
            if total_votes > 0:
                features["bullish_vote_ratio"] = model_votes.get("bullish", 0) / total_votes
                features["bearish_vote_ratio"] = model_votes.get("bearish", 0) / total_votes
                
        # Technical alignment
        tech_alignment = prediction.get("technical_alignment", 0.5)
        features["technical_alignment"] = tech_alignment
        
        return features
        
    def _calculate_feature_importance(self, features: Dict[str, float]) -> Dict[str, float]:
        """Calculate relative importance of features."""
        if not features:
            return {}
            
        # Simple importance based on magnitude
        total = sum(abs(v) for v in features.values())
        if total == 0:
            return {k: 1.0 / len(features) for k in features}
            
        return {k: abs(v) / total for k, v in features.items()}
        
    def _detect_disagreement(self, prediction: Dict[str, Any]) -> float:
        """Detect internal disagreement in the prediction."""
        disagreements = []
        
        # Check scenario divergence
        scenarios = prediction.get("scenarios", [])
        if len(scenarios) >= 2:
            probs = [s.get("probability", 0) for s in scenarios[:2]]
            if sum(probs) > 0:
                disagreement = 1 - abs(probs[0] - probs[1]) / sum(probs)
                disagreements.append(disagreement)
                
        # Check model vote split
        model_votes = prediction.get("model_votes", {})
        if model_votes:
            total = sum(model_votes.values())
            if total > 0:
                bullish = model_votes.get("bullish", 0) / total
                bearish = model_votes.get("bearish", 0) / total
                # High disagreement when votes are close to 50/50
                vote_disagreement = 1 - abs(bullish - bearish)
                disagreements.append(vote_disagreement)
                
        # Check risk conflicts
        risks = prediction.get("risk_factors", [])
        directional_risks = [r for r in risks if r.get("type") in ["bullish", "bearish"]]
        if len(directional_risks) >= 2:
            risk_disagreement = 0.5  # Moderate disagreement when multiple directional risks
            disagreements.append(risk_disagreement)
            
        return np.mean(disagreements) if disagreements else 0.0
        
    def _calculate_model_consensus(self, prediction: Dict[str, Any]) -> float:
        """Calculate consensus level among models."""
        model_votes = prediction.get("model_votes", {})
        if not model_votes:
            return 0.5
            
        total = sum(model_votes.values())
        if total == 0:
            return 0.5
            
        # Calculate entropy-based consensus
        probs = [v / total for v in model_votes.values()]
        entropy = -sum(p * np.log2(p) if p > 0 else 0 for p in probs)
        max_entropy = np.log2(len(probs))
        
        if max_entropy == 0:
            return 1.0
            
        # Normalize: 1 = full consensus, 0 = maximum disagreement
        return 1 - (entropy / max_entropy)
        
    async def _publish_signal_update(self, signal: MiroFishSignal):
        """Publish signal update to the bus."""
        await self.send_message(
            MessageType.MIROFISH_SIGNAL_UPDATE,
            {
                "signal_id": signal.signal_id,
                "ticker": signal.ticker,
                "timestamp": signal.timestamp.isoformat(),
                "direction": signal.direction.value,
                "confidence": signal.confidence,
                "strength": signal.strength,
                "confidence_change": signal.confidence_change,
                "direction_change": signal.direction_change,
                "internal_disagreement": signal.internal_disagreement,
                "model_consensus": signal.model_consensus,
                "scenario_summary": signal.scenario_summary,
                "risk_flags": signal.risk_flags,
                "predictive_features": signal.predictive_features,
            }
        )
        
    async def _publish_direction_change(self, signal: MiroFishSignal, prev_signal: Optional[MiroFishSignal]):
        """Publish direction change alert."""
        await self.send_message(
            MessageType.MIROFISH_SIGNAL_UPDATE,
            {
                "alert_type": "direction_change",
                "ticker": signal.ticker,
                "timestamp": signal.timestamp.isoformat(),
                "previous_direction": prev_signal.direction.value if prev_signal else "unknown",
                "new_direction": signal.direction.value,
                "confidence": signal.confidence,
                "significance": "high" if signal.confidence > 0.75 else "medium",
            },
            priority=2
        )
        
    async def _publish_confidence_alert(self, signal: MiroFishSignal, change: float):
        """Publish confidence change alert."""
        await self.send_message(
            MessageType.MIROFISH_SIGNAL_UPDATE,
            {
                "alert_type": "confidence_change",
                "ticker": signal.ticker,
                "timestamp": signal.timestamp.isoformat(),
                "confidence": signal.confidence,
                "change": change,
                "direction": signal.direction.value,
                "trend": "strengthening" if change > 0 else "weakening",
            }
        )
        
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task assignment."""
        task_type = task.get("type")
        ticker = task.get("ticker")
        
        if task_type == "fetch":
            if ticker:
                await self._fetch_prediction(ticker)
                return {"status": "fetched", "ticker": ticker}
            else:
                return {"error": "No ticker specified"}
                
        elif task_type == "get_signal":
            signal = self._current_signals.get(ticker)
            return {
                "ticker": ticker,
                "signal": self._signal_to_dict(signal) if signal else None
            }
            
        elif task_type == "get_history":
            history = self._signal_history.get(ticker)
            if history:
                return {
                    "ticker": ticker,
                    "signal_count": len(history.signals),
                    "trend_analysis": history.get_trend(),
                    "recent_signals": [
                        self._signal_to_dict(s) for s in history.get_recent_signals(10)
                    ]
                }
            return {"ticker": ticker, "signal_count": 0}
            
        elif task_type == "get_all_signals":
            return {
                "signals": {
                    ticker: self._signal_to_dict(signal)
                    for ticker, signal in self._current_signals.items()
                }
            }
            
        elif task_type == "ingest":
            # Ingest a raw prediction
            prediction = task.get("prediction")
            if ticker and prediction:
                await self._process_prediction(ticker, prediction)
                return {"status": "ingested", "ticker": ticker}
            return {"error": "Missing ticker or prediction"}
            
        return {"error": f"Unknown task type: {task_type}"}
        
    def _signal_to_dict(self, signal: MiroFishSignal) -> Dict[str, Any]:
        """Convert signal to dictionary."""
        if not signal:
            return None
        return {
            "signal_id": signal.signal_id,
            "ticker": signal.ticker,
            "timestamp": signal.timestamp.isoformat(),
            "direction": signal.direction.value,
            "confidence": signal.confidence,
            "strength": signal.strength,
            "confidence_change": signal.confidence_change,
            "direction_change": signal.direction_change,
            "internal_disagreement": signal.internal_disagreement,
            "model_consensus": signal.model_consensus,
            "scenario_summary": signal.scenario_summary,
            "catalyst_summary": signal.catalyst_summary,
            "risk_flags": signal.risk_flags,
            "predictive_features": signal.predictive_features,
            "feature_importance": signal.feature_importance,
            "timeframe": signal.timeframe,
            "prediction_horizon": signal.prediction_horizon,
        }
        
    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        status = super().get_status()
        status.update({
            "tracked_tickers": list(self._signal_history.keys()),
            "current_signals_count": len(self._current_signals),
            "has_mirofish_service": self._mirofish_service is not None,
        })
        return status


import asyncio
