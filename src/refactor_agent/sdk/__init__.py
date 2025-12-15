"""Claude Agent SDK integration using official query() function.

This module provides proper integration with the Claude Agent SDK including:
- 2-Step Smart Routing for token efficiency (70% savings!)
  - Step 1: Route (~400 tokens) - Claude picks agents from descriptions only
  - Step 2: Execute (~2-3k tokens) - Run with selected agent + skills only
- Automatic skill loading from agent frontmatter (deduplicated)
- Live report tracking on every edit (.refactor/reports/changes.md)
- Session management for context preservation
- Cost tracking by message ID
- Support for multiple agents and sequential execution
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
