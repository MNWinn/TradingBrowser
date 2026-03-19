"""
Risk Agent

Rejects poor trades based on risk criteria.
Enforces exposure limits, drawdown controls.
Prevents correlated entries.

Outputs:
- Approve/Reject decisions
- Risk-adjusted scores
- Violations list
- Position sizing
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np

from .base_agent import BaseAgent
from .message_bus import MessageType, AgentMessage


class RiskDecision(Enum):
    """Risk decision outcomes."""
    APPROVED = "approved"
    REJECTED = "rejected"
    CONDITIONAL = "conditional"  # Approved with modifications
    PENDING = "pending"  # Needs more info


class ViolationType(Enum):
    """Types of risk violations."""
    POSITION_SIZE = "position_size"
    RISK_REWARD = "risk_reward"
    CONVICTION_TOO_LOW = "conviction_too_low"
    EXPOSURE_LIMIT = "exposure_limit"
    CORRELATION_RISK = "correlation_risk"
    DRAWDOWN_VIOLATION = "drawdown_violation"
    CONCENTRATION_RISK = "concentration_risk"
    VOLATILITY_TOO_HIGH = "volatility_too_high"
    REGIME_MISMATCH = "regime_mismatch"
    SIGNAL_DISAGREEMENT = "signal_disagreement"


@dataclass
class RiskViolation:
    """A risk violation."""
    violation_type: ViolationType
    severity: str  # critical, high, medium, low
    description: str
    current_value: float
    limit_value: float
    recommendation: str


@dataclass
class RiskAssessment:
    """Complete risk assessment for a trade."""
    assessment_id: str
    proposal_id: str
    ticker: str
    timestamp: datetime
    
    # Decision
    decision: RiskDecision
    risk_score: float  # 0.0 to 1.0 (lower is better)
    risk_adjusted_score: float  # Conviction adjusted for risk
    
    # Violations
    violations: List[RiskViolation]
    critical_violations: int
    
    # Sizing
    recommended_position_size: float
    max_position_size: float
    
    # Adjustments (if conditional approval)
    adjustments: List[Dict[str, Any]]
    
    # Context
    portfolio_exposure: float
    sector_exposure: float
    correlated_positions: List[str]
    
    # Rationale
    approval_rationale: List[str]
    rejection_rationale: List[str]


@dataclass
class PortfolioState:
    """Current portfolio state for risk calculations."""
    total_value: float
    cash: float
    open_positions: Dict[str, Dict[str, Any]]
    daily_pnl: float
    total_pnl: float
    peak_value: float
    current_drawdown: float
    
    # Exposure tracking
    sector_exposure: Dict[str, float]
    long_exposure: float
    short_exposure: float
    gross_exposure: float
    net_exposure: float
    
    # Risk metrics
    var_95: float  # Value at Risk
    beta: float
    volatility: float


class RiskAgent(BaseAgent):
    """
    Agent for risk management and trade approval.
    """
    
    def __init__(self, message_bus=None, config=None):
        super().__init__("risk", message_bus, config)
        
        # Risk limits (configurable)
        self.max_position_size_pct = config.get("max_position_size", 0.25) if config else 0.25
        self.max_sector_exposure_pct = config.get("max_sector_exposure", 0.40) if config else 0.40
        self.max_portfolio_risk_pct = config.get("max_portfolio_risk", 0.02) if config else 0.02  # 2% daily VaR
        self.max_drawdown_pct = config.get("max_drawdown", 0.10) if config else 0.10
        self.min_risk_reward = config.get("min_risk_reward", 1.5) if config else 1.5
        self.min_conviction = config.get("min_conviction", 0.55) if config else 0.55
        self.max_correlation = config.get("max_correlation", 0.70) if config else 0.70
        self.max_volatility_pct = config.get("max_volatility", 0.05) if config else 0.05  # 5% daily
        
        # State
        self._portfolio: PortfolioState = PortfolioState(
            total_value=100000.0,
            cash=100000.0,
            open_positions={},
            daily_pnl=0.0,
            total_pnl=0.0,
            peak_value=100000.0,
            current_drawdown=0.0,
            sector_exposure={},
            long_exposure=0.0,
            short_exposure=0.0,
            gross_exposure=0.0,
            net_exposure=0.0,
            var_95=0.0,
            beta=0.0,
            volatility=0.0,
        )
        self._assessments: Dict[str, RiskAssessment] = {}
        self._assessment_history: List[RiskAssessment] = []
        
        # Sector mapping (simplified)
        self._sector_map: Dict[str, str] = {}
        
        # Register handlers
        self.register_handler(MessageType.TRADE_PROPOSAL, self._handle_trade_proposal)
        self.register_handler(MessageType.TRADE_OPENED, self._handle_trade_opened)
        self.register_handler(MessageType.TRADE_CLOSED, self._handle_trade_closed)
        self.register_handler(MessageType.PNL_UPDATE, self._handle_pnl_update)
        
    async def _handle_trade_proposal(self, message: AgentMessage):
        """Handle incoming trade proposal."""
        payload = message.payload
        proposal_id = payload.get("proposal_id")
        
        if proposal_id:
            assessment = await self.assess_trade(payload)
            self._assessments[proposal_id] = assessment
            self._assessment_history.append(assessment)
            
            # Publish assessment
            await self._publish_assessment(assessment)
            
    async def _handle_trade_opened(self, message: AgentMessage):
        """Handle trade opened notification."""
        payload = message.payload
        ticker = payload.get("ticker")
        position_size = payload.get("position_size", 0)
        direction = payload.get("direction", "long")
        
        # Update portfolio state
        self._portfolio.open_positions[ticker] = {
            "size": position_size,
            "direction": direction,
            "opened_at": datetime.utcnow(),
        }
        
        await self._recalculate_exposure()
        
    async def _handle_trade_closed(self, message: AgentMessage):
        """Handle trade closed notification."""
        payload = message.payload
        ticker = payload.get("ticker")
        pnl = payload.get("pnl", 0)
        
        # Update portfolio
        if ticker in self._portfolio.open_positions:
            del self._portfolio.open_positions[ticker]
            
        self._portfolio.total_pnl += pnl
        self._portfolio.total_value += pnl
        
        # Update peak and drawdown
        if self._portfolio.total_value > self._portfolio.peak_value:
            self._portfolio.peak_value = self._portfolio.total_value
        self._portfolio.current_drawdown = (
            self._portfolio.peak_value - self._portfolio.total_value
        ) / self._portfolio.peak_value
        
        await self._recalculate_exposure()
        
    async def _handle_pnl_update(self, message: AgentMessage):
        """Handle P&L update."""
        payload = message.payload
        daily_pnl = payload.get("daily_pnl", 0)
        self._portfolio.daily_pnl = daily_pnl
        
    async def assess_trade(self, proposal: Dict[str, Any]) -> RiskAssessment:
        """Perform comprehensive risk assessment on a trade proposal."""
        
        proposal_id = proposal.get("proposal_id", "unknown")
        ticker = proposal.get("ticker", "unknown")
        
        violations = []
        adjustments = []
        
        # Check 1: Position size
        position_size = proposal.get("position_size", 0)
        max_position = self._calculate_max_position_size(ticker)
        if position_size > max_position:
            violations.append(RiskViolation(
                violation_type=ViolationType.POSITION_SIZE,
                severity="critical" if position_size > max_position * 1.5 else "high",
                description=f"Position size {position_size:.2%} exceeds limit {max_position:.2%}",
                current_value=position_size,
                limit_value=max_position,
                recommendation=f"Reduce position to {max_position:.2%} or less"
            ))
            adjustments.append({
                "type": "reduce_position",
                "from": position_size,
                "to": max_position,
            })
            
        # Check 2: Risk/Reward
        risk_reward = proposal.get("risk_reward_ratio", 0)
        if risk_reward < self.min_risk_reward:
            violations.append(RiskViolation(
                violation_type=ViolationType.RISK_REWARD,
                severity="high" if risk_reward < 1.0 else "medium",
                description=f"Risk/Reward {risk_reward:.2f} below minimum {self.min_risk_reward}",
                current_value=risk_reward,
                limit_value=self.min_risk_reward,
                recommendation="Widen profit target or tighten stop loss"
            ))
            
        # Check 3: Conviction
        conviction = proposal.get("conviction_score", 0)
        if conviction < self.min_conviction:
            violations.append(RiskViolation(
                violation_type=ViolationType.CONVICTION_TOO_LOW,
                severity="medium",
                description=f"Conviction {conviction:.2f} below minimum {self.min_conviction}",
                current_value=conviction,
                limit_value=self.min_conviction,
                recommendation="Wait for stronger signal confirmation"
            ))
            
        # Check 4: Portfolio exposure
        new_exposure = self._portfolio.gross_exposure + position_size
        if new_exposure > 1.5:  # Max 150% gross exposure
            violations.append(RiskViolation(
                violation_type=ViolationType.EXPOSURE_LIMIT,
                severity="critical",
                description=f"New gross exposure would be {new_exposure:.2%}",
                current_value=new_exposure,
                limit_value=1.5,
                recommendation="Close existing positions before opening new ones"
            ))
            
        # Check 5: Drawdown
        if self._portfolio.current_drawdown > self.max_drawdown_pct * 0.8:
            severity = "critical" if self._portfolio.current_drawdown > self.max_drawdown_pct else "high"
            violations.append(RiskViolation(
                violation_type=ViolationType.DRAWDOWN_VIOLATION,
                severity=severity,
                description=f"Current drawdown {self._portfolio.current_drawdown:.2%} near limit {self.max_drawdown_pct:.2%}",
                current_value=self._portfolio.current_drawdown,
                limit_value=self.max_drawdown_pct,
                recommendation="Reduce position sizes or pause trading"
            ))
            
        # Check 6: Correlation
        correlated = self._find_correlated_positions(ticker)
        if correlated:
            violations.append(RiskViolation(
                violation_type=ViolationType.CORRELATION_RISK,
                severity="medium",
                description=f"Correlated positions already open: {', '.join(correlated)}",
                current_value=len(correlated),
                limit_value=0,
                recommendation="Consider closing correlated positions first"
            ))
            
        # Check 7: Sector concentration
        sector = self._get_sector(ticker)
        current_sector_exposure = self._portfolio.sector_exposure.get(sector, 0)
        new_sector_exposure = current_sector_exposure + position_size
        if new_sector_exposure > self.max_sector_exposure_pct:
            violations.append(RiskViolation(
                violation_type=ViolationType.CONCENTRATION_RISK,
                severity="high",
                description=f"Sector {sector} exposure would be {new_sector_exposure:.2%}",
                current_value=new_sector_exposure,
                limit_value=self.max_sector_exposure_pct,
                recommendation=f"Reduce position or diversify across sectors"
            ))
            
        # Check 8: Signal disagreement
        signal_agreement = proposal.get("signal_agreement", 1.0)
        if signal_agreement < 0.5:
            violations.append(RiskViolation(
                violation_type=ViolationType.SIGNAL_DISAGREEMENT,
                severity="medium",
                description=f"Low signal agreement ({signal_agreement:.2f}) indicates uncertainty",
                current_value=signal_agreement,
                limit_value=0.5,
                recommendation="Wait for signal alignment"
            ))
            
        # Calculate risk score
        critical_count = sum(1 for v in violations if v.severity == "critical")
        high_count = sum(1 for v in violations if v.severity == "high")
        medium_count = sum(1 for v in violations if v.severity == "medium")
        
        risk_score = min(1.0, (critical_count * 0.5 + high_count * 0.25 + medium_count * 0.1))
        
        # Risk-adjusted conviction
        risk_adjusted_score = conviction * (1 - risk_score)
        
        # Determine decision
        if critical_count > 0:
            decision = RiskDecision.REJECTED
        elif high_count > 1:
            decision = RiskDecision.REJECTED
        elif len(violations) > 0:
            decision = RiskDecision.CONDITIONAL
        else:
            decision = RiskDecision.APPROVED
            
        # Calculate recommended position size
        if decision != RiskDecision.REJECTED:
            recommended_size = min(position_size, max_position)
            # Reduce for risk
            recommended_size *= (1 - risk_score * 0.5)
        else:
            recommended_size = 0
            
        # Build rationale
        approval_rationale = []
        rejection_rationale = []
        
        if decision == RiskDecision.APPROVED:
            approval_rationale.append(f"Conviction score {conviction:.2f} meets threshold")
            approval_rationale.append(f"Risk/Reward ratio {risk_reward:.2f} is acceptable")
            if not correlated:
                approval_rationale.append("No correlation conflicts")
        else:
            for v in violations:
                rejection_rationale.append(f"{v.violation_type.value}: {v.description}")
                
        assessment = RiskAssessment(
            assessment_id=f"risk_{proposal_id}",
            proposal_id=proposal_id,
            ticker=ticker,
            timestamp=datetime.utcnow(),
            decision=decision,
            risk_score=risk_score,
            risk_adjusted_score=risk_adjusted_score,
            violations=violations,
            critical_violations=critical_count,
            recommended_position_size=recommended_size,
            max_position_size=max_position,
            adjustments=adjustments,
            portfolio_exposure=self._portfolio.gross_exposure,
            sector_exposure=current_sector_exposure,
            correlated_positions=correlated,
            approval_rationale=approval_rationale,
            rejection_rationale=rejection_rationale,
        )
        
        return assessment
        
    def _calculate_max_position_size(self, ticker: str) -> float:
        """Calculate maximum position size for a ticker."""
        base_max = self.max_position_size_pct
        
        # Reduce for drawdown
        drawdown_factor = max(0.5, 1 - (self._portfolio.current_drawdown / self.max_drawdown_pct))
        
        # Reduce for existing exposure
        exposure_factor = max(0.3, 1 - (self._portfolio.gross_exposure / 1.5))
        
        return base_max * drawdown_factor * exposure_factor
        
    def _find_correlated_positions(self, ticker: str) -> List[str]:
        """Find positions correlated with the given ticker."""
        # Simplified correlation check based on sector
        sector = self._get_sector(ticker)
        correlated = []
        
        for pos_ticker in self._portfolio.open_positions.keys():
            if self._get_sector(pos_ticker) == sector and pos_ticker != ticker:
                correlated.append(pos_ticker)
                
        return correlated
        
    def _get_sector(self, ticker: str) -> str:
        """Get sector for a ticker."""
        # Simplified sector mapping
        sector_map = {
            "AAPL": "technology", "MSFT": "technology", "GOOGL": "technology", "NVDA": "technology",
            "JPM": "financials", "BAC": "financials", "GS": "financials",
            "JNJ": "healthcare", "PFE": "healthcare",
            "XOM": "energy", "CVX": "energy",
            "SPY": "broad_market", "QQQ": "technology",
        }
        return sector_map.get(ticker, "unknown")
        
    async def _recalculate_exposure(self):
        """Recalculate portfolio exposure metrics."""
        long_exp = 0
        short_exp = 0
        sector_exp = {}
        
        for ticker, pos in self._portfolio.open_positions.items():
            size = pos.get("size", 0)
            direction = pos.get("direction", "long")
            
            if direction == "long":
                long_exp += size
            else:
                short_exp += size
                
            sector = self._get_sector(ticker)
            sector_exp[sector] = sector_exp.get(sector, 0) + size
            
        self._portfolio.long_exposure = long_exp
        self._portfolio.short_exposure = short_exp
        self._portfolio.gross_exposure = long_exp + short_exp
        self._portfolio.net_exposure = long_exp - short_exp
        self._portfolio.sector_exposure = sector_exp
        
    async def _publish_assessment(self, assessment: RiskAssessment):
        """Publish risk assessment to the bus."""
        if assessment.decision == RiskDecision.APPROVED:
            msg_type = MessageType.TRADE_APPROVED
        elif assessment.decision == RiskDecision.REJECTED:
            msg_type = MessageType.TRADE_REJECTED
        else:
            msg_type = MessageType.RISK_ASSESSMENT
            
        await self.send_message(
            msg_type,
            {
                "assessment_id": assessment.assessment_id,
                "proposal_id": assessment.proposal_id,
                "ticker": assessment.ticker,
                "timestamp": assessment.timestamp.isoformat(),
                "decision": assessment.decision.value,
                "risk_score": assessment.risk_score,
                "risk_adjusted_score": assessment.risk_adjusted_score,
                "recommended_position_size": assessment.recommended_position_size,
                "violations": [
                    {
                        "type": v.violation_type.value,
                        "severity": v.severity,
                        "description": v.description,
                    }
                    for v in assessment.violations
                ],
                "adjustments": assessment.adjustments,
                "rationale": assessment.approval_rationale if assessment.decision == RiskDecision.APPROVED else assessment.rejection_rationale,
            }
        )
        
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task assignment."""
        task_type = task.get("type")
        
        if task_type == "assess":
            proposal = task.get("proposal", {})
            assessment = await self.assess_trade(proposal)
            return {
                "assessment": {
                    "assessment_id": assessment.assessment_id,
                    "decision": assessment.decision.value,
                    "risk_score": assessment.risk_score,
                    "violations_count": len(assessment.violations),
                }
            }
            
        elif task_type == "get_portfolio_state":
            return {
                "portfolio": {
                    "total_value": self._portfolio.total_value,
                    "cash": self._portfolio.cash,
                    "open_positions": len(self._portfolio.open_positions),
                    "gross_exposure": self._portfolio.gross_exposure,
                    "net_exposure": self._portfolio.net_exposure,
                    "current_drawdown": self._portfolio.current_drawdown,
                    "daily_pnl": self._portfolio.daily_pnl,
                    "total_pnl": self._portfolio.total_pnl,
                }
            }
            
        elif task_type == "update_limits":
            limits = task.get("limits", {})
            self.max_position_size_pct = limits.get("max_position_size", self.max_position_size_pct)
            self.max_drawdown_pct = limits.get("max_drawdown", self.max_drawdown_pct)
            self.min_risk_reward = limits.get("min_risk_reward", self.min_risk_reward)
            return {"status": "updated", "limits": limits}
            
        elif task_type == "get_assessment":
            proposal_id = task.get("proposal_id")
            assessment = self._assessments.get(proposal_id)
            return {
                "assessment": {
                    "assessment_id": assessment.assessment_id,
                    "decision": assessment.decision.value,
                    "risk_score": assessment.risk_score,
                    "violations": [
                        {
                            "type": v.violation_type.value,
                            "severity": v.severity,
                        }
                        for v in assessment.violations
                    ],
                } if assessment else None
            }
            
        return {"error": f"Unknown task type: {task_type}"}
        
    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        status = super().get_status()
        status.update({
            "portfolio_value": self._portfolio.total_value,
            "open_positions": len(self._portfolio.open_positions),
            "gross_exposure": self._portfolio.gross_exposure,
            "current_drawdown": self._portfolio.current_drawdown,
            "assessments_count": len(self._assessments),
            "risk_limits": {
                "max_position_size": self.max_position_size_pct,
                "max_drawdown": self.max_drawdown_pct,
                "min_risk_reward": self.min_risk_reward,
                "min_conviction": self.min_conviction,
            }
        })
        return status


import asyncio
