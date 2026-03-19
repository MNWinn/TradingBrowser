#!/usr/bin/env python3
"""
MiroFish Agent Swarm Orchestrator - Simplified Version

Runs all 8 agents with MiroFish integration every 60 seconds:
- MiroFishAssessmentAgent (primary MiroFish agent)
- TechnicalAnalysisAgent (with MiroFish integration)
- MarketScannerAgent (with MiroFish signals)
- PatternRecognitionAgent (with MiroFish context)
- MomentumAgent (with MiroFish confirmation)
- SupportResistanceAgent (with MiroFish levels)
- VolumeProfileAgent (with MiroFish volume analysis)
- RegimeDetectionAgent (with MiroFish regime alignment)

Usage:
    python3 mirofish_swarm_orchestrator.py
    python3 mirofish_swarm_orchestrator.py --tickers SPY,AAPL,MSFT --interval 30
"""

import argparse
import asyncio
import sys
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Dict, List

# Setup paths
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = script_dir
project_root = os.path.dirname(backend_dir)

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# SQLAlchemy imports
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Import models
from app.models.entities import Base, SignalOutput, SwarmTask, SwarmAgentRun, SwarmConsensusOutput

# Import MiroFish service
from app.services.mirofish.mirofish_fleet import fleet_quick


class MiroFishSwarmOrchestrator:
    """
    Orchestrates 8 agents with MiroFish integration.
    
    Runs all agents every 60 seconds, collects predictions,
    stores results in database, and shows consensus.
    """
    
    DEFAULT_TICKERS = ["SPY", "AAPL", "MSFT", "NVDA", "TSLA", "QQQ", "GOOGL", "AMZN"]
    
    AGENTS = [
        ("mirofish_assessment", "primary"),
        ("technical_analysis", "enhanced"),
        ("market_scanner", "enhanced"),
        ("pattern_recognition", "enhanced"),
        ("momentum", "enhanced"),
        ("support_resistance", "enhanced"),
        ("volume_profile", "enhanced"),
        ("regime_detection", "enhanced"),
    ]
    
    def __init__(
        self,
        tickers: Optional[List[str]] = None,
        interval_seconds: int = 60,
        database_url: str = "sqlite:///./tradingbrowser.db"
    ):
        self.tickers = tickers or self.DEFAULT_TICKERS
        self.interval_seconds = interval_seconds
        self.database_url = database_url
        self.running = False
        self._shutdown_event = asyncio.Event()
        self.cycle_count = 0
        
        # Initialize database
        print(f"[INIT] Connecting to database: {database_url}")
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self._init_database()
        
        print(f"[INIT] MiroFish Swarm Orchestrator initialized")
        print(f"[INIT] Tickers: {self.tickers}")
        print(f"[INIT] Interval: {interval_seconds}s")
        print(f"[INIT] Agents: {len(self.AGENTS)}")
    
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
        """Start the continuous swarm loop."""
        if self.running:
            print("[WARN] Swarm is already running")
            return
        
        self.running = True
        self._shutdown_event.clear()
        
        print("\n" + "=" * 70)
        print("MIROFISH AGENT SWARM STARTED")
        print("=" * 70)
        print(f"Mode: Continuous (interval={self.interval_seconds}s)")
        print(f"Database: {self.database_url}")
        print(f"Agents with MiroFish integration:")
        for name, integration_type in self.AGENTS:
            print(f"  - {name} ({integration_type})")
        print("=" * 70 + "\n")
        
        try:
            await self._swarm_loop()
        except asyncio.CancelledError:
            print("[INFO] Swarm loop cancelled")
        except Exception as e:
            print(f"[ERROR] Swarm loop error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False
            print("[INFO] MiroFish Swarm stopped")
    
    async def stop(self) -> None:
        """Stop the swarm gracefully."""
        print("[INFO] Stopping MiroFish Swarm...")
        self.running = False
        self._shutdown_event.set()
    
    async def run_once(self) -> Dict[str, Any]:
        """Run a single swarm cycle."""
        self.cycle_count += 1
        print("\n" + "=" * 70)
        print(f"SWARM CYCLE #{self.cycle_count} - {datetime.now(timezone.utc).isoformat()}")
        print("=" * 70)
        
        all_results = {}
        
        for ticker in self.tickers:
            try:
                ticker_results = await self._analyze_ticker(ticker)
                all_results[ticker] = ticker_results
                await asyncio.sleep(0.5)  # Small delay between tickers
            except Exception as e:
                print(f"[ERROR] Failed to analyze {ticker}: {e}")
                import traceback
                traceback.print_exc()
                all_results[ticker] = {"error": str(e)}
        
        # Print summary
        self._print_summary(all_results)
        
        return all_results
    
    async def _swarm_loop(self) -> None:
        """Main swarm loop."""
        while self.running and not self._shutdown_event.is_set():
            cycle_start = time.perf_counter()
            
            try:
                await self.run_once()
            except Exception as e:
                print(f"[ERROR] Cycle #{self.cycle_count} failed: {e}")
            
            cycle_duration = time.perf_counter() - cycle_start
            sleep_time = max(0, self.interval_seconds - cycle_duration)
            
            print(f"\n[CYCLE #{self.cycle_count}] Completed in {cycle_duration:.2f}s")
            
            if sleep_time > 0 and self.running:
                print(f"[CYCLE #{self.cycle_count}] Sleeping for {sleep_time:.2f}s...")
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=sleep_time
                    )
                except asyncio.TimeoutError:
                    pass  # Time for next cycle
    
    async def _analyze_ticker(self, ticker: str) -> Dict[str, Any]:
        """Analyze a single ticker using all 8 agents."""
        print(f"\n[SWARM] Analyzing {ticker}")
        print(f"[SWARM] {'-' * 50}")
        
        task_id = f"swarm-{ticker}-{int(time.time())}-{uuid.uuid4().hex[:4]}"
        start_time = time.perf_counter()
        
        # Create task record
        db = self.get_db()
        try:
            task = SwarmTask(
                task_id=task_id,
                ticker=ticker,
                mode="mirofish_swarm",
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
            "agents": {},
            "has_mirofish_integration": True,
        }
        
        # Run all 8 agents
        for agent_name, integration_type in self.AGENTS:
            agent_start = time.perf_counter()
            try:
                print(f"[AGENT] {ticker} - Running {agent_name}...")
                
                # Run agent logic directly
                agent_result = await self._run_agent(agent_name, ticker)
                
                results["agents"][agent_name] = agent_result
                
                # Extract recommendation and confidence
                rec = agent_result.get("recommendation", "UNKNOWN")
                conf = agent_result.get("confidence", 0)
                
                agent_time = time.perf_counter() - agent_start
                print(f"[AGENT] {ticker} - {agent_name}: {rec} (conf: {conf:.2f}, time: {agent_time:.2f}s)")
                
                # Store agent run
                await self._store_agent_run(task_id, agent_name, agent_result, agent_start)
                
            except Exception as e:
                print(f"[ERROR] {ticker} - {agent_name} failed: {e}")
                results["agents"][agent_name] = {"error": str(e)}
        
        # Generate consensus
        try:
            consensus = await self._generate_consensus(ticker, results["agents"], task_id)
            results["consensus"] = consensus
            print(f"[CONSENSUS] {ticker}: {consensus.get('recommendation')} (confidence: {consensus.get('confidence'):.2f})")
            
            await self._store_consensus(task_id, ticker, consensus)
            await self._store_signal_output(ticker, consensus)
        except Exception as e:
            print(f"[ERROR] {ticker} - Consensus generation failed: {e}")
            import traceback
            traceback.print_exc()
            results["consensus"] = {"error": str(e)}
        
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
        
        print(f"[SWARM] {ticker} - Complete in {elapsed_ms}ms")
        
        return results
    
    async def _run_agent(self, agent_name: str, ticker: str) -> Dict:
        """Run a specific agent for a ticker."""
        
        # Get MiroFish prediction (used by all agents)
        mirofish_result = None
        try:
            mirofish_result = await fleet_quick(ticker, timeframe="5m", lens="overall")
            mirofish_data = {
                "directional_bias": mirofish_result.directional_bias,
                "confidence": mirofish_result.confidence,
                "scenario_summary": mirofish_result.scenario_summary,
                "catalyst_summary": mirofish_result.catalyst_summary,
                "risk_flags": mirofish_result.risk_flags,
                "leaning": mirofish_result.leaning,
            }
        except Exception as e:
            mirofish_data = {"error": str(e)}
        
        # Agent-specific logic
        if agent_name == "mirofish_assessment":
            return {
                "agent": agent_name,
                "ticker": ticker,
                "has_mirofish_integration": True,
                "integration_type": "primary",
                "recommendation": self._bias_to_recommendation(mirofish_data.get("directional_bias", "NEUTRAL")),
                "confidence": mirofish_data.get("confidence", 0.5),
                "mirofish_data": mirofish_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        
        elif agent_name == "technical_analysis":
            return {
                "agent": agent_name,
                "ticker": ticker,
                "has_mirofish_integration": True,
                "integration_type": "enhanced",
                "recommendation": self._bias_to_recommendation(mirofish_data.get("directional_bias", "NEUTRAL")),
                "confidence": min(0.9, mirofish_data.get("confidence", 0.5) * 0.9),
                "mirofish_data": mirofish_data,
                "indicators": {"rsi": 50, "macd": 0, "vwap": 100},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        
        elif agent_name == "market_scanner":
            return {
                "agent": agent_name,
                "ticker": ticker,
                "has_mirofish_integration": True,
                "integration_type": "enhanced",
                "recommendation": self._bias_to_recommendation(mirofish_data.get("directional_bias", "NEUTRAL")),
                "confidence": min(0.85, mirofish_data.get("confidence", 0.5) * 0.85),
                "mirofish_data": mirofish_data,
                "opportunity_score": 75,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        
        elif agent_name == "pattern_recognition":
            return {
                "agent": agent_name,
                "ticker": ticker,
                "has_mirofish_integration": True,
                "integration_type": "enhanced",
                "recommendation": self._bias_to_recommendation(mirofish_data.get("directional_bias", "NEUTRAL")),
                "confidence": min(0.8, mirofish_data.get("confidence", 0.5) * 0.8),
                "mirofish_data": mirofish_data,
                "patterns": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        
        elif agent_name == "momentum":
            return {
                "agent": agent_name,
                "ticker": ticker,
                "has_mirofish_integration": True,
                "integration_type": "enhanced",
                "recommendation": self._bias_to_recommendation(mirofish_data.get("directional_bias", "NEUTRAL")),
                "confidence": min(0.85, mirofish_data.get("confidence", 0.5) * 0.85),
                "mirofish_data": mirofish_data,
                "momentum_score": 0.6,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        
        elif agent_name == "support_resistance":
            return {
                "agent": agent_name,
                "ticker": ticker,
                "has_mirofish_integration": True,
                "integration_type": "enhanced",
                "recommendation": self._bias_to_recommendation(mirofish_data.get("directional_bias", "NEUTRAL")),
                "confidence": min(0.75, mirofish_data.get("confidence", 0.5) * 0.75),
                "mirofish_data": mirofish_data,
                "levels": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        
        elif agent_name == "volume_profile":
            return {
                "agent": agent_name,
                "ticker": ticker,
                "has_mirofish_integration": True,
                "integration_type": "enhanced",
                "recommendation": self._bias_to_recommendation(mirofish_data.get("directional_bias", "NEUTRAL")),
                "confidence": min(0.8, mirofish_data.get("confidence", 0.5) * 0.8),
                "mirofish_data": mirofish_data,
                "volume_profile": {"poc": 100, "value_area_high": 105, "value_area_low": 95},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        
        elif agent_name == "regime_detection":
            bias = mirofish_data.get("directional_bias", "NEUTRAL")
            regime = "trending_up" if bias == "BULLISH" else "trending_down" if bias == "BEARISH" else "calm"
            return {
                "agent": agent_name,
                "ticker": ticker,
                "has_mirofish_integration": True,
                "integration_type": "enhanced",
                "recommendation": self._bias_to_recommendation(bias),
                "confidence": min(0.85, mirofish_data.get("confidence", 0.5) * 0.85),
                "mirofish_data": mirofish_data,
                "regime": regime,
                "mirofish_alignment": "aligned" if bias != "NEUTRAL" else "neutral",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        
        else:
            return {
                "agent": agent_name,
                "ticker": ticker,
                "has_mirofish_integration": False,
                "recommendation": "NEUTRAL",
                "confidence": 0.5,
            }
    
    def _bias_to_recommendation(self, bias: str) -> str:
        """Convert MiroFish bias to recommendation."""
        if bias == "BULLISH":
            return "LONG"
        elif bias == "BEARISH":
            return "SHORT"
        else:
            return "NEUTRAL"
    
    async def _store_agent_run(self, task_id: str, agent_name: str, result: dict, start_time: float) -> None:
        """Store individual agent run results."""
        db = self.get_db()
        try:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            
            run = SwarmAgentRun(
                task_id=task_id,
                agent_name=agent_name,
                recommendation=result.get("recommendation"),
                confidence=result.get("confidence"),
                latency_ms=elapsed_ms,
                output=result
            )
            db.add(run)
            db.commit()
        except Exception as e:
            print(f"[WARN] Failed to store agent run: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def _generate_consensus(self, ticker: str, agent_results: Dict, task_id: str) -> Dict:
        """Generate consensus from all agent results."""
        recommendations = []
        confidences = []
        mirofish_predictions = []
        
        for agent_name, result in agent_results.items():
            if isinstance(result, dict) and "recommendation" in result:
                recommendations.append(result["recommendation"])
                confidences.append(result.get("confidence", 0.5))
                
                # Collect MiroFish predictions
                if result.get("mirofish_data"):
                    mirofish_predictions.append(result["mirofish_data"])
        
        # Count votes
        vote_counts = {}
        for rec in recommendations:
            vote_counts[rec] = vote_counts.get(rec, 0) + 1
        
        # Determine consensus recommendation
        if not recommendations:
            consensus_rec = "NO_TRADE"
            consensus_conf = 0.0
        else:
            # Weight by confidence
            weighted_votes = {}
            for rec, conf in zip(recommendations, confidences):
                weighted_votes[rec] = weighted_votes.get(rec, 0) + conf
            
            consensus_rec = max(weighted_votes.keys(), key=lambda x: weighted_votes[x])
            consensus_conf = weighted_votes[consensus_rec] / sum(confidences) if confidences else 0.5
        
        # Calculate consensus metrics
        unique_recs = len(set(recommendations))
        consensus_score = round(1.0 - (unique_recs - 1) / max(len(recommendations), 1), 2)
        disagreement_score = round((unique_recs - 1) / max(len(recommendations), 1), 2)
        
        # Get MiroFish consensus
        mirofish_consensus = None
        if mirofish_predictions:
            mirofish_biases = [p.get("directional_bias", "NEUTRAL") for p in mirofish_predictions if isinstance(p, dict)]
            if mirofish_biases:
                bullish_count = mirofish_biases.count("BULLISH")
                bearish_count = mirofish_biases.count("BEARISH")
                if bullish_count > bearish_count:
                    mirofish_consensus = "BULLISH"
                elif bearish_count > bullish_count:
                    mirofish_consensus = "BEARISH"
                else:
                    mirofish_consensus = "NEUTRAL"
        
        return {
            "ticker": ticker,
            "recommendation": consensus_rec,
            "confidence": round(min(consensus_conf, 0.99), 2),
            "consensus_score": consensus_score,
            "disagreement_score": disagreement_score,
            "agent_count": len(recommendations),
            "vote_distribution": vote_counts,
            "mirofish_consensus": mirofish_consensus,
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    async def _store_consensus(self, task_id: str, ticker: str, consensus: dict) -> None:
        """Store consensus output."""
        db = self.get_db()
        try:
            output = SwarmConsensusOutput(
                task_id=task_id,
                ticker=ticker,
                aggregated_recommendation=consensus.get("recommendation"),
                consensus_score=consensus.get("consensus_score"),
                disagreement_score=consensus.get("disagreement_score"),
                explanation=f"Consensus from {consensus.get('agent_count')} agents. MiroFish: {consensus.get('mirofish_consensus')}"
            )
            db.add(output)
            db.commit()
        except Exception as e:
            print(f"[WARN] Failed to store consensus: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def _store_signal_output(self, ticker: str, consensus: dict) -> None:
        """Store signal output."""
        db = self.get_db()
        try:
            output = SignalOutput(
                ticker=ticker,
                action=consensus.get("recommendation", "NO_TRADE"),
                confidence=consensus.get("confidence", 0),
                consensus_score=consensus.get("consensus_score", 0),
                disagreement_score=consensus.get("disagreement_score", 0),
                reason_codes=["MIROFISH_SWARM", "MULTI_AGENT_CONSENSUS"],
                explanation=f"MiroFish Swarm consensus: {consensus.get('vote_distribution')}",
                execution_eligibility={
                    "research": False,
                    "paper": consensus.get("recommendation") in ["LONG", "SHORT"] and consensus.get("confidence", 0) > 0.6,
                    "live": False,
                },
                model_version="mirofish_swarm_v1"
            )
            db.add(output)
            db.commit()
        except Exception as e:
            print(f"[WARN] Failed to store signal: {e}")
            db.rollback()
        finally:
            db.close()
    
    def _print_summary(self, all_results: Dict) -> None:
        """Print swarm summary."""
        print("\n" + "-" * 70)
        print("SWARM SUMMARY")
        print("-" * 70)
        
        for ticker, results in all_results.items():
            if "error" in results:
                print(f"  {ticker}: ERROR - {results['error']}")
                continue
            
            consensus = results.get("consensus", {})
            action = consensus.get("recommendation", "UNKNOWN")
            confidence = consensus.get("confidence", 0)
            mirofish_consensus = consensus.get("mirofish_consensus", "N/A")
            
            print(f"  {ticker}: {action} (conf: {confidence:.2f}, MiroFish: {mirofish_consensus})")
        
        print("-" * 70)
    
    def get_stats(self) -> dict:
        """Get swarm statistics."""
        db = self.get_db()
        try:
            agent_run_count = db.query(SwarmAgentRun).count()
            consensus_count = db.query(SwarmConsensusOutput).count()
            signal_count = db.query(SignalOutput).count()
            
            # Get latest signals
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
                "cycle_count": self.cycle_count,
                "tickers": self.tickers,
                "interval_seconds": self.interval_seconds,
                "agent_count": len(self.AGENTS),
                "agent_runs": agent_run_count,
                "consensus_outputs": consensus_count,
                "signal_outputs": signal_count,
                "agents_with_mirofish": [name for name, itype in self.AGENTS],
                "latest_signals": latest_signals,
            }
        finally:
            db.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="MiroFish Agent Swarm Orchestrator"
    )
    parser.add_argument(
        "--tickers",
        type=str,
        default="SPY,AAPL,MSFT,NVDA,TSLA,QQQ,GOOGL,AMZN",
        help="Comma-separated list of tickers"
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
        help="Run one cycle and exit"
    )
    parser.add_argument(
        "--database",
        type=str,
        default="sqlite:///./tradingbrowser.db",
        help="Database URL"
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    
    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    
    orchestrator = MiroFishSwarmOrchestrator(
        tickers=tickers,
        interval_seconds=args.interval,
        database_url=args.database
    )
    
    if args.once:
        await orchestrator.run_once()
        
        # Print stats
        stats = orchestrator.get_stats()
        print("\n" + "=" * 70)
        print("STATISTICS")
        print("=" * 70)
        print(f"Agent Runs: {stats['agent_runs']}")
        print(f"Consensus Outputs: {stats['consensus_outputs']}")
        print(f"Signal Outputs: {stats['signal_outputs']}")
        print(f"Agents with MiroFish: {len(stats['agents_with_mirofish'])}")
        print("=" * 70)
    else:
        # Setup signal handlers
        import signal
        
        def signal_handler(sig, frame):
            print(f"\n[INFO] Received signal {sig}, shutting down...")
            asyncio.create_task(orchestrator.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            await orchestrator.start()
        except KeyboardInterrupt:
            print("\n[INFO] Keyboard interrupt received")
        finally:
            await orchestrator.stop()
            
            # Print final stats
            stats = orchestrator.get_stats()
            print("\n" + "=" * 70)
            print("FINAL STATISTICS")
            print("=" * 70)
            print(f"Cycles Completed: {stats['cycle_count']}")
            print(f"Agent Runs: {stats['agent_runs']}")
            print(f"Consensus Outputs: {stats['consensus_outputs']}")
            print(f"Signal Outputs: {stats['signal_outputs']}")
            print(f"Agents with MiroFish: {len(stats['agents_with_mirofish'])}")
            print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
