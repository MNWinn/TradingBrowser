#!/usr/bin/env python3
"""Simple agent fleet runner - no Redis required"""
import asyncio
import sys
import os
sys.path.insert(0, '/home/mnwinnwork/.openclaw/workspace/TradingBrowser/backend')
os.chdir('/home/mnwinnwork/.openclaw/workspace/TradingBrowser/backend')

# Set SQLite database
os.environ['DATABASE_URL'] = 'sqlite:///./tradingbrowser.db'

from app.services.agents import (
    technical_analysis_agent,
    regime_detection_agent,
)
from app.services.agents.fleet import (
    market_scanner_agent,
    momentum_agent,
    pattern_recognition_agent,
    support_resistance_agent,
    volume_profile_agent,
)

AGENTS = [
    ("Technical Analysis", technical_analysis_agent),
    ("Regime Detection", regime_detection_agent),
    ("Market Scanner", market_scanner_agent),
    ("Momentum", momentum_agent),
    ("Pattern Recognition", pattern_recognition_agent),
    ("Support/Resistance", support_resistance_agent),
    ("Volume Profile", volume_profile_agent),
]

async def run_agent(name, agent_func, ticker):
    """Run a single agent"""
    try:
        result = await agent_func(ticker)
        rec = result.get('recommendation', 'N/A') if isinstance(result, dict) else 'N/A'
        conf = result.get('confidence', 0) if isinstance(result, dict) else 0
        print(f"  ✅ {name}: {rec} ({conf:.2f})")
        return result
    except Exception as e:
        print(f"  ❌ {name}: {str(e)[:50]}")
        return None

async def main():
    tickers = ['SPY', 'AAPL', 'MSFT', 'NVDA', 'TSLA']
    
    print("🚀 Starting Market Research Fleet")
    print(f"📊 Tickers: {', '.join(tickers)}")
    print(f"🤖 Agents: {len(AGENTS)}")
    print("=" * 60)
    
    cycle = 0
    while True:
        cycle += 1
        print(f"\n📊 Cycle {cycle} - Analyzing markets...")
        
        for ticker in tickers:
            print(f"\n📈 {ticker}:")
            tasks = [run_agent(name, func, ticker) for name, func in AGENTS]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful = sum(1 for r in results if r is not None and not isinstance(r, Exception))
            print(f"   Completed: {successful}/{len(AGENTS)} agents")
        
        print(f"\n💤 Cycle {cycle} complete. Sleeping 60s...")
        print("-" * 60)
        await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Fleet stopped by user")
