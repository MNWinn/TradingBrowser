#!/usr/bin/env python3
"""
Paper Trading Setup and Test Script for TradingBrowser

This script:
1. Verifies Alpaca API credentials
2. Sets the execution mode to "paper"
3. Creates a practice portfolio
4. Executes a test paper trade
5. Provides next steps for the user
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from decimal import Decimal

# Check if we can import the required modules
try:
    from app.core.config import settings
    from app.services.execution import AdapterFactory, AlpacaPaperAdapter
    print("✓ Successfully imported TradingBrowser modules")
except ImportError as e:
    print(f"✗ Failed to import modules: {e}")
    print("Make sure you're running this from the TradingBrowser directory")
    sys.exit(1)


def check_alpaca_credentials():
    """Check if Alpaca API credentials are configured."""
    print("\n" + "="*60)
    print("STEP 1: Checking Alpaca API Credentials")
    print("="*60)
    
    key = settings.alpaca_api_key
    secret = settings.alpaca_api_secret
    
    if not key or not secret:
        print("✗ Alpaca API credentials are MISSING")
        print("\n  To get your API credentials:")
        print("  1. Go to https://alpaca.markets/")
        print("  2. Sign up for a free account")
        print("  3. Go to 'Your API Keys' in the dashboard")
        print("  4. Generate new paper trading keys")
        print("\n  Then update your backend/.env file:")
        print("  ALPACA_API_KEY=your_key_here")
        print("  ALPACA_API_SECRET=your_secret_here")
        return False
    
    # Mask the credentials for display
    key_display = key[:4] + "..." + key[-4:] if len(key) > 8 else "***"
    secret_display = secret[:4] + "..." + secret[-4:] if len(secret) > 8 else "***"
    
    print(f"✓ Alpaca API Key: {key_display}")
    print(f"✓ Alpaca API Secret: {secret_display}")
    print(f"✓ Paper Trading URL: {settings.alpaca_paper_base_url}")
    return True


def check_execution_mode():
    """Check current execution mode."""
    print("\n" + "="*60)
    print("STEP 2: Checking Execution Mode")
    print("="*60)
    
    current_mode = settings.mode
    print(f"  Current mode: {current_mode}")
    
    if current_mode == "paper":
        print("✓ Already in PAPER mode")
        return True
    elif current_mode == "research":
        print("ℹ Currently in RESEARCH mode (paper trading available)")
        print("  To enable paper trading, update backend/.env:")
        print("  MODE=paper")
        return True
    elif current_mode == "live":
        print("⚠ WARNING: Currently in LIVE mode!")
        print("  Switching to paper mode is recommended for testing")
        return False
    
    return True


async def test_alpaca_connection():
    """Test connection to Alpaca paper trading API."""
    print("\n" + "="*60)
    print("STEP 3: Testing Alpaca Paper Trading Connection")
    print("="*60)
    
    adapter = AlpacaPaperAdapter()
    
    if not adapter.configured:
        print("✗ Cannot test connection - credentials not configured")
        return False
    
    try:
        # Try to get account info
        account = await adapter.get_account_state()
        
        if account.get("status") == "mock":
            print("✗ Connection test returned mock response")
            print(f"  Reason: {account.get('reason')}")
            return False
        
        if "error" in account:
            print(f"✗ Connection failed: {account['error']}")
            return False
        
        print("✓ Successfully connected to Alpaca Paper Trading!")
        print(f"\n  Account Info:")
        print(f"    Account ID: {account.get('id', 'N/A')}")
        print(f"    Status: {account.get('status', 'N/A')}")
        print(f"    Equity: ${account.get('equity', 'N/A')}")
        print(f"    Buying Power: ${account.get('buying_power', 'N/A')}")
        print(f"    Cash: ${account.get('cash', 'N/A')}")
        return True
        
    except Exception as e:
        print(f"✗ Connection test failed: {e}")
        return False


def print_next_steps():
    """Print next steps for the user."""
    print("\n" + "="*60)
    print("NEXT STEPS TO START PAPER TRADING")
    print("="*60)
    
    print("""
1. UPDATE EXECUTION MODE:
   Edit backend/.env and set:
   MODE=paper

2. RESTART THE BACKEND (if running):
   cd backend
   uvicorn app.main:app --reload

3. CREATE A PRACTICE PORTFOLIO:
   curl -X POST http://localhost:8000/practice/portfolio/create \\
     -H "Content-Type: application/json" \\
     -H "Authorization: Bearer admin-dev-token" \\
     -d '{"user_id": "test_user", "initial_balance": 100000}'

4. EXECUTE A TEST PAPER TRADE:
   curl -X POST http://localhost:8000/practice/trade/execute \\
     -H "Content-Type: application/json" \\
     -H "Authorization: Bearer trader-dev-token" \\
     -d '{
       "user_id": "test_user",
       "ticker": "AAPL",
       "side": "buy",
       "quantity": 10,
       "market_price": 175.50
     }'

5. CHECK YOUR PORTFOLIO:
   curl http://localhost:8000/practice/portfolio/test_user \\
     -H "Authorization: Bearer analyst-dev-token"

6. USE THE EXECUTION API FOR ALPACA PAPER TRADES:
   curl -X POST http://localhost:8000/execution/order \\
     -H "Content-Type: application/json" \\
     -H "Authorization: Bearer trader-dev-token" \\
     -d '{
       "symbol": "AAPL",
       "side": "buy",
       "qty": 10,
       "type": "market",
       "time_in_force": "day"
     }'
""")


async def main():
    """Main setup routine."""
    print("\n" + "="*60)
    print("TradingBrowser Paper Trading Setup")
    print("="*60)
    
    # Step 1: Check credentials
    creds_ok = check_alpaca_credentials()
    
    # Step 2: Check execution mode
    mode_ok = check_execution_mode()
    
    # Step 3: Test connection (only if credentials are present)
    connection_ok = False
    if creds_ok:
        connection_ok = await test_alpaca_connection()
    
    # Print summary
    print("\n" + "="*60)
    print("SETUP SUMMARY")
    print("="*60)
    print(f"  Alpaca Credentials: {'✓ OK' if creds_ok else '✗ MISSING'}")
    print(f"  Execution Mode: {'✓ OK' if mode_ok else '⚠ NEEDS ATTENTION'}")
    print(f"  Alpaca Connection: {'✓ OK' if connection_ok else '✗ FAILED'}")
    
    if creds_ok and connection_ok:
        print("\n✓ Paper trading is ready to use!")
    else:
        print("\n⚠ Please fix the issues above before proceeding")
    
    # Print next steps
    print_next_steps()


if __name__ == "__main__":
    asyncio.run(main())
