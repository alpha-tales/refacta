"""Claude Agent SDK integration using official query() function.

This module provides proper integration with the Claude Agent SDK including:
- Native SDK agent auto-selection via description matching (FREE)
- Automatic skill loading from agent frontmatter
- Live report tracking on every edit
- Session management for context preservation
- Cost tracking by message ID
- setting_sources for skills and CLAUDE.md loading
"""

from .client import (
    AgentClient,
    AgentDefinition,
    AgentResponse,
    CostTracker,
    SessionManager,
    build_agents_for_sdk,
    load_agent_definition,
    load_all_agents,
    parse_agent_frontmatter,
    run_agent,
    run_agent_sync,
)

from .report_tracker import (
    EditEntry,
    ReportTracker,
    get_tracker,
    reset_tracker,
)

__all__ = [
    # Client
    "AgentClient",
    "AgentDefinition",
    "AgentResponse",
    "CostTracker",
    "SessionManager",
    # Agent loading
    "build_agents_for_sdk",
    "load_agent_definition",
    "load_all_agents",
    "parse_agent_frontmatter",
    # Convenience functions
    "run_agent",
    "run_agent_sync",
    # Report tracking
    "EditEntry",
    "ReportTracker",
    "get_tracker",
    "reset_tracker",
]
