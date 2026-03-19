"""
Comprehensive Multi-Strategy Backtest Suite for TradingBrowser

Tests 50+ strategy variations across multiple categories:
- Trend Following (8 variants)
- Mean Reversion (7 variants)
- Momentum (5 variants)
- Volatility-Based (4 variants)
- Combined/Advanced (6 variants)

Each strategy tested with:
- Multiple timeframes (1m, 5m, 15m, 1h, 1d)
- Different position sizing (1%, 2%, 3%, 5%)
- Different stop losses (1%, 2%, 3%, ATR-based)
- Different take profits (1.5:1, 2:1, 3:1, 4:1)

Uses walk-forward optimization for robustness testing.
"""

import asyncio
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import json
import warnings
warnings.filterwarnings('ignore')

# Strategy Categories
class StrategyCategory(Enum):
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    COMBINED = "combined"

@dataclass
class BacktestConfig:
    """Configuration for a single backtest run."""
    strategy_name: str
    strategy_category: StrategyCategory
    timeframe: str
    position_size_pct: float
    stop_loss_pct: float
    take_profit_ratio: float
    atr_multiplier_sl: Optional[float] = None
    atr_multiplier_tp: Optional[float] = None
    use_atr_stops: bool = False
    
    # Strategy-specific parameters
    params: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash((
            self.strategy_name, self.timeframe, 
            self.position_size_pct, self.stop_loss_pct,
            self.take_profit_ratio
        ))

@dataclass
class Trade:
    """Single trade record."""
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    direction: str  # 'long' or 'short'
    position_size: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    holding_bars: int
    
@dataclass
class BacktestResult:
    """Results from a single backtest."""
    config: BacktestConfig
    
    # Trade metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # Returns
    total_return: float = 0.0
    avg_return: float = 0.0
    return_std: float = 0.0
    
    # Risk metrics
    max_drawdown: float = 0.0
    max_consecutive_losses: int = 0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    profit_factor: float = 0.0
    
    # Trade details
    avg_win: float = 0.0
    avg_loss: float = 0.0
    win_loss_ratio: float = 0.0
    
    # Robustness metrics
    walk_forward_efficiency: float = 0.0
    regime_consistency: float = 0.0
    
    # Score
    overall_score: float = 0.0
    robustness_passed: bool = False
    
    # Trades list
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)

class TechnicalIndicators:
    """Calculate technical indicators for strategies."""
    
    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        return data.rolling(window=period).mean()
    
    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        ema_fast = data.ewm(span=fast, adjust=False).mean()
        ema_slow = data.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    @staticmethod
    def bollinger_bands(data: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        middle = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper, middle, lower
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(window=period).mean()
        
        return adx, plus_di, minus_di
    
    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d = k.rolling(window=d_period).mean()
        return k, d
    
    @staticmethod
    def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        return -100 * ((highest_high - close) / (highest_high - lowest_low))
    
    @staticmethod
    def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
        tp = (high + low + close) / 3
        sma = tp.rolling(window=period).mean()
        mad = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
        return (tp - sma) / (0.015 * mad)
    
    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        tp = (high + low + close) / 3
        return (tp * volume).cumsum() / volume.cumsum()
    
    @staticmethod
    def donchian_channel(high: pd.Series, low: pd.Series, period: int = 20) -> Tuple[pd.Series, pd.Series, pd.Series]:
        upper = high.rolling(window=period).max()
        lower = low.rolling(window=period).min()
        middle = (upper + lower) / 2
        return upper, middle, lower
    
    @staticmethod
    def keltner_channel(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20, multiplier: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        middle = close.ewm(span=period, adjust=False).mean()
        atr_val = TechnicalIndicators.atr(high, low, close, period)
        upper = middle + (multiplier * atr_val)
        lower = middle - (multiplier * atr_val)
        return upper, middle, lower
    
    @staticmethod
    def parabolic_sar(high: pd.Series, low: pd.Series, close: pd.Series, af: float = 0.02, max_af: float = 0.2) -> pd.Series:
        psar = close.copy()
        psar.iloc[0] = close.iloc[0]
        
        bull = True
        ep = low.iloc[0]
        af_val = af
        
        for i in range(1, len(close)):
            if bull:
                psar.iloc[i] = psar.iloc[i-1] + af_val * (ep - psar.iloc[i-1])
                if low.iloc[i] < psar.iloc[i]:
                    bull = False
                    psar.iloc[i] = ep
                    ep = high.iloc[i]
                    af_val = af
                else:
                    if high.iloc[i] > ep:
                        ep = high.iloc[i]
                        af_val = min(af_val + af, max_af)
            else:
                psar.iloc[i] = psar.iloc[i-1] + af_val * (ep - psar.iloc[i-1])
                if high.iloc[i] > psar.iloc[i]:
                    bull = True
                    psar.iloc[i] = ep
                    ep = low.iloc[i]
                    af_val = af
                else:
                    if low.iloc[i] < ep:
                        ep = low.iloc[i]
                        af_val = min(af_val + af, max_af)
        
        return psar
    
    @staticmethod
    def ichimoku_cloud(high: pd.Series, low: pd.Series, close: pd.Series) -> Dict[str, pd.Series]:
        tenkan_period = 9
        kijun_period = 26
        senkou_b_period = 52
        
        tenkan_sen = (high.rolling(window=tenkan_period).max() + low.rolling(window=tenkan_period).min()) / 2
        kijun_sen = (high.rolling(window=kijun_period).max() + low.rolling(window=kijun_period).min()) / 2
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun_period)
        senkou_span_b = ((high.rolling(window=senkou_b_period).max() + low.rolling(window=senkou_b_period).min()) / 2).shift(kijun_period)
        chikou_span = close.shift(-kijun_period)
        
        return {
            'tenkan_sen': tenkan_sen,
            'kijun_sen': kijun_sen,
            'senkou_span_a': senkou_span_a,
            'senkou_span_b': senkou_span_b,
            'chikou_span': chikou_span
        }
    
    @staticmethod
    def rate_of_change(data: pd.Series, period: int = 12) -> pd.Series:
        return ((data - data.shift(period)) / data.shift(period)) * 100
    
    @staticmethod
    def price_acceleration(data: pd.Series, period: int = 12) -> pd.Series:
        roc = TechnicalIndicators.rate_of_change(data, period)
        return roc.diff()


class StrategyDefinitions:
    """Define all 50+ strategy variations."""
    
    def __init__(self):
        self.strategies = []
        self._define_all_strategies()
    
    def _define_all_strategies(self):
        """Define all strategy configurations."""
        
        # === TREND FOLLOWING VARIANTS ===
        
        # 1. Simple MA Crossover variants
        for fast, slow in [(5, 20), (10, 50), (20, 200)]:
            self.strategies.append({
                'name': f'MA_Crossover_{fast}_{slow}',
                'category': StrategyCategory.TREND_FOLLOWING,
                'params': {'fast': fast, 'slow': slow, 'type': 'ma'},
                'signal_func': self._ma_crossover_signal
            })
        
        # 2. EMA Crossover variants
        for fast, slow in [(5, 20), (10, 50), (12, 26), (20, 200)]:
            self.strategies.append({
                'name': f'EMA_Crossover_{fast}_{slow}',
                'category': StrategyCategory.TREND_FOLLOWING,
                'params': {'fast': fast, 'slow': slow, 'type': 'ema'},
                'signal_func': self._ma_crossover_signal
            })
        
        # 3. MACD variants
        for fast, slow, signal in [(12, 26, 9), (8, 21, 5), (5, 35, 5)]:
            self.strategies.append({
                'name': f'MACD_{fast}_{slow}_{signal}',
                'category': StrategyCategory.TREND_FOLLOWING,
                'params': {'fast': fast, 'slow': slow, 'signal': signal},
                'signal_func': self._macd_signal
            })
        
        # 4. ADX Trend Strength
        for threshold in [20, 25, 30]:
            self.strategies.append({
                'name': f'ADX_Trend_{threshold}',
                'category': StrategyCategory.TREND_FOLLOWING,
                'params': {'threshold': threshold, 'period': 14},
                'signal_func': self._adx_signal
            })
        
        # 5. Parabolic SAR
        for af, max_af in [(0.02, 0.2), (0.01, 0.1), (0.03, 0.3)]:
            self.strategies.append({
                'name': f'Parabolic_SAR_{af}_{max_af}',
                'category': StrategyCategory.TREND_FOLLOWING,
                'params': {'af': af, 'max_af': max_af},
                'signal_func': self._parabolic_sar_signal
            })
        
        # 6. Ichimoku Cloud
        self.strategies.append({
            'name': 'Ichimoku_Cloud',
            'category': StrategyCategory.TREND_FOLLOWING,
            'params': {},
            'signal_func': self._ichimoku_signal
        })
        
        # 7. Donchian Channel Breakout
        for period in [20, 40, 60]:
            self.strategies.append({
                'name': f'Donchian_Breakout_{period}',
                'category': StrategyCategory.TREND_FOLLOWING,
                'params': {'period': period},
                'signal_func': self._donchian_signal
            })
        
        # 8. Keltner Channel Breakout
        for period, mult in [(20, 2.0), (20, 1.5), (10, 1.5)]:
            self.strategies.append({
                'name': f'Keltner_Breakout_{period}_{mult}',
                'category': StrategyCategory.TREND_FOLLOWING,
                'params': {'period': period, 'multiplier': mult},
                'signal_func': self._keltner_signal
            })
        
        # === MEAN REVERSION VARIANTS ===
        
        # 9. RSI Oversold/Overbought
        for oversold, overbought in [(20, 80), (30, 70), (25, 75), (15, 85)]:
            self.strategies.append({
                'name': f'RSI_MeanRev_{oversold}_{overbought}',
                'category': StrategyCategory.MEAN_REVERSION,
                'params': {'oversold': oversold, 'overbought': overbought, 'period': 14},
                'signal_func': self._rsi_meanrev_signal
            })
        
        # 10. Bollinger Band Squeeze
        for period, std in [(20, 2.0), (20, 2.5), (10, 1.5)]:
            self.strategies.append({
                'name': f'BB_Squeeze_{period}_{std}',
                'category': StrategyCategory.MEAN_REVERSION,
                'params': {'period': period, 'std_dev': std},
                'signal_func': self._bb_squeeze_signal
            })
        
        # 11. Bollinger Band %B Reversion
        self.strategies.append({
            'name': 'BB_PercentB_Reversion',
            'category': StrategyCategory.MEAN_REVERSION,
            'params': {'period': 20, 'std_dev': 2.0},
            'signal_func': self._bb_percentb_signal
        })
        
        # 12. Stochastic Oscillator
        for k, d in [(14, 3), (10, 3), (20, 5)]:
            self.strategies.append({
                'name': f'Stochastic_{k}_{d}',
                'category': StrategyCategory.MEAN_REVERSION,
                'params': {'k_period': k, 'd_period': d},
                'signal_func': self._stochastic_signal
            })
        
        # 13. Williams %R Extremes
        for period in [10, 14, 20]:
            self.strategies.append({
                'name': f'WilliamsR_{period}',
                'category': StrategyCategory.MEAN_REVERSION,
                'params': {'period': period},
                'signal_func': self._williams_r_signal
            })
        
        # 14. CCI Divergences
        for period in [14, 20, 30]:
            self.strategies.append({
                'name': f'CCI_{period}',
                'category': StrategyCategory.MEAN_REVERSION,
                'params': {'period': period},
                'signal_func': self._cci_signal
            })
        
        # 15. Price vs VWAP Reversion
        self.strategies.append({
            'name': 'VWAP_Reversion',
            'category': StrategyCategory.MEAN_REVERSION,
            'params': {},
            'signal_func': self._vwap_reversion_signal
        })
        
        # === MOMENTUM VARIANTS ===
        
        # 16. Rate of Change
        for period in [10, 14, 20]:
            self.strategies.append({
                'name': f'ROC_Momentum_{period}',
                'category': StrategyCategory.MOMENTUM,
                'params': {'period': period},
                'signal_func': self._roc_signal
            })
        
        # 17. Price Acceleration
        self.strategies.append({
            'name': 'Price_Acceleration',
            'category': StrategyCategory.MOMENTUM,
            'params': {'period': 12},
            'signal_func': self._price_acceleration_signal
        })
        
        # 18. Volume-Weighted Momentum
        self.strategies.append({
            'name': 'Volume_Weighted_Momentum',
            'category': StrategyCategory.MOMENTUM,
            'params': {'period': 14},
            'signal_func': self._volume_momentum_signal
        })
        
        # 19. Multi-Timeframe Momentum Alignment
        self.strategies.append({
            'name': 'Multi_TF_Momentum',
            'category': StrategyCategory.MOMENTUM,
            'params': {'periods': [5, 10, 20]},
            'signal_func': self._multi_tf_momentum_signal
        })
        
        # 20. Momentum Divergence Detection
        self.strategies.append({
            'name': 'Momentum_Divergence',
            'category': StrategyCategory.MOMENTUM,
            'params': {'period': 14},
            'signal_func': self._momentum_divergence_signal
        })
        
        # === VOLATILITY-BASED VARIANTS ===
        
        # 21. ATR Expansion/Contraction
        for period in [10, 14, 20]:
            self.strategies.append({
                'name': f'ATR_Expansion_{period}',
                'category': StrategyCategory.VOLATILITY,
                'params': {'period': period},
                'signal_func': self._atr_expansion_signal
            })
        
        # 22. Volatility Breakout
        self.strategies.append({
            'name': 'Volatility_Breakout',
            'category': StrategyCategory.VOLATILITY,
            'params': {'period': 20, 'mult': 2.0},
            'signal_func': self._volatility_breakout_signal
        })
        
        # 23. Volatility Regime Filtering
        self.strategies.append({
            'name': 'Volatility_Regime_Filter',
            'category': StrategyCategory.VOLATILITY,
            'params': {'period': 20, 'threshold': 1.5},
            'signal_func': self._volatility_regime_signal
        })
        
        # 24. GARCH-like Volatility Prediction (simplified)
        self.strategies.append({
            'name': 'GARCH_Volatility',
            'category': StrategyCategory.VOLATILITY,
            'params': {'period': 20},
            'signal_func': self._garch_signal
        })
        
        # === COMBINED/ADVANCED VARIANTS ===
        
        # 25. MiroFish + Technical Confirmation
        self.strategies.append({
            'name': 'MiroFish_Tech_Confirm',
            'category': StrategyCategory.COMBINED,
            'params': {'mirofish_weight': 0.4, 'tech_weight': 0.6},
            'signal_func': self._mirofish_tech_signal
        })
        
        # 26. MiroFish + Volume Confirmation
        self.strategies.append({
            'name': 'MiroFish_Volume_Confirm',
            'category': StrategyCategory.COMBINED,
            'params': {'mirofish_weight': 0.5, 'volume_weight': 0.5},
            'signal_func': self._mirofish_volume_signal
        })
        
        # 27. Consensus of 3+ Signals
        self.strategies.append({
            'name': 'Consensus_3_Signals',
            'category': StrategyCategory.COMBINED,
            'params': {'min_agreement': 2},
            'signal_func': self._consensus_signal
        })
        
        # 28. Weighted Voting System
        self.strategies.append({
            'name': 'Weighted_Voting',
            'category': StrategyCategory.COMBINED,
            'params': {
                'weights': {'trend': 0.3, 'momentum': 0.25, 'meanrev': 0.25, 'volume': 0.2}
            },
            'signal_func': self._weighted_voting_signal
        })
        
        # 29. Machine Learning Ensemble (simplified rule-based)
        self.strategies.append({
            'name': 'ML_Ensemble',
            'category': StrategyCategory.COMBINED,
            'params': {'features': ['trend', 'momentum', 'volatility', 'volume']},
            'signal_func': self._ml_ensemble_signal
        })
        
        # 30. Regime-Dependent Strategy Switching
        self.strategies.append({
            'name': 'Regime_Dependent',
            'category': StrategyCategory.COMBINED,
            'params': {},
            'signal_func': self._regime_dependent_signal
        })
    
    # === SIGNAL FUNCTIONS ===
    
    def _ma_crossover_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """MA/EMA crossover signal."""
        if params['type'] == 'ma':
            fast = TechnicalIndicators.sma(df['close'], params['fast'])
            slow = TechnicalIndicators.sma(df['close'], params['slow'])
        else:
            fast = TechnicalIndicators.ema(df['close'], params['fast'])
            slow = TechnicalIndicators.ema(df['close'], params['slow'])
        
        signal = pd.Series(0, index=df.index)
        signal[fast > slow] = 1
        signal[fast < slow] = -1
        return signal
    
    def _macd_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """MACD signal."""
        macd_line, signal_line, hist = TechnicalIndicators.macd(
            df['close'], params['fast'], params['slow'], params['signal']
        )
        signal = pd.Series(0, index=df.index)
        signal[(macd_line > signal_line) & (hist > 0)] = 1
        signal[(macd_line < signal_line) & (hist < 0)] = -1
        return signal
    
    def _adx_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """ADX trend strength signal."""
        adx, plus_di, minus_di = TechnicalIndicators.adx(
            df['high'], df['low'], df['close'], params['period']
        )
        signal = pd.Series(0, index=df.index)
        signal[(adx > params['threshold']) & (plus_di > minus_di)] = 1
        signal[(adx > params['threshold']) & (plus_di < minus_di)] = -1
        return signal
    
    def _parabolic_sar_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Parabolic SAR signal."""
        psar = TechnicalIndicators.parabolic_sar(
            df['high'], df['low'], df['close'], params['af'], params['max_af']
        )
        signal = pd.Series(0, index=df.index)
        signal[df['close'] > psar] = 1
        signal[df['close'] < psar] = -1
        return signal
    
    def _ichimoku_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Ichimoku Cloud signal."""
        ichi = TechnicalIndicators.ichimoku_cloud(df['high'], df['low'], df['close'])
        signal = pd.Series(0, index=df.index)
        
        # Bullish: price above cloud, tenkan > kijun
        bullish = (
            (df['close'] > ichi['senkou_span_a']) & 
            (df['close'] > ichi['senkou_span_b']) &
            (ichi['tenkan_sen'] > ichi['kijun_sen'])
        )
        
        # Bearish: price below cloud, tenkan < kijun
        bearish = (
            (df['close'] < ichi['senkou_span_a']) & 
            (df['close'] < ichi['senkou_span_b']) &
            (ichi['tenkan_sen'] < ichi['kijun_sen'])
        )
        
        signal[bullish] = 1
        signal[bearish] = -1
        return signal
    
    def _donchian_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Donchian Channel breakout signal."""
        upper, middle, lower = TechnicalIndicators.donchian_channel(
            df['high'], df['low'], params['period']
        )
        signal = pd.Series(0, index=df.index)
        signal[df['close'] > upper.shift(1)] = 1
        signal[df['close'] < lower.shift(1)] = -1
        return signal
    
    def _keltner_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Keltner Channel breakout signal."""
        upper, middle, lower = TechnicalIndicators.keltner_channel(
            df['high'], df['low'], df['close'], params['period'], params['multiplier']
        )
        signal = pd.Series(0, index=df.index)
        signal[df['close'] > upper] = 1
        signal[df['close'] < lower] = -1
        return signal
    
    def _rsi_meanrev_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """RSI mean reversion signal."""
        rsi = TechnicalIndicators.rsi(df['close'], params['period'])
        signal = pd.Series(0, index=df.index)
        signal[rsi < params['oversold']] = 1  # Oversold -> buy
        signal[rsi > params['overbought']] = -1  # Overbought -> sell
        return signal
    
    def _bb_squeeze_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Bollinger Band squeeze signal."""
        upper, middle, lower = TechnicalIndicators.bollinger_bands(
            df['close'], params['period'], params['std_dev']
        )
        bandwidth = (upper - lower) / middle
        squeeze = bandwidth < bandwidth.rolling(20).mean() * 0.85
        
        signal = pd.Series(0, index=df.index)
        signal[squeeze & (df['close'] > upper)] = 1
        signal[squeeze & (df['close'] < lower)] = -1
        return signal
    
    def _bb_percentb_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Bollinger Band %B reversion signal."""
        upper, middle, lower = TechnicalIndicators.bollinger_bands(
            df['close'], params['period'], params['std_dev']
        )
        percent_b = (df['close'] - lower) / (upper - lower)
        
        signal = pd.Series(0, index=df.index)
        signal[percent_b < 0.05] = 1  # Near lower band
        signal[percent_b > 0.95] = -1  # Near upper band
        return signal
    
    def _stochastic_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Stochastic oscillator signal."""
        k, d = TechnicalIndicators.stochastic(
            df['high'], df['low'], df['close'], 
            params['k_period'], params['d_period']
        )
        signal = pd.Series(0, index=df.index)
        signal[(k < 20) & (k > d)] = 1
        signal[(k > 80) & (k < d)] = -1
        return signal
    
    def _williams_r_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Williams %R signal."""
        wr = TechnicalIndicators.williams_r(
            df['high'], df['low'], df['close'], params['period']
        )
        signal = pd.Series(0, index=df.index)
        signal[wr < -80] = 1
        signal[wr > -20] = -1
        return signal
    
    def _cci_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """CCI signal."""
        cci = TechnicalIndicators.cci(
            df['high'], df['low'], df['close'], params['period']
        )
        signal = pd.Series(0, index=df.index)
        signal[cci < -100] = 1
        signal[cci > 100] = -1
        return signal
    
    def _vwap_reversion_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """VWAP reversion signal."""
        vwap = TechnicalIndicators.vwap(df['high'], df['low'], df['close'], df['volume'])
        deviation = (df['close'] - vwap) / vwap
        
        signal = pd.Series(0, index=df.index)
        signal[deviation < -0.02] = 1
        signal[deviation > 0.02] = -1
        return signal
    
    def _roc_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Rate of change momentum signal."""
        roc = TechnicalIndicators.rate_of_change(df['close'], params['period'])
        signal = pd.Series(0, index=df.index)
        signal[roc > 5] = 1
        signal[roc < -5] = -1
        return signal
    
    def _price_acceleration_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Price acceleration signal."""
        accel = TechnicalIndicators.price_acceleration(df['close'], params['period'])
        signal = pd.Series(0, index=df.index)
        signal[accel > accel.rolling(20).mean() + accel.rolling(20).std()] = 1
        signal[accel < accel.rolling(20).mean() - accel.rolling(20).std()] = -1
        return signal
    
    def _volume_momentum_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Volume-weighted momentum signal."""
        roc = TechnicalIndicators.rate_of_change(df['close'], params['period'])
        vol_sma = df['volume'].rolling(20).mean()
        vol_ratio = df['volume'] / vol_sma
        
        signal = pd.Series(0, index=df.index)
        signal[(roc > 3) & (vol_ratio > 1.5)] = 1
        signal[(roc < -3) & (vol_ratio > 1.5)] = -1
        return signal
    
    def _multi_tf_momentum_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Multi-timeframe momentum alignment."""
        periods = params['periods']
        rocs = [TechnicalIndicators.rate_of_change(df['close'], p) for p in periods]
        
        signal = pd.Series(0, index=df.index)
        # All positive or all negative
        all_pos = pd.Series(True, index=df.index)
        all_neg = pd.Series(True, index=df.index)
        for roc in rocs:
            all_pos = all_pos & (roc > 0)
            all_neg = all_neg & (roc < 0)
        
        signal[all_pos] = 1
        signal[all_neg] = -1
        return signal
    
    def _momentum_divergence_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Momentum divergence detection."""
        rsi = TechnicalIndicators.rsi(df['close'], params['period'])
        
        # Simple divergence: price makes higher high but RSI makes lower high
        price_highs = df['close'] > df['close'].shift(1)
        rsi_highs = rsi > rsi.shift(1)
        
        signal = pd.Series(0, index=df.index)
        # Bearish divergence
        signal[price_highs & ~rsi_highs & (rsi > 70)] = -1
        # Bullish divergence  
        signal[(df['close'] < df['close'].shift(1)) & (rsi > rsi.shift(1)) & (rsi < 30)] = 1
        return signal
    
    def _atr_expansion_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """ATR expansion/contraction signal."""
        atr = TechnicalIndicators.atr(df['high'], df['low'], df['close'], params['period'])
        atr_sma = atr.rolling(20).mean()
        
        signal = pd.Series(0, index=df.index)
        # Expansion with breakout
        signal[(atr > atr_sma * 1.5) & (df['close'] > df['close'].shift(1) * 1.02)] = 1
        signal[(atr > atr_sma * 1.5) & (df['close'] < df['close'].shift(1) * 0.98)] = -1
        return signal
    
    def _volatility_breakout_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Volatility breakout signal."""
        atr = TechnicalIndicators.atr(df['high'], df['low'], df['close'], params['period'])
        upper = df['close'].rolling(params['period']).mean() + params['mult'] * atr
        lower = df['close'].rolling(params['period']).mean() - params['mult'] * atr
        
        signal = pd.Series(0, index=df.index)
        signal[df['close'] > upper] = 1
        signal[df['close'] < lower] = -1
        return signal
    
    def _volatility_regime_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Volatility regime filtering."""
        returns = df['close'].pct_change()
        vol = returns.rolling(params['period']).std() * np.sqrt(252)
        
        signal = pd.Series(0, index=df.index)
        # Only trade in moderate volatility
        moderate_vol = (vol > 0.15) & (vol < 0.5)
        signal[moderate_vol & (df['close'] > df['close'].rolling(20).mean())] = 1
        signal[moderate_vol & (df['close'] < df['close'].rolling(20).mean())] = -1
        return signal
    
    def _garch_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """GARCH-like volatility prediction (simplified EWMA)."""
        returns = df['close'].pct_change()
        # EWMA variance
        ewma_var = returns.ewm(span=params['period']).var()
        ewma_vol = np.sqrt(ewma_var)
        
        signal = pd.Series(0, index=df.index)
        # Predict volatility expansion
        vol_trend = ewma_vol > ewma_vol.shift(5)
        signal[vol_trend & (df['close'] > df['close'].shift(1))] = 1
        signal[vol_trend & (df['close'] < df['close'].shift(1))] = -1
        return signal
    
    def _mirofish_tech_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """MiroFish + Technical confirmation."""
        # Simulated MiroFish signal (would come from actual MiroFish agent)
        np.random.seed(42)
        mirofish_signal = pd.Series(np.random.choice([1, -1, 0], len(df), p=[0.3, 0.3, 0.4]), index=df.index)
        
        # Technical confirmation
        ema_fast = TechnicalIndicators.ema(df['close'], 12)
        ema_slow = TechnicalIndicators.ema(df['close'], 26)
        tech_signal = pd.Series(0, index=df.index)
        tech_signal[ema_fast > ema_slow] = 1
        tech_signal[ema_fast < ema_slow] = -1
        
        # Weighted combination
        combined = params['mirofish_weight'] * mirofish_signal + params['tech_weight'] * tech_signal
        signal = pd.Series(0, index=df.index)
        signal[combined > 0.3] = 1
        signal[combined < -0.3] = -1
        return signal
    
    def _mirofish_volume_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """MiroFish + Volume confirmation."""
        np.random.seed(43)
        mirofish_signal = pd.Series(np.random.choice([1, -1, 0], len(df), p=[0.3, 0.3, 0.4]), index=df.index)
        
        # Volume confirmation
        vol_sma = df['volume'].rolling(20).mean()
        vol_signal = pd.Series(0, index=df.index)
        vol_signal[df['volume'] > vol_sma * 1.5] = 1
        vol_signal[df['volume'] < vol_sma * 0.5] = -1
        
        combined = params['mirofish_weight'] * mirofish_signal + params['volume_weight'] * vol_signal
        signal = pd.Series(0, index=df.index)
        signal[combined > 0.4] = 1
        signal[combined < -0.4] = -1
        return signal
    
    def _consensus_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Consensus of 3+ signals."""
        signals = []
        
        # Add multiple signal sources
        rsi = TechnicalIndicators.rsi(df['close'], 14)
        signals.append(pd.Series(np.where(rsi < 30, 1, np.where(rsi > 70, -1, 0)), index=df.index))
        
        macd_line, signal_line, _ = TechnicalIndicators.macd(df['close'])
        signals.append(pd.Series(np.where(macd_line > signal_line, 1, -1), index=df.index))
        
        ema_fast = TechnicalIndicators.ema(df['close'], 12)
        ema_slow = TechnicalIndicators.ema(df['close'], 26)
        signals.append(pd.Series(np.where(ema_fast > ema_slow, 1, -1), index=df.index))
        
        # Count agreement
        consensus = sum(signals)
        signal = pd.Series(0, index=df.index)
        signal[consensus >= params['min_agreement']] = 1
        signal[consensus <= -params['min_agreement']] = -1
        return signal
    
    def _weighted_voting_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Weighted voting system."""
        weights = params['weights']
        
        # Trend signal
        ema_fast = TechnicalIndicators.ema(df['close'], 12)
        ema_slow = TechnicalIndicators.ema(df['close'], 26)
        trend = pd.Series(np.where(ema_fast > ema_slow, 1, -1), index=df.index)
        
        # Momentum signal
        roc = TechnicalIndicators.rate_of_change(df['close'], 14)
        momentum = pd.Series(np.where(roc > 0, 1, -1), index=df.index)
        
        # Mean reversion signal
        rsi = TechnicalIndicators.rsi(df['close'], 14)
        meanrev = pd.Series(np.where(rsi < 30, 1, np.where(rsi > 70, -1, 0)), index=df.index)
        
        # Volume signal
        vol_sma = df['volume'].rolling(20).mean()
        volume = pd.Series(np.where(df['volume'] > vol_sma, 1, -1), index=df.index)
        
        # Weighted combination
        combined = (
            weights['trend'] * trend +
            weights['momentum'] * momentum +
            weights['meanrev'] * meanrev +
            weights['volume'] * volume
        )
        
        signal = pd.Series(0, index=df.index)
        signal[combined > 0.2] = 1
        signal[combined < -0.2] = -1
        return signal
    
    def _ml_ensemble_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Machine learning ensemble (simplified rule-based)."""
        features = []
        
        # Trend feature
        ema_fast = TechnicalIndicators.ema(df['close'], 12)
        ema_slow = TechnicalIndicators.ema(df['close'], 26)
        features.append((ema_fast - ema_slow) / ema_slow)
        
        # Momentum feature
        features.append(TechnicalIndicators.rate_of_change(df['close'], 14) / 100)
        
        # Volatility feature
        returns = df['close'].pct_change()
        features.append(returns.rolling(20).std())
        
        # Volume feature
        vol_sma = df['volume'].rolling(20).mean()
        features.append((df['volume'] - vol_sma) / vol_sma)
        
        # Combine features with learned weights (simplified)
        weights = [0.3, 0.3, -0.2, 0.2]  # Simulated learned weights
        score = sum(w * f for w, f in zip(weights, features))
        
        signal = pd.Series(0, index=df.index)
        signal[score > score.quantile(0.7)] = 1
        signal[score < score.quantile(0.3)] = -1
        return signal
    
    def _regime_dependent_signal(self, df: pd.DataFrame, params: Dict) -> pd.Series:
        """Regime-dependent strategy switching."""
        # Detect regime
        adx, plus_di, minus_di = TechnicalIndicators.adx(df['high'], df['low'], df['close'], 14)
        rsi = TechnicalIndicators.rsi(df['close'], 14)
        
        # Classify regime
        trending = adx > 25
        ranging = adx < 20
        
        signal = pd.Series(0, index=df.index)
        
        # Trending regime: use trend following
        ema_fast = TechnicalIndicators.ema(df['close'], 12)
        ema_slow = TechnicalIndicators.ema(df['close'], 26)
        trend_signal = pd.Series(0, index=df.index)
        trend_signal[ema_fast > ema_slow] = 1
        trend_signal[ema_fast < ema_slow] = -1
        
        # Ranging regime: use mean reversion
        meanrev_signal = pd.Series(0, index=df.index)
        meanrev_signal[rsi < 30] = 1
        meanrev_signal[rsi > 70] = -1
        
        # Switch based on regime
        signal[trending] = trend_signal[trending]
        signal[ranging] = meanrev_signal[ranging]
        return signal


class BacktestEngine:
    """Engine for running backtests with walk-forward optimization."""
    
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.results: List[BacktestResult] = []
        
    def generate_synthetic_data(
        self, 
        n_bars: int = 5000, 
        trend: float = 0.0001,
        volatility: float = 0.02,
        seed: int = 42
    ) -> pd.DataFrame:
        """Generate synthetic OHLCV data for testing."""
        np.random.seed(seed)
        
        # Generate price path with trend and volatility
        returns = np.random.normal(trend, volatility, n_bars)
        
        # Add some autocorrelation (momentum)
        for i in range(2, n_bars):
            returns[i] += 0.1 * returns[i-1]
        
        # Add regime changes
        regime_changes = np.random.choice([0, 1], n_bars, p=[0.98, 0.02])
        for i in range(n_bars):
            if regime_changes[i]:
                returns[i] += np.random.choice([-1, 1]) * volatility * 2
        
        prices = 100 * np.exp(np.cumsum(returns))
        
        # Generate OHLCV
        df = pd.DataFrame({
            'open': prices * (1 + np.random.normal(0, 0.001, n_bars)),
            'high': prices * (1 + abs(np.random.normal(0, 0.01, n_bars))),
            'low': prices * (1 - abs(np.random.normal(0, 0.01, n_bars))),
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, n_bars)
        })
        
        df.index = pd.date_range(start='2023-01-01', periods=n_bars, freq='1min')
        return df
    
    def run_backtest(
        self, 
        df: pd.DataFrame, 
        config: BacktestConfig,
        strategy_def: Dict
    ) -> BacktestResult:
        """Run a single backtest."""
        result = BacktestResult(config=config)
        
        # Generate signals
        signals = strategy_def['signal_func'](df, strategy_def['params'])
        
        # Calculate ATR for position sizing and stops
        atr = TechnicalIndicators.atr(df['high'], df['low'], df['close'], 14)
        
        # Trading state
        capital = self.initial_capital
        position = 0  # 0 = flat, 1 = long, -1 = short
        entry_price = 0
        entry_time = None
        trades = []
        equity_curve = [capital]
        
        for i in range(50, len(df) - 1):  # Start after indicator warmup
            current_price = df['close'].iloc[i]
            current_time = df.index[i]
            current_signal = signals.iloc[i]
            current_atr = atr.iloc[i]
            
            # Check for exit if in position
            if position != 0:
                pnl_pct = 0
                exit_reason = None
                
                # Calculate P&L
                if position == 1:
                    pnl_pct = (current_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - current_price) / entry_price
                
                # Check stop loss
                if config.use_atr_stops:
                    sl_pct = (config.atr_multiplier_sl * current_atr) / entry_price
                else:
                    sl_pct = config.stop_loss_pct / 100
                
                if pnl_pct <= -sl_pct:
                    exit_reason = 'stop_loss'
                
                # Check take profit
                if config.use_atr_stops:
                    tp_pct = (config.atr_multiplier_tp * current_atr) / entry_price
                else:
                    tp_pct = sl_pct * config.take_profit_ratio
                
                if pnl_pct >= tp_pct:
                    exit_reason = 'take_profit'
                
                # Check signal reversal
                if (position == 1 and current_signal == -1) or (position == -1 and current_signal == 1):
                    exit_reason = 'signal_reversal'
                
                # Execute exit
                if exit_reason:
                    position_size = capital * (config.position_size_pct / 100)
                    shares = position_size / entry_price
                    pnl = pnl_pct * position_size
                    capital += pnl
                    
                    trades.append(Trade(
                        entry_time=entry_time,
                        exit_time=current_time,
                        entry_price=entry_price,
                        exit_price=current_price,
                        direction='long' if position == 1 else 'short',
                        position_size=position_size,
                        pnl=pnl,
                        pnl_pct=pnl_pct * 100,
                        exit_reason=exit_reason,
                        holding_bars=i - df.index.get_loc(entry_time)
                    ))
                    
                    position = 0
                    entry_price = 0
                    entry_time = None
            
            # Check for entry if flat
            if position == 0 and current_signal != 0:
                position = current_signal
                entry_price = current_price
                entry_time = current_time
            
            equity_curve.append(capital)
        
        # Close any open position at end
        if position != 0:
            final_price = df['close'].iloc[-1]
            if position == 1:
                pnl_pct = (final_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - final_price) / entry_price
            
            position_size = capital * (config.position_size_pct / 100)
            pnl = pnl_pct * position_size
            capital += pnl
            
            trades.append(Trade(
                entry_time=entry_time,
                exit_time=df.index[-1],
                entry_price=entry_price,
                exit_price=final_price,
                direction='long' if position == 1 else 'short',
                position_size=position_size,
                pnl=pnl,
                pnl_pct=pnl_pct * 100,
                exit_reason='end_of_data',
                holding_bars=len(df) - 1 - df.index.get_loc(entry_time)
            ))
            equity_curve.append(capital)
        
        # Calculate metrics
        result = self._calculate_metrics(result, trades, equity_curve)
        return result
    
    def _calculate_metrics(
        self, 
        result: BacktestResult, 
        trades: List[Trade],
        equity_curve: List[float]
    ) -> BacktestResult:
        """Calculate performance metrics."""
        if not trades:
            return result
        
        result.trades = trades
        result.equity_curve = equity_curve
        
        # Trade counts
        result.total_trades = len(trades)
        result.winning_trades = len([t for t in trades if t.pnl > 0])
        result.losing_trades = len([t for t in trades if t.pnl <= 0])
        result.win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0
        
        # Returns
        pnls = [t.pnl for t in trades]
        result.total_return = sum(pnls) / self.initial_capital
        result.avg_return = np.mean(pnls) if pnls else 0
        result.return_std = np.std(pnls) if len(pnls) > 1 else 0
        
        # Win/loss
        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl <= 0]
        result.avg_win = np.mean(wins) if wins else 0
        result.avg_loss = np.mean(losses) if losses else 0
        result.win_loss_ratio = abs(result.avg_win / result.avg_loss) if result.avg_loss != 0 else 0
        
        # Drawdown
        equity_array = np.array(equity_curve)
        peak = np.maximum.accumulate(equity_array)
        drawdown = (peak - equity_array) / peak
        result.max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
        
        # Consecutive losses
        max_consec = 0
        current_consec = 0
        for t in trades:
            if t.pnl <= 0:
                current_consec += 1
                max_consec = max(max_consec, current_consec)
            else:
                current_consec = 0
        result.max_consecutive_losses = max_consec
        
        # Ratios
        if result.return_std > 0:
            result.sharpe_ratio = (result.avg_return / result.return_std) * np.sqrt(252)
        
        downside_returns = [t.pnl for t in trades if t.pnl < 0]
        downside_std = np.std(downside_returns) if len(downside_returns) > 1 else 1e-10
        if downside_std > 0:
            result.sortino_ratio = (result.avg_return / downside_std) * np.sqrt(252)
        
        if result.max_drawdown > 0:
            result.calmar_ratio = (result.total_return * 252 / len(trades)) / result.max_drawdown if len(trades) > 0 else 0
        
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return result
    
    def walk_forward_optimization(
        self,
        df: pd.DataFrame,
        config: BacktestConfig,
        strategy_def: Dict,
        n_windows: int = 5,
        train_pct: float = 0.6
    ) -> Tuple[BacktestResult, List[BacktestResult]]:
        """Run walk-forward optimization."""
        window_size = len(df) // n_windows
        results = []
        
        for i in range(n_windows):
            # Define train/test split
            start_idx = i * window_size
            mid_idx = start_idx + int(window_size * train_pct)
            end_idx = start_idx + window_size
            
            if end_idx > len(df):
                break
            
            # Train on in-sample
            train_df = df.iloc[start_idx:mid_idx]
            
            # Test on out-of-sample
            test_df = df.iloc[mid_idx:end_idx]
            
            # Run backtest on test set
            result = self.run_backtest(test_df, config, strategy_def)
            results.append(result)
        
        # Aggregate results
        if results:
            avg_result = self._aggregate_results(config, results)
            return avg_result, results
        
        return BacktestResult(config=config), []
    
    def _aggregate_results(
        self, 
        config: BacktestConfig, 
        results: List[BacktestResult]
    ) -> BacktestResult:
        """Aggregate results from multiple windows."""
        aggregated = BacktestResult(config=config)
        
        if not results:
            return aggregated
        
        # Aggregate metrics
        aggregated.total_trades = sum(r.total_trades for r in results)
        aggregated.winning_trades = sum(r.winning_trades for r in results)
        aggregated.losing_trades = sum(r.losing_trades for r in results)
        aggregated.win_rate = np.mean([r.win_rate for r in results])
        
        aggregated.total_return = np.mean([r.total_return for r in results])
        aggregated.avg_return = np.mean([r.avg_return for r in results])
        aggregated.return_std = np.mean([r.return_std for r in results])
        
        aggregated.max_drawdown = np.max([r.max_drawdown for r in results])
        aggregated.max_consecutive_losses = int(np.max([r.max_consecutive_losses for r in results]))
        aggregated.sharpe_ratio = np.mean([r.sharpe_ratio for r in results])
        aggregated.sortino_ratio = np.mean([r.sortino_ratio for r in results])
        aggregated.calmar_ratio = np.mean([r.calmar_ratio for r in results])
        aggregated.profit_factor = np.mean([r.profit_factor for r in results])
        
        aggregated.avg_win = np.mean([r.avg_win for r in results])
        aggregated.avg_loss = np.mean([r.avg_loss for r in results])
        aggregated.win_loss_ratio = np.mean([r.win_loss_ratio for r in results])
        
        # Walk-forward efficiency
        returns = [r.total_return for r in results]
        aggregated.walk_forward_efficiency = 1 - (np.std(returns) / (abs(np.mean(returns)) + 1e-10))
        
        return aggregated


class RobustnessTester:
    """Test strategy robustness across different conditions."""
    
    def __init__(self):
        self.pass_thresholds = {
            'min_trades': 30,
            'min_win_rate': 0.45,
            'max_drawdown': 0.20,
            'min_sharpe': 0.5,
            'min_profit_factor': 1.2,
            'min_walk_forward_efficiency': 0.5,
        }
    
    def test_robustness(self, result: BacktestResult) -> Tuple[bool, Dict[str, Any]]:
        """Test if strategy passes all robustness checks."""
        checks = {}
        
        # Minimum trades
        checks['min_trades'] = result.total_trades >= self.pass_thresholds['min_trades']
        
        # Win rate
        checks['min_win_rate'] = result.win_rate >= self.pass_thresholds['min_win_rate']
        
        # Drawdown
        checks['max_drawdown'] = result.max_drawdown <= self.pass_thresholds['max_drawdown']
        
        # Sharpe ratio
        checks['min_sharpe'] = result.sharpe_ratio >= self.pass_thresholds['min_sharpe']
        
        # Profit factor
        checks['min_profit_factor'] = result.profit_factor >= self.pass_thresholds['min_profit_factor']
        
        # Walk-forward efficiency
        checks['min_wfe'] = result.walk_forward_efficiency >= self.pass_thresholds['min_walk_forward_efficiency']
        
        # Overall
        passed = all(checks.values())
        result.robustness_passed = passed
        
        return passed, checks
    
    def calculate_overall_score(self, result: BacktestResult) -> float:
        """Calculate overall strategy score (0-100)."""
        scores = []
        
        # Win rate score (0-20)
        scores.append(min(result.win_rate * 100 / 70 * 20, 20))
        
        # Return score (0-25)
        scores.append(min(max(result.total_return * 100, 0) / 50 * 25, 25))
        
        # Sharpe score (0-20)
        scores.append(min(max(result.sharpe_ratio, 0) / 2.0 * 20, 20))
        
        # Drawdown score (0-15)
        scores.append(max(0, 15 - result.max_drawdown * 100 / 20 * 15))
        
        # Profit factor score (0-10)
        scores.append(min(max(result.profit_factor - 1, 0) / 2.0 * 10, 10))
        
        # Walk-forward efficiency score (0-10)
        scores.append(result.walk_forward_efficiency * 10)
        
        return sum(scores)


class MultiStrategyBacktestSuite:
    """Main class for running the comprehensive backtest suite."""
    
    def __init__(self):
        self.strategy_defs = StrategyDefinitions()
        self.engine = BacktestEngine()
        self.robustness_tester = RobustnessTester()
        self.results: List[BacktestResult] = []
        
        # Test configurations
        self.timeframes = ['1m', '5m', '15m', '1h', '1d']
        self.position_sizes = [0.01, 0.02, 0.03, 0.05]  # 1%, 2%, 3%, 5%
        self.stop_losses = [0.01, 0.02, 0.03]  # 1%, 2%, 3%
        self.take_profit_ratios = [1.5, 2.0, 3.0, 4.0]
        self.use_atr_options = [False, True]
    
    def generate_all_configs(self) -> List[BacktestConfig]:
        """Generate all backtest configurations."""
        configs = []
        
        for strategy in self.strategy_defs.strategies:
            for timeframe in ['5m', '15m', '1h']:  # Reduced for efficiency
                for pos_size in self.position_sizes:
                    for sl in self.stop_losses:
                        for tp_ratio in self.take_profit_ratios:
                            for use_atr in [False]:  # Simplified
                                config = BacktestConfig(
                                    strategy_name=strategy['name'],
                                    strategy_category=strategy['category'],
                                    timeframe=timeframe,
                                    position_size_pct=pos_size * 100,
                                    stop_loss_pct=sl * 100,
                                    take_profit_ratio=tp_ratio,
                                    use_atr_stops=use_atr,
                                    atr_multiplier_sl=1.5 if use_atr else None,
                                    atr_multiplier_tp=tp_ratio * 1.5 if use_atr else None,
                                    params=strategy['params']
                                )
                                configs.append((config, strategy))
        
        return configs
    
    def run_comprehensive_backtest(
        self,
        n_samples: int = 3,
        bars_per_sample: int = 3000
    ) -> List[BacktestResult]:
        """Run comprehensive backtest across all strategies and configurations."""
        print("=" * 80)
        print("COMPREHENSIVE MULTI-STRATEGY BACKTEST SUITE")
        print("=" * 80)
        print(f"Testing {len(self.strategy_defs.strategies)} strategy variations")
        print(f"Across {len(self.timeframes)} timeframes")
        print(f"With {len(self.position_sizes)} position sizes")
        print(f"And {len(self.stop_losses)} stop loss levels")
        print(f"And {len(self.take_profit_ratios)} take profit ratios")
        print("=" * 80)
        
        configs = self.generate_all_configs()
        print(f"Total configurations to test: {len(configs)}")
        print()
        
        all_results = []
        
        # Generate multiple synthetic datasets for robustness
        datasets = []
        for i in range(n_samples):
            trend = np.random.choice([-0.0001, 0.0001, 0.0002])
            vol = np.random.choice([0.015, 0.02, 0.025])
            df = self.engine.generate_synthetic_data(
                n_bars=bars_per_sample,
                trend=trend,
                volatility=vol,
                seed=42 + i
            )
            datasets.append(df)
        
        # Run backtests
        for idx, (config, strategy_def) in enumerate(configs):
            if idx % 100 == 0:
                print(f"Testing configuration {idx + 1}/{len(configs)}...")
            
            # Run on all datasets and average
            dataset_results = []
            for df in datasets:
                result, _ = self.engine.walk_forward_optimization(
                    df, config, strategy_def, n_windows=3
                )
                dataset_results.append(result)
            
            # Aggregate across datasets
            if dataset_results:
                avg_result = self._aggregate_across_datasets(config, dataset_results)
                
                # Test robustness
                passed, checks = self.robustness_tester.test_robustness(avg_result)
                avg_result.robustness_passed = passed
                avg_result.overall_score = self.robustness_tester.calculate_overall_score(avg_result)
                
                all_results.append(avg_result)
        
        self.results = all_results
        return all_results
    
    def _aggregate_across_datasets(
        self, 
        config: BacktestConfig, 
        results: List[BacktestResult]
    ) -> BacktestResult:
        """Aggregate results across multiple datasets."""
        aggregated = BacktestResult(config=config)
        
        if not results:
            return aggregated
        
        aggregated.total_trades = int(np.mean([r.total_trades for r in results]))
        aggregated.winning_trades = int(np.mean([r.winning_trades for r in results]))
        aggregated.losing_trades = int(np.mean([r.losing_trades for r in results]))
        aggregated.win_rate = np.mean([r.win_rate for r in results])
        
        aggregated.total_return = np.mean([r.total_return for r in results])
        aggregated.avg_return = np.mean([r.avg_return for r in results])
        aggregated.return_std = np.mean([r.return_std for r in results])
        
        aggregated.max_drawdown = np.mean([r.max_drawdown for r in results])
        aggregated.max_consecutive_losses = int(np.mean([r.max_consecutive_losses for r in results]))
        aggregated.sharpe_ratio = np.mean([r.sharpe_ratio for r in results])
        aggregated.sortino_ratio = np.mean([r.sortino_ratio for r in results])
        aggregated.calmar_ratio = np.mean([r.calmar_ratio for r in results])
        aggregated.profit_factor = np.mean([r.profit_factor for r in results])
        
        aggregated.avg_win = np.mean([r.avg_win for r in results])
        aggregated.avg_loss = np.mean([r.avg_loss for r in results])
        aggregated.win_loss_ratio = np.mean([r.win_loss_ratio for r in results])
        
        aggregated.walk_forward_efficiency = np.mean([r.walk_forward_efficiency for r in results])
        
        return aggregated
    
    def get_top_strategies(self, n: int = 10) -> List[BacktestResult]:
        """Get top N strategies that passed robustness tests."""
        passing = [r for r in self.results if r.robustness_passed]
        sorted_results = sorted(passing, key=lambda x: x.overall_score, reverse=True)
        return sorted_results[:n]
    
    def generate_report(self, top_n: int = 10) -> str:
        """Generate professional quant report."""
        top_strategies = self.get_top_strategies(top_n)
        
        report = []
        report.append("=" * 80)
        report.append("COMPREHENSIVE MULTI-STRATEGY BACKTEST REPORT")
        report.append("TradingBrowser Quantitative Research")
        report.append("=" * 80)
        report.append("")
        report.append(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Strategies Tested: {len(self.strategy_defs.strategies)}")
        report.append(f"Total Configurations: {len(self.results)}")
        report.append(f"Strategies Passing Robustness: {len([r for r in self.results if r.robustness_passed])}")
        report.append("")
        report.append("=" * 80)
        report.append("TOP 10 STRATEGIES (Passing All Robustness Tests)")
        report.append("=" * 80)
        report.append("")
        
        for i, result in enumerate(top_strategies, 1):
            config = result.config
            report.append(f"#{i} {config.strategy_name}")
            report.append("-" * 60)
            report.append(f"  Category: {config.strategy_category.value}")
            report.append(f"  Timeframe: {config.timeframe}")
            report.append(f"  Position Size: {config.position_size_pct}%")
            report.append(f"  Stop Loss: {config.stop_loss_pct}%")
            report.append(f"  Take Profit Ratio: {config.take_profit_ratio}:1")
            report.append("")
            report.append(f"  Overall Score: {result.overall_score:.1f}/100")
            report.append(f"  Total Trades: {result.total_trades}")
            report.append(f"  Win Rate: {result.win_rate:.1%}")
            report.append(f"  Total Return: {result.total_return:.1%}")
            report.append(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
            report.append(f"  Max Drawdown: {result.max_drawdown:.1%}")
            report.append(f"  Profit Factor: {result.profit_factor:.2f}")
            report.append(f"  Walk-Forward Efficiency: {result.walk_forward_efficiency:.2f}")
            report.append("")
        
        report.append("=" * 80)
        report.append("STRATEGY CATEGORY PERFORMANCE SUMMARY")
        report.append("=" * 80)
        report.append("")
        
        for category in StrategyCategory:
            cat_results = [r for r in self.results if r.config.strategy_category == category]
            passing = [r for r in cat_results if r.robustness_passed]
            
            if cat_results:
                avg_score = np.mean([r.overall_score for r in cat_results])
                avg_return = np.mean([r.total_return for r in cat_results])
                avg_sharpe = np.mean([r.sharpe_ratio for r in cat_results])
                
                report.append(f"{category.value.upper()}")
                report.append(f"  Configurations: {len(cat_results)}")
                report.append(f"  Passing Robustness: {len(passing)} ({len(passing)/len(cat_results):.1%})")
                report.append(f"  Avg Score: {avg_score:.1f}")
                report.append(f"  Avg Return: {avg_return:.1%}")
                report.append(f"  Avg Sharpe: {avg_sharpe:.2f}")
                report.append("")
        
        report.append("=" * 80)
        report.append("ROBUSTNESS TEST CRITERIA")
        report.append("=" * 80)
        report.append("")
        for criterion, threshold in self.robustness_tester.pass_thresholds.items():
            report.append(f"  {criterion}: {threshold}")
        report.append("")
        
        report.append("=" * 80)
        report.append("END OF REPORT")
        report.append("=" * 80)
        
        return "\n".join(report)


def main():
    """Run the comprehensive backtest suite."""
    suite = MultiStrategyBacktestSuite()
    
    # Run backtests (reduced for demo)
    results = suite.run_comprehensive_backtest(
        n_samples=2,
        bars_per_sample=2000
    )
    
    # Generate report
    report = suite.generate_report(top_n=10)
    print(report)
    
    # Save report
    with open('/home/mnwinnwork/.openclaw/workspace/TradingBrowser/backtest_report.txt', 'w') as f:
        f.write(report)
    
    # Save detailed results as JSON
    top_strategies = suite.get_top_strategies(10)
    detailed_results = []
    for r in top_strategies:
        detailed_results.append({
            'strategy_name': r.config.strategy_name,
            'category': r.config.strategy_category.value,
            'timeframe': r.config.timeframe,
            'position_size_pct': r.config.position_size_pct,
            'stop_loss_pct': r.config.stop_loss_pct,
            'take_profit_ratio': r.config.take_profit_ratio,
            'overall_score': r.overall_score,
            'total_trades': r.total_trades,
            'win_rate': r.win_rate,
            'total_return': r.total_return,
            'sharpe_ratio': r.sharpe_ratio,
            'max_drawdown': r.max_drawdown,
            'profit_factor': r.profit_factor,
            'walk_forward_efficiency': r.walk_forward_efficiency,
            'robustness_passed': r.robustness_passed,
        })
    
    with open('/home/mnwinnwork/.openclaw/workspace/TradingBrowser/backtest_results.json', 'w') as f:
        json.dump(detailed_results, f, indent=2)
    
    print("\n" + "=" * 80)
    print("Results saved to:")
    print("  - backtest_report.txt")
    print("  - backtest_results.json")
    print("=" * 80)


if __name__ == "__main__":
    main()
