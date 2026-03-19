#!/usr/bin/env python3
"""
Simple Paper Trading Test for TradingBrowser

This script demonstrates paper trading functionality by:
1. Creating a practice portfolio
2. Executing a few paper trades
3. Showing portfolio performance
"""

import asyncio
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from decimal import Decimal

try:
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.services.practice import get_practice_engine
    from app.services.execution import AdapterFactory
    print("✓ Imports successful\n")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)


async def test_practice_trading():
    """Test the practice trading engine."""
    print("="*60)
    print("TESTING PRACTICE TRADING ENGINE")
    print("="*60)
    
    db = SessionLocal()
    engine = get_practice_engine(db)
    
    user_id = "test_trader_001"
    
    # Step 1: Create portfolio
    print("\n1. Creating practice portfolio...")
    portfolio = engine.create_portfolio(
        user_id=user_id,
        initial_balance=Decimal("100000.00")
    )
    print(f"   ✓ Portfolio created with ${portfolio.initial_balance} initial balance")
    
    # Step 2: Execute buy trade
    print("\n2. Executing BUY trade (AAPL x 10 @ $175.50)...")
    trade1 = await engine.execute_trade(
        user_id=user_id,
        ticker="AAPL",
        side="buy",
        quantity=Decimal("10"),
        market_price=Decimal("175.50"),
        rationale={"test": "First paper trade", "strategy": "buy_and_hold"}
    )
    print(f"   ✓ Trade executed: {trade1.trade_id}")
    print(f"     - Status: {trade1.status.value}")
    print(f"     - Fill Price: ${trade1.price}")
    print(f"     - Commission: ${trade1.commission}")
    print(f"     - Total Cost: ${trade1.total_cost}")
    
    # Step 3: Execute another buy
    print("\n3. Executing BUY trade (MSFT x 5 @ $330.00)...")
    trade2 = await engine.execute_trade(
        user_id=user_id,
        ticker="MSFT",
        side="buy",
        quantity=Decimal("5"),
        market_price=Decimal("330.00"),
        rationale={"test": "Second paper trade", "strategy": "diversification"}
    )
    print(f"   ✓ Trade executed: {trade2.trade_id}")
    print(f"     - Status: {trade2.status.value}")
    print(f"     - Fill Price: ${trade2.price}")
    
    # Step 4: Check portfolio
    print("\n4. Checking portfolio summary...")
    summary = engine.get_portfolio_summary(user_id)
    print(f"   ✓ Portfolio Summary:")
    print(f"     - Cash Balance: ${summary['cash_balance']}")
    print(f"     - Total Equity: ${summary['total_equity']}")
    print(f"     - Total P&L: ${summary['total_pnl']} ({summary['total_pnl_percent']:.2f}%)")
    print(f"     - Positions: {summary['positions_count']}")
    
    for pos in summary['positions']:
        print(f"\n     Position: {pos['ticker']}")
        print(f"       - Quantity: {pos['quantity']}")
        print(f"       - Avg Entry: ${pos['avg_entry_price']}")
        print(f"       - Market Value: ${pos['market_value']}")
        print(f"       - Unrealized P&L: ${pos['unrealized_pnl']}")
    
    # Step 5: Update prices and check P&L
    print("\n5. Simulating price changes...")
    new_prices = {
        "AAPL": Decimal("180.00"),  # Up $4.50
        "MSFT": Decimal("325.00"),  # Down $5.00
    }
    engine.update_positions_prices(user_id, new_prices)
    
    summary = engine.get_portfolio_summary(user_id)
    print(f"   ✓ Updated Portfolio:")
    print(f"     - Total Equity: ${summary['total_equity']}")
    print(f"     - Total P&L: ${summary['total_pnl']} ({summary['total_pnl_percent']:.2f}%)")
    
    # Step 6: Execute sell trade
    print("\n6. Executing SELL trade (AAPL x 5 @ $180.00)...")
    trade3 = await engine.execute_trade(
        user_id=user_id,
        ticker="AAPL",
        side="sell",
        quantity=Decimal("5"),
        market_price=Decimal("180.00"),
        rationale={"test": "Taking partial profits"}
    )
    print(f"   ✓ Trade executed: {trade3.trade_id}")
    print(f"     - Status: {trade3.status.value}")
    print(f"     - Fill Price: ${trade3.price}")
    
    # Final portfolio check
    print("\n7. Final portfolio summary...")
    summary = engine.get_portfolio_summary(user_id)
    print(f"   ✓ Final Portfolio:")
    print(f"     - Cash Balance: ${summary['cash_balance']}")
    print(f"     - Total Equity: ${summary['total_equity']}")
    print(f"     - Total P&L: ${summary['total_pnl']} ({summary['total_pnl_percent']:.2f}%)")
    print(f"     - Positions: {summary['positions_count']}")
    
    print("\n" + "="*60)
    print("PRACTICE TRADING TEST COMPLETE ✓")
    print("="*60)
    
    db.close()
    return True


async def test_alpaca_adapter():
    """Test the Alpaca paper trading adapter."""
    print("\n" + "="*60)
    print("TESTING ALPACA PAPER TRADING ADAPTER")
    print("="*60)
    
    adapter = AdapterFactory.get_adapter("paper")
    
    print(f"\n1. Adapter type: {type(adapter).__name__}")
    print(f"   Configured: {adapter.configured}")
    
    if adapter.configured:
        print("\n2. Testing account state retrieval...")
        account = await adapter.get_account_state()
        
        if "error" not in account and account.get("status") != "mock":
            print(f"   ✓ Account connected!")
            print(f"     - Account ID: {account.get('id')}")
            print(f"     - Status: {account.get('status')}")
            print(f"     - Equity: ${account.get('equity')}")
            print(f"     - Buying Power: ${account.get('buying_power')}")
        else:
            print(f"   ⚠ Could not connect to Alpaca")
            if account.get("status") == "mock":
                print(f"     Reason: Credentials not configured properly")
            else:
                print(f"     Response: {account}")
        
        print("\n3. Testing order validation...")
        test_order = {
            "symbol": "AAPL",
            "side": "buy",
            "qty": 10,
            "type": "market",
            "time_in_force": "day"
        }
        ok, reason = adapter.validate_order(test_order)
        print(f"   {'✓' if ok else '✗'} Order validation: {reason}")
        
        print("\n4. Testing order submission (dry run)...")
        # Note: This would actually submit an order if connected
        # result = await adapter.submit_order(test_order)
        # print(f"   Result: {result}")
        print("   ℹ Skipping actual order submission (dry run mode)")
    else:
        print("\n   ⚠ Alpaca adapter not configured")
        print("   Set ALPACA_API_KEY and ALPACA_API_SECRET in backend/.env")
    
    print("\n" + "="*60)
    print("ALPACA ADAPTER TEST COMPLETE")
    print("="*60)
    
    return True


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("TradingBrowser Paper Trading Test Suite")
    print("="*60)
    print(f"\nTest started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Test practice engine
        await test_practice_trading()
        
        # Test Alpaca adapter
        await test_alpaca_adapter()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED SUCCESSFULLY ✓")
        print("="*60)
        print("\nYou can now start paper trading!")
        print("Run: python setup_paper_trading.py")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
