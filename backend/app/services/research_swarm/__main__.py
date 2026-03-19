"""
Research Swarm Module - Continuous Market Analysis

This module provides a continuous research loop that:
1. Runs every 60 seconds
2. Analyzes SPY, QQQ, AAPL, MSFT, NVDA, TSLA
3. Uses TechnicalAnalysisAgent and RegimeDetectionAgent
4. Stores results in feature_snapshots and signal_outputs tables
5. Logs all activity
6. Runs as a background service

Usage:
    cd /home/mnwinnwork/.openclaw/workspace/TradingBrowser && python3 -m backend.app.services.research_swarm

Or directly:
    python3 backend/app/services/research_swarm/__main__.py
"""

import asyncio
import json
import logging
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# Add project root to path for imports (handle both module and direct execution)
project_root = "/home/mnwinnwork/.openclaw/workspace/TradingBrowser"
backend_root = "/home/mnwinnwork/.openclaw/workspace/TradingBrowser/backend"

if project_root not in sys.path:
    sys.path.insert(0, project_root)
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Import agents - try both import styles
try:
    from app.services.agents.technical_analysis import technical_analysis_agent
    from app.services.agents.regime_detection import regime_detection_agent
    from app.services.market_data import get_bars_snapshot, get_quote_snapshot
    from app.models.entities import FeatureSnapshot, SignalOutput, SwarmTask, SwarmAgentRun, SwarmConsensusOutput
    from app.models.entities import Base
except ImportError:
    # Fallback for when running as module
    from backend.app.services.agents.technical_analysis import technical_analysis_agent
    from backend.app.services.agents.regime_detection import regime_detection_agent
    from backend.app.services.market_data import get_bars_snapshot, get_quote_snapshot
    from backend.app.models.entities import FeatureSnapshot, SignalOutput, SwarmTask, SwarmAgentRun, SwarmConsensusOutput
    from backend.app.models.entities import Base

# Database configuration - using SQLite as specified
DATABASE_URL = "sqlite:///./research_swarm.db"


class ResearchSwarm:
    """
    Continuous market research swarm that analyzes tickers every 60 seconds.
    
    Attributes:
        tickers: List of tickers to analyze
        interval_seconds: Time between analysis cycles (default 60)
        running: Whether the swarm is currently running
        db_session: Database session for persistence
    """
    
    DEFAULT_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"]
    
    def __init__(
        self,
        tickers: Optional[list[str]] = None,
        interval_seconds: int = 60,
        database_url: str = DATABASE_URL
    ):
        self.tickers = tickers or self.DEFAULT_TICKERS
        self.interval_seconds = interval_seconds
        self.running = False
        self._shutdown_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self.database_url = database_url
        
        # Initialize database
        self.engine = create_engine(self.database_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Create tables
        self._init_database()
        
        logger.info(f"ResearchSwarm initialized with tickers: {self.tickers}")
        logger.info(f"Database: {self.database_url}")
        logger.info(f"Analysis interval: {self.interval_seconds}s")
    
    def _init_database(self) -> None:
        """Initialize database tables."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created/verified")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            raise
    
    def get_db(self) -> Session:
        """Get database session."""
        return self.SessionLocal()
    
    async def start(self) -> None:
        """Start the continuous research loop."""
        if self.running:
            logger.warning("ResearchSwarm is already running")
            return
        
        self.running = True
        self._shutdown_event.clear()
        logger.info("=" * 60)
        logger.info("Research Swarm Starting")
        logger.info("=" * 60)
        
        try:
            await self._research_loop()
        except asyncio.CancelledError:
            logger.info("Research loop cancelled")
        except Exception as e:
            logger.exception(f"Research loop error: {e}")
        finally:
            self.running = False
            logger.info("Research Swarm stopped")
    
    async def stop(self) -> None:
        """Stop the research loop gracefully."""
        logger.info("Stopping ResearchSwarm...")
        self.running = False
        self._shutdown_event.set()
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("ResearchSwarm stopped")
    
    async def _research_loop(self) -> None:
        """Main research loop - runs continuously until stopped."""
        cycle_count = 0
        
        while self.running and not self._shutdown_event.is_set():
            cycle_count += 1
            cycle_start = time.perf_counter()
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Research Cycle #{cycle_count} - {datetime.now(timezone.utc).isoformat()}")
            logger.info(f"{'='*60}")
            
            try:
                await self._analyze_all_tickers()
            except Exception as e:
                logger.exception(f"Error in research cycle #{cycle_count}: {e}")
            
            cycle_duration = time.perf_counter() - cycle_start
            logger.info(f"Cycle #{cycle_count} completed in {cycle_duration:.2f}s")
            
            # Calculate sleep time
            sleep_time = max(0, self.interval_seconds - cycle_duration)
            
            if sleep_time > 0 and self.running:
                logger.info(f"Sleeping for {sleep_time:.2f}s until next cycle...")
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=sleep_time
                    )
                except asyncio.TimeoutError:
                    pass  # Normal - time to run next cycle
    
    async def _analyze_all_tickers(self) -> None:
        """Analyze all configured tickers."""
        for ticker in self.tickers:
            if not self.running:
                break
            
            try:
                await self._analyze_ticker(ticker)
                # Small delay between tickers to avoid rate limits
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.exception(f"Error analyzing {ticker}: {e}")
    
    async def _analyze_ticker(self, ticker: str) -> dict[str, Any]:
        """
        Analyze a single ticker using all available agents.
        
        Args:
            ticker: Stock symbol to analyze
            
        Returns:
            Dictionary with analysis results
        """
        logger.info(f"\n--- Analyzing {ticker} ---")
        task_id = f"swarm-{ticker}-{int(time.time())}-{uuid.uuid4().hex[:4]}"
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
            logger.error(f"Failed to create task record: {e}")
            task = None
        finally:
            db.close()
        
        results = {
            "ticker": ticker,
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agents": {}
        }
        
        # Run Technical Analysis Agent
        try:
            logger.info(f"[{ticker}] Running Technical Analysis...")
            ta_result = await technical_analysis_agent(ticker, timeframe="5m", limit=100)
            results["agents"]["technical_analysis"] = ta_result
            logger.info(f"[{ticker}] TA Signal: {ta_result.get('recommendation')} (confidence: {ta_result.get('confidence')})")
            
            # Store TA features
            await self._store_feature_snapshot(ticker, ta_result)
            
            # Store agent run
            await self._store_agent_run(task_id, ta_result, start_time)
            
        except Exception as e:
            logger.exception(f"[{ticker}] Technical analysis failed: {e}")
            results["agents"]["technical_analysis"] = {"error": str(e)}
        
        # Run Regime Detection Agent
        try:
            logger.info(f"[{ticker}] Running Regime Detection...")
            regime_result = await regime_detection_agent(ticker)
            results["agents"]["regime_detection"] = regime_result
            regime = regime_result.get('regime', 'unknown')
            logger.info(f"[{ticker}] Regime: {regime} (confidence: {regime_result.get('confidence')})")
            
            # Store regime in features
            await self._store_regime_snapshot(ticker, regime_result)
            
            # Store agent run
            await self._store_agent_run(task_id, regime_result, start_time)
            
        except Exception as e:
            logger.exception(f"[{ticker}] Regime detection failed: {e}")
            results["agents"]["regime_detection"] = {"error": str(e)}
        
        # Generate consensus signal
        try:
            signal = await self._generate_signal(ticker, results["agents"], task_id)
            results["signal"] = signal
            logger.info(f"[{ticker}] Signal: {signal.get('action')} (confidence: {signal.get('confidence')})")
            
            # Store signal output
            await self._store_signal_output(signal)
            
        except Exception as e:
            logger.exception(f"[{ticker}] Signal generation failed: {e}")
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
            logger.error(f"Failed to update task record: {e}")
        finally:
            db.close()
        
        logger.info(f"[{ticker}] Analysis complete in {elapsed_ms}ms")
        
        return results
    
    async def _store_feature_snapshot(self, ticker: str, ta_result: dict) -> None:
        """Store technical analysis features in database."""
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
                "data_source": ta_result.get("data_source"),
                "simulated": ta_result.get("simulated"),
            }
            
            snapshot = FeatureSnapshot(
                ticker=ticker,
                features=features,
                regime=None  # Will be updated by regime detection
            )
            db.add(snapshot)
            db.commit()
            logger.debug(f"[{ticker}] Feature snapshot stored (id={snapshot.id})")
        except Exception as e:
            logger.error(f"[{ticker}] Failed to store feature snapshot: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def _store_regime_snapshot(self, ticker: str, regime_result: dict) -> None:
        """Store regime detection results in database."""
        db = self.get_db()
        try:
            regime = regime_result.get("regime")
            metrics = regime_result.get("metrics", {})
            
            features = {
                "regime": regime,
                "regime_confidence": regime_result.get("confidence"),
                "adx": metrics.get("adx"),
                "plus_di": metrics.get("plus_di"),
                "minus_di": metrics.get("minus_di"),
                "volatility_annualized": metrics.get("volatility_annualized"),
                "volatility_percentile": metrics.get("volatility_percentile"),
                "price_change_5d_pct": metrics.get("price_change_5d_pct"),
                "regime_recommendation": regime_result.get("recommendation"),
            }
            
            snapshot = FeatureSnapshot(
                ticker=ticker,
                features=features,
                regime=regime
            )
            db.add(snapshot)
            db.commit()
            logger.debug(f"[{ticker}] Regime snapshot stored (id={snapshot.id})")
        except Exception as e:
            logger.error(f"[{ticker}] Failed to store regime snapshot: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def _store_agent_run(self, task_id: str, agent_result: dict, start_time: float) -> None:
        """Store agent run results in database."""
        db = self.get_db()
        try:
            agent_name = agent_result.get("agent", "unknown")
            
            # Calculate latency
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
            logger.debug(f"Agent run stored: {agent_name} (id={run.id})")
        except Exception as e:
            logger.error(f"Failed to store agent run: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def _generate_signal(
        self,
        ticker: str,
        agent_results: dict[str, Any],
        task_id: str
    ) -> dict[str, Any]:
        """
        Generate trading signal from agent results.
        
        Args:
            ticker: Stock symbol
            agent_results: Dictionary of agent outputs
            task_id: Task identifier
            
        Returns:
            Signal dictionary
        """
        # Collect recommendations
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
            # Count votes
            long_votes = sum(1 for r in recommendations if r == "LONG")
            short_votes = sum(1 for r in recommendations if r == "SHORT")
            watch_votes = sum(1 for r in recommendations if r in ["WATCHLIST", "MEAN_REVERSION"])
            no_trade_votes = sum(1 for r in recommendations if r in ["NO_TRADE", "REDUCE_SIZE"])
            
            if long_votes >= 2:
                action = "LONG"
            elif short_votes >= 2:
                action = "SHORT"
            elif watch_votes >= 2:
                action = "WATCHLIST"
            elif no_trade_votes >= 2:
                action = "NO_TRADE"
            elif long_votes >= 1:
                action = "LONG"
            elif short_votes >= 1:
                action = "SHORT"
            else:
                action = "NEUTRAL"
            
            # Calculate confidence
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
            confidence = round(min(avg_confidence * 1.2, 0.99), 2)  # Boost slightly, cap at 0.99
        
        # Get current price
        try:
            quote = get_quote_snapshot(ticker)
            current_price = quote.get("price")
        except Exception:
            current_price = None
        
        # Calculate consensus/disagreement scores
        unique_recs = len(set(recommendations))
        consensus_score = round(1.0 - (unique_recs - 1) / max(len(recommendations), 1), 2)
        disagreement_score = round((unique_recs - 1) / max(len(recommendations), 1), 2)
        
        signal = {
            "ticker": ticker,
            "action": action,
            "confidence": confidence,
            "consensus_score": consensus_score,
            "disagreement_score": disagreement_score,
            "current_price": current_price,
            "reason_codes": ["RESEARCH_SWARM", "TECHNICAL_ANALYSIS", "REGIME_DETECTION"],
            "explanation": f"Signal generated from {len(recommendations)} agents. Consensus: {consensus_score}",
            "execution_eligibility": {
                "research": False,
                "paper": action in ["LONG", "SHORT"],
                "live": False,
            },
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        return signal
    
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
                model_version="research_swarm_v1"
            )
            db.add(output)
            db.commit()
            logger.debug(f"Signal output stored (id={output.id})")
        except Exception as e:
            logger.error(f"Failed to store signal output: {e}")
            db.rollback()
        finally:
            db.close()
    
    def get_stats(self) -> dict[str, Any]:
        """Get swarm statistics."""
        db = self.get_db()
        try:
            from sqlalchemy import func
            
            # Count feature snapshots
            feature_count = db.query(FeatureSnapshot).count()
            
            # Count signals
            signal_count = db.query(SignalOutput).count()
            
            # Count agent runs
            agent_run_count = db.query(SwarmAgentRun).count()
            
            # Get latest signals per ticker
            latest_signals = {}
            for ticker in self.tickers:
                signal = db.query(SignalOutput).filter(
                    SignalOutput.ticker == ticker
                ).order_by(SignalOutput.id.desc()).first()
                if signal:
                    latest_signals[ticker] = {
                        "action": signal.action,
                        "confidence": signal.confidence,
                        "created_at": signal.created_at.isoformat() if signal.created_at else None
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


async def main():
    """Main entry point for the research swarm."""
    swarm = ResearchSwarm()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        asyncio.create_task(swarm.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await swarm.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await swarm.stop()
        
        # Print final stats
        stats = swarm.get_stats()
        logger.info("\n" + "=" * 60)
        logger.info("Final Statistics:")
        logger.info(f"  Feature Snapshots: {stats['feature_snapshots']}")
        logger.info(f"  Signal Outputs: {stats['signal_outputs']}")
        logger.info(f"  Agent Runs: {stats['agent_runs']}")
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
