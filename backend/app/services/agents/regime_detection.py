"""
Market Regime Detection Agent

This agent analyzes price data to classify market regimes:
- trending_up: Strong upward trend (ADX > 25, positive directional movement)
- trending_down: Strong downward trend (ADX > 25, negative directional movement)
- mean_reverting: Low trend strength with oscillating price action
- volatile: High realized volatility relative to historical norms
- calm: Low volatility, range-bound price action
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Literal

from app.services.market_data import get_bars_snapshot


RegimeType = Literal["trending_up", "trending_down", "mean_reverting", "volatile", "calm"]


def calculate_realized_volatility(
    closes: pd.Series,
    window: int = 20,
    annualize: bool = True
) -> pd.Series:
    """
    Calculate realized volatility from price data using log returns.
    
    Args:
        closes: Series of closing prices
        window: Rolling window for volatility calculation
        annualize: Whether to annualize the volatility (for comparison)
    
    Returns:
        Series of realized volatility values
    """
    # Calculate log returns
    log_returns = np.log(closes / closes.shift(1))
    
    # Calculate rolling standard deviation of log returns
    volatility = log_returns.rolling(window=window, min_periods=window//2).std()
    
    if annualize:
        # Annualize assuming ~252 trading days, adjusted for timeframe
        # For intraday data, we use sqrt(252 * bars_per_day)
        volatility = volatility * np.sqrt(252)
    
    return volatility


def calculate_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Average Directional Index (ADX) and Directional Movement Indicators.
    
    Args:
        high: Series of high prices
        low: Series of low prices
        close: Series of closing prices
        period: Period for ADX calculation (default 14)
    
    Returns:
        Tuple of (ADX, +DI, -DI) series
    """
    # Calculate True Range (TR)
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Calculate Directional Movement
    plus_dm = high.diff()
    minus_dm = -low.diff()
    
    # +DM: when current high - previous high > previous low - current low
    plus_dm = np.where(
        (plus_dm > minus_dm) & (plus_dm > 0),
        plus_dm,
        0
    )
    
    # -DM: when previous low - current low > current high - previous high
    minus_dm = np.where(
        (minus_dm > plus_dm) & (minus_dm > 0),
        minus_dm,
        0
    )
    
    # Convert to Series
    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)
    
    # Calculate smoothed TR and DM using Wilder's smoothing
    alpha = 1 / period
    
    atr = tr.ewm(alpha=alpha, min_periods=period).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=alpha, min_periods=period).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=alpha, min_periods=period).mean() / atr)
    
    # Calculate DX and ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    dx = dx.replace([np.inf, -np.inf], 0).fillna(0)
    
    adx = dx.ewm(alpha=alpha, min_periods=period).mean()
    
    return adx, plus_di, minus_di


def classify_regime(
    adx: float,
    plus_di: float,
    minus_di: float,
    current_vol: float,
    vol_percentile: float,
    price_change_5d: float
) -> tuple[RegimeType, float]:
    """
    Classify market regime based on ADX, volatility, and price action.
    
    Args:
        adx: Current ADX value (0-100)
        plus_di: Current +DI value
        minus_di: Current -DI value
        current_vol: Current realized volatility
        vol_percentile: Current volatility percentile (0-1)
        price_change_5d: 5-day price change percentage
    
    Returns:
        Tuple of (regime_type, confidence_score)
    """
    confidence = 0.5  # Base confidence
    
    # Strong trend detection (ADX > 25)
    if adx > 25:
        trend_strength = min((adx - 25) / 50, 1.0)  # Normalize 25-75 to 0-1
        
        if plus_di > minus_di:
            regime = "trending_up"
            # Higher confidence if price change aligns with trend
            confidence = 0.6 + (trend_strength * 0.3)
            if price_change_5d > 0:
                confidence += 0.1
        else:
            regime = "trending_down"
            confidence = 0.6 + (trend_strength * 0.3)
            if price_change_5d < 0:
                confidence += 0.1
    
    # Volatile regime - high volatility percentile
    elif vol_percentile > 0.8:
        regime = "volatile"
        # Confidence based on how extreme the volatility is
        confidence = 0.5 + ((vol_percentile - 0.8) / 0.2) * 0.4
    
    # Calm regime - low volatility and no trend
    elif vol_percentile < 0.2 and adx < 20:
        regime = "calm"
        # Confidence based on how low both volatility and ADX are
        vol_component = (0.2 - vol_percentile) / 0.2
        adx_component = (20 - adx) / 20 if adx < 20 else 0
        confidence = 0.5 + (vol_component + adx_component) / 2 * 0.4
    
    # Mean reverting - low ADX, moderate volatility
    else:
        regime = "mean_reverting"
        # Confidence inversely related to trend strength
        adx_component = (25 - adx) / 25 if adx < 25 else 0
        vol_component = 1 - abs(vol_percentile - 0.5) * 2  # Peak at 50th percentile
        confidence = 0.5 + (adx_component * 0.3) + (vol_component * 0.2)
    
    # Cap confidence at 0.95
    confidence = min(confidence, 0.95)
    
    return regime, round(confidence, 2)


def calculate_regime_metrics(df: pd.DataFrame) -> dict:
    """
    Calculate all metrics needed for regime classification.
    
    Args:
        df: DataFrame with 'high', 'low', 'close' columns
    
    Returns:
        Dictionary of calculated metrics
    """
    # Ensure we have enough data
    if len(df) < 20:
        raise ValueError(f"Insufficient data points: {len(df)} (minimum 20 required)")
    
    # Calculate realized volatility
    vol_20 = calculate_realized_volatility(df["close"], window=20)
    vol_10 = calculate_realized_volatility(df["close"], window=10)
    
    # Calculate ADX
    adx, plus_di, minus_di = calculate_adx(df["high"], df["low"], df["close"], period=14)
    
    # Calculate volatility percentiles
    vol_percentile = vol_20.rolling(window=60, min_periods=20).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5,
        raw=False
    )
    
    # Calculate 5-day price change
    price_change_5d = ((df["close"] - df["close"].shift(5)) / df["close"].shift(5)) * 100
    
    return {
        "adx": adx,
        "plus_di": plus_di,
        "minus_di": minus_di,
        "volatility_20d": vol_20,
        "volatility_10d": vol_10,
        "volatility_percentile": vol_percentile,
        "price_change_5d": price_change_5d,
    }


async def detect_market_regime(
    ticker: str,
    timeframe: str = "1d",
    lookback: int = 100
) -> dict:
    """
    Detect the current market regime for a given ticker.
    
    Args:
        ticker: Stock symbol to analyze
        timeframe: Bar timeframe (e.g., "1d", "1h", "15m")
        lookback: Number of bars to fetch for analysis
    
    Returns:
        Dictionary with regime classification and supporting metrics
    """
    # Fetch bar data
    data = get_bars_snapshot(ticker, timeframe=timeframe, limit=lookback)
    bars = data.get("bars", [])
    
    if len(bars) < 30:
        return {
            "agent": "regime_detection",
            "ticker": ticker,
            "timeframe": timeframe,
            "regime": "unknown",
            "confidence": 0.0,
            "error": f"Insufficient data: {len(bars)} bars (minimum 30 required)",
            "metrics": {},
        }
    
    # Convert to DataFrame
    df = pd.DataFrame(bars)
    df["t"] = pd.to_datetime(df["t"])
    df = df.sort_values("t").reset_index(drop=True)
    
    # Ensure required columns exist
    required_cols = ["h", "l", "c"]
    if not all(col in df.columns for col in required_cols):
        # Try alternate column names
        col_map = {"high": "h", "low": "l", "close": "c", "open": "o"}
        for old, new in col_map.items():
            if old in df.columns and new not in df.columns:
                df[new] = df[old]
    
    # Rename for consistency
    df = df.rename(columns={"h": "high", "l": "low", "c": "close", "o": "open", "v": "volume"})
    
    try:
        # Calculate metrics
        metrics = calculate_regime_metrics(df)
        
        # Get current values (last non-null)
        current_adx = metrics["adx"].dropna().iloc[-1] if not metrics["adx"].dropna().empty else 0
        current_plus_di = metrics["plus_di"].dropna().iloc[-1] if not metrics["plus_di"].dropna().empty else 0
        current_minus_di = metrics["minus_di"].dropna().iloc[-1] if not metrics["minus_di"].dropna().empty else 0
        current_vol = metrics["volatility_20d"].dropna().iloc[-1] if not metrics["volatility_20d"].dropna().empty else 0
        current_vol_pct = metrics["volatility_percentile"].dropna().iloc[-1] if not metrics["volatility_percentile"].dropna().empty else 0.5
        current_price_change = metrics["price_change_5d"].dropna().iloc[-1] if not metrics["price_change_5d"].dropna().empty else 0
        
        # Classify regime
        regime, confidence = classify_regime(
            adx=current_adx,
            plus_di=current_plus_di,
            minus_di=current_minus_di,
            current_vol=current_vol,
            vol_percentile=current_vol_pct,
            price_change_5d=current_price_change
        )
        
        # Calculate additional context
        avg_volume = df["volume"].tail(20).mean() if "volume" in df.columns else None
        
        # Determine recommendation based on regime
        regime_recommendations = {
            "trending_up": "LONG",
            "trending_down": "SHORT",
            "mean_reverting": "MEAN_REVERSION",
            "volatile": "REDUCE_SIZE",
            "calm": "ACCUMULATE",
        }
        
        return {
            "agent": "regime_detection",
            "ticker": ticker,
            "timeframe": timeframe,
            "regime": regime,
            "confidence": confidence,
            "recommendation": regime_recommendations.get(regime, "NEUTRAL"),
            "metrics": {
                "adx": round(current_adx, 2),
                "plus_di": round(current_plus_di, 2),
                "minus_di": round(current_minus_di, 2),
                "volatility_annualized": round(current_vol * 100, 2),  # As percentage
                "volatility_percentile": round(current_vol_pct, 2),
                "price_change_5d_pct": round(current_price_change, 2),
                "avg_volume_20d": int(avg_volume) if avg_volume is not None else None,
            },
            "data_quality": {
                "bars_analyzed": len(df),
                "source": data.get("source", "unknown"),
                "simulated": data.get("simulated", False),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        return {
            "agent": "regime_detection",
            "ticker": ticker,
            "timeframe": timeframe,
            "regime": "error",
            "confidence": 0.0,
            "error": str(e),
            "metrics": {},
        }


async def regime_detection_agent(ticker: str) -> dict:
    """
    Agent interface for the swarm orchestrator.
    Analyzes daily timeframe by default for regime classification.
    
    Args:
        ticker: Stock symbol to analyze
    
    Returns:
        Standardized agent response dictionary
    """
    result = await detect_market_regime(ticker, timeframe="1d", lookback=100)
    
    # Map regime to standardized recommendation
    regime = result.get("regime", "unknown")
    
    recommendation_map = {
        "trending_up": "LONG",
        "trending_down": "SHORT",
        "mean_reverting": "WATCHLIST",  # Requires specific strategy
        "volatile": "NO_TRADE",  # Too risky
        "calm": "LONG",  # Good accumulation phase
        "unknown": "WATCHLIST",
        "error": "NO_TRADE",
    }
    
    return {
        "agent": "regime_detection",
        "recommendation": recommendation_map.get(regime, "WATCHLIST"),
        "confidence": result.get("confidence", 0.5),
        "regime": regime,
        "metrics": result.get("metrics", {}),
        "context": result,
    }
