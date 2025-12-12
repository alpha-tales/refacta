"""Main console UI for the AlphaTales Refactor Agent.

Provides an interactive, conversational interface with:
- Menu-based selection
- @ triggered file autocomplete
- Natural language conversation
- Rich terminal output
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, Callable

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from .autocomplete import FileCompleter
from .menu import MenuSelector, TargetScope, OperationType


# Custom prompt style
PROMPT_STYLE = Style.from_dict({
    "prompt": "#00d7ff bold",
    "path": "#808080",
})


class ConsoleUI:
    """Interactive console UI for the refactoring agent."""

    def __init__(
        self,
        project_path: Optional[Path] = None,
        on_message: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the console UI.

        Args:
            project_path: Project directory path
            on_message: Callback for handling user messages
        """
        self.project_path = Path(project_path or os.getcwd()).resolve()
        self.on_message = on_message
        self.console = Console()
        self.menu = MenuSelector(self.console)

        # Setup prompt session with history
        history_dir = Path.home() / ".alphatales"
        history_dir.mkdir(exist_ok=True)
        history_file = history_dir / "command_history"

        self.file_completer = FileCompleter(self.project_path)
        self.session: PromptSession = PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=self.file_completer,
            style=PROMPT_STYLE,
            multiline=False,
            complete_while_typing=False,
        )

        # State
        self.scope: Optional[TargetScope] = None
        self.operation: Optional[OperationType] = None
        self.selected_paths: list[str] = []
        self.source_lang: Optional[str] = None
        self.target_lang: Optional[str] = None

    def show_banner(self) -> None:
        """Display the welcome banner."""
        banner = """
 ╔═══════════════════════════════════════════════════════════════╗
 ║                                                               ║
 ║     █████╗ ██╗     ██████╗ ██╗  ██╗ █████╗ ████████╗ █████╗   ║
 ║    ██╔══██╗██║     ██╔══██╗██║  ██║██╔══██╗╚══██╔══╝██╔══██╗  ║
 ║    ███████║██║     ██████╔╝███████║███████║   ██║   ███████║  ║
 ║    ██╔══██║██║     ██╔═══╝ ██╔══██║██╔══██║   ██║   ██╔══██║  ║
 ║    ██║  ██║███████╗██║     ██║  ██║██║  ██║   ██║   ██║  ██║  ║
 ║    ╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝  ║
 ║                                                               ║
 ║              AI-Powered Code Refactoring Agent                ║
 ║                       Version 2.0                             ║
 ╚═══════════════════════════════════════════════════════════════╝
        """
        self.console.print(Panel(
            Text(banner, style="cyan"),
            border_style="cyan",
            padding=(0, 0),
        ))

    def show_welcome(self) -> None:
        """Display welcome message with instructions."""
        welcome = """
## Welcome to AlphaTales Refactor Agent!

I can help you **refactor** or **migrate** your codebase using AI.

### How to Use:
1. Select what to work on (entire project, modules, or files)
2. Choose operation type (Refactor or Migrate)
3. Chat naturally about what you want to change

### Tips:
- Type **@** to autocomplete files and folders
- Type **help** for more commands
- Type **exit** to quit

Let's get started!
        """
        self.console.print(Panel(
            Markdown(welcome),
            border_style="green",
            padding=(1, 2),
        ))

    def show_project_info(self) -> None:
        """Display current project information."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="dim")
        table.add_column("Value", style="cyan")

        table.add_row("Project:", str(self.project_path))

        # Count files by type
        file_counts = self._count_files()
        if file_counts:
            counts_str = ", ".join(f"{ext}: {count}" for ext, count in file_counts.items())
            table.add_row("Files:", counts_str)

        self.console.print(Panel(table, title="[bold]Current Project[/bold]", border_style="blue"))
        self.console.print()

    def _count_files(self) -> dict[str, int]:
        """Count files by extension in the project."""
        counts: dict[str, int] = {}
        extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cs"}

        try:
            for ext in extensions:
                count = len(list(self.project_path.rglob(f"*{ext}")))
                if count > 0:
                    counts[ext] = count
        except Exception:
            pass

        return dict(sorted(counts.items(), key=lambda x: -x[1])[:5])

    async def run_setup_flow(self) -> bool:
        """Run the initial setup flow for scope and operation selection.

        Returns:
            True if setup completed, False if cancelled
        """
        try:
            # Step 1: Select scope
            self.console.print("\n[bold cyan]Step 1: What do you want to work on?[/bold cyan]")
            self.scope = self.menu.show_scope_menu()
            self.console.print(f"[green]Selected: {self.scope.value}[/green]\n")

            # Step 2: If specific modules/files, let user select
            if self.scope in (TargetScope.SPECIFIC_MODULES, TargetScope.SPECIFIC_FILES):
                await self._select_targets()

            # Step 3: Select operation type
            self.console.print("[bold cyan]Step 2: What would you like to do?[/bold cyan]")
            self.operation = self.menu.show_operation_menu()
            self.console.print(f"[green]Selected: {self.operation.value}[/green]\n")

            # Step 4: If migration, select languages
            if self.operation == OperationType.MIGRATE:
                self.console.print("[bold cyan]Step 3: Select languages for migration[/bold cyan]")
                self.source_lang, self.target_lang = self.menu.show_migration_options()
                self.console.print(
                    f"[green]Migration: {self.source_lang} -> {self.target_lang}[/green]\n"
                )

            # Show summary
            self._show_setup_summary()
            return True

        except KeyboardInterrupt:
            self.console.print("\n[yellow]Setup cancelled.[/yellow]")
            return False

    async def _select_targets(self) -> None:
        """Let user select specific files/folders using @ autocomplete."""
        self.console.print()
        self.console.print(Panel(
            "[bold]Select files/folders[/bold]\n\n"
            "Type [cyan]@[/cyan] to autocomplete files and folders.\n"
            "Add multiple paths separated by spaces.\n"
            "Press [cyan]Enter[/cyan] when done.\n\n"
            "[dim]Example: @src/main.py @src/utils/[/dim]",
            border_style="yellow",
        ))
        self.console.print()

        # Refresh file cache
        self.file_completer.refresh_cache()

        # Get user input with autocomplete
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.session.prompt("Select targets: ")
            )

            # Parse selected paths
            paths = []
            for part in response.split():
                path = part.lstrip("@").strip()
                if path:
                    full_path = self.project_path / path
                    if full_path.exists():
                        paths.append(path)
                    else:
                        self.console.print(f"[yellow]Warning: Path not found: {path}[/yellow]")

            self.selected_paths = paths

            if paths:
                self.console.print(f"[green]Selected {len(paths)} target(s)[/green]")
            else:
                self.console.print("[yellow]No valid paths selected. Will use all files.[/yellow]")
                self.scope = TargetScope.ALL_PROJECT

        except KeyboardInterrupt:
            self.console.print("[yellow]Selection cancelled.[/yellow]")

    def _show_setup_summary(self) -> None:
        """Show summary of setup selections."""
        table = Table(title="Setup Summary", show_header=False, box=None)
        table.add_column("Setting", style="dim")
        table.add_column("Value", style="cyan")

        table.add_row("Scope:", self.scope.value if self.scope else "N/A")
        table.add_row("Operation:", self.operation.value if self.operation else "N/A")

        if self.selected_paths:
            table.add_row("Targets:", ", ".join(self.selected_paths[:3]))
            if len(self.selected_paths) > 3:
                table.add_row("", f"... and {len(self.selected_paths) - 3} more")

        if self.operation == OperationType.MIGRATE:
            table.add_row("Migration:", f"{self.source_lang} -> {self.target_lang}")

        self.console.print(Panel(table, border_style="green"))
        self.console.print()

    async def get_user_input(self) -> Optional[str]:
        """Get user input with @ autocomplete.

        Returns:
            User input string, or None if cancelled
        """
        try:
            # Build prompt
            prompt_parts = []
            if self.operation == OperationType.REFACTOR:
                prompt_parts.append("[cyan]refactor[/cyan]")
            elif self.operation == OperationType.MIGRATE:
                prompt_parts.append(f"[magenta]migrate ({self.source_lang}->{self.target_lang})[/magenta]")

            self.console.print()

            # Get input
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.session.prompt(
                    [("class:prompt", ">>> ")],
                    bottom_toolbar=self._get_toolbar,
                )
            )

            return response.strip() if response else None

        except KeyboardInterrupt:
            return None
        except EOFError:
            return None

    def _get_toolbar(self) -> str:
        """Get the bottom toolbar text."""
        return " [Ctrl+C] Cancel | [@] Autocomplete files | [help] Show help | [exit] Quit "

    def show_help(self) -> None:
        """Display help information."""
        help_text = """
## Commands

| Command | Description |
|---------|-------------|
| **help** | Show this help message |
| **exit** / **quit** | Exit the application |
| **clear** / **cls** | Clear the screen |
| **status** | Show current settings |
| **reset** | Reset and start over |

## Tips

- Type **@** followed by characters to autocomplete files/folders
- Use natural language to describe what you want to refactor
- Be specific about files, functions, or patterns you want to change

## Examples

```
Refactor @src/main.py to use async/await
Improve error handling in @utils/file_ops.py
Add type hints to all functions in @services/
Rename variables to follow snake_case convention
```
        """
        self.console.print(Panel(Markdown(help_text), title="Help", border_style="yellow"))

    def show_status(self) -> None:
        """Display current status and settings."""
        self._show_setup_summary()

    def show_processing(self, message: str = "Processing...") -> Live:
        """Show a processing indicator.

        Args:
            message: Message to display

        Returns:
            Live context manager
        """
        return Live(
            Spinner("dots", text=f"[cyan]{message}[/cyan]"),
            console=self.console,
            refresh_per_second=10,
        )

    def show_response(self, response: str) -> None:
        """Display agent response.

        Args:
            response: Response text to display
        """
        self.console.print()
        self.console.print(Panel(
            Markdown(response),
            title="[bold cyan]Agent Response[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        ))

    def show_error(self, error: str) -> None:
        """Display an error message.

        Args:
            error: Error message
        """
        self.console.print(f"\n[red bold]Error:[/red bold] {error}\n")

    def show_success(self, message: str) -> None:
        """Display a success message.

        Args:
            message: Success message
        """
        self.console.print(f"\n[green bold]Success:[/green bold] {message}\n")

    def show_warning(self, message: str) -> None:
        """Display a warning message.

        Args:
            message: Warning message
        """
        self.console.print(f"\n[yellow bold]Warning:[/yellow bold] {message}\n")

    def clear_screen(self) -> None:
        """Clear the console screen."""
        self.console.clear()

    def show_goodbye(self) -> None:
        """Display goodbye message."""
        self.console.print("\n[cyan]Goodbye! Happy coding![/cyan]\n")
