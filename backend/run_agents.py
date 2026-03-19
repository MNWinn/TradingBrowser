#!/usr/bin/env python3
"""
Agent Launcher - Simple SQLite-based Research Swarm Runner

Run without Redis dependency:
    cd /home/mnwinnwork/.openclaw/workspace/TradingBrowser/backend
    python3 run_agents.py

Or from project root:
    python3 backend/run_agents.py

Options:
    --tickers SPY,QQQ,AAPL    # Custom tickers (default: SPY,QQQ,AAPL,MSFT,NVDA,TSLA)
    --interval 60             # Analysis interval in seconds (default: 60)
    --once                    # Run one cycle and exit
    --database sqlite:///./agents.db  # Database URL
"""

import argparse
import asyncio
import sys
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

# Setup paths
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = script_dir
project_root = os.path.dirname(backend_dir)

# Add paths for imports
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# SQLAlchemy imports
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Import models
from app.models.entities import Base, FeatureSnapshot, SignalOutput, SwarmTask, SwarmAgentRun

# Import agents
from app.services.agents.technical_analysis import technical_analysis_agent
from app.services.agents.regime_detection import regime_detection_agent
from app.services.agents.fleet.mirofish_assessment import run_mirofish_assessment

# Import market data
from app.services.market_data import get_quote_snapshot


class SimpleAgentRunner:
    """
    Simple agent runner that uses SQLite only - no Redis required.
    
    Runs the research pipeline with:
    - Technical Analysis
    - Regime Detection  
    - MiroFish Assessment
    - Signal generation and storage
    """
    
    DEFAULT_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"]
    
    def __init__(
        self,
        tickers: Optional[list[str]] = None,
        interval_seconds: int = 60,
        database_url: str = "sqlite:///./agents.db"
    ):
        self.tickers = tickers or self.DEFAULT_TICKERS
        self.interval_seconds = interval_seconds
        self.database_url = database_url
        self.running = False
        self._shutdown_event = asyncio.Event()
        
        # Initialize database
        print(f"[INIT] Connecting to database: {database_url}")
        self.engine = create_engine(self.database_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self._init_database()
        
        print(f"[INIT] Agent Runner initialized")
        print(f"[INIT] Tickers: {self.tickers}")
        print(f"[INIT] Interval: {interval_seconds}s")
    
    def _init_database(self) -> None:
        """Initialize database tables."""
        try:
            Base.metadata.create_all(bind=self.engine)
            print("[INIT] Database tables created/verified")
        except Exception as e:
            print(f"[ERROR] Database initialization failed: {e}")
            raise
    
    def get_db(self) -> Session:
        """Get database session."""
        return self.SessionLocal()
    
    async def start(self) -> None:
        """Start the continuous analysis loop."""
        if self.running:
            print("[WARN] Agent Runner is already running")
            return
        
        self.running = True
        self._shutdown_event.clear()
        
        print("\n" + "=" * 60)
        print("AGENT RUNNER STARTED")
        print("=" * 60)
        print(f"Mode: Continuous (interval={self.interval_seconds}s)")
        print(f"Database: {self.database_url}")
        print("=" * 60 + "\n")
        
        try:
            await self._analysis_loop()
        except asyncio.CancelledError:
            print("[INFO] Analysis loop cancelled")
        except Exception as e:
            print(f"[ERROR] Analysis loop error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False
            print("[INFO] Agent Runner stopped")
    
    async def stop(self) -> None:
        """Stop the analysis loop gracefully."""
        print("[INFO] Stopping Agent Runner...")
        self.running = False
        self._shutdown_event.set()
    
    async def run_once(self) -> dict:
        """Run a single analysis cycle."""
        print("\n" + "=" * 60)
        print(f"SINGLE RUN - {datetime.now(timezone.utc).isoformat()}")
        print("=" * 60)
        
        results = {}
        for ticker in self.tickers:
            try:
                result = await self._analyze_ticker(ticker)
                results[ticker] = result
                await asyncio.sleep(0.5)  # Small delay between tickers
            except Exception as e:
                print(f"[ERROR] Failed to analyze {ticker}: {e}")
                results[ticker] = {"error": str(e)}
        
        # Print summary
        print("\n" + "-" * 60)
        print("SUMMARY")
        print("-" * 60)
        for ticker, result in results.items():
            signal = result.get("signal", {})
            action = signal.get("action", "ERROR")
            confidence = signal.get("confidence", 0)
            print(f"  {ticker}: {action} (confidence: {confidence:.2f})")
        print("-" * 60)
        
        return results
    
    async def _analysis_loop(self) -> None:
        """Main analysis loop."""
        cycle_count = 0
        
        while self.running and not self._shutdown_event.is_set():
            cycle_count += 1
            cycle_start = time.perf_counter()
            
            print(f"\n{'='*60}")
            print(f"CYCLE #{cycle_count} - {datetime.now(timezone.utc).isoformat()}")
            print(f"{'='*60}")
            
            try:
                await self.run_once()
            except Exception as e:
                print(f"[ERROR] Cycle #{cycle_count} failed: {e}")
            
            cycle_duration = time.perf_counter() - cycle_start
            sleep_time = max(0, self.interval_seconds - cycle_duration)
            
            print(f"\n[CYCLE #{cycle_count}] Completed in {cycle_duration:.2f}s")
            
            if sleep_time > 0 and self.running:
                print(f"[CYCLE #{cycle_count}] Sleeping for {sleep_time:.2f}s...")
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=sleep_time
                    )
                except asyncio.TimeoutError:
                    pass  # Time for next cycle
    
    async def _analyze_ticker(self, ticker: str) -> dict[str, Any]:
        """Analyze a single ticker using all agents."""
        print(f"\n[ANALYZE] {ticker}")
        print(f"[ANALYZE] {'-' * 40}")
        
        task_id = f"agent-{ticker}-{int(time.time())}-{uuid.uuid4().hex[:4]}"
        start_time = time.perf_counter()
        
        # Create task record
        db = self.get_db()
        try:
            task = SwarmTask(
                task_id=task_id,
                ticker=ticker,
                mode="research",
                status="running",
                started_at=datetime.now(timezone.utc)
            )
            db.add(task)
            db.commit()
        except Exception as e:
            print(f"[WARN] Failed to create task record: {e}")
            task = None
        finally:
            db.close()
        
        results = {
            "ticker": ticker,
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agents": {}
        }
        
        # 1. Technical Analysis
        try:
            print(f"[ANALYZE] {ticker} - Running Technical Analysis...")
            ta_result = await technical_analysis_agent(ticker, timeframe="5m", limit=100)
            results["agents"]["technical_analysis"] = ta_result
            rec = ta_result.get("recommendation", "UNKNOWN")
            conf = ta_result.get("confidence", 0)
            print(f"[ANALYZE] {ticker} - TA: {rec} (confidence: {conf:.2f})")
            
            await self._store_feature_snapshot(ticker, ta_result)
            await self._store_agent_run(task_id, "technical_analysis", ta_result, start_time)
        except Exception as e:
            print(f"[ERROR] {ticker} - Technical analysis failed: {e}")
            results["agents"]["technical_analysis"] = {"error": str(e)}
        
        # 2. Regime Detection
        try:
            print(f"[ANALYZE] {ticker} - Running Regime Detection...")
            regime_result = await regime_detection_agent(ticker)
            results["agents"]["regime_detection"] = regime_result
            regime = regime_result.get("regime", "unknown")
            conf = regime_result.get("confidence", 0)
            print(f"[ANALYZE] {ticker} - Regime: {regime} (confidence: {conf:.2f})")
            
            await self._store_regime_snapshot(ticker, regime_result)
            await self._store_agent_run(task_id, "regime_detection", regime_result, start_time)
        except Exception as e:
            print(f"[ERROR] {ticker} - Regime detection failed: {e}")
            results["agents"]["regime_detection"] = {"error": str(e)}
        
        # 3. MiroFish Assessment
        try:
            print(f"[ANALYZE] {ticker} - Running MiroFish Assessment...")
            miro_result = await run_mirofish_assessment(ticker, deep_mode=False)
            results["agents"]["mirofish"] = miro_result
            rec = miro_result.get("recommendation", "UNKNOWN")
            conf = miro_result.get("confidence", 0)
            print(f"[ANALYZE] {ticker} - MiroFish: {rec} (confidence: {conf:.2f})")
            
            await self._store_agent_run(task_id, "mirofish_assessment", miro_result, start_time)
        except Exception as e:
            print(f"[ERROR] {ticker} - MiroFish assessment failed: {e}")
            results["agents"]["mirofish"] = {"error": str(e)}
        
        # Generate consensus signal
        try:
            signal = await self._generate_signal(ticker, results["agents"], task_id)
            results["signal"] = signal
            print(f"[ANALYZE] {ticker} - Signal: {signal.get('action')} (confidence: {signal.get('confidence'):.2f})")
            
            await self._store_signal_output(signal)
        except Exception as e:
            print(f"[ERROR] {ticker} - Signal generation failed: {e}")
            results["signal"] = {"error": str(e)}
        
        # Update task completion
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        results["latency_ms"] = elapsed_ms
        
        db = self.get_db()
        try:
            if task:
                task.status = "completed"
                task.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as e:
            print(f"[WARN] Failed to update task record: {e}")
        finally:
            db.close()
        
        print(f"[ANALYZE] {ticker} - Complete in {elapsed_ms}ms")
        
        return results
    
    async def _store_feature_snapshot(self, ticker: str, ta_result: dict) -> None:
        """Store technical analysis features."""
        db = self.get_db()
        try:
            indicators = ta_result.get("indicators", {})
            features = {
                "rsi": indicators.get("rsi"),
                "macd": indicators.get("macd"),
                "vwap": indicators.get("vwap"),
                "bollinger_bands": indicators.get("bollinger_bands"),
                "price": indicators.get("price"),
                "signals": ta_result.get("signals", []),
                "ta_recommendation": ta_result.get("recommendation"),
                "ta_confidence": ta_result.get("confidence"),
            }
            
            snapshot = FeatureSnapshot(
                ticker=ticker,
                features=features,
                regime=None
            )
            db.add(snapshot)
            db.commit()
        except Exception as e:
            print(f"[WARN] Failed to store feature snapshot: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def _store_regime_snapshot(self, ticker: str, regime_result: dict) -> None:
        """Store regime detection results."""
        db = self.get_db()
        try:
            regime = regime_result.get("regime")
            metrics = regime_result.get("metrics", {})
            
            features = {
                "regime": regime,
                "regime_confidence": regime_result.get("confidence"),
                "adx": metrics.get("adx"),
                "volatility_annualized": metrics.get("volatility_annualized"),
                "price_change_5d_pct": metrics.get("price_change_5d_pct"),
            }
            
            snapshot = FeatureSnapshot(
                ticker=ticker,
                features=features,
                regime=regime
            )
            db.add(snapshot)
            db.commit()
        except Exception as e:
            print(f"[WARN] Failed to store regime snapshot: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def _store_agent_run(
        self, 
        task_id: str, 
        agent_name: str, 
        agent_result: dict, 
        start_time: float
    ) -> None:
        """Store agent run results."""
        db = self.get_db()
        try:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            
            run = SwarmAgentRun(
                task_id=task_id,
                agent_name=agent_name,
                recommendation=agent_result.get("recommendation"),
                confidence=agent_result.get("confidence"),
                latency_ms=elapsed_ms,
                output=agent_result
            )
            db.add(run)
            db.commit()
        except Exception as e:
            print(f"[WARN] Failed to store agent run: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def _generate_signal(
        self,
        ticker: str,
        agent_results: dict[str, Any],
        task_id: str
    ) -> dict[str, Any]:
        """Generate trading signal from agent results."""
        recommendations = []
        confidences = []
        
        for agent_name, result in agent_results.items():
            if isinstance(result, dict) and "recommendation" in result:
                recommendations.append(result["recommendation"])
                confidences.append(result.get("confidence", 0.5))
        
        # Simple consensus logic
        if not recommendations:
            action = "NO_TRADE"
            confidence = 0.0
        else:
            long_votes = sum(1 for r in recommendations if r == "LONG")
            short_votes = sum(1 for r in recommendations if r == "SHORT")
            watch_votes = sum(1 for r in recommendations if r in ["WATCHLIST", "MEAN_REVERSION"])
            
            if long_votes >= 2:
                action = "LONG"
            elif short_votes >= 2:
                action = "SHORT"
            elif watch_votes >= 2:
                action = "WATCHLIST"
            elif long_votes >= 1:
                action = "LONG"
            elif short_votes >= 1:
                action = "SHORT"
            else:
                action = "NEUTRAL"
            
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
            confidence = round(min(avg_confidence * 1.2, 0.99), 2)
        
        # Get current price
        try:
            quote = get_quote_snapshot(ticker)
            current_price = quote.get("price")
        except Exception:
            current_price = None
        
        unique_recs = len(set(recommendations))
        consensus_score = round(1.0 - (unique_recs - 1) / max(len(recommendations), 1), 2)
        disagreement_score = round((unique_recs - 1) / max(len(recommendations), 1), 2)
        
        return {
            "ticker": ticker,
            "action": action,
            "confidence": confidence,
            "consensus_score": consensus_score,
            "disagreement_score": disagreement_score,
            "current_price": current_price,
            "reason_codes": ["AGENT_RUNNER", "TECHNICAL_ANALYSIS", "REGIME_DETECTION", "MIROFISH"],
            "explanation": f"Signal from {len(recommendations)} agents. Consensus: {consensus_score}",
            "execution_eligibility": {
                "research": False,
                "paper": action in ["LONG", "SHORT"],
                "live": False,
            },
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    async def _store_signal_output(self, signal: dict) -> None:
        """Store signal output in database."""
        db = self.get_db()
        try:
            output = SignalOutput(
                ticker=signal["ticker"],
                action=signal["action"],
                confidence=signal["confidence"],
                consensus_score=signal["consensus_score"],
                disagreement_score=signal["disagreement_score"],
                reason_codes=signal.get("reason_codes", []),
                explanation=signal.get("explanation", ""),
                execution_eligibility=signal.get("execution_eligibility", {}),
                model_version="agent_runner_v1"
            )
            db.add(output)
            db.commit()
        except Exception as e:
            print(f"[WARN] Failed to store signal output: {e}")
            db.rollback()
        finally:
            db.close()
    
    def get_stats(self) -> dict:
        """Get runner statistics."""
        db = self.get_db()
        try:
            feature_count = db.query(FeatureSnapshot).count()
            signal_count = db.query(SignalOutput).count()
            agent_run_count = db.query(SwarmAgentRun).count()
            
            latest_signals = {}
            for ticker in self.tickers:
                signal = db.query(SignalOutput).filter(
                    SignalOutput.ticker == ticker
                ).order_by(SignalOutput.id.desc()).first()
                if signal:
                    latest_signals[ticker] = {
                        "action": signal.action,
                        "confidence": signal.confidence,
                    }
            
            return {
                "running": self.running,
                "tickers": self.tickers,
                "interval_seconds": self.interval_seconds,
                "database_url": self.database_url,
                "feature_snapshots": feature_count,
                "signal_outputs": signal_count,
                "agent_runs": agent_run_count,
                "latest_signals": latest_signals,
            }
        finally:
            db.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Agent Launcher - SQLite-based Research Swarm"
    )
    parser.add_argument(
        "--tickers",
        type=str,
        default="SPY,QQQ,AAPL,MSFT,NVDA,TSLA",
        help="Comma-separated list of tickers (default: SPY,QQQ,AAPL,MSFT,NVDA,TSLA)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Analysis interval in seconds (default: 60)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one analysis cycle and exit"
    )
    parser.add_argument(
        "--database",
        type=str,
        default="sqlite:///./agents.db",
        help="Database URL (default: sqlite:///./agents.db)"
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    
    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    
    runner = SimpleAgentRunner(
        tickers=tickers,
        interval_seconds=args.interval,
        database_url=args.database
    )
    
    if args.once:
        await runner.run_once()
        
        # Print stats
        stats = runner.get_stats()
        print("\n" + "=" * 60)
        print("STATISTICS")
        print("=" * 60)
        print(f"Feature Snapshots: {stats['feature_snapshots']}")
        print(f"Signal Outputs: {stats['signal_outputs']}")
        print(f"Agent Runs: {stats['agent_runs']}")
        print("=" * 60)
    else:
        # Setup signal handlers
        import signal
        
        def signal_handler(sig, frame):
            print(f"\n[INFO] Received signal {sig}, shutting down...")
            asyncio.create_task(runner.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            await runner.start()
        except KeyboardInterrupt:
            print("\n[INFO] Keyboard interrupt received")
        finally:
            await runner.stop()
            
            # Print final stats
            stats = runner.get_stats()
            print("\n" + "=" * 60)
            print("FINAL STATISTICS")
            print("=" * 60)
            print(f"Feature Snapshots: {stats['feature_snapshots']}")
            print(f"Signal Outputs: {stats['signal_outputs']}")
            print(f"Agent Runs: {stats['agent_runs']}")
            print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
