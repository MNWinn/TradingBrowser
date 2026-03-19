#!/usr/bin/env python3
"""
$50 Capital Scaling Strategy - Quantitative Edge Application
Uses ATR Breakout research with fractional share optimization
"""

import json
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Trade:
    date: str
    ticker: str
    entry: float
    exit: float
    shares: float
    side: str
    pnl: float
    pnl_pct: float
    capital_after: float
    reasoning: str

class FiftyDollarStrategy:
    def __init__(self, initial_capital: float = 50.0):
        self.capital = initial_capital
        self.initial_capital = initial_capital
        self.trades: List[Trade] = []
        self.peak_capital = initial_capital
        self.max_drawdown = 0
        
    def can_trade(self) -> bool:
        """Check if we have enough capital after costs"""
        # Need at least $10 to make meaningful trade after costs
        return self.capital >= 10
    
    def calculate_position(self, price: float, risk_pct: float = 0.02) -> float:
        """Calculate fractional shares for $50 capital"""
        risk_amount = self.capital * risk_pct  # $1 risk
        # ATR typically 1-3% of price for SPY
        atr = price * 0.015  # 1.5% ATR
        stop_distance = atr  # Stop at 1 ATR
        
        # Position size = Risk / Stop distance
        if stop_distance > 0:
            position_value = risk_amount / (stop_distance / price)
        else:
            position_value = self.capital * 0.20  # 20% of capital
            
        # Cap at 80% of capital (leave buffer)
        position_value = min(position_value, self.capital * 0.80)
        
        shares = position_value / price
        return round(shares, 4)  # Fractional shares to 4 decimals
    
    def simulate_day(self, day: int, date: str) -> Optional[Trade]:
        """Simulate one trading day with ATR Breakout strategy"""
        
        if not self.can_trade():
            return None
            
        # Current SPY price (simulated around $200)
        price = 200 + (day * 0.5) + (day % 7 * 2)  # Trend + noise
        
        # ATR Breakout Signal Logic
        # Previous day ATR
        prev_atr = price * 0.015
        
        # Breakout level = yesterday's close + 0.5 ATR
        breakout_level = price - 1 + (0.5 * prev_atr)
        
        # Current price breaks above?
        current_price = price + (day % 3)  # Some days breakout, some don't
        
        signal_strength = 0
        if current_price > breakout_level:
            signal_strength = (current_price - breakout_level) / prev_atr
            
        # Only trade if signal > 0.5 (moderate conviction)
        if signal_strength < 0.5:
            return None  # No trade today
            
        # Calculate position
        shares = self.calculate_position(current_price)
        position_value = shares * current_price
        
        if position_value < 5:  # Too small
            return None
            
        # Risk management
        stop_price = current_price - (current_price * 0.02)  # 2% stop
        target_price = current_price + (current_price * 0.03)  # 3% target (1.5:1)
        
        # Simulate outcome based on research (47.7% win rate)
        import random
        is_win = random.random() < 0.477
        
        if is_win:
            exit_price = target_price
            pnl_pct = 0.03
        else:
            exit_price = stop_price
            pnl_pct = -0.02
            
        pnl = position_value * pnl_pct
        
        # Costs (spread + commission)
        spread_cost = position_value * 0.001  # 0.1% spread
        commission = 0  # Alpaca free
        total_cost = spread_cost + commission
        
        pnl -= total_cost
        
        # Update capital
        self.capital += pnl
        
        # Track drawdown
        if self.capital > self.peak_capital:
            self.peak_capital = self.capital
        dd = (self.peak_capital - self.capital) / self.peak_capital
        self.max_drawdown = max(self.max_drawdown, dd)
        
        reasoning = f"ATR Breakout: Signal strength {signal_strength:.2f}, "
        reasoning += f"Position: ${position_value:.2f} ({shares} shares), "
        reasoning += f"Risk: 2%, Target: 3%"
        
        trade = Trade(
            date=date,
            ticker="SPY",
            entry=current_price,
            exit=exit_price,
            shares=shares,
            side="LONG",
            pnl=pnl,
            pnl_pct=pnl_pct * 100,
            capital_after=self.capital,
            reasoning=reasoning
        )
        
        self.trades.append(trade)
        return trade
    
    def run_simulation(self, days: int = 90):
        """Run 90-day simulation"""
        print(f"$50 SCALING SIMULATION - ATR Breakout Strategy")
        print("=" * 60)
        print(f"Starting Capital: ${self.initial_capital:.2f}")
        print(f"Strategy: ATR Breakout (47.7% win rate, 1.5:1 R/R)")
        print(f"Risk per trade: 2% of capital")
        print(f"Fractional shares enabled")
        print("=" * 60)
        print()
        
        from datetime import datetime, timedelta
        start_date = datetime(2024, 1, 1)
        
        for day in range(days):
            current_date = start_date + timedelta(days=day)
            date_str = current_date.strftime("%Y-%m-%d")
            
            trade = self.simulate_day(day, date_str)
            
            if trade:
                status = "✅ WIN" if trade.pnl > 0 else "❌ LOSS"
                print(f"{date_str}: {status} ${trade.pnl:+.2f} | "
                      f"Capital: ${trade.capital_after:.2f} | "
                      f"{trade.shares} shares @ ${trade.entry:.2f}")
                
            # Weekly summary
            if (day + 1) % 7 == 0:
                week_pnl = self.capital - self.initial_capital
                week_return = (week_pnl / self.initial_capital) * 100
                print(f"--- Week {(day+1)//7}: ${self.capital:.2f} ({week_return:+.1f}%) ---")
                print()
        
        # Final results
        total_pnl = self.capital - self.initial_capital
        total_return = (total_pnl / self.initial_capital) * 100
        wins = len([t for t in self.trades if t.pnl > 0])
        losses = len([t for t in self.trades if t.pnl <= 0])
        win_rate = wins / len(self.trades) * 100 if self.trades else 0
        
        print("=" * 60)
        print("FINAL RESULTS (90 Days)")
        print("=" * 60)
        print(f"Starting Capital: ${self.initial_capital:.2f}")
        print(f"Ending Capital: ${self.capital:.2f}")
        print(f"Total P&L: ${total_pnl:+.2f} ({total_return:+.1f}%)")
        print(f"Total Trades: {len(self.trades)}")
        print(f"Wins: {wins} | Losses: {losses}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Max Drawdown: {self.max_drawdown*100:.1f}%")
        print(f"Avg Trade: ${total_pnl/len(self.trades) if self.trades else 0:+.2f}")
        print()
        
        # Scaling projection
        if total_return > 0:
            monthly_return = total_return / 3
            print("SCALING PROJECTION:")
            print(f"Monthly Return: {monthly_return:.1f}%")
            print(f"Compound Growth:")
            capital = self.initial_capital
            for month in range(1, 13):
                capital *= (1 + monthly_return/100)
                print(f"  Month {month}: ${capital:.2f}")
        
        return {
            "starting_capital": self.initial_capital,
            "ending_capital": self.capital,
            "total_return": total_return,
            "trades": len(self.trades),
            "win_rate": win_rate,
            "max_drawdown": self.max_drawdown * 100
        }

def main():
    strategy = FiftyDollarStrategy(initial_capital=50.0)
    results = strategy.run_simulation(days=90)
    
    # Save results
    with open('fifty_dollar_simulation.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 60)
    print("SIMULATION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
