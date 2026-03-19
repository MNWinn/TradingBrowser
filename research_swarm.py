#!/usr/bin/env python3
"""
Research Swarm - Standalone Entry Point

This script allows running the research swarm directly:
    cd /home/mnwinnwork/.openclaw/workspace/TradingBrowser
    python3 -m research_swarm

Or:
    python3 research_swarm.py
"""

import sys
import os

# Add paths for imports
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if os.path.join(project_root, 'backend') not in sys.path:
    sys.path.insert(0, os.path.join(project_root, 'backend'))

# Import and run the research swarm
from backend.app.services.research_swarm import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
