"""
MiroFish Analytics - Comprehensive analytics and visualization for MiroFish predictions.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable
from collections import defaultdict

import numpy as np
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.mirofish_predictions import (
    MiroFishPrediction,
    PredictionOutcome,
    MiroFishAccuracySummary,
)

logger = logging.getLogger(__name__)


@dataclass
class AccuracyMetrics:
    """Accuracy metrics for a set of predictions."""
    total_predictions: int = 0
    correct_predictions: int = 0
    accuracy_rate: float = 0.0
    by_signal_type: dict[str, dict] = field(default_factory=dict)
    by_ticker: dict[str, dict] = field(default_factory=dict)
    by_timeframe: dict[str, dict] = field(default_factory=dict)
    confidence_calibration: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "accuracy_rate": round(self.accuracy_rate, 4),
            "by_signal_type": self.by_signal_type,
            "by_ticker": self.by_ticker,
            "by_timeframe": self.by_timeframe,
            "confidence_calibration": self.confidence_calibration,
        }


@dataclass
class PerformanceMetrics:
    """Performance metrics for trading signals."""
    total_signals: int = 0
    winning_signals: int = 0
    losing_signals: int = 0
    win_rate: float = 0.0
    average_return: float = 0.0
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    profit_factor: float = 0.0
    best_ticker: str | None = None
    worst_ticker: str | None = None
    best_return: float = 0.0
    worst_return: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "total_signals": self.total_signals,
            "winning_signals": self.winning_signals,
            "losing_signals": self.losing_signals,
            "win_rate": round(self.win_rate, 4),
            "average_return": round(self.average_return, 4),
            "total_return": round(self.total_return, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "profit_factor": round(self.profit_factor, 4),
            "best_ticker": self.best_ticker,
            "worst_ticker": self.worst_ticker,
            "best_return": round(self.best_return, 4),
            "worst_return": round(self.worst_return, 4),
        }


@dataclass
class TimeSeriesAnalysis:
    """Time series analysis results."""
    prediction_trend: list[dict] = field(default_factory=list)
    confidence_evolution: list[dict] = field(default_factory=list)
    signal_strength_timeline: list[dict] = field(default_factory=list)
    accuracy_over_time: list[dict] = field(default_factory=list)
    multi_timeframe_alignment: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "prediction_trend": self.prediction_trend,
            "confidence_evolution": self.confidence_evolution,
            "signal_strength_timeline": self.signal_strength_timeline,
            "accuracy_over_time": self.accuracy_over_time,
            "multi_timeframe_alignment": self.multi_timeframe_alignment,
        }


@dataclass
class VisualizationData:
    """Data prepared for visualization."""
    accuracy_heatmap: dict = field(default_factory=dict)
    confidence_distribution: dict = field(default_factory=dict)
    signal_timeline: list[dict] = field(default_factory=list)
    price_correlation: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "accuracy_heatmap": self.accuracy_heatmap,
            "confidence_distribution": self.confidence_distribution,
            "signal_timeline": self.signal_timeline,
            "price_correlation": self.price_correlation,
        }


class MiroFishAnalytics:
    """Comprehensive analytics for MiroFish predictions."""
    
    def __init__(self):
        self._cache: dict[str, Any] = {}
        self._cache_ttl: dict[str, datetime] = {}
        self._default_cache_ttl = timedelta(minutes=5)
    
    def _get_db(self) -> Session:
        """Get database session."""
        return SessionLocal()
    
    def _get_cached(self, key: str) -> Any | None:
        """Get cached value if not expired."""
        if key in self._cache and key in self._cache_ttl:
            if datetime.now(timezone.utc) < self._cache_ttl[key]:
                return self._cache[key]
        return None
    
    def _set_cached(self, key: str, value: Any, ttl: timedelta | None = None) -> None:
        """Cache a value with TTL."""
        self._cache[key] = value
        self._cache_ttl[key] = datetime.now(timezone.utc) + (ttl or self._default_cache_ttl)
    
    def store_prediction(
        self,
        ticker: str,
        signal_type: str,
        confidence: float,
        timeframe: str,
        lens: str = "overall",
        metadata: dict | None = None,
        price_at_prediction: float | None = None,
    ) -> MiroFishPrediction:
        """Store a new MiroFish prediction."""
        db = self._get_db()
        try:
            prediction = MiroFishPrediction(
                ticker=ticker.upper(),
                signal_type=signal_type.upper(),
                confidence=round(confidence, 4),
                timeframe=timeframe,
                lens=lens,
                metadata=metadata or {},
                price_at_prediction=price_at_prediction,
                predicted_at=datetime.now(timezone.utc),
            )
            db.add(prediction)
            db.commit()
            db.refresh(prediction)
            logger.info(f"Stored prediction for {ticker}: {signal_type} @ {confidence:.2%}")
            return prediction
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to store prediction: {e}")
            raise
        finally:
            db.close()
    
    def record_outcome(
        self,
        prediction_id: int,
        actual_return: float,
        outcome_price: float,
        outcome_time: datetime | None = None,
        was_correct: bool | None = None,
        metadata: dict | None = None,
    ) -> PredictionOutcome:
        """Record the outcome of a prediction."""
        db = self._get_db()
        try:
            prediction = db.query(MiroFishPrediction).filter(
                MiroFishPrediction.id == prediction_id
            ).first()
            
            if not prediction:
                raise ValueError(f"Prediction {prediction_id} not found")
            
            if was_correct is None:
                was_correct = self._calculate_correctness(
                    prediction.signal_type,
                    actual_return,
                )
            
            outcome = PredictionOutcome(
                prediction_id=prediction_id,
                actual_return=round(actual_return, 4),
                outcome_price=outcome_price,
                outcome_time=outcome_time or datetime.now(timezone.utc),
                was_correct=was_correct,
                metadata=metadata or {},
            )
            db.add(outcome)
            
            prediction.outcome_id = outcome.id
            prediction.resolved_at = outcome.outcome_time
            
            db.commit()
            db.refresh(outcome)
            self._update_accuracy_summary(db, prediction)
            
            logger.info(f"Recorded outcome for prediction {prediction_id}: {actual_return:.2%}")
            return outcome
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to record outcome: {e}")
            raise
        finally:
            db.close()
    
    def _calculate_correctness(self, signal_type: str, actual_return: float) -> bool:
        """Determine if a prediction was correct based on signal type and return."""
        signal = signal_type.upper()
        if signal in ["LONG", "BULLISH"]:
            return actual_return > 0
        elif signal in ["SHORT", "BEARISH"]:
            return actual_return < 0
        else:
            return abs(actual_return) < 0.01
    
    def _update_accuracy_summary(self, db: Session, prediction: MiroFishPrediction) -> None:
        """Update accuracy summary for the prediction's dimensions."""
        summary = db.query(MiroFishAccuracySummary).filter(
            and_(
                MiroFishAccuracySummary.ticker == prediction.ticker,
                MiroFishAccuracySummary.timeframe == prediction.timeframe,
                MiroFishAccuracySummary.signal_type == prediction.signal_type,
            )
        ).first()
        
        if not summary:
            summary = MiroFishAccuracySummary(
                ticker=prediction.ticker,
                timeframe=prediction.timeframe,
                signal_type=prediction.signal_type,
            )
            db.add(summary)
        
        summary.total_predictions += 1
        if prediction.outcome and prediction.outcome.was_correct:
            summary.correct_predictions += 1
        
        if summary.total_predictions > 0:
            summary.accuracy_rate = summary.correct_predictions / summary.total_predictions
        
        summary.updated_at = datetime.now(timezone.utc)
        db.commit()
    
    def get_overall_accuracy(
        self,
        days: int = 30,
        ticker: str | None = None,
        timeframe: str | None = None,
    ) -> AccuracyMetrics:
        """Get overall accuracy metrics."""
        cache_key = f"accuracy_{days}_{ticker}_{timeframe}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        db = self._get_db()
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            
            query = db.query(MiroFishPrediction).filter(
                MiroFishPrediction.predicted_at >= since,
                MiroFishPrediction.outcome_id.isnot(None)
            )
            
            if ticker:
                query = query.filter(MiroFishPrediction.ticker == ticker.upper())
            if timeframe:
                query = query.filter(MiroFishPrediction.timeframe == timeframe)
            
            predictions = query.all()
            
            metrics = self._calculate_accuracy_metrics(predictions)
            self._set_cached(cache_key, metrics)
            return metrics
        finally:
            db.close()
    
    def _calculate_accuracy_metrics(
        self,
        predictions: list[MiroFishPrediction],
    ) -> AccuracyMetrics:
        """Calculate accuracy metrics from a list of predictions."""
        if not predictions:
            return AccuracyMetrics()
        
        metrics = AccuracyMetrics()
        metrics.total_predictions = len(predictions)
        metrics.correct_predictions = sum(
            1 for p in predictions if p.outcome and p.outcome.was_correct
        )
        metrics.accuracy_rate = (
            metrics.correct_predictions / metrics.total_predictions
            if metrics.total_predictions > 0 else 0.0
        )
        
        # By signal type
        by_signal = defaultdict(lambda: {"total": 0, "correct": 0})
        for p in predictions:
            by_signal[p.signal_type]["total"] += 1
            if p.outcome and p.outcome.was_correct:
                by_signal[p.signal_type]["correct"] += 1
        
        metrics.by_signal_type = {
            signal: {
                "total": data["total"],
                "correct": data["correct"],
                "accuracy": data["correct"] / data["total"] if data["total"] > 0 else 0.0,
            }
            for signal, data in by_signal.items()
        }
        
        # By ticker
        by_ticker = defaultdict(lambda: {"total": 0, "correct": 0})
        for p in predictions:
            by_ticker[p.ticker]["total"] += 1
            if p.outcome and p.outcome.was_correct:
                by_ticker[p.ticker]["correct"] += 1
        
        metrics.by_ticker = {
            ticker: {
                "total": data["total"],
                "correct": data["correct"],
                "accuracy": data["correct"] / data["total"] if data["total"] > 0 else 0.0,
            }
            for ticker, data in by_ticker.items()
        }
        
        # By timeframe
        by_timeframe = defaultdict(lambda: {"total": 0, "correct": 0})
        for p in predictions:
            by_timeframe[p.timeframe]["total"] += 1
            if p.outcome and p.outcome.was_correct:
                by_timeframe[p.timeframe]["correct"] += 1
        
        metrics.by_timeframe = {
            tf: {
                "total": data["total"],
                "correct": data["correct"],
                "accuracy": data["correct"] / data["total"] if data["total"] > 0 else 0.0,
            }
            for tf, data in by_timeframe.items()
        }
        
        # Confidence calibration
        metrics.confidence_calibration = self._calculate_confidence_calibration(predictions)
        
        return metrics
    
    def _calculate_confidence_calibration(
        self,
        predictions: list[MiroFishPrediction],
    ) -> dict:
        """Calculate confidence calibration."""
        bins = {
            "0.0-0.2": {"total": 0, "correct": 0},
            "0.2-0.4": {"total": 0, "correct": 0},
            "0.4-0.6": {"total": 0, "correct": 0},
            "0.6-0.8": {"total": 0, "correct": 0},
            "0.8-1.0": {"total": 0, "correct": 0},
        }
        
        for p in predictions:
            conf = p.confidence
            if conf < 0.2:
                bin_key = "0.0-0.2"
            elif conf < 0.4:
                bin_key = "0.2-0.4"
            elif conf < 0.6:
                bin_key = "0.4-0.6"
            elif conf < 0.8:
                bin_key = "0.6-0.8"
            else:
                bin_key = "0.8-1.0"
            
            bins[bin_key]["total"] += 1
            if p.outcome and p.outcome.was_correct:
                bins[bin_key]["correct"] += 1
        
        calibration = {}
        for bin_key, data in bins.items():
            calibration[bin_key] = {
                "total": data["total"],
                "correct": data["correct"],
                "accuracy": data["correct"] / data["total"] if data["total"] > 0 else 0.0,
                "avg_confidence": self._get_bin_midpoint(bin_key),
            }
        
        return calibration
    
    def _get_bin_midpoint(self, bin_key: str) -> float:
        """Get midpoint of a confidence bin."""
        ranges = {
            "0.0-0.2": 0.1,
            "0.2-0.4": 0.3,
            "0.4-0.6": 0.5,
            "0.6-0.8": 0.7,
            "0.8-1.0": 0.9,
        }
        return ranges.get(bin_key, 0.5)
    
    def get_ticker_accuracy(self, ticker: str, days: int = 30) -> dict:
        """Get detailed accuracy analysis for a specific ticker."""
        db = self._get_db()
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            
            predictions = db.query(MiroFishPrediction).filter(
                MiroFishPrediction.ticker == ticker.upper(),
                MiroFishPrediction.predicted_at >= since,
                MiroFishPrediction.outcome_id.isnot(None)
            ).all()
            
            metrics = self._calculate_accuracy_metrics(predictions)
            
            signal_distribution = defaultdict(int)
            for p in predictions:
                signal_distribution[p.signal_type] += 1
            
            return {
                "ticker": ticker.upper(),
                "period_days": days,
                "accuracy": metrics.to_dict(),
                "signal_distribution": dict(signal_distribution),
                "total_predictions": len(predictions),
            }
        finally:
            db.close()
    
    def get_timeframe_accuracy(self, timeframe: str, days: int = 30) -> dict:
        """Get accuracy analysis for a specific timeframe."""
        db = self._get_db()
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            
            predictions = db.query(MiroFishPrediction).filter(
                MiroFishPrediction.timeframe == timeframe,
                MiroFishPrediction.predicted_at >= since,
                MiroFishPrediction.outcome_id.isnot(None)
            ).all()
            
            metrics = self._calculate_accuracy_metrics(predictions)
            avg_time_to_resolution = self._calculate_avg_resolution_time(predictions)
            
            return {
                "timeframe": timeframe,
                "period_days": days,
                "accuracy": metrics.to_dict(),
                "avg_time_to_resolution_hours": avg_time_to_resolution,
                "total_predictions": len(predictions),
            }
        finally:
            db.close()
    
    def _calculate_avg_resolution_time(self, predictions: list[MiroFishPrediction]) -> float:
        """Calculate average time to resolution in hours."""
        times = []
        for p in predictions:
            if p.resolved_at and p.predicted_at:
                delta = p.resolved_at - p.predicted_at
                times.append(delta.total_seconds() / 3600)
        
        return sum(times) / len(times) if times else 0.0
    
    def get_time_series_analysis(
        self,
        ticker: str | None = None,
        days: int = 30,
    ) -> TimeSeriesAnalysis:
        """Get time series analysis of predictions."""
        db = self._get_db()
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            
            query = db.query(MiroFishPrediction).filter(
                MiroFishPrediction.predicted_at >= since
            )
            
            if ticker:
                query = query.filter(MiroFishPrediction.ticker == ticker.upper())
            
            predictions = query.order_by(asc(MiroFishPrediction.predicted_at)).all()
            
            analysis = TimeSeriesAnalysis()
            
            # Prediction trend
            daily_signals = defaultdict(lambda: defaultdict(int))
            for p in predictions:
                day = p.predicted_at.strftime("%Y-%m-%d")
                daily_signals[day][p.signal_type] += 1
            
            for day in sorted(daily_signals.keys()):
                analysis.prediction_trend.append({
                    "date": day,
                    "counts": dict(daily_signals[day]),
                })
            
            # Confidence evolution
            daily_confidence = defaultdict(list)
            for p in predictions:
                day = p.predicted_at.strftime("%Y-%m-%d")
                daily_confidence[day].append(p.confidence)
            
            for day in sorted(daily_confidence.keys()):
                confs = daily_confidence[day]
                analysis.confidence_evolution.append({
                    "date": day,
                    "avg_confidence": sum(confs) / len(confs),
                    "min_confidence": min(confs),
                    "max_confidence": max(confs),
                    "count": len(confs),
                })
            
            # Signal strength timeline
            for p in predictions:
                strength = self._calculate_signal_strength(p)
                analysis.signal_strength_timeline.append({
                    "timestamp": p.predicted_at.isoformat(),
                    "ticker": p.ticker,
                    "signal_type": p.signal_type,
                    "strength": strength,
                    "confidence": p.confidence,
                })
            
            # Accuracy over time
            window_size = min(20, len(predictions))
            if window_size > 0:
                for i in range(window_size, len(predictions) + 1):
                    window = predictions[i - window_size:i]
                    correct = sum(1 for p in window if p.outcome and p.outcome.was_correct)
                    accuracy = correct / window_size
                    
                    analysis.accuracy_over_time.append({
                        "timestamp": window[-1].predicted_at.isoformat(),
                        "window_accuracy": accuracy,
                        "window_size": window_size,
                    })
            
            # Multi-timeframe alignment
            analysis.multi_timeframe_alignment = self._analyze_timeframe_alignment(predictions)
            
            return analysis
        finally:
            db.close()
    
    def _calculate_signal_strength(self, prediction: MiroFishPrediction) -> float:
        """Calculate signal strength based on confidence and signal type."""
        base_strength = prediction.confidence
        
        if prediction.signal_type in ["LONG", "SHORT", "BULLISH", "BEARISH"]:
            return base_strength * 1.2
        
        return base_strength
    
    def _analyze_timeframe_alignment(self, predictions: list[MiroFishPrediction]) -> dict:
        """Analyze alignment across multiple timeframes."""
        grouped = defaultdict(lambda: defaultdict(list))
        
        for p in predictions:
            hour_key = p.predicted_at.replace(minute=0, second=0, microsecond=0)
            grouped[p.ticker][hour_key].append(p)
        
        alignment_stats = {
            "total_analyzed": 0,
            "fully_aligned": 0,
            "partially_aligned": 0,
            "conflicting": 0,
            "alignment_score_avg": 0.0,
        }
        
        scores = []
        for ticker, hours in grouped.items():
            for hour, preds in hours.items():
                if len(preds) < 2:
                    continue
                
                alignment_stats["total_analyzed"] += 1
                
                signals = [p.signal_type for p in preds]
                bullish_count = sum(1 for s in signals if s in ["LONG", "BULLISH"])
                bearish_count = sum(1 for s in signals if s in ["SHORT", "BEARISH"])
                neutral_count = len(signals) - bullish_count - bearish_count
                
                total = len(signals)
                max_agreement = max(bullish_count, bearish_count, neutral_count)
                alignment_score = max_agreement / total
                scores.append(alignment_score)
                
                if alignment_score == 1.0:
                    alignment_stats["fully_aligned"] += 1
                elif alignment_score >= 0.6:
                    alignment_stats["partially_aligned"] += 1
                else:
                    alignment_stats["conflicting"] += 1
        
        if scores:
            alignment_stats["alignment_score_avg"] = sum(scores) / len(scores)
        
        return alignment_stats
    
    def get_performance_metrics(
        self,
        ticker: str | None = None,
        signal_type: str | None = None,
        days: int = 30,
    ) -> PerformanceMetrics:
        """Get comprehensive performance metrics."""
        db = self._get_db()
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            
            query = db.query(MiroFishPrediction).join(PredictionOutcome).filter(
                MiroFishPrediction.predicted_at >= since,
                MiroFishPrediction.outcome_id.isnot(None)
            )
            
            if ticker:
                query = query.filter(MiroFishPrediction.ticker == ticker.upper())
            if signal_type:
                query = query.filter(MiroFishPrediction.signal_type == signal_type.upper())
            
            predictions = query.all()
            
            return self._calculate_performance_metrics(predictions)
        finally:
            db.close()
    
    def _calculate_performance_metrics(
        self,
        predictions: list[MiroFishPrediction],
    ) -> PerformanceMetrics:
        """Calculate performance metrics from predictions."""
        metrics = PerformanceMetrics()
        
        if not predictions:
            return metrics
        
        returns = []
        ticker_returns = defaultdict(list)
        
        for p in predictions:
            if not p.outcome:
                continue
            
            ret = p.outcome.actual_return
            returns.append(ret)
            ticker_returns[p.ticker].append(ret)
            
            metrics.total_signals += 1
            if ret > 0:
                metrics.winning_signals += 1
            elif ret < 0:
                metrics.losing_signals += 1
        
        if metrics.total_signals == 0:
            return metrics
        
        metrics.win_rate = metrics.winning_signals / metrics.total_signals
        metrics.average_return = sum(returns) / len(returns)
        metrics.total_return = sum(returns)
        
        # Sharpe ratio
        if len(returns) > 1:
            mean_return = np.mean(returns)
            std_return = np.std(returns, ddof=1)
            if std_return > 0:
                metrics.sharpe_ratio = mean_return / std_return * math.sqrt(252)
        
        # Max drawdown
        metrics.max_drawdown, metrics.max_drawdown_pct = self._calculate_max_drawdown(returns)
        
        # Profit factor
        gross_profit = sum(r for r in returns if r > 0)
        gross_loss = abs(sum(r for r in returns if r < 0))
        if gross_loss > 0:
            metrics.profit_factor = gross_profit / gross_loss
        else:
            metrics.profit_factor = float('inf') if gross_profit > 0 else 0.0
        
        # Best/worst tickers
        if ticker_returns:
            ticker_avg = {
                ticker: sum(rets) / len(rets)
                for ticker, rets in ticker_returns.items()
                if len(rets) >= 3
            }
            
            if ticker_avg:
                metrics.best_ticker = max(ticker_avg, key=ticker_avg.get)
                metrics.best_return = ticker_avg[metrics.best_ticker]
                metrics.worst_ticker = min(ticker_avg, key=ticker_avg.get)
                metrics.worst_return = ticker_avg[metrics.worst_ticker]
        
        return metrics
    
    def _calculate_max_drawdown(self, returns: list[float]) -> tuple[float, float]:
        """Calculate maximum drawdown from a series of returns."""
        if not returns:
            return 0.0, 0.0
        
        cumulative = [1.0]
        for r in returns:
            cumulative.append(cumulative[-1] * (1 + r))
        
        peak = cumulative[0]
        max_dd = 0.0
        max_dd_pct = 0.0
        
        for value in cumulative:
            if value > peak:
                peak = value
            else:
                dd = peak - value
                dd_pct = dd / peak
                if dd > max_dd:
                    max_dd = dd
                    max_dd_pct = dd_pct
        
        return max_dd, max_dd_pct
    
    def get_signal_type_performance(self, days: int = 30) -> dict:
        """Get performance breakdown by signal type."""
        db = self._get_db()
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            
            predictions = db.query(MiroFishPrediction).join(PredictionOutcome).filter(
                MiroFishPrediction.predicted_at >= since,
                MiroFishPrediction.outcome_id.isnot(None)
            ).all()
            
            by_type = defaultdict(list)
            for p in predictions:
                by_type[p.signal_type].append(p)
            
            result = {}
            for signal_type, preds in by_type.items():
                metrics = self._calculate_performance_metrics(preds)
                result[signal_type] = {
                    "metrics": metrics.to_dict(),
                    "count": len(preds),
                }
            
            return {
                "period_days": days,
                "by_signal_type": result,
            }
        finally:
            db.close()
    
    def get_visualization_data(
        self,
        ticker: str | None = None,
        days: int = 30,
    ) -> VisualizationData:
        """Get data prepared for visualization."""
        db = self._get_db()
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            
            query = db.query(MiroFishPrediction).filter(
                MiroFishPrediction.predicted_at >= since
            )
            
            if ticker:
                query = query.filter(MiroFishPrediction.ticker == ticker.upper())
            
            predictions = query.all()
            
            viz = VisualizationData()
            
            # Accuracy heatmap data (ticker x timeframe)
            heatmap_data = defaultdict(lambda: defaultdict(lambda: {"total": 0, "correct": 0}))
            for p in predictions:
                if p.outcome:
                    heatmap_data[p.ticker][p.timeframe]["total"] += 1
                    if p.outcome.was_correct:
                        heatmap_data[p.ticker][p.timeframe]["correct"] += 1
            
            viz.accuracy_heatmap = {
                "tickers": list(heatmap_data.keys()),
                "timeframes": list(set(tf for ticker_data in heatmap_data.values() for tf in ticker_data.keys())),
                "data": {
                    ticker: {
                        tf: {
                            "accuracy": data["correct"] / data["total"] if data["total"] > 0 else 0.0,
                            "total": data["total"],
                        }
                        for tf, data in tf_data.items()
                    }
                    for ticker, tf_data in heatmap_data.items()
                },
            }
            
            # Confidence distribution
            confidence_bins = defaultdict(int)
            for p in predictions:
                bin_key = int(p.confidence * 10) / 10
                confidence_bins[bin_key] += 1
            
            viz.confidence_distribution = {
                "bins": sorted(confidence_bins.keys()),
                "counts": [confidence_bins[b] for b in sorted(confidence_bins.keys())],
                "by_outcome": self._get_confidence_by_outcome(predictions),
            }
            
            # Signal timeline
            for p in sorted(predictions, key=lambda x: x.predicted_at):
                viz.signal_timeline.append({
                    "timestamp": p.predicted_at.isoformat(),
                    "ticker": p.ticker,
                    "signal_type": p.signal_type,
                    "confidence": p.confidence,
                    "timeframe": p.timeframe,
                    "outcome": {
                        "was_correct": p.outcome.was_correct if p.outcome else None,
                        "actual_return": p.outcome.actual_return if p.outcome else None,
                    } if p.outcome else None,
                })
            
            # Price correlation
            viz.price_correlation = self._calculate_price_correlation(predictions)
            
            return viz
        finally:
            db.close()
    
    def _get_confidence_by_outcome(self, predictions: list[MiroFishPrediction]) -> dict:
        """Get confidence distribution broken down by outcome."""
        correct_confs = []
        incorrect_confs = []
        
        for p in predictions:
            if p.outcome:
                if p.outcome.was_correct:
                    correct_confs.append(p.confidence)
                else:
                    incorrect_confs.append(p.confidence)
        
        return {
            "correct": {
                "count": len(correct_confs),
                "avg_confidence": sum(correct_confs) / len(correct_confs) if correct_confs else 0.0,
                "distribution": self._bin_confidences(correct_confs),
            },
            "incorrect": {
                "count": len(incorrect_confs),
                "avg_confidence": sum(incorrect_confs) / len(incorrect_confs) if incorrect_confs else 0.0,
                "distribution": self._bin_confidences(incorrect_confs),
            },
        }
    
    def _bin_confidences(self, confidences: list[float]) -> dict:
        """Bin confidences into ranges."""
        bins = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
        for c in confidences:
            if c < 0.2:
                bins["0.0-0.2"] += 1
            elif c < 0.4:
                bins["0.2-0.4"] += 1
            elif c < 0.6:
                bins["0.4-0.6"] += 1
            elif c < 0.8:
                bins["0.6-0.8"] += 1
            else:
                bins["0.8-1.0"] += 1
        return bins
    
    def _calculate_price_correlation(self, predictions: list[MiroFishPrediction]) -> dict:
        """Calculate correlation between predictions and price movements."""
        # Group by ticker and calculate correlation
        ticker_data = defaultdict(lambda: {"predictions": [], "returns": []})
        
        for p in predictions:
            if p.outcome and p.price_at_prediction:
                ticker_data[p.ticker]["predictions"].append({
                    "signal": 1 if p.signal_type in ["LONG", "BULLISH"] else (-1 if p.signal_type in ["SHORT", "BEARISH"] else 0),
                    "confidence": p.confidence,
                })
                ticker_data[p.ticker]["returns"].append(p.outcome.actual_return)
        
        correlations = {}
        for ticker, data in ticker_data.items():
            if len(data["returns"]) >= 5:
                try:
                    signals = [p["signal"] * p["confidence"] for p in data["predictions"]]
                    returns = data["returns"]
                    correlation = np.corrcoef(signals, returns)[0, 1] if len(signals) == len(returns) else 0.0
                    correlations[ticker] = {
                        "correlation": round(correlation, 4),
                        "sample_size": len(returns),
                    }
                except Exception:
                    correlations[ticker] = {"correlation": 0.0, "sample_size": len(returns)}
        
        return {
            "by_ticker": correlations,
            "average_correlation": round(np.mean([c["correlation"] for c in correlations.values()]), 4) if correlations else 0.0,
        }


# Singleton instance
_analytics: MiroFishAnalytics | None = None


def get_analytics() -> MiroFishAnalytics:
    """Get or create the singleton analytics instance."""
    global _analytics
    if _analytics is None:
        _analytics = MiroFishAnalytics()
    return _analytics


# Convenience functions for easy access
def store_prediction(
    ticker: str,
    signal_type: str,
    confidence: float,
    timeframe: str,
    lens: str = "overall",
    metadata: dict | None = None,
    price_at_prediction: float | None = None,
) -> MiroFishPrediction:
    """Store a new MiroFish prediction."""
    return get_analytics().store_prediction(
        ticker=ticker,
        signal_type=signal_type,
        confidence=confidence,
        timeframe=timeframe,
        lens=lens,
        metadata=metadata,
        price_at_prediction=price_at_prediction,
    )


def record_outcome(
    prediction_id: int,
    actual_return: float,
    outcome_price: float,
    outcome_time: datetime | None = None,
    was_correct: bool | None = None,
    metadata: dict | None = None,
) -> PredictionOutcome:
    """Record the outcome of a prediction."""
    return get_analytics().record_outcome(
        prediction_id=prediction_id,
        actual_return=actual_return,
        outcome_price=outcome_price,
        outcome_time=outcome_time,
        was_correct=was_correct,
        metadata=metadata,
    )


def get_overall_accuracy(days: int = 30, ticker: str | None = None, timeframe: str | None = None) -> AccuracyMetrics:
    """Get overall accuracy metrics."""
    return get_analytics().get_overall_accuracy(days=days, ticker=ticker, timeframe=timeframe)


def get_ticker_accuracy(ticker: str, days: int = 30) -> dict:
    """Get detailed accuracy analysis for a specific ticker."""
    return get_analytics().get_ticker_accuracy(ticker=ticker, days=days)


def get_timeframe_accuracy(timeframe: str, days: int = 30) -> dict:
    """Get accuracy analysis for a specific timeframe."""
    return get_analytics().get_timeframe_accuracy(timeframe=timeframe, days=days)


def get_time_series_analysis(ticker: str | None = None, days: int = 30) -> TimeSeriesAnalysis:
    """Get time series analysis of predictions."""
    return get_analytics().get_time_series_analysis(ticker=ticker, days=days)


def get_performance_metrics(ticker: str | None = None, signal_type: str | None = None, days: int = 30) -> PerformanceMetrics:
    """Get comprehensive performance metrics."""
    return get_analytics().get_performance_metrics(ticker=ticker, signal_type=signal_type, days=days)


def get_signal_type_performance(days: int = 30) -> dict:
    """Get performance breakdown by signal type."""
    return get_analytics().get_signal_type_performance(days=days)


def get_visualization_data(ticker: str | None = None, days: int = 30) -> VisualizationData:
    """Get data prepared for visualization."""
    return get_analytics().get_visualization_data(ticker=ticker, days=days)
