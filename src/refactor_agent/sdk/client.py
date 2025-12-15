"""Claude Agent SDK client using official query() function.

This module provides proper integration with the Claude Agent SDK,
including session management, setting sources, and cost tracking.

Features:
- Native SDK agent selection via description matching (FREE)
- Automatic skill loading from agent frontmatter
- Live report tracking on every edit
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ToolUseBlock

from ..models import EditOperation
from .report_tracker import ReportTracker, get_tracker


@dataclass
class AgentDefinition:
    """Parsed agent definition from .md file."""

    name: str
    description: str
    prompt: str
    tools: List[str]
    skills: List[str]
    model: str = "haiku"


def parse_agent_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from agent markdown file.

    Args:
        content: Full content of the .md file

    Returns:
        Tuple of (frontmatter_dict, body_content)
    """
    # Match YAML frontmatter between --- markers
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        return {}, content

    frontmatter_str = match.group(1)
    body = match.group(2)

    try:
        frontmatter = yaml.safe_load(frontmatter_str) or {}
    except yaml.YAMLError:
        frontmatter = {}

    return frontmatter, body


def load_agent_definition(agent_file: Path) -> Optional[AgentDefinition]:
    """Load and parse a single agent definition from .md file.

    Args:
        agent_file: Path to the agent .md file

    Returns:
        AgentDefinition or None if parsing fails
    """
    if not agent_file.exists():
        return None

    content = agent_file.read_text(encoding="utf-8")
    frontmatter, body = parse_agent_frontmatter(content)

    name = frontmatter.get("name", agent_file.stem)
    description = frontmatter.get("description", "")

    # Parse tools (comma-separated string or list)
    tools_raw = frontmatter.get("tools", "")
    if isinstance(tools_raw, str):
        tools = [t.strip() for t in tools_raw.split(",") if t.strip()]
    else:
        tools = list(tools_raw) if tools_raw else []

    # Parse skills (comma-separated string or list)
    skills_raw = frontmatter.get("skills", "")
    if isinstance(skills_raw, str):
        skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
    else:
        skills = list(skills_raw) if skills_raw else []

    model = frontmatter.get("model", "haiku")

    return AgentDefinition(
        name=name,
        description=description,
        prompt=body.strip(),
        tools=tools,
        skills=skills,
        model=model,
    )


def load_all_agents(project_path: Path) -> Dict[str, AgentDefinition]:
    """Load all agent definitions from .claude/agents/ directory.

    Args:
        project_path: Root project path

    Returns:
        Dict mapping agent name to AgentDefinition
    """
    agents_dir = project_path / ".claude" / "agents"
    agents = {}

    if not agents_dir.exists():
        return agents

    for agent_file in agents_dir.glob("*.md"):
        agent_def = load_agent_definition(agent_file)
        if agent_def:
            agents[agent_def.name] = agent_def

    return agents


def build_agents_for_sdk(agents: Dict[str, AgentDefinition]) -> Dict[str, dict]:
    """Convert AgentDefinitions to SDK-compatible agents dict.

    This is the format expected by the `agents` parameter in ClaudeAgentOptions.

    Args:
        agents: Dict of AgentDefinition objects

    Returns:
        Dict suitable for SDK's agents parameter
    """
    sdk_agents = {}

    for name, agent_def in agents.items():
        sdk_agents[name] = {
            "description": agent_def.description,
            "prompt": agent_def.prompt,
        }

        # Only include tools if specified (otherwise inherits all)
        if agent_def.tools:
            sdk_agents[name]["tools"] = agent_def.tools

        # Map model names to SDK format
        model_map = {
            "haiku": "haiku",
            "sonnet": "sonnet",
            "opus": "opus",
        }
        if agent_def.model in model_map:
            sdk_agents[name]["model"] = model_map[agent_def.model]

    return sdk_agents


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
    - Native SDK agent selection via description matching (FREE - no extra API call)
    - Automatic skill loading from agent frontmatter
    - Live report tracking on every edit
    - Session management for context preservation across pipeline stages
    - Proper cost tracking by message ID (no double counting)
    """

    project_path: Path
    refacta_path: Optional[Path] = None  # Path to refacta source (for agents/skills)
    model: str = "claude-sonnet-4-5-20250929"
    max_turns: int = 5  # Default: 5 turns for simple edits
    max_turns_full: int = 15  # Full mode: 15 turns for comprehensive refactoring
    max_turns_smart: int = 20  # Smart routing: 20 turns (need enough for Glob + multiple Read + Edit)
    _session_manager: SessionManager = field(default_factory=SessionManager)
    _cost_tracker: CostTracker = field(default_factory=CostTracker)
    _on_message: Optional[Callable[[Any], None]] = None
    _agents: Dict[str, AgentDefinition] = field(default_factory=dict)
    _report_tracker: Optional[ReportTracker] = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Validate environment and load agents."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.project_path = Path(self.project_path).resolve()

        # Set refacta_path - default to P:\Source\refacta for agents/skills
        if self.refacta_path is None:
            self.refacta_path = Path(r"P:\Source\refacta")
        else:
            self.refacta_path = Path(self.refacta_path).resolve()

        # Load agents from REFACTA source (not target project)
        self._agents = load_all_agents(self.refacta_path)

        # Initialize report tracker
        self._report_tracker = get_tracker(self.project_path)

    def get_available_agents(self) -> List[str]:
        """Get list of available agent names."""
        return list(self._agents.keys())

    def get_agent_info(self, agent_name: str) -> Optional[AgentDefinition]:
        """Get agent definition by name."""
        return self._agents.get(agent_name)

    def get_report_tracker(self) -> ReportTracker:
        """Get the report tracker instance."""
        if self._report_tracker is None:
            self._report_tracker = get_tracker(self.project_path)
        return self._report_tracker

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

    def _build_options_with_auto_selection(
        self,
        resume_session: Optional[str] = None,
    ) -> ClaudeAgentOptions:
        """Build SDK options with native agent auto-selection.

        The SDK automatically loads agents from .claude/agents/ when
        setting_sources: ["project"] is used. Claude then selects the best
        agent based on description matching. This is FREE - no extra API call!

        Args:
            resume_session: Session ID to resume

        Returns:
            ClaudeAgentOptions configured for auto-selection
        """
        options_dict = {
            "model": self.model,
            "max_turns": self.max_turns_full,
            "cwd": str(self.project_path),
            "setting_sources": ["project"],  # Loads agents, skills, and CLAUDE.md
        }

        # Session management
        if resume_session:
            options_dict["resume"] = resume_session

        return ClaudeAgentOptions(**options_dict)

    # =========================================================================
    # 2-STEP SMART ROUTING (Token Efficient)
    # Step 1: Send descriptions only (~400 tokens) → Claude picks agents
    # Step 2: Load selected agent + skills only (~2-3k tokens)
    # Total: ~3k tokens vs ~10k for loading all agents
    # =========================================================================

    def _build_routing_prompt(self) -> str:
        """Build a compact routing prompt with agent descriptions only.

        This is used for Step 1 of smart routing - just ~400 tokens.
        Returns a formatted list of agent names and descriptions.
        """
        descriptions = []
        for name, agent_def in self._agents.items():
            # Use only the description, not the full prompt
            desc = agent_def.description or f"Agent for {name} tasks"
            descriptions.append(f"- {name}: {desc}")

        return "\n".join(descriptions)

    async def _route_to_agents(self, user_prompt: str) -> List[str]:
        """Route user request to agent(s) using DESCRIPTION-BASED routing.

        Uses 1 API call (~500 tokens) to let Claude pick the best agent
        based on agent descriptions.

        Args:
            user_prompt: The user's request

        Returns:
            List of agent names to use (e.g., ["python-refactorer"])
        """
        agent_list = self._build_routing_prompt()

        routing_system_prompt = f"""You are an agent router. Select the best agent for this task.

Available agents:
{agent_list}

Return ONLY a JSON array with 1 agent name. Example: ["python-refactorer"]"""

        options = ClaudeAgentOptions(
            model="claude-sonnet-4-5-20250929",
            max_turns=1,
            cwd=str(self.project_path),
            system_prompt=routing_system_prompt,
        )

        result_text = ""
        try:
            async for message in query(prompt=user_prompt, options=options):
                if isinstance(message, AssistantMessage):
                    if hasattr(message, 'content'):
                        for block in message.content:
                            if hasattr(block, 'text'):
                                result_text += block.text
        except Exception:
            pass

        # Parse JSON response
        try:
            text = result_text.strip()
            if "[" in text:
                start = text.find("[")
                end = text.rfind("]") + 1
                text = text[start:end]
            agents = json.loads(text)
            if isinstance(agents, list):
                valid = [a for a in agents if a in self._agents]
                if valid:
                    return valid
        except:
            pass

        # Fallback to keyword matching
        user_lower = user_prompt.lower()
        if any(kw in user_lower for kw in [".py", "python", "backend"]):
            return ["python-refactorer"]
        if any(kw in user_lower for kw in [".tsx", ".jsx", "react", "frontend"]):
            return ["nextjs-refactorer"]
        return ["python-refactorer"]

    def _load_skill_content(self, skill_name: str) -> Optional[str]:
        """Load a skill file from .claude/skills/ directory.

        Args:
            skill_name: Name of the skill (without .md extension)

        Returns:
            Content of the skill file, or None if not found
        """
        # Load skills from REFACTA source (not target project)
        skill_file = self.refacta_path / ".claude" / "skills" / f"{skill_name}.md"
        if skill_file.exists():
            return skill_file.read_text(encoding="utf-8")
        return None

    def _load_skills_for_agents(self, agent_names: List[str]) -> Dict[str, str]:
        """Load unique skills needed by the selected agents.

        Deduplicates skills - if multiple agents need the same skill,
        it's loaded only once.

        Args:
            agent_names: List of selected agent names

        Returns:
            Dict mapping skill_name to skill_content
        """
        # Collect unique skill names from all selected agents
        unique_skills = set()
        for agent_name in agent_names:
            agent_def = self._agents.get(agent_name)
            if agent_def and agent_def.skills:
                unique_skills.update(agent_def.skills)

        # Load each unique skill once
        skills = {}
        for skill_name in unique_skills:
            content = self._load_skill_content(skill_name)
            if content:
                skills[skill_name] = content

        return skills

    def _build_system_prompt_with_skills(
        self,
        agent_name: str,
        skills: Dict[str, str],
        concise_mode: bool = True,
    ) -> str:
        """Build a complete system prompt with agent definition and skills.

        Args:
            agent_name: The agent to use
            skills: Dict of skill_name -> skill_content
            concise_mode: If True, add token-saving instructions

        Returns:
            Complete system prompt string
        """
        agent_def = self._agents.get(agent_name)
        if not agent_def:
            return f"You are {agent_name}. Working directory: {self.project_path}"

        # Start with agent prompt
        prompt_parts = [agent_def.prompt]

        # Add skills content (only first 500 chars per skill in concise mode)
        if skills:
            prompt_parts.append("\n\n# Skills and Guidelines\n")
            for skill_name, skill_content in skills.items():
                if concise_mode and len(skill_content) > 500:
                    # Truncate long skills to save tokens
                    skill_content = skill_content[:500] + "\n... (truncated for efficiency)"
                prompt_parts.append(f"\n## {skill_name}\n\n{skill_content}")

        # Add working directory
        prompt_parts.append(f"\n\nWorking directory: {self.project_path}")

        # Add token-saving instructions in concise mode
        if concise_mode:
            prompt_parts.append("""

# IMPORTANT: Token Efficiency Rules
- Complete the task in 1-2 turns maximum
- Make edits directly without explaining what you'll do
- Don't read files you don't need to edit
- Skip verbose explanations - just do the work
- If task is done, stop immediately""")

        return "\n".join(prompt_parts)

    async def run_with_smart_routing(
        self,
        prompt: str,
        on_edit: Optional[Callable[[EditOperation], None]] = None,
        on_text: Optional[Callable[[str], None]] = None,
        *,
        resume_session: bool = True,
        track_report: bool = True,
    ) -> AgentResponse:
        """Run with 2-step smart routing for token efficiency.

        Step 1: Route (~400 tokens) - Claude picks best agent(s) from descriptions
        Step 2: Execute (~2-3k tokens) - Run with selected agent + skills only

        Total: ~3k tokens vs ~10k for loading all agents (70% savings!)

        Args:
            prompt: User's request
            on_edit: Callback for each edit (for live UI updates)
            on_text: Callback for each text chunk (for streaming)
            resume_session: Whether to resume from previous session
            track_report: Whether to track edits in report file

        Returns:
            AgentResponse with results
        """
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0
        all_edits: List[EditOperation] = []

        try:
            # STEP 1: Route to agents (~400 tokens)
            selected_agents = await self._route_to_agents(prompt)

            if not selected_agents:
                return AgentResponse(
                    content="Could not determine appropriate agent for this task.",
                    agent_name="router",
                    success=False,
                    error="No agents selected",
                )

            # STEP 2: Skip skills loading - saves ~2k tokens per request!
            # Agent prompts are sufficient for most tasks
            skills = {}  # Empty - don't load skills to save tokens

            # Initialize response variables BEFORE the loop
            content_parts = []
            response_session_id = None

            # STEP 3: Execute with each selected agent sequentially
            for agent_name in selected_agents:
                agent_def = self._agents.get(agent_name)
                if not agent_def:
                    continue

                # Tools needed for refactoring
                # Read: to read file contents
                # Edit: to make changes
                # Glob: to find files in folders (needed for folder scope)
                allowed_tools = ["Read", "Edit", "Glob"]

                # Build system prompt with clear instructions
                system_prompt = f"""You are {agent_name}. Working dir: {self.project_path}

INSTRUCTIONS:
1. If given a FOLDER path (like @folder/subfolder), use Glob to find ALL files:
   - For Python: Glob pattern "folder/**/*.py"
   - For TypeScript/React: Glob pattern "folder/**/*.tsx" or "folder/**/*.ts"
2. Process EVERY file found - do NOT stop after one file!
3. For EACH file in the list:
   a. Read the file using Read tool
   b. Apply changes using Edit tool
4. Edit tool requires: file_path, old_string (exact text to replace), new_string (replacement text)

CRITICAL: You MUST edit ALL files, not just the first one. Keep going until every file is processed.
Do not stop early. Do not summarize. Complete ALL files."""

                # Build options - NO session resume for smart routing (saves 10k+ tokens!)
                # Each task starts fresh to minimize input tokens
                options_dict = {
                    "model": "claude-sonnet-4-5-20250929",  # Force Haiku for execution
                    "max_turns": self.max_turns_smart,  # 10 turns to complete task
                    "cwd": str(self.project_path),
                    "allowed_tools": allowed_tools,
                    "system_prompt": system_prompt,
                }
                # NOTE: Removed session resume - was causing 15k+ tokens per call!

                options = ClaudeAgentOptions(**options_dict)

                # Execute - per-iteration variables only
                input_tokens = 0
                output_tokens = 0
                cost_usd = 0.0
                got_result = False
                shown_files = set()
                streamed_text_ids = set()

                try:
                    async for message in query(prompt=prompt, options=options):
                        msg_class = type(message).__name__

                        # Handle AssistantMessage
                        if isinstance(message, AssistantMessage):
                            if hasattr(message, 'content'):
                                for block in message.content:
                                    # Stream text content LIVE
                                    if hasattr(block, 'text'):
                                        text = block.text
                                        block_id = id(block)
                                        if block_id not in streamed_text_ids:
                                            streamed_text_ids.add(block_id)
                                            content_parts.append(text)
                                            if on_text and text.strip():
                                                on_text(text)

                                    # Capture Edit tool calls
                                    if isinstance(block, ToolUseBlock):
                                        if block.name == 'Edit':
                                            tool_input = block.input
                                            if isinstance(tool_input, dict):
                                                file_path = tool_input.get('file_path', '')
                                                if file_path and file_path not in shown_files:
                                                    shown_files.add(file_path)
                                                    edit_op = EditOperation(
                                                        file_path=file_path,
                                                        old_string=tool_input.get('old_string', ''),
                                                        new_string=tool_input.get('new_string', ''),
                                                    )
                                                    all_edits.append(edit_op)

                                                    # Track in report
                                                    if track_report and self._report_tracker:
                                                        self._report_tracker.on_edit(
                                                            file_path=file_path,
                                                            old_string=edit_op.old_string,
                                                            new_string=edit_op.new_string,
                                                            agent_name=agent_name,
                                                            success=True,
                                                        )

                                                    # Live callback
                                                    if on_edit:
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

                # Store session for this agent
                if response_session_id:
                    self._session_manager.set_agent_session(agent_name, response_session_id)

                # Accumulate totals
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens
                total_cost += cost_usd

            # Return combined results
            tokens_used = total_input_tokens + total_output_tokens

            return AgentResponse(
                content="\n".join(content_parts) if content_parts else "",
                agent_name=", ".join(selected_agents),
                success=True,
                tokens_used=tokens_used,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                cost_usd=total_cost,
                session_id=response_session_id,
                edits=all_edits,
            )

        except Exception as e:
            return AgentResponse(
                content="",
                agent_name="smart-router",
                success=False,
                error=str(e),
            )

    # =========================================================================
    # END 2-STEP SMART ROUTING
    # =========================================================================

    async def run_with_auto_selection(
        self,
        prompt: str,
        on_edit: Optional[Callable[[EditOperation], None]] = None,
        on_text: Optional[Callable[[str], None]] = None,
        *,
        resume_session: bool = True,
        track_report: bool = True,
    ) -> AgentResponse:
        """Run with SDK native agent auto-selection.

        Claude automatically picks the best agent(s) based on the prompt
        and agent descriptions. This is FREE - no extra API call needed!

        Args:
            prompt: User's request
            on_edit: Callback for each edit (for live UI updates)
            on_text: Callback for each text chunk (for streaming)
            resume_session: Whether to resume from previous session
            track_report: Whether to track edits in report file

        Returns:
            AgentResponse with results
        """
        try:
            session_id = None
            if resume_session:
                session_id = self._session_manager.get_main_session()

            options = self._build_options_with_auto_selection(session_id)

            content_parts = []
            response_session_id = None
            input_tokens = 0
            output_tokens = 0
            cost_usd = 0.0
            got_result = False
            edits: List[EditOperation] = []
            shown_files = set()
            streamed_text_ids = set()
            current_agent = "auto"

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
                                    block_id = id(block)
                                    if block_id not in streamed_text_ids:
                                        streamed_text_ids.add(block_id)
                                        content_parts.append(text)
                                        if on_text and text.strip():
                                            on_text(text)

                                # Capture Edit tool calls
                                if isinstance(block, ToolUseBlock):
                                    if block.name == 'Edit':
                                        tool_input = block.input
                                        if isinstance(tool_input, dict):
                                            file_path = tool_input.get('file_path', '')
                                            if file_path and file_path not in shown_files:
                                                shown_files.add(file_path)
                                                edit_op = EditOperation(
                                                    file_path=file_path,
                                                    old_string=tool_input.get('old_string', ''),
                                                    new_string=tool_input.get('new_string', ''),
                                                )
                                                edits.append(edit_op)

                                                # Track in report
                                                if track_report and self._report_tracker:
                                                    self._report_tracker.on_edit(
                                                        file_path=file_path,
                                                        old_string=edit_op.old_string,
                                                        new_string=edit_op.new_string,
                                                        agent_name=current_agent,
                                                        success=True,
                                                    )

                                                # Live callback
                                                if on_edit:
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
                self._session_manager.set_main_session(response_session_id)

            content = "\n".join(content_parts) if content_parts else ""
            tokens_used = input_tokens + output_tokens

            return AgentResponse(
                content=content,
                agent_name=current_agent,
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
                agent_name="auto",
                success=False,
                error=str(e),
            )

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
    model: str = "claude-sonnet-4-5-20250929",
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
    model: str = "claude-sonnet-4-5-20250929",
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
