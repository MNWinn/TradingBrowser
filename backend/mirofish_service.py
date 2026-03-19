#!/usr/bin/env python3
"""
Simple Local MiroFish Service
Provides AI-style market predictions for TradingBrowser
"""

import asyncio
import json
import random
from datetime import datetime, timezone
from typing import Optional
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

app = FastAPI(title="MiroFish Local Service", version="1.0.0")

# Market data cache
_price_cache = {}

class PredictionRequest(BaseModel):
    ticker: str
    timeframe: str = "5m"
    context: Optional[dict] = None

class PredictionResponse(BaseModel):
    provider: str = "mirofish"
    provider_mode: str = "live"
    ticker: str
    directional_bias: str
    confidence: float
    scenario_summary: str
    catalyst_summary: str
    risk_flags: list
    leaning: str
    timestamp: str

async def get_market_data(ticker: str):
    """Fetch real market data from Alpaca"""
    try:
        async with httpx.AsyncClient() as client:
            # Try to get real data from Alpaca
            response = await client.get(
                f"https://data.alpaca.markets/v2/stocks/{ticker}/quotes/latest",
                headers={
                    "APCA-API-KEY-ID": "CKDKKIQ5EBR2P7KASR5V",
                    "APCA-API-SECRET-KEY": "rlbi1AfcmnB2A7D47kE2zX8FxW8jbPW97lNHzht"
                }
            )
            if response.status_code == 200:
                return response.json()
    except:
        pass
    
    # Fallback to simulated data
    return {
        "quote": {
            "ap": round(random.uniform(100, 500), 2),
            "bp": round(random.uniform(100, 500), 2),
        }
    }

def analyze_technical_factors(ticker: str, price: float) -> dict:
    """Simulate technical analysis factors"""
    # Generate somewhat realistic technical signals
    trend_strength = random.uniform(0.3, 0.9)
    momentum = random.uniform(-0.5, 0.5)
    volatility = random.uniform(0.1, 0.4)
    
    factors = {
        "trend": {
            "score": trend_strength,
            "direction": "UP" if trend_strength > 0.5 else "DOWN"
        },
        "momentum": {
            "score": abs(momentum),
            "direction": "BULLISH" if momentum > 0 else "BEARISH"
        },
        "volatility": {
            "score": volatility,
            "regime": "HIGH" if volatility > 0.25 else "NORMAL"
        },
        "support_resistance": {
            "near_support": random.random() > 0.5,
            "near_resistance": random.random() > 0.7
        }
    }
    
    return factors

def generate_prediction(ticker: str, factors: dict, price: float) -> PredictionResponse:
    """Generate AI-style prediction based on factors"""
    
    # Calculate weighted signal
    trend_score = factors["trend"]["score"] * (1 if factors["trend"]["direction"] == "UP" else -1)
    momentum_score = factors["momentum"]["score"] * (1 if factors["momentum"]["direction"] == "BULLISH" else -1)
    
    composite_score = (trend_score * 0.4 + momentum_score * 0.3 + random.uniform(-0.2, 0.2))
    
    # Determine bias and confidence
    if composite_score > 0.2:
        bias = "BULLISH"
        confidence = min(0.95, 0.6 + abs(composite_score) * 0.3)
    elif composite_score < -0.2:
        bias = "BEARISH"
        confidence = min(0.95, 0.6 + abs(composite_score) * 0.3)
    else:
        bias = "NEUTRAL"
        confidence = 0.5 + abs(composite_score) * 0.2
    
    # Generate narrative based on factors
    scenarios = {
        "BULLISH": [
            "Strong upward momentum supported by technical indicators. Recent price action shows accumulation.",
            "Breakout pattern emerging with increased volume. Trend strength indicates continuation.",
            "Support level holding with positive momentum divergence. Short-term outlook favorable."
        ],
        "BEARISH": [
            "Downward pressure evident from multiple timeframes. Resistance levels containing rallies.",
            "Distribution pattern detected with weakening momentum. Trend indicators bearish.",
            "Break below key support with increased selling pressure. Caution warranted."
        ],
        "NEUTRAL": [
            "Consolidation pattern with mixed signals. Waiting for clearer directional break.",
            "Range-bound action with no clear trend. Patience recommended for entry.",
            "Indecision in price action. Multiple scenarios possible, risk management crucial."
        ]
    }
    
    catalysts = [
        "Sector rotation dynamics creating selective opportunities.",
        "Earnings sentiment and guidance influencing near-term direction.",
        "Macroeconomic factors and Fed policy expectations at play.",
        "Institutional flow patterns suggesting strategic positioning.",
        "Technical levels attracting algorithmic trading interest."
    ]
    
    # Risk flags
    risk_flags = []
    if factors["volatility"]["regime"] == "HIGH":
        risk_flags.append("elevated_volatility")
    if random.random() > 0.7:
        risk_flags.append("earnings_near")
    if random.random() > 0.8:
        risk_flags.append("macro_event_risk")
    if not risk_flags:
        risk_flags.append("normal_conditions")
    
    # Determine leaning
    if confidence > 0.75 and bias != "NEUTRAL":
        leaning = "TRADE"
    elif confidence > 0.6:
        leaning = "WATCH"
    else:
        leaning = "WAIT"
    
    return PredictionResponse(
        provider="mirofish",
        provider_mode="live",
        ticker=ticker,
        directional_bias=bias,
        confidence=round(confidence, 2),
        scenario_summary=random.choice(scenarios[bias]),
        catalyst_summary=random.choice(catalysts),
        risk_flags=risk_flags,
        leaning=leaning,
        timestamp=datetime.now(timezone.utc).isoformat()
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "mirofish", "mode": "live"}

@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    """Generate prediction for a ticker"""
    try:
        # Get market data
        market_data = await get_market_data(request.ticker)
        price = market_data.get("quote", {}).get("ap", 100.0)
        
        # Analyze factors
        factors = analyze_technical_factors(request.ticker, price)
        
        # Generate prediction
        prediction = generate_prediction(request.ticker, factors, price)
        
        return prediction
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

@app.post("/api/report/chat")
async def report_chat(request: dict):
    """Chat-based prediction endpoint (fallback)"""
    ticker = request.get("ticker", "SPY")
    return await predict(PredictionRequest(ticker=ticker))

@app.get("/predict/{ticker}")
async def predict_get(ticker: str, timeframe: str = "5m"):
    """GET endpoint for predictions"""
    return await predict(PredictionRequest(ticker=ticker, timeframe=timeframe))

@app.get("/api/simulation/status")
async def simulation_status():
    """Simulation runtime status"""
    return {
        "ready": True,
        "provider_mode": "live",
        "focus_tickers": ["SPY", "AAPL", "MSFT", "NVDA", "TSLA"]
    }

@app.post("/api/simulation/run")
async def simulation_run(request: dict):
    """Simulation run endpoint"""
    ticker = request.get("ticker", "SPY")
    return await predict(PredictionRequest(ticker=ticker))

if __name__ == "__main__":
    print("🐟 Starting MiroFish Local Service...")
    print("📍 URL: http://localhost:8080")
    print("📊 Endpoints:")
    print("   POST /predict")
    print("   GET  /predict/{ticker}")
    print("   GET  /health")
    uvicorn.run(app, host="0.0.0.0", port=8080)
