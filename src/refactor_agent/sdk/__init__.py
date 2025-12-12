"""Claude Agent SDK integration using official query() function.

This module provides proper integration with the Claude Agent SDK including:
- Session management for context preservation
- Cost tracking by message ID
- setting_sources for skills and CLAUDE.md loading
"""

from .client import (
    AgentClient,
    AgentResponse,
    CostTracker,
    SessionManager,
    run_agent,
    run_agent_sync,
)

__all__ = [
    "AgentClient",
    "AgentResponse",
    "CostTracker",
    "SessionManager",
    "run_agent",
    "run_agent_sync",
]
