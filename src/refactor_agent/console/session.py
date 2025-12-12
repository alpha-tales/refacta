"""Interactive session handler for conversational refactoring.

Manages the conversation loop between the user and the AI agent.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from rich.console import Console

from .ui import ConsoleUI
from .menu import TargetScope, OperationType
from ..sdk.client import AgentClient
from ..utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


class RefactorSession:
    """Interactive refactoring session with natural language conversation.

    Uses Claude Agent SDK with session management for context preservation.
    """

    def __init__(
        self,
        project_path: Optional[Path] = None,
        model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        """Initialize the refactoring session.

        Args:
            project_path: Path to the project to refactor
            model: Claude model to use
        """
        self.project_path = Path(project_path or os.getcwd()).resolve()
        self.model = model
        self.console = Console()
        self.ui = ConsoleUI(project_path=self.project_path)
        self.client: Optional[AgentClient] = None
        self.conversation_history: list[dict] = []

    async def start(self) -> None:
        """Start the interactive session."""
        # Setup logging
        setup_logging(self.project_path / "logs", console=False)

        # Show welcome
        self.ui.show_banner()
        self.ui.show_welcome()
        self.ui.show_project_info()

        # Run setup flow
        if not await self.ui.run_setup_flow():
            self.ui.show_goodbye()
            return

        # Initialize AI client
        self.console.print()
        with self.ui.show_processing("Initializing AI agent..."):
            try:
                self.client = AgentClient(
                    project_path=self.project_path,
                    model=self.model,
                )
            except Exception as e:
                self.ui.show_error(f"Failed to initialize AI agent: {e}")
                self.ui.show_error("Please check your ANTHROPIC_API_KEY in .env file")
                return

        self.console.print("[green]AI agent ready![/green]")

        # Show initial prompt
        self._show_conversation_prompt()

        # Main conversation loop
        await self._conversation_loop()

        # Cleanup
        self.ui.show_goodbye()

    def _show_conversation_prompt(self) -> None:
        """Show the initial conversation prompt based on selections."""
        if self.ui.operation == OperationType.REFACTOR:
            scope_text = self._get_scope_text()
            self.console.print(f"\n[cyan]Ready to refactor {scope_text}.[/cyan]")
            self.console.print("[dim]Tell me what you'd like to improve...[/dim]\n")
        else:
            self.console.print(
                f"\n[magenta]Ready to migrate from {self.ui.source_lang} to {self.ui.target_lang}.[/magenta]"
            )
            self.console.print("[dim]Tell me which parts to migrate first...[/dim]\n")

    def _get_scope_text(self) -> str:
        """Get human-readable scope text."""
        if self.ui.scope == TargetScope.ALL_PROJECT:
            return "the entire project"
        elif self.ui.selected_paths:
            if len(self.ui.selected_paths) == 1:
                return f"'{self.ui.selected_paths[0]}'"
            else:
                return f"{len(self.ui.selected_paths)} selected targets"
        return "selected files"

    async def _conversation_loop(self) -> None:
        """Main conversation loop."""
        while True:
            try:
                # Get user input
                user_input = await self.ui.get_user_input()

                if user_input is None:
                    continue

                # Handle commands
                lower_input = user_input.lower().strip()

                if lower_input in ("exit", "quit"):
                    break

                if lower_input == "help":
                    self.ui.show_help()
                    continue

                if lower_input in ("clear", "cls"):
                    self.ui.clear_screen()
                    self.ui.show_banner()
                    continue

                if lower_input == "status":
                    self.ui.show_status()
                    continue

                if lower_input == "reset":
                    self.console.print("[yellow]Resetting session...[/yellow]")
                    self.conversation_history.clear()
                    if await self.ui.run_setup_flow():
                        self._show_conversation_prompt()
                    continue

                if not user_input.strip():
                    continue

                # Process with AI agent
                await self._process_message(user_input)

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]")
                continue

    async def _process_message(self, message: str) -> None:
        """Process a user message with the AI agent.

        Args:
            message: User's message
        """
        # Build context-aware prompt
        prompt = self._build_prompt(message)

        # Show processing indicator
        with self.ui.show_processing("Thinking..."):
            try:
                # Determine which agent to use based on operation
                if self.ui.operation == OperationType.MIGRATE:
                    agent_name = self._get_migration_agent()
                else:
                    agent_name = self._get_refactor_agent()

                # Call the agent
                response = await self.client.run_agent(
                    agent_name=agent_name,
                    prompt=prompt,
                    stream=False,
                )

                if response.success:
                    self.ui.show_response(response.content)
                    self.console.print(f"[dim]Tokens used: {response.tokens_used:,}[/dim]")

                    # Add to history
                    self.conversation_history.append({
                        "role": "user",
                        "content": message,
                    })
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": response.content,
                    })
                else:
                    self.ui.show_error(f"Agent error: {response.error}")

            except Exception as e:
                logger.exception("Error processing message")
                self.ui.show_error(str(e))

    def _build_prompt(self, user_message: str) -> str:
        """Build a context-aware prompt for the AI agent.

        Args:
            user_message: The user's message

        Returns:
            Complete prompt with context
        """
        parts = []

        # Add operation context
        if self.ui.operation == OperationType.REFACTOR:
            parts.append("You are helping refactor code to improve quality.")
        else:
            parts.append(
                f"You are helping migrate code from {self.ui.source_lang} to {self.ui.target_lang}."
            )

        # Add scope context
        if self.ui.scope == TargetScope.ALL_PROJECT:
            parts.append(f"Working on the entire project at: {self.project_path}")
        elif self.ui.selected_paths:
            parts.append(f"Working on specific targets: {', '.join(self.ui.selected_paths)}")

        # Add conversation history (last 4 exchanges for context)
        if self.conversation_history:
            parts.append("\nRecent conversation:")
            for msg in self.conversation_history[-8:]:
                role = "User" if msg["role"] == "user" else "Assistant"
                parts.append(f"{role}: {msg['content'][:200]}...")

        # Add current request
        parts.append(f"\nUser request: {user_message}")

        # Add instructions
        parts.append("""
Instructions:
1. Read the relevant files using the file paths mentioned
2. Analyze the code and understand the user's request
3. Make the requested changes using Edit tool
4. Explain what you changed and why
5. Be concise but thorough

IMPORTANT: Use @ paths in the user message as actual file paths relative to the project root.
""")

        return "\n".join(parts)

    def _get_refactor_agent(self) -> str:
        """Get the appropriate refactor agent based on file types."""
        # Check file extensions in selected paths or project
        if self.ui.selected_paths:
            paths = self.ui.selected_paths
        else:
            paths = [str(p) for p in self.project_path.rglob("*") if p.is_file()][:100]

        # Count by type
        py_count = sum(1 for p in paths if p.endswith(".py"))
        js_count = sum(1 for p in paths if any(p.endswith(e) for e in [".js", ".jsx", ".ts", ".tsx"]))

        if py_count > js_count:
            return "python-refactorer"
        elif js_count > 0:
            return "nextjs-refactorer"
        else:
            return "python-refactorer"  # Default

    def _get_migration_agent(self) -> str:
        """Get the migration agent (uses rules-interpreter for now)."""
        # For migration, we'll use rules-interpreter to create a migration plan
        return "rules-interpreter"


async def run_interactive_session(
    project_path: Optional[Path] = None,
    model: str = "claude-haiku-4-5-20251001",
) -> None:
    """Run an interactive refactoring session (Rich-based).

    Args:
        project_path: Path to the project
        model: Claude model to use
    """
    session = RefactorSession(
        project_path=project_path,
        model=model,
    )
    await session.start()


def run_textual_app(
    project_path: Optional[Path] = None,
    model: str = "claude-haiku-4-5-20251001",
) -> None:
    """Run the Textual-based TUI application.

    This provides a Claude Code-style interface with:
    - Split panel layout (chat + file tree + progress)
    - Visual diff viewer with red/green highlighting
    - Interactive menu-based operation selection
    - Real-time progress tracking

    Args:
        project_path: Path to the project
        model: Claude model to use
    """
    from .app import run_app

    run_app(
        project_path=Path(project_path) if project_path else None,
        model=model,
    )
