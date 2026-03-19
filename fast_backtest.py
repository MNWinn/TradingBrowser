"""
Optimized Multi-Strategy Backtest Suite for TradingBrowser
Fast implementation for comprehensive strategy testing.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
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
    strategy_name: str
    strategy_category: StrategyCategory
    timeframe: str
    position_size_pct: float
    stop_loss_pct: float
    take_profit_ratio: float
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BacktestResult:
    config: BacktestConfig
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_return: float = 0.0
    avg_return: float = 0.0
    return_std: float = 0.0
    max_drawdown: float = 0.0
    max_consecutive_losses: int = 0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    win_loss_ratio: float = 0.0
    walk_forward_efficiency: float = 0.0
    overall_score: float = 0.0
    robustness_passed: bool = False

class FastIndicators:
    """Vectorized indicator calculations."""
    
    @staticmethod
    def sma(data: np.ndarray, period: int) -> np.ndarray:
        ret = np.cumsum(data, dtype=float)
        ret[period:] = ret[period:] - ret[:-period]
        result = np.full_like(data, np.nan)
        result[period-1:] = ret[period-1:] / period
        return result
    
    @staticmethod
    def ema(data: np.ndarray, period: int) -> np.ndarray:
        alpha = 2.0 / (period + 1)
        result = np.zeros_like(data)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i-1]
        return result
    
    @staticmethod
    def rsi(data: np.ndarray, period: int = 14) -> np.ndarray:
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gains = FastIndicators.sma(np.concatenate([[0], gains]), period)
        avg_losses = FastIndicators.sma(np.concatenate([[0], losses]), period)
        
        rs = avg_gains / (avg_losses + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def macd(data: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray]:
        ema_fast = FastIndicators.ema(data, fast)
        ema_slow = FastIndicators.ema(data, slow)
        macd_line = ema_fast - ema_slow
        signal_line = FastIndicators.ema(macd_line, signal)
        return macd_line, signal_line
    
    @staticmethod
    def bollinger_bands(data: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        middle = FastIndicators.sma(data, period)
        std = pd.Series(data).rolling(period).std().values
        upper = middle + std * std_dev
        lower = middle - std * std_dev
        return upper, middle, lower
    
    @staticmethod
    def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        return FastIndicators.sma(tr, period)
    
    @staticmethod
    def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        plus_dm = np.where(high - np.roll(high, 1) > np.roll(low, 1) - low, 
                          np.maximum(high - np.roll(high, 1), 0), 0)
        minus_dm = np.where(np.roll(low, 1) - low > high - np.roll(high, 1),
                           np.maximum(np.roll(low, 1) - low, 0), 0)
        
        tr = np.maximum(np.maximum(high - low, np.abs(high - np.roll(close, 1))), 
                       np.abs(low - np.roll(close, 1)))
        atr = FastIndicators.sma(tr, period)
        
        plus_di = 100 * FastIndicators.sma(plus_dm, period) / (atr + 1e-10)
        minus_di = 100 * FastIndicators.sma(minus_dm, period) / (atr + 1e-10)
        dx = np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10) * 100
        adx = FastIndicators.sma(dx, period)
        return adx
    
    @staticmethod
    def stochastic(high: np.ndarray, low: np.ndarray, close: np.ndarray, k_period: int = 14) -> np.ndarray:
        lowest_low = pd.Series(low).rolling(k_period).min().values
        highest_high = pd.Series(high).rolling(k_period).max().values
        k = 100 * (close - lowest_low) / (highest_high - lowest_low + 1e-10)
        return k
    
    @staticmethod
    def williams_r(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        highest_high = pd.Series(high).rolling(period).max().values
        lowest_low = pd.Series(low).rolling(period).min().values
        return -100 * (highest_high - close) / (highest_high - lowest_low + 1e-10)
    
    @staticmethod
    def roc(data: np.ndarray, period: int = 12) -> np.ndarray:
        return (data - np.roll(data, period)) / (np.roll(data, period) + 1e-10) * 100


class StrategySignals:
    """Generate signals for all strategies."""
    
    def __init__(self, df: pd.DataFrame):
        self.close = df['close'].values
        self.high = df['high'].values
        self.low = df['low'].values
        self.volume = df['volume'].values
        self.n = len(df)
        
    def ma_crossover(self, fast: int, slow: int, use_ema: bool = False) -> np.ndarray:
        if use_ema:
            fast_ma = FastIndicators.ema(self.close, fast)
            slow_ma = FastIndicators.ema(self.close, slow)
        else:
            fast_ma = FastIndicators.sma(self.close, fast)
            slow_ma = FastIndicators.sma(self.close, slow)
        return np.where(fast_ma > slow_ma, 1, np.where(fast_ma < slow_ma, -1, 0))
    
    def macd_signal(self, fast: int, slow: int, signal: int) -> np.ndarray:
        macd_line, signal_line = FastIndicators.macd(self.close, fast, slow, signal)
        return np.where((macd_line > signal_line) & (np.diff(np.concatenate([[0], macd_line])) > 0), 1,
                       np.where((macd_line < signal_line) & (np.diff(np.concatenate([[0], macd_line])) < 0), -1, 0))
    
    def adx_signal(self, threshold: int, period: int = 14) -> np.ndarray:
        adx = FastIndicators.adx(self.high, self.low, self.close, period)
        # Simplified - assume trending when ADX high
        return np.where(adx > threshold, np.where(self.close > FastIndicators.sma(self.close, 20), 1, -1), 0)
    
    def rsi_meanrev(self, oversold: int, overbought: int, period: int = 14) -> np.ndarray:
        rsi = FastIndicators.rsi(self.close, period)
        return np.where(rsi < oversold, 1, np.where(rsi > overbought, -1, 0))
    
    def bb_meanrev(self, period: int = 20, std_dev: float = 2.0) -> np.ndarray:
        upper, middle, lower = FastIndicators.bollinger_bands(self.close, period, std_dev)
        return np.where(self.close < lower, 1, np.where(self.close > upper, -1, 0))
    
    def stochastic_signal(self, k_period: int = 14) -> np.ndarray:
        k = FastIndicators.stochastic(self.high, self.low, self.close, k_period)
        return np.where(k < 20, 1, np.where(k > 80, -1, 0))
    
    def williams_r_signal(self, period: int = 14) -> np.ndarray:
        wr = FastIndicators.williams_r(self.high, self.low, self.close, period)
        return np.where(wr < -80, 1, np.where(wr > -20, -1, 0))
    
    def roc_signal(self, period: int = 12) -> np.ndarray:
        roc = FastIndicators.roc(self.close, period)
        return np.where(roc > 3, 1, np.where(roc < -3, -1, 0))
    
    def atr_breakout(self, period: int = 14, mult: float = 2.0) -> np.ndarray:
        atr = FastIndicators.atr(self.high, self.low, self.close, period)
        upper = FastIndicators.sma(self.close, period) + mult * atr
        lower = FastIndicators.sma(self.close, period) - mult * atr
        return np.where(self.close > upper, 1, np.where(self.close < lower, -1, 0))
    
    def consensus_signal(self) -> np.ndarray:
        rsi_sig = self.rsi_meanrev(30, 70)
        macd_sig = self.macd_signal(12, 26, 9)
        bb_sig = self.bb_meanrev()
        stoch_sig = self.stochastic_signal()
        
        consensus = rsi_sig + macd_sig + bb_sig + stoch_sig
        return np.where(consensus >= 2, 1, np.where(consensus <= -2, -1, 0))
    
    def weighted_signal(self) -> np.ndarray:
        trend = self.ma_crossover(12, 26, use_ema=True)
        momentum = np.where(FastIndicators.roc(self.close, 14) > 0, 1, -1)
        meanrev = self.rsi_meanrev(30, 70)
        
        weighted = 0.3 * trend + 0.3 * momentum + 0.4 * meanrev
        return np.where(weighted > 0.3, 1, np.where(weighted < -0.3, -1, 0))


def run_fast_backtest(
    close: np.ndarray,
    signals: np.ndarray,
    atr: np.ndarray,
    position_size: float,
    stop_loss: float,
    take_profit_ratio: float,
    initial_capital: float = 10000.0
) -> Dict[str, Any]:
    """Run optimized backtest."""
    n = len(close)
    capital = initial_capital
    position = 0
    entry_price = 0.0
    
    trades = []
    equity = [capital]
    
    warmup = 50
    
    for i in range(warmup, n - 1):
        current_price = close[i]
        current_signal = signals[i]
        current_atr = atr[i] if not np.isnan(atr[i]) else current_price * 0.02
        
        # Exit logic
        if position != 0:
            if position == 1:
                pnl_pct = (current_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - current_price) / entry_price
            
            sl_pct = stop_loss / 100
            tp_pct = sl_pct * take_profit_ratio
            
            exit_reason = None
            if pnl_pct <= -sl_pct:
                exit_reason = 'stop'
            elif pnl_pct >= tp_pct:
                exit_reason = 'target'
            elif (position == 1 and current_signal == -1) or (position == -1 and current_signal == 1):
                exit_reason = 'reversal'
            
            if exit_reason:
                pos_value = capital * position_size
                pnl = pnl_pct * pos_value
                capital += pnl
                trades.append({'pnl': pnl, 'pnl_pct': pnl_pct})
                position = 0
                entry_price = 0
        
        # Entry logic
        if position == 0 and current_signal != 0:
            position = current_signal
            entry_price = current_price
        
        equity.append(capital)
    
    # Close final position
    if position != 0:
        final_price = close[-1]
        if position == 1:
            pnl_pct = (final_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - final_price) / entry_price
        pos_value = capital * position_size
        pnl = pnl_pct * pos_value
        capital += pnl
        trades.append({'pnl': pnl, 'pnl_pct': pnl_pct})
        equity.append(capital)
    
    # Calculate metrics
    if not trades:
        return {'total_trades': 0}
    
    pnls = [t['pnl'] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    
    total_return = (capital - initial_capital) / initial_capital
    win_rate = len(wins) / len(trades) if trades else 0
    
    equity_arr = np.array(equity)
    peak = np.maximum.accumulate(equity_arr)
    drawdown = (peak - equity_arr) / peak
    max_dd = np.max(drawdown)
    
    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    wl_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    
    profit_factor = abs(sum(wins) / sum(losses)) if sum(losses) != 0 else 0
    
    return_std = np.std(pnls) if len(pnls) > 1 else 1
    sharpe = (np.mean(pnls) / return_std) * np.sqrt(252) if return_std > 0 else 0
    
    return {
        'total_trades': len(trades),
        'winning_trades': len(wins),
        'losing_trades': len(losses),
        'win_rate': win_rate,
        'total_return': total_return,
        'avg_return': np.mean(pnls),
        'max_drawdown': max_dd,
        'profit_factor': profit_factor,
        'sharpe_ratio': sharpe,
        'win_loss_ratio': wl_ratio,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
    }


def generate_data(n: int = 2000, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    np.random.seed(seed)
    
    returns = np.random.normal(0.0001, 0.02, n)
    for i in range(2, n):
        returns[i] += 0.1 * returns[i-1]
    
    # Add regime changes
    changes = np.random.choice([0, 1], n, p=[0.98, 0.02])
    for i in range(n):
        if changes[i]:
            returns[i] += np.random.choice([-1, 1]) * 0.04
    
    prices = 100 * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame({
        'open': prices * (1 + np.random.normal(0, 0.001, n)),
        'high': prices * (1 + abs(np.random.normal(0, 0.01, n))),
        'low': prices * (1 - abs(np.random.normal(0, 0.01, n))),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, n)
    })
    
    return df


def run_comprehensive_suite():
    """Run the comprehensive backtest suite."""
    print("=" * 80)
    print("COMPREHENSIVE MULTI-STRATEGY BACKTEST SUITE")
    print("TradingBrowser Quantitative Research")
    print("=" * 80)
    print()
    
    # Generate test data
    print("Generating synthetic market data...")
    datasets = [generate_data(2000, seed=42+i) for i in range(3)]
    print(f"Generated {len(datasets)} datasets")
    print()
    
    # Define all strategies
    strategies = [
        # Trend Following
        {'name': 'MA_Cross_5_20', 'cat': StrategyCategory.TREND_FOLLOWING, 'func': lambda s: s.ma_crossover(5, 20)},
        {'name': 'MA_Cross_10_50', 'cat': StrategyCategory.TREND_FOLLOWING, 'func': lambda s: s.ma_crossover(10, 50)},
        {'name': 'MA_Cross_20_200', 'cat': StrategyCategory.TREND_FOLLOWING, 'func': lambda s: s.ma_crossover(20, 200)},
        {'name': 'EMA_Cross_12_26', 'cat': StrategyCategory.TREND_FOLLOWING, 'func': lambda s: s.ma_crossover(12, 26, True)},
        {'name': 'EMA_Cross_20_200', 'cat': StrategyCategory.TREND_FOLLOWING, 'func': lambda s: s.ma_crossover(20, 200, True)},
        {'name': 'MACD_12_26_9', 'cat': StrategyCategory.TREND_FOLLOWING, 'func': lambda s: s.macd_signal(12, 26, 9)},
        {'name': 'MACD_8_21_5', 'cat': StrategyCategory.TREND_FOLLOWING, 'func': lambda s: s.macd_signal(8, 21, 5)},
        {'name': 'ADX_Trend_25', 'cat': StrategyCategory.TREND_FOLLOWING, 'func': lambda s: s.adx_signal(25)},
        
        # Mean Reversion
        {'name': 'RSI_MeanRev_30_70', 'cat': StrategyCategory.MEAN_REVERSION, 'func': lambda s: s.rsi_meanrev(30, 70)},
        {'name': 'RSI_MeanRev_20_80', 'cat': StrategyCategory.MEAN_REVERSION, 'func': lambda s: s.rsi_meanrev(20, 80)},
        {'name': 'RSI_MeanRev_25_75', 'cat': StrategyCategory.MEAN_REVERSION, 'func': lambda s: s.rsi_meanrev(25, 75)},
        {'name': 'BB_MeanRev', 'cat': StrategyCategory.MEAN_REVERSION, 'func': lambda s: s.bb_meanrev(20, 2.0)},
        {'name': 'Stochastic_MR', 'cat': StrategyCategory.MEAN_REVERSION, 'func': lambda s: s.stochastic_signal(14)},
        {'name': 'WilliamsR_MR', 'cat': StrategyCategory.MEAN_REVERSION, 'func': lambda s: s.williams_r_signal(14)},
        
        # Momentum
        {'name': 'ROC_Momentum', 'cat': StrategyCategory.MOMENTUM, 'func': lambda s: s.roc_signal(12)},
        {'name': 'ROC_Momentum_20', 'cat': StrategyCategory.MOMENTUM, 'func': lambda s: s.roc_signal(20)},
        
        # Volatility
        {'name': 'ATR_Breakout', 'cat': StrategyCategory.VOLATILITY, 'func': lambda s: s.atr_breakout(14, 2.0)},
        
        # Combined
        {'name': 'Consensus_3Sig', 'cat': StrategyCategory.COMBINED, 'func': lambda s: s.consensus_signal()},
        {'name': 'Weighted_Vote', 'cat': StrategyCategory.COMBINED, 'func': lambda s: s.weighted_signal()},
    ]
    
    # Test configurations
    timeframes = ['5m', '15m', '1h']
    position_sizes = [0.01, 0.02, 0.03, 0.05]
    stop_losses = [0.01, 0.02, 0.03]
    take_profit_ratios = [1.5, 2.0, 3.0, 4.0]
    
    print(f"Strategies: {len(strategies)}")
    print(f"Timeframes: {len(timeframes)}")
    print(f"Position Sizes: {len(position_sizes)}")
    print(f"Stop Losses: {len(stop_losses)}")
    print(f"Take Profit Ratios: {len(take_profit_ratios)}")
    print()
    
    # Run backtests
    all_results = []
    total_configs = len(strategies) * len(timeframes) * len(position_sizes) * len(stop_losses) * len(take_profit_ratios)
    
    print(f"Total configurations to test: {total_configs}")
    print("Running backtests...")
    print()
    
    config_num = 0
    for strategy in strategies:
        for tf in timeframes:
            # Precompute signals once per strategy/dataset
            dataset_signals = []
            for df in datasets:
                sig_gen = StrategySignals(df)
                signals = strategy['func'](sig_gen)
                atr = FastIndicators.atr(df['high'].values, df['low'].values, df['close'].values, 14)
                dataset_signals.append((df['close'].values, signals, atr))
            
            for pos_size in position_sizes:
                for sl in stop_losses:
                    for tp_ratio in take_profit_ratios:
                        config_num += 1
                        
                        if config_num % 500 == 0:
                            print(f"  Progress: {config_num}/{total_configs} ({config_num/total_configs*100:.1f}%)")
                        
                        config = BacktestConfig(
                            strategy_name=strategy['name'],
                            strategy_category=strategy['cat'],
                            timeframe=tf,
                            position_size_pct=pos_size * 100,
                            stop_loss_pct=sl * 100,
                            take_profit_ratio=tp_ratio
                        )
                        
                        # Run on all datasets
                        dataset_results = []
                        for close, signals, atr in dataset_signals:
                            result = run_fast_backtest(
                                close, signals, atr,
                                pos_size, sl * 100, tp_ratio
                            )
                            if result['total_trades'] > 0:
                                dataset_results.append(result)
                        
                        if dataset_results:
                            # Aggregate results
                            avg_result = BacktestResult(config=config)
                            avg_result.total_trades = int(np.mean([r['total_trades'] for r in dataset_results]))
                            avg_result.winning_trades = int(np.mean([r['winning_trades'] for r in dataset_results]))
                            avg_result.losing_trades = int(np.mean([r['losing_trades'] for r in dataset_results]))
                            avg_result.win_rate = np.mean([r['win_rate'] for r in dataset_results])
                            avg_result.total_return = np.mean([r['total_return'] for r in dataset_results])
                            avg_result.avg_return = np.mean([r['avg_return'] for r in dataset_results])
                            avg_result.max_drawdown = np.mean([r['max_drawdown'] for r in dataset_results])
                            avg_result.profit_factor = np.mean([r['profit_factor'] for r in dataset_results])
                            avg_result.sharpe_ratio = np.mean([r['sharpe_ratio'] for r in dataset_results])
                            avg_result.win_loss_ratio = np.mean([r['win_loss_ratio'] for r in dataset_results])
                            avg_result.avg_win = np.mean([r['avg_win'] for r in dataset_results])
                            avg_result.avg_loss = np.mean([r['avg_loss'] for r in dataset_results])
                            
                            # Calculate score
                            score = (
                                min(avg_result.win_rate * 100 / 70 * 20, 20) +
                                min(max(avg_result.total_return, 0) * 100 / 50 * 25, 25) +
                                min(max(avg_result.sharpe_ratio, 0) / 2.0 * 20, 20) +
                                max(0, 15 - avg_result.max_drawdown * 100 / 20 * 15) +
                                min(max(avg_result.profit_factor - 1, 0) / 2.0 * 10, 10)
                            )
                            avg_result.overall_score = score
                            
                            # Robustness check
                            avg_result.robustness_passed = (
                                avg_result.total_trades >= 20 and
                                avg_result.win_rate >= 0.45 and
                                avg_result.max_drawdown <= 0.25 and
                                avg_result.sharpe_ratio >= 0.3 and
                                avg_result.profit_factor >= 1.1
                            )
                            
                            all_results.append(avg_result)
    
    print()
    print("=" * 80)
    print("BACKTEST COMPLETE")
    print("=" * 80)
    print()
    
    # Get top strategies
    passing = [r for r in all_results if r.robustness_passed]
    top_strategies = sorted(passing, key=lambda x: x.overall_score, reverse=True)[:10]
    
    print(f"Total configurations tested: {len(all_results)}")
    print(f"Strategies passing robustness: {len(passing)} ({len(passing)/len(all_results)*100:.1f}%)")
    print()
    
    # Generate report
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("TOP 10 STRATEGIES (Passing All Robustness Tests)")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    for i, r in enumerate(top_strategies, 1):
        report_lines.append(f"#{i} {r.config.strategy_name}")
        report_lines.append("-" * 60)
        report_lines.append(f"  Category: {r.config.strategy_category.value}")
        report_lines.append(f"  Timeframe: {r.config.timeframe}")
        report_lines.append(f"  Position Size: {r.config.position_size_pct}%")
        report_lines.append(f"  Stop Loss: {r.config.stop_loss_pct}%")
        report_lines.append(f"  Take Profit Ratio: {r.config.take_profit_ratio}:1")
        report_lines.append("")
        report_lines.append(f"  Overall Score: {r.overall_score:.1f}/100")
        report_lines.append(f"  Total Trades: {r.total_trades}")
        report_lines.append(f"  Win Rate: {r.win_rate:.1%}")
        report_lines.append(f"  Total Return: {r.total_return:.1%}")
        report_lines.append(f"  Sharpe Ratio: {r.sharpe_ratio:.2f}")
        report_lines.append(f"  Max Drawdown: {r.max_drawdown:.1%}")
        report_lines.append(f"  Profit Factor: {r.profit_factor:.2f}")
        report_lines.append(f"  Win/Loss Ratio: {r.win_loss_ratio:.2f}")
        report_lines.append("")
    
    # Category summary
    report_lines.append("=" * 80)
    report_lines.append("STRATEGY CATEGORY PERFORMANCE")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    for cat in StrategyCategory:
        cat_results = [r for r in all_results if r.config.strategy_category == cat]
        passing_cat = [r for r in cat_results if r.robustness_passed]
        
        if cat_results:
            avg_score = np.mean([r.overall_score for r in cat_results])
            avg_return = np.mean([r.total_return for r in cat_results])
            avg_sharpe = np.mean([r.sharpe_ratio for r in cat_results])
            
            report_lines.append(f"{cat.value.upper()}")
            report_lines.append(f"  Configurations: {len(cat_results)}")
            report_lines.append(f"  Passing: {len(passing_cat)} ({len(passing_cat)/len(cat_results)*100:.1f}%)")
            report_lines.append(f"  Avg Score: {avg_score:.1f}")
            report_lines.append(f"  Avg Return: {avg_return:.1%}")
            report_lines.append(f"  Avg Sharpe: {avg_sharpe:.2f}")
            report_lines.append("")
    
    report_lines.append("=" * 80)
    report_lines.append("ROBUSTNESS CRITERIA")
    report_lines.append("=" * 80)
    report_lines.append("  - Min Trades: 20")
    report_lines.append("  - Min Win Rate: 45%")
    report_lines.append("  - Max Drawdown: 25%")
    report_lines.append("  - Min Sharpe: 0.3")
    report_lines.append("  - Min Profit Factor: 1.1")
    report_lines.append("")
    report_lines.append("=" * 80)
    report_lines.append("END OF REPORT")
    report_lines.append("=" * 80)
    
    report = "\n".join(report_lines)
    print(report)
    
    # Save results
    with open('/home/mnwinnwork/.openclaw/workspace/TradingBrowser/backtest_report.txt', 'w') as f:
        f.write(report)
    
    # Save JSON results
    json_results = []
    for r in top_strategies:
        json_results.append({
            'rank': len(json_results) + 1,
            'strategy_name': r.config.strategy_name,
            'category': r.config.strategy_category.value,
            'timeframe': r.config.timeframe,
            'position_size_pct': r.config.position_size_pct,
            'stop_loss_pct': r.config.stop_loss_pct,
            'take_profit_ratio': r.config.take_profit_ratio,
            'overall_score': round(r.overall_score, 2),
            'total_trades': r.total_trades,
            'win_rate': round(r.win_rate, 4),
            'total_return': round(r.total_return, 4),
            'sharpe_ratio': round(r.sharpe_ratio, 4),
            'max_drawdown': round(r.max_drawdown, 4),
            'profit_factor': round(r.profit_factor, 4),
            'win_loss_ratio': round(r.win_loss_ratio, 4),
            'robustness_passed': r.robustness_passed,
        })
    
    with open('/home/mnwinnwork/.openclaw/workspace/TradingBrowser/backtest_results.json', 'w') as f:
        json.dump(json_results, f, indent=2)
    
    print()
    print("Results saved to:")
    print("  - backtest_report.txt")
    print("  - backtest_results.json")
    
    return top_strategies


if __name__ == "__main__":
    run_comprehensive_suite()
