"""
$100,000 Paper Trading Configuration - Full Strategy
Proper position sizing, not micro-trades
"""

TRADING_CONFIG = {
    # Capital
    'initial_capital': 100000.00,
    'current_capital': 100000.00,
    
    # Risk Management (Professional)
    'risk_per_trade_pct': 0.02,  # 2% = $2,000 risk per trade
    'max_position_pct': 0.10,     # 10% max = $10,000 per position
    'max_drawdown_stop': 0.10,    # Stop trading at 10% drawdown
    'daily_loss_limit': 0.05,     # Stop after 5% daily loss
    
    # Strategy: ATR Breakout
    'strategy': 'ATR_Breakout',
    'timeframe': '5m',
    'atr_period': 14,
    'breakout_threshold': 0.5,    # 0.5 ATR breakout
    
    # Entry/Exit
    'stop_loss_pct': 0.02,        # 2% stop loss
    'take_profit_pct': 0.03,      # 3% target (1.5:1 R/R)
    'trailing_stop': False,       # No trailing initially
    
    # MiroFish Integration
    'mirofish_min_confidence': 0.70,  # 70% minimum
    'use_mirofish_confirmation': True,
    
    # Position Sizing
    'position_sizing_method': 'fixed_risk',  # Fixed $ risk per trade
    'fixed_risk_amount': 2000.00,  # $2,000 risk per trade
    
    # Trade Management
    'max_trades_per_day': 3,
    'max_open_positions': 2,
    'time_window_start': '09:45',  # 9:45 AM ET
    'time_window_end': '15:30',    # 3:30 PM ET
    
    # Tickers
    'primary_tickers': ['SPY', 'QQQ', 'IWM'],  # Index ETFs
    'secondary_tickers': ['AAPL', 'MSFT', 'NVDA', 'TSLA'],  # Large caps
    
    # Execution
    'order_type': 'MARKET',  # Market orders for speed
    'time_in_force': 'DAY',  # Day orders
    'allow_fractional': True,  # Use fractional shares
}

def calculate_position_size(capital: float, risk_amount: float, entry_price: float, stop_price: float) -> dict:
    """Calculate proper position size for $100k strategy"""
    
    # Risk amount (default $2,000)
    risk = risk_amount
    
    # Stop distance as percentage
    stop_distance_pct = abs(entry_price - stop_price) / entry_price
    
    # Position value = Risk / Stop distance
    if stop_distance_pct > 0:
        position_value = risk / stop_distance_pct
    else:
        position_value = capital * 0.05  # Fallback: 5% of capital
    
    # Cap at max position size
    max_position = capital * TRADING_CONFIG['max_position_pct']
    position_value = min(position_value, max_position)
    
    # Calculate shares
    shares = position_value / entry_price
    
    # Round to 2 decimal places for fractional shares
    shares = round(shares, 2)
    
    return {
        'shares': shares,
        'position_value': shares * entry_price,
        'risk_amount': shares * entry_price * stop_distance_pct,
        'risk_pct_of_capital': (shares * entry_price * stop_distance_pct) / capital * 100,
        'position_pct_of_capital': (shares * entry_price) / capital * 100
    }

# Example calculation
if __name__ == "__main__":
    print("=" * 60)
    print("$100,000 PAPER TRADING - POSITION SIZING EXAMPLES")
    print("=" * 60)
    
    examples = [
        {'capital': 100000, 'entry': 200.00, 'stop': 196.00, 'risk': 2000},
        {'capital': 100000, 'entry': 400.00, 'stop': 392.00, 'risk': 2000},
        {'capital': 100000, 'entry': 150.00, 'stop': 147.00, 'risk': 2000},
    ]
    
    for ex in examples:
        result = calculate_position_size(ex['capital'], ex['risk'], ex['entry'], ex['stop'])
        print(f"\nEntry: ${ex['entry']:.2f} | Stop: ${ex['stop']:.2f}")
        print(f"  Shares: {result['shares']}")
        print(f"  Position Value: ${result['position_value']:,.2f}")
        print(f"  Risk Amount: ${result['risk_amount']:,.2f}")
        print(f"  Risk % of Capital: {result['risk_pct_of_capital']:.2f}%")
        print(f"  Position % of Capital: {result['position_pct_of_capital']:.2f}%")
    
    print("\n" + "=" * 60)
    print("Strategy: Risk $2,000 per trade (2% of $100k)")
    print("Stop Loss: 2% from entry")
    print("Target: 3% from entry (1.5:1 reward/risk)")
    print("Max Position: 10% of capital ($10,000)")
    print("=" * 60)
