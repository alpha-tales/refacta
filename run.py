#!/usr/bin/env python3
"""AlphaTales Refactor Agent v2.0 - Entry Point.

Usage:
    python run.py                              # Start interactive console
    python run.py -p ./my-project              # Start with specific project
    python run.py run ./project ./rules.md    # Run automated pipeline
    python run.py scan ./project               # Scan project only
    python run.py --help                       # Show help
"""

import sys
import os

# Add src to path for development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Load environment variables
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from refactor_agent.cli import main

if __name__ == "__main__":
    main()
