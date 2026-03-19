"""
Fleet of Market Research Agents for TradingBrowser.

Specialized agents for comprehensive market analysis:
- MiroFishAssessmentAgent: Deep MiroFish analysis with multiple timeframes
- MarketScannerAgent: Scans entire market for opportunities
- PatternRecognitionAgent: Identifies chart patterns
- MomentumAgent: Tracks momentum indicators and divergences
- SupportResistanceAgent: Dynamic S/R level detection
- VolumeProfileAgent: Analyzes volume at price levels
"""

from .mirofish_assessment import MiroFishAssessmentAgent
from .market_scanner import MarketScannerAgent
from .pattern_recognition import PatternRecognitionAgent
from .momentum import MomentumAgent
from .support_resistance import SupportResistanceAgent
from .volume_profile import VolumeProfileAgent

__all__ = [
    "MiroFishAssessmentAgent",
    "MarketScannerAgent",
    "PatternRecognitionAgent",
    "MomentumAgent",
    "SupportResistanceAgent",
    "VolumeProfileAgent",
]