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
from pathlib import Path

from dotenv import load_dotenv

# Add src to path for development imports
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

# Load environment variables from .env file if it exists
ENV_PATH = SCRIPT_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

from refactor_agent.cli import main

if __name__ == "__main__":
    main()
