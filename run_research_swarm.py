#!/usr/bin/env python3
"""
Research Swarm Service Runner

Run the research swarm as a background service:
    python3 run_research_swarm.py

Options:
    --tickers SPY,QQQ,AAPL    # Custom tickers (default: SPY,QQQ,AAPL,MSFT,NVDA,TSLA)
    --interval 30             # Analysis interval in seconds (default: 60)
    --once                    # Run one cycle and exit
"""

import argparse
import asyncio
import sys
import os

# Add paths for imports
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if os.path.join(project_root, 'backend') not in sys.path:
    sys.path.insert(0, os.path.join(project_root, 'backend'))

from backend.app.services.research_swarm import ResearchSwarm


def parse_args():
    parser = argparse.ArgumentParser(description='Research Swarm - Continuous Market Analysis')
    parser.add_argument(
        '--tickers',
        type=str,
        default='SPY,QQQ,AAPL,MSFT,NVDA,TSLA',
        help='Comma-separated list of tickers to analyze (default: SPY,QQQ,AAPL,MSFT,NVDA,TSLA)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Analysis interval in seconds (default: 60)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run one analysis cycle and exit'
    )
    parser.add_argument(
        '--database',
        type=str,
        default='sqlite:///./research_swarm.db',
        help='Database URL (default: sqlite:///./research_swarm.db)'
    )
    return parser.parse_args()


async def run_once(swarm: ResearchSwarm):
    """Run a single analysis cycle."""
    print("Running single analysis cycle...")
    await swarm._analyze_all_tickers()
    
    stats = swarm.get_stats()
    print("\n" + "=" * 60)
    print("Analysis Complete!")
    print("=" * 60)
    print(f"Feature Snapshots: {stats['feature_snapshots']}")
    print(f"Signal Outputs: {stats['signal_outputs']}")
    print(f"Agent Runs: {stats['agent_runs']}")
    print("\nLatest Signals:")
    for ticker, signal in stats['latest_signals'].items():
        print(f"  {ticker}: {signal['action']} (confidence: {signal['confidence']:.2f})")


async def main():
    args = parse_args()
    
    tickers = [t.strip().upper() for t in args.tickers.split(',')]
    
    print("=" * 60)
    print("Research Swarm Configuration")
    print("=" * 60)
    print(f"Tickers: {tickers}")
    print(f"Interval: {args.interval}s")
    print(f"Database: {args.database}")
    print(f"Mode: {'Single run' if args.once else 'Continuous'}")
    print("=" * 60)
    
    swarm = ResearchSwarm(
        tickers=tickers,
        interval_seconds=args.interval,
        database_url=args.database
    )
    
    if args.once:
        await run_once(swarm)
    else:
        import signal
        
        def signal_handler(sig, frame):
            print(f"\nReceived signal {sig}, shutting down...")
            asyncio.create_task(swarm.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            await swarm.start()
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received")
        finally:
            await swarm.stop()
            
            stats = swarm.get_stats()
            print("\n" + "=" * 60)
            print("Final Statistics:")
            print("=" * 60)
            print(f"  Feature Snapshots: {stats['feature_snapshots']}")
            print(f"  Signal Outputs: {stats['signal_outputs']}")
            print(f"  Agent Runs: {stats['agent_runs']}")
            print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
