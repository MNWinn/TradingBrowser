"""Practice Trading Challenges - Trading challenges and achievement system.

This module provides daily challenges, risk management exercises,
consistency goals, and an achievement system for practice trading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from app.models.entities import PaperOrder


class ChallengeType(str, Enum):
    DAILY = "daily"
    RISK_MANAGEMENT = "risk_management"
    CONSISTENCY = "consistency"
    PROFIT_TARGET = "profit_target"
    SKILL_BASED = "skill_based"


class ChallengeStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class AchievementTier(str, Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"


@dataclass
class Challenge:
    """Represents a trading challenge."""
    
    challenge_id: str
    name: str
    description: str
    challenge_type: ChallengeType
    criteria: dict[str, Any]
    reward_points: int
    status: ChallengeStatus = ChallengeStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    completed_at: datetime | None = None
    progress: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        """Check if challenge has expired."""
        if self.expires_at:
            return datetime.now(timezone.utc) > self.expires_at
        return False
    
    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        current = self.progress.get("current", 0)
        target = self.progress.get("target", 1)
        if target == 0:
            return 0.0
        return min((current / target) * 100, 100.0)


@dataclass
class Achievement:
    """Represents an earned achievement."""
    
    achievement_id: str
    name: str
    description: str
    tier: AchievementTier
    icon: str
    earned_at: datetime
    criteria_met: dict[str, Any] = field(default_factory=dict)


@dataclass
class DailyChallengeSet:
    """Set of daily challenges for a user."""
    
    date: str  # YYYY-MM-DD
    challenges: list[Challenge] = field(default_factory=list)
    total_points_earned: int = 0
    all_completed: bool = False


class ChallengeManager:
    """Manager for trading challenges and achievements."""
    
    # Challenge templates
    DAILY_CHALLENGE_TEMPLATES = [
        {
            "name": "Winning Streak",
            "description": "Complete 3 winning trades in a row",
            "type": ChallengeType.DAILY,
            "criteria": {"consecutive_wins": 3},
            "points": 100,
        },
        {
            "name": "Profit Hunter",
            "description": "Achieve $500 in total profit today",
            "type": ChallengeType.DAILY,
            "criteria": {"daily_profit": 500},
            "points": 150,
        },
        {
            "name": "Volume Trader",
            "description": "Execute 10 trades today",
            "type": ChallengeType.DAILY,
            "criteria": {"trade_count": 10},
            "points": 75,
        },
        {
            "name": "Diversified Portfolio",
            "description": "Trade 5 different tickers today",
            "type": ChallengeType.DAILY,
            "criteria": {"unique_tickers": 5},
            "points": 100,
        },
        {
            "name": "Quick Scalper",
            "description": "Complete 5 trades with < 15 min holding time",
            "type": ChallengeType.DAILY,
            "criteria": {"quick_trades": 5, "max_duration_minutes": 15},
            "points": 125,
        },
    ]
    
    RISK_CHALLENGE_TEMPLATES = [
        {
            "name": "Risk Manager",
            "description": "Complete 10 trades without exceeding 2% risk per trade",
            "type": ChallengeType.RISK_MANAGEMENT,
            "criteria": {"trades_with_proper_risk": 10, "max_risk_percent": 2.0},
            "points": 200,
        },
        {
            "name": "Stop Loss Discipline",
            "description": "Use stop losses on 20 consecutive trades",
            "type": ChallengeType.RISK_MANAGEMENT,
            "criteria": {"consecutive_stops": 20},
            "points": 250,
        },
        {
            "name": "Drawdown Recovery",
            "description": "Recover from a 5% drawdown within 5 trades",
            "type": ChallengeType.RISK_MANAGEMENT,
            "criteria": {"recover_from_drawdown": 5.0, "max_trades": 5},
            "points": 300,
        },
        {
            "name": "Position Sizing Pro",
            "description": "Maintain consistent position sizing across 15 trades",
            "type": ChallengeType.RISK_MANAGEMENT,
            "criteria": {"consistent_sizing_trades": 15, "variance_threshold": 0.1},
            "points": 175,
        },
    ]
    
    CONSISTENCY_TEMPLATES = [
        {
            "name": "Weekly Consistency",
            "description": "Trade for 5 consecutive days",
            "type": ChallengeType.CONSISTENCY,
            "criteria": {"consecutive_days": 5},
            "points": 300,
        },
        {
            "name": "Green Week",
            "description": "End each day of the week with positive P&L",
            "type": ChallengeType.CONSISTENCY,
            "criteria": {"positive_days_week": 5},
            "points": 500,
        },
        {
            "name": "Win Rate Warrior",
            "description": "Maintain 60%+ win rate over 50 trades",
            "type": ChallengeType.CONSISTENCY,
            "criteria": {"min_win_rate": 60, "trade_count": 50},
            "points": 400,
        },
        {
            "name": "Sharpe Ratio Master",
            "description": "Achieve Sharpe ratio > 1.5 over 30 days",
            "type": ChallengeType.CONSISTENCY,
            "criteria": {"min_sharpe": 1.5, "period_days": 30},
            "points": 600,
        },
    ]
    
    PROFIT_TEMPLATES = [
        {
            "name": "First Profit",
            "description": "Make your first profitable trade",
            "type": ChallengeType.PROFIT_TARGET,
            "criteria": {"first_profit": True},
            "points": 50,
        },
        {
            "name": "Century Club",
            "description": "Achieve $100 in total profits",
            "type": ChallengeType.PROFIT_TARGET,
            "criteria": {"total_profit": 100},
            "points": 100,
        },
        {
            "name": "Grand Slam",
            "description": "Achieve $1,000 in total profits",
            "type": ChallengeType.PROFIT_TARGET,
            "criteria": {"total_profit": 1000},
            "points": 250,
        },
        {
            "name": "Five Figure Club",
            "description": "Achieve $10,000 in total profits",
            "type": ChallengeType.PROFIT_TARGET,
            "criteria": {"total_profit": 10000},
            "points": 1000,
        },
    ]
    
    # Achievement definitions
    ACHIEVEMENT_DEFINITIONS = [
        {
            "id": "first_trade",
            "name": "First Steps",
            "description": "Execute your first paper trade",
            "tier": AchievementTier.BRONZE,
            "icon": "🎯",
            "criteria": {"total_trades": 1},
        },
        {
            "id": "hundred_trades",
            "name": "Centurion",
            "description": "Execute 100 paper trades",
            "tier": AchievementTier.SILVER,
            "icon": "⚔️",
            "criteria": {"total_trades": 100},
        },
        {
            "id": "thousand_trades",
            "name": "Veteran Trader",
            "description": "Execute 1,000 paper trades",
            "tier": AchievementTier.GOLD,
            "icon": "🏆",
            "criteria": {"total_trades": 1000},
        },
        {
            "id": "profit_streak_10",
            "name": "Hot Streak",
            "description": "Achieve 10 consecutive winning trades",
            "tier": AchievementTier.SILVER,
            "icon": "🔥",
            "criteria": {"max_consecutive_wins": 10},
        },
        {
            "id": "profit_streak_20",
            "name": "Unstoppable",
            "description": "Achieve 20 consecutive winning trades",
            "tier": AchievementTier.GOLD,
            "icon": "⚡",
            "criteria": {"max_consecutive_wins": 20},
        },
        {
            "id": "sharpe_1",
            "name": "Risk Aware",
            "description": "Achieve Sharpe ratio > 1.0",
            "tier": AchievementTier.SILVER,
            "icon": "📊",
            "criteria": {"max_sharpe": 1.0},
        },
        {
            "id": "sharpe_2",
            "name": "Sharpe Mind",
            "description": "Achieve Sharpe ratio > 2.0",
            "tier": AchievementTier.GOLD,
            "icon": "🧠",
            "criteria": {"max_sharpe": 2.0},
        },
        {
            "id": "no_drawdown_week",
            "name": "Steady Hand",
            "description": "Complete a week with no drawdown > 2%",
            "tier": AchievementTier.GOLD,
            "icon": "🎪",
            "criteria": {"week_max_drawdown": 2.0},
        },
        {
            "id": "diverse_trader",
            "name": "Portfolio Diversifier",
            "description": "Trade 50 different tickers",
            "tier": AchievementTier.SILVER,
            "icon": "🌐",
            "criteria": {"unique_tickers_traded": 50},
        },
        {
            "id": "strategy_master",
            "name": "Strategy Master",
            "description": "Successfully use 5 different strategies",
            "tier": AchievementTier.PLATINUM,
            "icon": "🎭",
            "criteria": {"strategies_used": 5},
        },
        {
            "id": "challenge_champion",
            "name": "Challenge Champion",
            "description": "Complete 50 challenges",
            "tier": AchievementTier.GOLD,
            "icon": "👑",
            "criteria": {"challenges_completed": 50},
        },
        {
            "id": "perfect_day",
            "name": "Perfect Day",
            "description": "Complete all daily challenges in one day",
            "tier": AchievementTier.PLATINUM,
            "icon": "💎",
            "criteria": {"perfect_day": True},
        },
    ]
    
    def __init__(self, db: Session):
        self.db = db
        self._user_challenges: dict[str, list[Challenge]] = {}
        self._user_achievements: dict[str, list[Achievement]] = {}
        self._user_points: dict[str, int] = {}
    
    def generate_daily_challenges(self, user_id: str) -> DailyChallengeSet:
        """Generate a new set of daily challenges for a user."""
        import random
        import uuid
        
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Select 3 random daily challenges
        selected = random.sample(self.DAILY_CHALLENGE_TEMPLATES, min(3, len(self.DAILY_CHALLENGE_TEMPLATES)))
        
        challenges = []
        for template in selected:
            challenge = Challenge(
                challenge_id=f"daily_{uuid.uuid4().hex[:8]}",
                name=template["name"],
                description=template["description"],
                challenge_type=ChallengeType.DAILY,
                criteria=template["criteria"],
                reward_points=template["points"],
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                progress={"current": 0, "target": self._get_target_value(template["criteria"])},
            )
            challenges.append(challenge)
        
        challenge_set = DailyChallengeSet(
            date=today,
            challenges=challenges,
        )
        
        # Store for user
        if user_id not in self._user_challenges:
            self._user_challenges[user_id] = []
        self._user_challenges[user_id].extend(challenges)
        
        return challenge_set
    
    def get_active_challenges(self, user_id: str) -> list[Challenge]:
        """Get all active challenges for a user."""
        if user_id not in self._user_challenges:
            return []
        
        active = []
        for challenge in self._user_challenges[user_id]:
            if challenge.status == ChallengeStatus.ACTIVE and not challenge.is_expired:
                active.append(challenge)
        
        return active
    
    def assign_risk_challenge(self, user_id: str, challenge_index: int = 0) -> Challenge | None:
        """Assign a risk management challenge to a user."""
        import uuid
        
        if challenge_index >= len(self.RISK_CHALLENGE_TEMPLATES):
            return None
        
        template = self.RISK_CHALLENGE_TEMPLATES[challenge_index]
        
        challenge = Challenge(
            challenge_id=f"risk_{uuid.uuid4().hex[:8]}",
            name=template["name"],
            description=template["description"],
            challenge_type=ChallengeType.RISK_MANAGEMENT,
            criteria=template["criteria"],
            reward_points=template["points"],
            progress={"current": 0, "target": self._get_target_value(template["criteria"])},
        )
        
        if user_id not in self._user_challenges:
            self._user_challenges[user_id] = []
        self._user_challenges[user_id].append(challenge)
        
        return challenge
    
    def assign_consistency_challenge(self, user_id: str, challenge_index: int = 0) -> Challenge | None:
        """Assign a consistency challenge to a user."""
        import uuid
        
        if challenge_index >= len(self.CONSISTENCY_TEMPLATES):
            return None
        
        template = self.CONSISTENCY_TEMPLATES[challenge_index]
        
        challenge = Challenge(
            challenge_id=f"consistency_{uuid.uuid4().hex[:8]}",
            name=template["name"],
            description=template["description"],
            challenge_type=ChallengeType.CONSISTENCY,
            criteria=template["criteria"],
            reward_points=template["points"],
            progress={"current": 0, "target": self._get_target_value(template["criteria"])},
        )
        
        if user_id not in self._user_challenges:
            self._user_challenges[user_id] = []
        self._user_challenges[user_id].append(challenge)
        
        return challenge
    
    def update_challenge_progress(
        self,
        user_id: str,
        challenge_id: str,
        progress_update: dict[str, Any],
    ) -> Challenge | None:
        """Update progress for a specific challenge."""
        if user_id not in self._user_challenges:
            return None
        
        for challenge in self._user_challenges[user_id]:
            if challenge.challenge_id == challenge_id:
                # Update progress
                challenge.progress.update(progress_update)
                challenge.progress["current"] = progress_update.get("current", challenge.progress.get("current", 0))
                
                # Check completion
                if challenge.progress_percent >= 100:
                    challenge.status = ChallengeStatus.COMPLETED
                    challenge.completed_at = datetime.now(timezone.utc)
                    
                    # Award points
                    self._award_points(user_id, challenge.reward_points)
                    
                    # Check for achievements
                    self._check_achievements(user_id)
                
                return challenge
        
        return None
    
    def check_trade_challenges(self, user_id: str, trade_data: dict[str, Any]) -> list[Challenge]:
        """Check and update challenges based on a new trade."""
        updated = []
        
        active_challenges = self.get_active_challenges(user_id)
        
        for challenge in active_challenges:
            progress_made = False
            
            if challenge.challenge_type == ChallengeType.DAILY:
                progress_made = self._check_daily_challenge(challenge, trade_data)
            elif challenge.challenge_type == ChallengeType.RISK_MANAGEMENT:
                progress_made = self._check_risk_challenge(challenge, trade_data)
            elif challenge.challenge_type == ChallengeType.CONSISTENCY:
                progress_made = self._check_consistency_challenge(challenge, trade_data)
            elif challenge.challenge_type == ChallengeType.PROFIT_TARGET:
                progress_made = self._check_profit_challenge(challenge, trade_data)
            
            if progress_made:
                updated.append(challenge)
        
        return updated
    
    def get_user_achievements(self, user_id: str) -> list[Achievement]:
        """Get all achievements earned by a user."""
        return self._user_achievements.get(user_id, [])
    
    def get_user_points(self, user_id: str) -> int:
        """Get total points earned by a user."""
        return self._user_points.get(user_id, 0)
    
    def get_leaderboard(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get leaderboard of top users by points."""
        sorted_users = sorted(
            self._user_points.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        return [
            {
                "user_id": user_id,
                "points": points,
                "rank": i + 1,
            }
            for i, (user_id, points) in enumerate(sorted_users)
        ]
    
    def _get_target_value(self, criteria: dict[str, Any]) -> int:
        """Extract target value from criteria."""
        # Common target keys
        target_keys = [
            "consecutive_wins", "daily_profit", "trade_count", "unique_tickers",
            "quick_trades", "trades_with_proper_risk", "consecutive_stops",
            "consistent_sizing_trades", "consecutive_days", "positive_days_week",
            "trade_count", "total_profit"
        ]
        
        for key in target_keys:
            if key in criteria:
                return criteria[key]
        
        return 1
    
    def _award_points(self, user_id: str, points: int) -> None:
        """Award points to a user."""
        if user_id not in self._user_points:
            self._user_points[user_id] = 0
        self._user_points[user_id] += points
    
    def _check_achievements(self, user_id: str) -> list[Achievement]:
        """Check and award any new achievements."""
        new_achievements = []
        
        # Get user stats
        user_stats = self._get_user_stats(user_id)
        
        # Check each achievement
        for achievement_def in self.ACHIEVEMENT_DEFINITIONS:
            # Check if already earned
            already_earned = any(
                a.achievement_id == achievement_def["id"]
                for a in self._user_achievements.get(user_id, [])
            )
            
            if already_earned:
                continue
            
            # Check criteria
            criteria = achievement_def["criteria"]
            if self._check_achievement_criteria(criteria, user_stats):
                achievement = Achievement(
                    achievement_id=achievement_def["id"],
                    name=achievement_def["name"],
                    description=achievement_def["description"],
                    tier=achievement_def["tier"],
                    icon=achievement_def["icon"],
                    earned_at=datetime.now(timezone.utc),
                    criteria_met=criteria,
                )
                
                if user_id not in self._user_achievements:
                    self._user_achievements[user_id] = []
                self._user_achievements[user_id].append(achievement)
                
                # Award bonus points based on tier
                tier_points = {
                    AchievementTier.BRONZE: 50,
                    AchievementTier.SILVER: 100,
                    AchievementTier.GOLD: 250,
                    AchievementTier.PLATINUM: 500,
                    AchievementTier.DIAMOND: 1000,
                }
                self._award_points(user_id, tier_points.get(achievement_def["tier"], 50))
                
                new_achievements.append(achievement)
        
        return new_achievements
    
    def _get_user_stats(self, user_id: str) -> dict[str, Any]:
        """Get statistics for a user."""
        # Query database for user stats
        query = select(PaperOrder).where(PaperOrder.status == "filled")
        orders = self.db.scalars(query).all()
        
        # Filter by user_id from rationale
        user_orders = [
            o for o in orders
            if (o.rationale or {}).get("user_id") == user_id
        ]
        
        total_trades = len(user_orders)
        
        # Calculate wins
        wins = sum(
            1 for o in user_orders
            if Decimal(str((o.rationale or {}).get("realized_pnl", 0))) > 0
        )
        
        # Get unique tickers
        unique_tickers = len(set(o.ticker for o in user_orders))
        
        # Get unique strategies
        unique_strategies = len(set(
            (o.rationale or {}).get("strategy_id")
            for o in user_orders
            if (o.rationale or {}).get("strategy_id")
        ))
        
        # Get completed challenges count
        completed_challenges = sum(
            1 for c in self._user_challenges.get(user_id, [])
            if c.status == ChallengeStatus.COMPLETED
        )
        
        return {
            "total_trades": total_trades,
            "wins": wins,
            "unique_tickers_traded": unique_tickers,
            "strategies_used": unique_strategies,
            "challenges_completed": completed_challenges,
            "max_consecutive_wins": self._calculate_max_consecutive_wins(user_orders),
        }
    
    def _calculate_max_consecutive_wins(self, orders: list) -> int:
        """Calculate maximum consecutive winning trades."""
        max_streak = 0
        current_streak = 0
        
        for order in orders:
            pnl = Decimal(str((order.rationale or {}).get("realized_pnl", 0)))
            if pnl > 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    def _check_achievement_criteria(
        self,
        criteria: dict[str, Any],
        user_stats: dict[str, Any],
    ) -> bool:
        """Check if user meets achievement criteria."""
        for key, value in criteria.items():
            if key == "total_trades":
                if user_stats.get("total_trades", 0) < value:
                    return False
            elif key == "max_consecutive_wins":
                if user_stats.get("max_consecutive_wins", 0) < value:
                    return False
            elif key == "unique_tickers_traded":
                if user_stats.get("unique_tickers_traded", 0) < value:
                    return False
            elif key == "strategies_used":
                if user_stats.get("strategies_used", 0) < value:
                    return False
            elif key == "challenges_completed":
                if user_stats.get("challenges_completed", 0) < value:
                    return False
        
        return True
    
    def _check_daily_challenge(self, challenge: Challenge, trade_data: dict[str, Any]) -> bool:
        """Check progress on a daily challenge."""
        criteria = challenge.criteria
        
        if "consecutive_wins" in criteria:
            # Would need trade history to check
            pass
        elif "daily_profit" in criteria:
            current_profit = challenge.progress.get("current_profit", 0)
            trade_pnl = trade_data.get("pnl", 0)
            challenge.progress["current_profit"] = current_profit + trade_pnl
            challenge.progress["current"] = challenge.progress["current_profit"]
        elif "trade_count" in criteria:
            challenge.progress["current"] = challenge.progress.get("current", 0) + 1
        elif "unique_tickers" in criteria:
            tickers = challenge.progress.get("tickers", [])
            ticker = trade_data.get("ticker")
            if ticker and ticker not in tickers:
                tickers.append(ticker)
                challenge.progress["tickers"] = tickers
                challenge.progress["current"] = len(tickers)
        
        return True
    
    def _check_risk_challenge(self, challenge: Challenge, trade_data: dict[str, Any]) -> bool:
        """Check progress on a risk management challenge."""
        criteria = challenge.criteria
        
        if "trades_with_proper_risk" in criteria:
            risk_percent = trade_data.get("risk_percent", 0)
            max_risk = criteria.get("max_risk_percent", 2.0)
            if risk_percent <= max_risk:
                challenge.progress["current"] = challenge.progress.get("current", 0) + 1
        elif "consecutive_stops" in criteria:
            has_stop = trade_data.get("has_stop_loss", False)
            if has_stop:
                challenge.progress["current"] = challenge.progress.get("current", 0) + 1
            else:
                challenge.progress["current"] = 0  # Reset on failure
        
        return True
    
    def _check_consistency_challenge(self, challenge: Challenge, trade_data: dict[str, Any]) -> bool:
        """Check progress on a consistency challenge."""
        # These are typically checked at day end
        return False
    
    def _check_profit_challenge(self, challenge: Challenge, trade_data: dict[str, Any]) -> bool:
        """Check progress on a profit target challenge."""
        criteria = challenge.criteria
        
        if "total_profit" in criteria:
            current_profit = challenge.progress.get("current_profit", 0)
            trade_pnl = trade_data.get("pnl", 0)
            if trade_pnl > 0:
                challenge.progress["current_profit"] = current_profit + trade_pnl
                challenge.progress["current"] = challenge.progress["current_profit"]
        
        return True


# Global challenge manager instance
_challenge_manager: ChallengeManager | None = None


def get_challenge_manager(db: Session) -> ChallengeManager:
    """Get or create the challenge manager instance."""
    global _challenge_manager
    if _challenge_manager is None:
        _challenge_manager = ChallengeManager(db)
    return _challenge_manager
