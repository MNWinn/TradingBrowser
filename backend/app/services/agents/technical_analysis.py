"""
Technical Analysis Agent for TradingBrowser Swarm

Calculates technical indicators:
- RSI (Relative Strength Index) - 14 period default
- MACD (Moving Average Convergence Divergence) - 12, 26, 9
- VWAP (Volume Weighted Average Price)
- Bollinger Bands - 20 period, 2 std dev

Returns structured output matching the swarm agent interface format.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.services.market_data import get_bars_snapshot


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).
    
    Args:
        prices: Series of closing prices
        period: RSI period (default 14)
    
    Returns:
        Series of RSI values (0-100)
    """
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_macd(
    prices: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> dict[str, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    
    Args:
        prices: Series of closing prices
        fast_period: Fast EMA period (default 12)
        slow_period: Slow EMA period (default 26)
        signal_period: Signal line period (default 9)
    
    Returns:
        Dictionary with 'macd', 'signal', and 'histogram' Series
    """
    ema_fast = prices.ewm(span=fast_period, adjust=False).mean()
    ema_slow = prices.ewm(span=slow_period, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram
    }


def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Calculate Volume Weighted Average Price (VWAP).
    
    Args:
        df: DataFrame with 'high', 'low', 'close', 'volume' columns
    
    Returns:
        Series of VWAP values
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    vwap = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()
    return vwap


def calculate_bollinger_bands(
    prices: pd.Series,
    period: int = 20,
    std_dev: float = 2.0
) -> dict[str, pd.Series]:
    """
    Calculate Bollinger Bands.
    
    Args:
        prices: Series of closing prices
        period: Moving average period (default 20)
        std_dev: Standard deviation multiplier (default 2.0)
    
    Returns:
        Dictionary with 'upper', 'middle', and 'lower' Series
    """
    middle = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    
    return {
        "upper": upper,
        "middle": middle,
        "lower": lower
    }


def generate_signal_from_indicators(
    rsi: float,
    macd: float,
    macd_signal: float,
    macd_histogram: float,
    price: float,
    vwap: float,
    bb_upper: float,
    bb_lower: float
) -> dict[str, Any]:
    """
    Generate trading signal based on technical indicators.
    
    Returns:
        Dictionary with signal recommendation and confidence
    """
    signals = []
    confidence_factors = []
    
    # RSI signals
    if rsi < 30:
        signals.append("oversold")
        confidence_factors.append(0.6)
    elif rsi > 70:
        signals.append("overbought")
        confidence_factors.append(0.6)
    else:
        signals.append("neutral_rsi")
        confidence_factors.append(0.3)
    
    # MACD signals
    if macd > macd_signal and macd_histogram > 0:
        signals.append("macd_bullish")
        confidence_factors.append(0.7)
    elif macd < macd_signal and macd_histogram < 0:
        signals.append("macd_bearish")
        confidence_factors.append(0.7)
    else:
        signals.append("macd_neutral")
        confidence_factors.append(0.3)
    
    # VWAP signals
    if price > vwap:
        signals.append("above_vwap")
        confidence_factors.append(0.5)
    else:
        signals.append("below_vwap")
        confidence_factors.append(0.5)
    
    # Bollinger Bands signals
    if price < bb_lower:
        signals.append("bb_oversold")
        confidence_factors.append(0.6)
    elif price > bb_upper:
        signals.append("bb_overbought")
        confidence_factors.append(0.6)
    else:
        signals.append("bb_mid")
        confidence_factors.append(0.4)
    
    # Determine overall recommendation
    bullish_count = sum(1 for s in signals if s in ["oversold", "macd_bullish", "above_vwap", "bb_oversold"])
    bearish_count = sum(1 for s in signals if s in ["overbought", "macd_bearish", "below_vwap", "bb_overbought"])
    
    if bullish_count >= 3:
        recommendation = "LONG"
    elif bearish_count >= 3:
        recommendation = "SHORT"
    elif bullish_count >= 2 or bearish_count >= 2:
        recommendation = "WATCHLIST"
    else:
        recommendation = "NO_TRADE"
    
    # Calculate confidence as average of relevant factors
    confidence = sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.5
    
    return {
        "recommendation": recommendation,
        "confidence": round(min(confidence, 0.95), 2),
        "signals": signals
    }


async def technical_analysis_agent(
    ticker: str,
    timeframe: str = "5m",
    limit: int = 100
) -> dict[str, Any]:
    """
    Technical Analysis Agent for the TradingBrowser Swarm.
    
    Calculates RSI, MACD, VWAP, and Bollinger Bands to generate
    trading signals.
    
    Args:
        ticker: Stock symbol to analyze
        timeframe: Bar timeframe (default "5m")
        limit: Number of bars to fetch (default 100)
    
    Returns:
        Dictionary matching swarm agent interface format with:
        - agent: "technical_analysis"
        - recommendation: "LONG", "SHORT", "WATCHLIST", or "NO_TRADE"
        - confidence: float 0-1
        - indicators: dict with calculated indicator values
        - signals: list of individual signal flags
    """
    # Fetch market data
    data = get_bars_snapshot(ticker, timeframe=timeframe, limit=limit)
    bars = data.get("bars", [])
    
    if not bars or len(bars) < 30:
        return {
            "agent": "technical_analysis",
            "recommendation": "NO_TRADE",
            "confidence": 0.0,
            "error": "Insufficient data for analysis",
            "indicators": {},
            "signals": []
        }
    
    # Create DataFrame
    df = pd.DataFrame(bars)
    df["t"] = pd.to_datetime(df["t"])
    df = df.sort_values("t").reset_index(drop=True)
    
    # Rename columns for easier access
    df = df.rename(columns={
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume"
    })
    
    # Calculate indicators
    df["rsi"] = calculate_rsi(df["close"], period=14)
    
    macd_data = calculate_macd(df["close"], fast_period=12, slow_period=26, signal_period=9)
    df["macd"] = macd_data["macd"]
    df["macd_signal"] = macd_data["signal"]
    df["macd_histogram"] = macd_data["histogram"]
    
    df["vwap"] = calculate_vwap(df)
    
    bb_data = calculate_bollinger_bands(df["close"], period=20, std_dev=2.0)
    df["bb_upper"] = bb_data["upper"]
    df["bb_middle"] = bb_data["middle"]
    df["bb_lower"] = bb_data["lower"]
    
    # Get latest values
    latest = df.iloc[-1]
    
    # Generate signal
    signal_data = generate_signal_from_indicators(
        rsi=float(latest["rsi"]),
        macd=float(latest["macd"]),
        macd_signal=float(latest["macd_signal"]),
        macd_histogram=float(latest["macd_histogram"]),
        price=float(latest["close"]),
        vwap=float(latest["vwap"]),
        bb_upper=float(latest["bb_upper"]),
        bb_lower=float(latest["bb_lower"])
    )
    
    # Build indicators dict with latest values
    indicators = {
        "rsi": round(float(latest["rsi"]), 2) if not pd.isna(latest["rsi"]) else None,
        "macd": {
            "macd_line": round(float(latest["macd"]), 4) if not pd.isna(latest["macd"]) else None,
            "signal_line": round(float(latest["macd_signal"]), 4) if not pd.isna(latest["macd_signal"]) else None,
            "histogram": round(float(latest["macd_histogram"]), 4) if not pd.isna(latest["macd_histogram"]) else None
        },
        "vwap": round(float(latest["vwap"]), 2) if not pd.isna(latest["vwap"]) else None,
        "bollinger_bands": {
            "upper": round(float(latest["bb_upper"]), 2) if not pd.isna(latest["bb_upper"]) else None,
            "middle": round(float(latest["bb_middle"]), 2) if not pd.isna(latest["bb_middle"]) else None,
            "lower": round(float(latest["bb_lower"]), 2) if not pd.isna(latest["bb_lower"]) else None
        },
        "price": round(float(latest["close"]), 2),
        "timestamp": latest["t"].isoformat() if hasattr(latest["t"], "isoformat") else str(latest["t"])
    }
    
    return {
        "agent": "technical_analysis",
        "recommendation": signal_data["recommendation"],
        "confidence": signal_data["confidence"],
        "indicators": indicators,
        "signals": signal_data["signals"],
        "ticker": ticker,
        "timeframe": timeframe,
        "data_source": data.get("source", "unknown"),
        "simulated": data.get("simulated", False)
    }


# Synchronous wrapper for compatibility with existing sync code
def run_technical_analysis(
    ticker: str,
    timeframe: str = "5m",
    limit: int = 100
) -> dict[str, Any]:
    """
    Synchronous wrapper for technical_analysis_agent.
    
    Args:
        ticker: Stock symbol to analyze
        timeframe: Bar timeframe (default "5m")
        limit: Number of bars to fetch (default 100)
    
    Returns:
        Dictionary with technical analysis results
    """
    import asyncio
    return asyncio.run(technical_analysis_agent(ticker, timeframe, limit))
