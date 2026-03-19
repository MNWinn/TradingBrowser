# Paper Trading Setup Guide for TradingBrowser

This guide will help you set up and start paper trading with TradingBrowser.

## Overview

TradingBrowser supports two types of paper trading:

1. **Practice Trading Engine** - Virtual portfolio management with simulated trades (works immediately)
2. **Alpaca Paper Trading** - Real paper trading through Alpaca Markets API (requires API keys)

## Quick Start

### Option 1: Practice Trading (Immediate - No API Keys Needed)

The practice trading engine is already set up and working. You can start using it right away:

```bash
# Start the backend
cd backend
uvicorn app.main:app --reload

# Create a practice portfolio
curl -X POST http://localhost:8000/practice/portfolio/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer admin-dev-token" \
  -d '{"user_id": "my_trader", "initial_balance": 100000}'

# Execute a paper trade
curl -X POST http://localhost:8000/practice/trade/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer trader-dev-token" \
  -d '{
    "user_id": "my_trader",
    "ticker": "AAPL",
    "side": "buy",
    "quantity": 10,
    "market_price": 175.50
  }'

# Check your portfolio
curl http://localhost:8000/practice/portfolio/my_trader \
  -H "Authorization: Bearer analyst-dev-token"
```

### Option 2: Alpaca Paper Trading (Requires API Keys)

#### Step 1: Get Alpaca API Keys

1. Go to https://alpaca.markets/
2. Sign up for a free account (choose "Paper Trading" account type)
3. Log in to your dashboard
4. Go to "Your API Keys" section
5. Generate new paper trading keys
6. Copy your API Key ID and Secret Key

#### Step 2: Configure TradingBrowser

Edit `backend/.env` and add your credentials:

```bash
# Alpaca API Settings
ALPACA_API_KEY=your_api_key_here
ALPACA_API_SECRET=your_secret_key_here
```

#### Step 3: Set Execution Mode to Paper

Edit `backend/.env`:

```bash
MODE=paper
```

#### Step 4: Restart and Test

```bash
# Restart the backend
cd backend
uvicorn app.main:app --reload

# Check execution mode
curl http://localhost:8000/execution/mode \
  -H "Authorization: Bearer analyst-dev-token"

# Submit a paper order through Alpaca
curl -X POST http://localhost:8000/execution/order \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer trader-dev-token" \
  -d '{
    "symbol": "AAPL",
    "side": "buy",
    "qty": 10,
    "type": "market",
    "time_in_force": "day"
  }'
```

## Available API Endpoints

### Practice Trading Endpoints

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/practice/portfolio/create` | POST | Create a new practice portfolio | admin |
| `/practice/portfolio/{user_id}` | GET | Get portfolio summary | analyst |
| `/practice/portfolio/{user_id}/reset` | POST | Reset portfolio | admin |
| `/practice/trade/execute` | POST | Execute a paper trade | trader |
| `/practice/trade/close-all/{user_id}` | POST | Close all positions | trader |
| `/practice/strategies` | GET | List available strategies | analyst |
| `/practice/strategy/{type}/analyze` | POST | Analyze ticker with strategy | analyst |
| `/practice/evaluation/{user_id}/summary` | GET | Get performance summary | analyst |
| `/practice/leaderboard` | GET | View leaderboard | analyst |

### Execution Endpoints

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/execution/mode` | GET | Get current execution mode | analyst |
| `/execution/mode` | PUT | Update execution mode | admin |
| `/execution/validate` | POST | Validate an order | analyst |
| `/execution/order` | POST | Submit an order | trader |
| `/execution/order/fill` | POST | Handle order fill | trader |
| `/execution/live-readiness` | GET | Check live trading readiness | analyst |
| `/execution/analytics` | GET | Get execution analytics | analyst |

## Execution Modes

- **research** - No order execution (analysis only)
- **paper** - Paper trading via Alpaca paper API
- **live** - Live trading via Alpaca live API (requires additional safeguards)

## Testing Your Setup

Run the setup verification script:

```bash
cd backend
python3 setup_paper_trading.py
```

Run the comprehensive test suite:

```bash
cd backend
python3 ../test_paper_trading.py
```

## Troubleshooting

### "unauthorized" Error from Alpaca

Your API credentials are invalid or expired. Generate new keys at https://alpaca.markets/

### "Mode is research" Error

Update `backend/.env` to set `MODE=paper` and restart the backend.

### Practice Trades Not Persisting

The practice engine uses in-memory storage by default. For persistent storage, ensure your database is properly configured in `backend/.env`.

## Next Steps

1. **Explore Strategies**: Try different trading strategies via `/practice/strategies`
2. **Track Performance**: Monitor your P&L with `/practice/evaluation/{user_id}/summary`
3. **Complete Challenges**: Earn points by completing trading challenges
4. **Go Live**: When ready, switch to live trading (requires thorough testing and compliance checks)

## Security Notes

- Never commit your `.env` file with real API keys
- Use paper trading extensively before considering live trading
- The live trading mode requires explicit enablement and compliance checks
- All trades are logged in the audit log for compliance review
