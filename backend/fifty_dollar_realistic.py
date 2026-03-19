#!/usr/bin/env python3
"""
$50 SCALING STRATEGY - REALISTIC PROJECTION
Based on ATR Breakout research with fractional shares
"""

import random
from datetime import datetime

def simulate_50_dollar_scaling():
    """Realistic simulation of $50 scaling with ATR Breakout"""
    
    print("=" * 70)
    print("$50 SCALING STRATEGY - QUANTITATIVE PROJECTION")
    print("=" * 70)
    print()
    print("STRATEGY: ATR Breakout on SPY (Fractional Shares)")
    print("Based on research: 47.7% win rate, 1.5:1 reward/risk")
    print()
    
    # Parameters from research
    win_rate = 0.477
    avg_win_pct = 0.03  # 3%
    avg_loss_pct = -0.02  # -2%
    trades_per_month = 12  # Conservative - every 2-3 days
    
    print("PARAMETERS:")
    print(f"  Win Rate: {win_rate:.1%}")
    print(f"  Avg Win: {avg_win_pct:.1%}")
    print(f"  Avg Loss: {avg_loss_pct:.1%}")
    print(f"  Trades/Month: {trades_per_month}")
    print(f"  Position Size: $10-40 per trade (20-80% of capital)")
    print(f"  Risk per Trade: 2% of capital ($1 max loss)")
    print()
    
    # Monthly simulation
    capital = 50.0
    print("=" * 70)
    print("MONTH-BY-MONTH PROJECTION (Realistic)")
    print("=" * 70)
    print(f"{'Month':<8} {'Start':<10} {'Trades':<8} {'Wins':<6} {'PnL':<12} {'End':<10} {'Return':<10}")
    print("-" * 70)
    
    for month in range(1, 13):
        start_capital = capital
        wins = 0
        losses = 0
        monthly_pnl = 0
        
        for _ in range(trades_per_month):
            # Determine position size (20-40% of capital, min $10)
            position_pct = random.uniform(0.20, 0.40)
            position_size = max(10, capital * position_pct)
            position_size = min(position_size, capital * 0.80)  # Cap at 80%
            
            # Simulate trade
            is_win = random.random() < win_rate
            
            if is_win:
                pnl = position_size * avg_win_pct
                wins += 1
            else:
                pnl = position_size * avg_loss_pct
                losses += 1
                
            # Subtract spread cost (0.1%)
            spread_cost = position_size * 0.001
            pnl -= spread_cost
            
            monthly_pnl += pnl
            capital += pnl
            
            # Stop if capital too low
            if capital < 10:
                break
        
        monthly_return = (monthly_pnl / start_capital) * 100
        
        print(f"{month:<8} ${start_capital:<9.2f} {trades_per_month:<8} {wins:<6} "
              f"${monthly_pnl:<+11.2f} ${capital:<9.2f} {monthly_return:+.1f}%")
    
    print("-" * 70)
    total_return = ((capital - 50) / 50) * 100
    print(f"FINAL: ${capital:.2f} | Total Return: {total_return:+.1f}% | "
          f"Annualized: {(total_return):.0f}%")
    print("=" * 70)
    print()
    
    # Multiple scenarios
    print("=" * 70)
    print("SCENARIO ANALYSIS (Based on 1000 Simulations)")
    print("=" * 70)
    
    scenarios = []
    for _ in range(1000):
        cap = 50.0
        for _ in range(12):  # 12 months
            for _ in range(trades_per_month):
                position = max(10, cap * random.uniform(0.20, 0.40))
                position = min(position, cap * 0.80)
                
                if random.random() < win_rate:
                    pnl = position * avg_win_pct
                else:
                    pnl = position * avg_loss_pct
                    
                pnl -= position * 0.001  # Spread
                cap += pnl
                
                if cap < 10:
                    break
            if cap < 10:
                break
        scenarios.append(cap)
    
    scenarios.sort()
    p10 = scenarios[100]  # 10th percentile
    p50 = scenarios[500]  # Median
    p90 = scenarios[900]  # 90th percentile
    
    print(f"Worst Case (10th percentile):  ${p10:.2f} ({((p10-50)/50)*100:+.0f}%)")
    print(f"Median (50th percentile):       ${p50:.2f} ({((p50-50)/50)*100:+.0f}%)")
    print(f"Best Case (90th percentile):    ${p90:.2f} ({((p90-50)/50)*100:+.0f}%)")
    print()
    
    profitable = sum(1 for s in scenarios if s > 50)
    print(f"Probability of Profit: {profitable/10:.0f}%")
    print(f"Probability of Doubling: {sum(1 for s in scenarios if s > 100)/10:.0f}%")
    print(f"Probability of Ruin (<$10): {sum(1 for s in scenarios if s < 10)/10:.0f}%")
    print("=" * 70)
    print()
    
    # Risk Management Rules
    print("=" * 70)
    print("RISK MANAGEMENT RULES FOR $50 CAPITAL")
    print("=" * 70)
    print("1. NEVER risk more than $1 per trade (2% of $50)")
    print("2. STOP trading after 3 consecutive losses")
    print("3. STOP if capital drops below $40 (20% drawdown)")
    print("4. Only trade ATR Breakout with >70% MiroFish confidence")
    print("5. Trade only SPY/QQQ (liquid, tight spreads)")
    print("6. Use fractional shares via Robinhood/Webull")
    print("7. Maximum 1 trade per day")
    print("8. Take profits at 1.5:1 ratio (never get greedy)")
    print()
    print("CAPITAL PRESERVATION > GROWTH at $50 scale")
    print("=" * 70)
    print()
    
    # The Reality
    print("=" * 70)
    print("REALISTIC EXPECTATIONS")
    print("=" * 70)
    print("Month 1-3: LEARNING PHASE")
    print("  - Expect $45-60 range")
    print("  - Focus on execution quality")
    print("  - Document every trade")
    print()
    print("Month 4-6: VALIDATION PHASE")
    print("  - If profitable, scale to $100-200")
    print("  - If losing, reassess strategy")
    print()
    print("Month 7-12: SCALING PHASE")
    print("  - With proven edge, increase size gradually")
    print("  - Target: $200-500 by month 12")
    print()
    print("CRITICAL: At $50, one bad trade can ruin you.")
    print("Goal: SURVIVE first, then scale.")
    print("=" * 70)

if __name__ == "__main__":
    random.seed(42)  # Reproducible
    simulate_50_dollar_scaling()
