"""Logging configuration for the refactor agent.

Provides structured logging with console and file output, optimized for
token efficiency by keeping log messages concise.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

# Remove default handler
logger.remove()

# Global logger instance
_logger_configured = False


def setup_logging(
    log_dir: Optional[Path] = None,
    level: str = "INFO",
    *,
    console: bool = True,
    file: bool = True,
) -> None:
    """Configure logging for the application.

    Args:
        log_dir: Directory for log files (default: ./logs)
        level: Minimum log level
        console: Enable console output
        file: Enable file output
    """
    global _logger_configured

    if _logger_configured:
        return

    # Console handler with colors
    if console:
        logger.add(
            sys.stderr,
            format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
            level=level,
            colorize=True,
        )

    # File handler
    if file:
        log_dir = log_dir or Path("./logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"refactor_{datetime.now():%Y%m%d}.log"
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=level,
            rotation="10 MB",
            retention="7 days",
            compression="zip",
        )

    _logger_configured = True


def get_logger(name: str = "refactor_agent"):
    """Get a logger instance.

    Args:
        name: Logger name (typically module name)

    Returns:
        Logger instance
    """
    return logger.bind(name=name)
