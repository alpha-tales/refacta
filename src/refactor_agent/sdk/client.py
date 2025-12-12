"""Claude Agent SDK client using official query() function.

This module provides proper integration with the Claude Agent SDK,
including session management, setting sources, and cost tracking.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, List, Optional

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ToolUseBlock

from ..console.diff_viewer import EditOperation


@dataclass
class AgentResponse:
    """Response from an agent execution."""

    content: str
    agent_name: str
    success: bool
    error: Optional[str] = None
    tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    session_id: Optional[str] = None
    edits: List[EditOperation] = field(default_factory=list)


@dataclass
class SessionManager:
    """Manages session IDs for context preservation across agent calls."""

    _sessions: dict[str, str] = field(default_factory=dict)
    _main_session: Optional[str] = None

    def set_main_session(self, session_id: str) -> None:
        """Set the main pipeline session ID."""
        self._main_session = session_id

    def get_main_session(self) -> Optional[str]:
        """Get the main pipeline session ID."""
        return self._main_session

    def set_agent_session(self, agent_name: str, session_id: str) -> None:
        """Store session ID for a specific agent."""
        self._sessions[agent_name] = session_id

    def get_agent_session(self, agent_name: str) -> Optional[str]:
        """Get stored session ID for an agent."""
        return self._sessions.get(agent_name)

    def clear(self) -> None:
        """Clear all sessions."""
        self._sessions.clear()
        self._main_session = None


@dataclass
class CostTracker:
    """Tracks token usage and costs across agent calls."""

    _processed_message_ids: set[str] = field(default_factory=set)
    _total_input_tokens: int = 0
    _total_output_tokens: int = 0
    _total_cost_usd: float = 0.0

    def process_message(self, message: Any) -> Optional[dict]:
        """Process a message for cost tracking (deduplicates by message ID).

        Returns usage dict if this is a new message, None if already processed.
        """
        # Only process assistant messages with usage
        if not hasattr(message, 'type') or message.type != 'assistant':
            return None

        if not hasattr(message, 'usage') or not message.usage:
            return None

        # Get message ID for deduplication
        message_id = getattr(message, 'id', None)
        if not message_id:
            return None

        # Skip if already processed (same ID = same usage)
        if message_id in self._processed_message_ids:
            return None

        self._processed_message_ids.add(message_id)

        # Extract usage
        usage = message.usage
        input_tokens = getattr(usage, 'input_tokens', 0) or usage.get('input_tokens', 0) if isinstance(usage, dict) else 0
        output_tokens = getattr(usage, 'output_tokens', 0) or usage.get('output_tokens', 0) if isinstance(usage, dict) else 0

        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens

        return {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'message_id': message_id,
        }

    def add_from_result(self, result_message: Any) -> None:
        """Add cumulative usage from a result message."""
        if hasattr(result_message, 'total_cost_usd'):
            self._total_cost_usd = result_message.total_cost_usd
        elif hasattr(result_message, 'usage') and hasattr(result_message.usage, 'total_cost_usd'):
            self._total_cost_usd = result_message.usage.total_cost_usd

    @property
    def total_tokens(self) -> int:
        return self._total_input_tokens + self._total_output_tokens

    @property
    def total_input_tokens(self) -> int:
        return self._total_input_tokens

    @property
    def total_output_tokens(self) -> int:
        return self._total_output_tokens

    @property
    def total_cost_usd(self) -> float:
        return self._total_cost_usd

    def reset(self) -> None:
        """Reset all tracking."""
        self._processed_message_ids.clear()
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost_usd = 0.0


@dataclass
class AgentClient:
    """Client for running Claude agents using official SDK with best practices.

    Features:
    - Uses official query() function from claude_agent_sdk
    - Configures setting_sources to load skills and CLAUDE.md
    - Session management for context preservation across pipeline stages
    - Proper cost tracking by message ID (no double counting)
    - Limited to 3 max_turns to reduce API costs (each turn = 1 API call)
    """

    project_path: Path
    model: str = "claude-haiku-4-5-20251001"
    max_turns: int = 3  # Default: 3 turns for simple edits
    max_turns_full: int = 10  # Full mode: 10 turns for comprehensive refactoring
    _session_manager: SessionManager = field(default_factory=SessionManager)
    _cost_tracker: CostTracker = field(default_factory=CostTracker)
    _on_message: Optional[Callable[[Any], None]] = None

    def __post_init__(self) -> None:
        """Validate environment."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.project_path = Path(self.project_path).resolve()

    def set_message_callback(self, callback: Callable[[Any], None]) -> None:
        """Set callback for real-time message handling."""
        self._on_message = callback

    def _get_allowed_tools(self, agent_name: str, minimal: bool = False) -> list[str]:
        """Get allowed tools based on agent type.

        TOKEN COST INFO:
        - Each tool adds ~500-1000 tokens to the request
        - 6 tools = ~3,000-6,000 tokens just for tool definitions
        - Use minimal=True for simple tasks to reduce costs

        Args:
            agent_name: Name of the agent
            minimal: If True, return only essential tools (Read + Edit)
                    This can reduce input tokens by ~3,000-5,000
        """
        if minimal:
            # MINIMAL MODE: Only Read + Edit = ~1,000 tokens for tool definitions
            # Use this for simple file editing tasks
            return ["Read", "Edit"]

        # FULL MODE: All tools the agent might need
        # ~3,000-6,000 tokens for tool definitions
        tool_mapping = {
            "project-scanner": ["Read", "Glob", "Grep", "Write"],
            "rules-interpreter": ["Read", "Write"],
            "python-refactorer": ["Read", "Edit", "Write", "Glob", "Grep", "Bash"],
            "nextjs-refactorer": ["Read", "Edit", "Write", "Glob", "Grep"],
            "compliance-checker": ["Read", "Glob", "Grep", "Write"],
            "build-runner": ["Bash", "Read"],
            "summary-reporter": ["Read", "Write"],
        }
        return tool_mapping.get(agent_name, ["Read", "Glob", "Grep"])

    def _load_agent_prompt(self, agent_name: str) -> Optional[str]:
        """Load agent definition from .claude/agents/<agent_name>.md file."""
        agent_file = self.project_path / ".claude" / "agents" / f"{agent_name}.md"
        if agent_file.exists():
            return agent_file.read_text(encoding="utf-8")
        return None

    def _build_options(
        self,
        agent_name: str,
        resume_session: Optional[str] = None,
        use_full_preset: bool = False,
        minimal_tools: bool = False,
    ) -> ClaudeAgentOptions:
        """Build SDK options - PROPERLY uses agent .md files and skills.

        MODES:
        1. use_full_preset=True: Full agent structure with skills (~20k tokens)
           - Loads .claude/agents/<agent_name>.md
           - Loads .claude/skills/* via setting_sources
           - Uses claude_code preset + agent prompt

        2. use_full_preset=False, minimal_tools=False: Agent prompt only (~2-5k tokens)
           - Loads .claude/agents/<agent_name>.md as system prompt
           - No skills, no claude_code preset

        3. minimal_tools=True: Cheap mode (~1-2k tokens)
           - Minimal prompt with Read+Edit only
           - For simple quick edits

        Args:
            agent_name: Name of the agent (matches .claude/agents/<name>.md)
            resume_session: Session ID to resume
            use_full_preset: If True, use full agent + skills + claude_code preset
            minimal_tools: If True, use minimal prompt (overrides agent .md)
        """
        allowed_tools = self._get_allowed_tools(agent_name, minimal=minimal_tools)

        # Use higher max_turns for full mode (comprehensive refactoring needs more iterations)
        turns = self.max_turns_full if use_full_preset else self.max_turns

        options_dict = {
            "model": self.model,
            "max_turns": turns,
            "cwd": str(self.project_path),
            "allowed_tools": allowed_tools,
        }

        if use_full_preset:
            # FULL AGENT MODE: Load agent .md + skills + claude_code preset
            # This is the PROPER way to use AlphaTales agents
            # Uses max_turns_full (10) to allow comprehensive file refactoring
            options_dict["setting_sources"] = ["project"]  # Loads skills and CLAUDE.md
            options_dict["allowed_tools"].append("Skill")

            # Load agent definition and append to claude_code preset
            agent_prompt = self._load_agent_prompt(agent_name)
            append_text = agent_prompt if agent_prompt else f"You are the {agent_name} agent."
            append_text += f"\n\nWorking directory: {self.project_path}"

            options_dict["system_prompt"] = {
                "type": "preset",
                "preset": "claude_code",
                "append": append_text,
            }

        elif not minimal_tools:
            # AGENT PROMPT MODE: Load agent .md but no skills/preset (cheaper)
            agent_prompt = self._load_agent_prompt(agent_name)
            if agent_prompt:
                options_dict["system_prompt"] = agent_prompt + f"\n\nWorking directory: {self.project_path}"
            else:
                options_dict["system_prompt"] = self._build_minimal_system_prompt(agent_name, allowed_tools)

        else:
            # MINIMAL MODE: Quick cheap edits
            options_dict["system_prompt"] = self._build_minimal_system_prompt(agent_name, allowed_tools)

        # Session management for context preservation
        if resume_session:
            options_dict["resume"] = resume_session

        return ClaudeAgentOptions(**options_dict)

    def _build_minimal_system_prompt(self, agent_name: str, tools: list[str]) -> str:
        """Build a minimal system prompt based on enabled tools.

        This replaces the ~20,000 token claude_code preset with ~100-200 tokens.
        Only describes tools that are actually enabled.
        """
        # Minimal but actionable prompt - tells agent to USE tools, not describe
        tool_descriptions = {
            "Read": "Read file contents",
            "Edit": "Edit files (old_string→new_string)",
            "Write": "Create new files",
            "Glob": "Find files by pattern",
            "Grep": "Search file contents",
            "Bash": "Run shell commands",
        }

        tool_list = ", ".join(f"{t}" for t in tools if t in tool_descriptions)
        return f"""You are {agent_name}. Working dir: {self.project_path}
Tools: {tool_list}

IMPORTANT: Always USE tools to complete tasks. Do not just describe what you would do.
1. Use Read tool to read the file first
2. Use Edit tool to make changes (provide exact old_string and new_string)
3. Confirm what you changed

Be direct and concise. Execute actions, don't just plan them."""

    async def run_agent(
        self,
        agent_name: str,
        prompt: str,
        *,
        stream: bool = False,
        resume_session: bool = True,
        use_full_preset: bool = False,
        minimal_tools: bool = True,  # DEFAULT: Use minimal tools to save tokens
    ) -> AgentResponse:
        """Run an agent with the given prompt using official SDK.

        Args:
            agent_name: Name of the agent (matches .claude/agents/<name>.md)
            prompt: The task prompt for the agent
            stream: Whether to stream the response (for real-time feedback)
            resume_session: Whether to resume from previous session (context sharing)
            use_full_preset: If True, use full claude_code preset (~20k tokens)
                            If False, use minimal prompt (~500 tokens) - DEFAULT
            minimal_tools: If True (DEFAULT), use only Read+Edit tools (~1k tokens)
                          If False, use all tools for agent (~3-6k tokens)

        TOKEN COST ESTIMATES:
        - Minimal (default): ~1,500-2,500 input tokens
        - Full preset + all tools: ~23,000-26,000 input tokens

        Returns:
            AgentResponse with the agent's output
        """
        try:
            # Get session ID if resuming
            session_id = None
            if resume_session:
                session_id = self._session_manager.get_agent_session(agent_name)

            options = self._build_options(
                agent_name, session_id, use_full_preset, minimal_tools
            )

            content_parts = []
            response_session_id = None
            input_tokens = 0
            output_tokens = 0
            cost_usd = 0.0
            got_result = False
            edits: List[EditOperation] = []

            # Use async iteration with official query() function
            # NOTE: SDK messages are different classes, not dicts with 'type' field
            try:
                async for message in query(prompt=prompt, options=options):
                    msg_class = type(message).__name__

                    # Handle message callback for real-time feedback
                    if self._on_message:
                        self._on_message(message)

                    # Capture session ID from SystemMessage init
                    if msg_class == 'SystemMessage':
                        if hasattr(message, 'subtype') and message.subtype == 'init':
                            # Session ID is in ResultMessage, not SystemMessage
                            pass

                    # Capture Edit tool calls using proper SDK types (isinstance checks)
                    if isinstance(message, AssistantMessage):
                        if hasattr(message, 'content'):
                            for block in message.content:
                                # Capture text content
                                if hasattr(block, 'text'):
                                    content_parts.append(block.text)

                                # Capture Edit tool calls using ToolUseBlock
                                if isinstance(block, ToolUseBlock):
                                    if block.name == 'Edit':
                                        tool_input = block.input
                                        if isinstance(tool_input, dict):
                                            file_path = tool_input.get('file_path', '')
                                            # Avoid duplicates
                                            if file_path and not any(e.file_path == file_path for e in edits):
                                                edit_op = EditOperation(
                                                    file_path=file_path,
                                                    old_string=tool_input.get('old_string', ''),
                                                    new_string=tool_input.get('new_string', ''),
                                                )
                                                edits.append(edit_op)

                    # Handle ResultMessage
                    if msg_class == 'ResultMessage':
                        got_result = True
                        # Get session ID from result
                        if hasattr(message, 'session_id'):
                            response_session_id = message.session_id
                        # Get cost
                        if hasattr(message, 'total_cost_usd'):
                            cost_usd = message.total_cost_usd
                        # Get usage
                        if hasattr(message, 'usage') and message.usage:
                            usage = message.usage
                            input_tokens = usage.get('input_tokens', 0)
                            output_tokens = usage.get('output_tokens', 0)

            except Exception as query_error:
                # SDK may throw error at end - check if we got results
                if not got_result and not content_parts:
                    raise query_error
                # Otherwise ignore - we got the response before the error

            # Store session for future resumption
            if response_session_id:
                self._session_manager.set_agent_session(agent_name, response_session_id)

            content = "\n".join(content_parts) if content_parts else ""
            tokens_used = input_tokens + output_tokens

            return AgentResponse(
                content=content,
                agent_name=agent_name,
                success=True,
                tokens_used=tokens_used,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                session_id=response_session_id,
                edits=edits,
            )

        except Exception as e:
            return AgentResponse(
                content="",
                agent_name=agent_name,
                success=False,
                error=str(e),
            )

    async def run_agent_with_live_updates(
        self,
        agent_name: str,
        prompt: str,
        on_edit: Callable[[EditOperation], None],
        on_text: Optional[Callable[[str], None]] = None,
        *,
        resume_session: bool = True,
        use_full_preset: bool = False,
        minimal_tools: bool = False,  # DEFAULT: Use agent .md prompts
    ) -> AgentResponse:
        """Run an agent with LIVE callbacks - shows text and diffs as they happen.

        This provides true streaming experience:
        - Text chunks appear as they're generated
        - Edit diffs appear immediately when Edit tool is called
        - Order is preserved: first text, then edit, then more text, etc.

        Uses proper agent structure from .claude/agents/<agent_name>.md

        Args:
            agent_name: Name of the agent (loads .claude/agents/<name>.md)
            prompt: The task prompt
            on_edit: Callback called immediately when an Edit tool is used
            on_text: Callback called for each text chunk (streaming response)
            resume_session: Whether to resume from previous session
            use_full_preset: If True, use full agent + skills + claude_code preset
            minimal_tools: If True, use minimal prompt (overrides agent .md)

        Returns:
            AgentResponse with final results
        """
        try:
            session_id = None
            if resume_session:
                session_id = self._session_manager.get_agent_session(agent_name)

            options = self._build_options(
                agent_name, session_id, use_full_preset=use_full_preset, minimal_tools=minimal_tools
            )

            content_parts = []
            response_session_id = None
            input_tokens = 0
            output_tokens = 0
            cost_usd = 0.0
            got_result = False
            edits: List[EditOperation] = []
            shown_files = set()  # Track which files we've shown diffs for
            streamed_text_ids = set()  # Track streamed text blocks to avoid duplicates

            try:
                async for message in query(prompt=prompt, options=options):
                    msg_class = type(message).__name__

                    # Handle AssistantMessage - contains both text and tool calls
                    if isinstance(message, AssistantMessage):
                        if hasattr(message, 'content'):
                            for block in message.content:
                                # Stream text content LIVE
                                if hasattr(block, 'text'):
                                    text = block.text
                                    # Get block ID to avoid duplicates
                                    block_id = id(block)
                                    if block_id not in streamed_text_ids:
                                        streamed_text_ids.add(block_id)
                                        content_parts.append(text)
                                        # LIVE TEXT CALLBACK
                                        if on_text and text.strip():
                                            on_text(text)

                                # Capture Edit tool calls and notify immediately
                                if isinstance(block, ToolUseBlock):
                                    if block.name == 'Edit':
                                        tool_input = block.input
                                        if isinstance(tool_input, dict):
                                            file_path = tool_input.get('file_path', '')
                                            # Only show each file once
                                            if file_path and file_path not in shown_files:
                                                shown_files.add(file_path)
                                                edit_op = EditOperation(
                                                    file_path=file_path,
                                                    old_string=tool_input.get('old_string', ''),
                                                    new_string=tool_input.get('new_string', ''),
                                                )
                                                edits.append(edit_op)
                                                # LIVE EDIT CALLBACK - show diff immediately!
                                                on_edit(edit_op)

                    # Handle ResultMessage
                    if msg_class == 'ResultMessage':
                        got_result = True
                        if hasattr(message, 'session_id'):
                            response_session_id = message.session_id
                        if hasattr(message, 'total_cost_usd'):
                            cost_usd = message.total_cost_usd
                        if hasattr(message, 'usage') and message.usage:
                            usage = message.usage
                            input_tokens = usage.get('input_tokens', 0)
                            output_tokens = usage.get('output_tokens', 0)

            except Exception as query_error:
                if not got_result and not content_parts:
                    raise query_error

            if response_session_id:
                self._session_manager.set_agent_session(agent_name, response_session_id)

            content = "\n".join(content_parts) if content_parts else ""
            tokens_used = input_tokens + output_tokens

            return AgentResponse(
                content=content,
                agent_name=agent_name,
                success=True,
                tokens_used=tokens_used,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                session_id=response_session_id,
                edits=edits,
            )

        except Exception as e:
            return AgentResponse(
                content="",
                agent_name=agent_name,
                success=False,
                error=str(e),
            )

    # Backwards compatibility alias
    async def run_agent_with_live_edits(
        self,
        agent_name: str,
        prompt: str,
        on_edit: Callable[[EditOperation], None],
        *,
        resume_session: bool = True,
        use_full_preset: bool = False,
        minimal_tools: bool = False,
    ) -> AgentResponse:
        """Backwards compatibility - use run_agent_with_live_updates instead."""
        return await self.run_agent_with_live_updates(
            agent_name, prompt, on_edit,
            on_text=None,
            resume_session=resume_session,
            use_full_preset=use_full_preset,
            minimal_tools=minimal_tools,
        )

    async def run_agent_streaming(
        self,
        agent_name: str,
        prompt: str,
        on_text: Callable[[str], None],
        *,
        resume_session: bool = True,
        minimal_tools: bool = True,  # DEFAULT: Use minimal tools to save tokens
    ) -> AgentResponse:
        """Run an agent with streaming text output.

        Args:
            agent_name: Name of the agent
            prompt: The task prompt
            on_text: Callback for each text chunk
            resume_session: Whether to resume from previous session
            minimal_tools: If True (DEFAULT), use only Read+Edit tools

        Returns:
            AgentResponse with final results
        """
        try:
            session_id = None
            if resume_session:
                session_id = self._session_manager.get_agent_session(agent_name)

            options = self._build_options(
                agent_name, session_id, use_full_preset=False, minimal_tools=minimal_tools
            )

            content_parts = []
            response_session_id = None
            input_tokens = 0
            output_tokens = 0

            async for message in query(prompt=prompt, options=options):
                # Capture session ID
                if hasattr(message, 'type') and message.type == 'system':
                    if hasattr(message, 'subtype') and message.subtype == 'init':
                        response_session_id = getattr(message, 'session_id', None)

                # Track costs
                usage_info = self._cost_tracker.process_message(message)
                if usage_info:
                    input_tokens += usage_info['input_tokens']
                    output_tokens += usage_info['output_tokens']

                # Stream text content
                if hasattr(message, 'type') and message.type == 'assistant':
                    if hasattr(message, 'message') and hasattr(message.message, 'content'):
                        for block in message.message.content:
                            if hasattr(block, 'text'):
                                on_text(block.text)
                                content_parts.append(block.text)

                # Handle result
                if hasattr(message, 'type') and message.type == 'result':
                    self._cost_tracker.add_from_result(message)
                    if hasattr(message, 'result'):
                        result_text = str(message.result)
                        on_text(result_text)
                        content_parts.append(result_text)

            if response_session_id:
                self._session_manager.set_agent_session(agent_name, response_session_id)

            return AgentResponse(
                content="\n".join(content_parts),
                agent_name=agent_name,
                success=True,
                tokens_used=input_tokens + output_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                session_id=response_session_id,
            )

        except Exception as e:
            return AgentResponse(
                content="",
                agent_name=agent_name,
                success=False,
                error=str(e),
            )

    def get_session_manager(self) -> SessionManager:
        """Get the session manager for manual session handling."""
        return self._session_manager

    def get_cost_tracker(self) -> CostTracker:
        """Get the cost tracker for usage reporting."""
        return self._cost_tracker

    def reset_sessions(self) -> None:
        """Clear all stored sessions."""
        self._session_manager.clear()

    def reset_cost_tracking(self) -> None:
        """Reset cost tracking."""
        self._cost_tracker.reset()


async def run_agent(
    agent_name: str,
    prompt: str,
    project_path: Path,
    *,
    model: str = "claude-haiku-4-5-20251001",
    stream: bool = False,
    minimal_tools: bool = True,
) -> AgentResponse:
    """Convenience function to run an agent.

    Args:
        agent_name: Name of the agent
        prompt: Task prompt
        project_path: Path to the project root
        model: Claude model to use
        stream: Whether to stream response
        minimal_tools: If True (DEFAULT), use only Read+Edit (~1k tokens)

    Returns:
        AgentResponse with results
    """
    client = AgentClient(project_path=project_path, model=model)
    return await client.run_agent(agent_name, prompt, stream=stream, minimal_tools=minimal_tools)


def run_agent_sync(
    agent_name: str,
    prompt: str,
    project_path: Path,
    *,
    model: str = "claude-haiku-4-5-20251001",
    stream: bool = False,
    minimal_tools: bool = True,
) -> AgentResponse:
    """Synchronous wrapper for run_agent.

    Args:
        agent_name: Name of the agent
        prompt: Task prompt
        project_path: Path to the project root
        model: Claude model to use
        stream: Whether to stream response
        minimal_tools: If True (DEFAULT), use only Read+Edit (~1k tokens)

    Returns:
        AgentResponse with results
    """
    return asyncio.run(
        run_agent(
            agent_name=agent_name,
            prompt=prompt,
            project_path=project_path,
            model=model,
            stream=stream,
            minimal_tools=minimal_tools,
        )
    )
