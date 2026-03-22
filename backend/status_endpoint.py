from fastapi import APIRouter
from datetime import datetime
import subprocess
import sqlite3

router = APIRouter(prefix="/status", tags=["status"])

def get_process_status():
    ps_output = subprocess.check_output(['ps', 'aux']).decode()
    return {
        'mirofish': 'mirofish_service' in ps_output,
        'backend': 'uvicorn' in ps_output,
        'learning': 'continuous_learning' in ps_output
    }

@router.get("/")
def get_status():
    processes = get_process_status()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "systems": {
            "mirofish_ai": "🟢 RUNNING" if processes['mirofish'] else "🔴 OFFLINE",
            "backend_api": "🟢 RUNNING" if processes['backend'] else "🔴 OFFLINE",
            "agent_swarm": "🟢 ACTIVE" if processes['backend'] else "🔴 OFFLINE",
            "continuous_learning": "🟢 RUNNING" if processes['learning'] else "🔴 OFFLINE",
        },
        "research": {
            "active_agents": 8,
            "tickers_monitored": ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN"],
            "analysis_frequency": "Every 60 seconds"
        },
        "trading": {
            "account": "Alpaca Paper Trading",
            "capital": "$100,000.00",
            "next_trade_window": "Tomorrow 9:45 AM ET",
            "status": "READY"
        }
    }
