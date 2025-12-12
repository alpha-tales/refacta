"""Interactive menu selector for the console UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys


class TargetScope(Enum):
    """Target scope for refactoring."""
    ALL_PROJECT = "all"
    SPECIFIC_MODULES = "modules"
    SPECIFIC_FILES = "files"


class OperationType(Enum):
    """Type of operation to perform."""
    REFACTOR = "refactor"
    MIGRATE = "migrate"


@dataclass
class MenuSelection:
    """Result of menu selection."""
    scope: TargetScope
    operation: OperationType
    target_path: Optional[str] = None


class MenuSelector:
    """Interactive menu selector with keyboard navigation."""

    def __init__(self, console: Optional[Console] = None) -> None:
        """Initialize menu selector.

        Args:
            console: Rich console instance
        """
        self.console = console or Console()

    def show_scope_menu(self) -> TargetScope:
        """Show target scope selection menu.

        Returns:
            Selected target scope
        """
        options = [
            ("1", "All Project", "Refactor entire codebase", TargetScope.ALL_PROJECT),
            ("2", "Specific Modules", "Select specific folders/modules", TargetScope.SPECIFIC_MODULES),
            ("3", "Specific Files", "Select individual files", TargetScope.SPECIFIC_FILES),
        ]

        self._show_menu_panel(
            title="Select Target Scope",
            subtitle="What do you want to work on?",
            options=[(key, name, desc) for key, name, desc, _ in options],
        )

        while True:
            choice = prompt("Enter choice (1-3): ").strip()
            for key, _, _, scope in options:
                if choice == key:
                    return scope

            self.console.print("[red]Invalid choice. Please enter 1, 2, or 3.[/red]")

    def show_operation_menu(self) -> OperationType:
        """Show operation type selection menu.

        Returns:
            Selected operation type
        """
        options = [
            ("1", "Refactor", "Improve code quality (same language)", OperationType.REFACTOR),
            ("2", "Migrate", "Convert to different language/framework", OperationType.MIGRATE),
        ]

        self._show_menu_panel(
            title="Select Operation",
            subtitle="What would you like to do?",
            options=[(key, name, desc) for key, name, desc, _ in options],
        )

        while True:
            choice = prompt("Enter choice (1-2): ").strip()
            for key, _, _, operation in options:
                if choice == key:
                    return operation

            self.console.print("[red]Invalid choice. Please enter 1 or 2.[/red]")

    def show_migration_options(self) -> tuple[str, str]:
        """Show migration source and target language selection.

        Returns:
            Tuple of (source_language, target_language)
        """
        languages = [
            ("1", "Python"),
            ("2", "JavaScript"),
            ("3", "TypeScript"),
            ("4", "Java"),
            ("5", "C#"),
            ("6", "Go"),
            ("7", "Rust"),
            ("8", "Ruby"),
            ("9", "PHP"),
        ]

        # Source language
        self._show_menu_panel(
            title="Source Language",
            subtitle="What language is your current code in?",
            options=[(key, name, "") for key, name in languages],
        )

        source = None
        while source is None:
            choice = prompt("Enter source language (1-9): ").strip()
            for key, name in languages:
                if choice == key:
                    source = name
                    break
            if source is None:
                self.console.print("[red]Invalid choice.[/red]")

        # Target language
        self._show_menu_panel(
            title="Target Language",
            subtitle="What language do you want to convert to?",
            options=[(key, name, "") for key, name in languages if name != source],
        )

        target = None
        while target is None:
            choice = prompt("Enter target language: ").strip()
            for key, name in languages:
                if choice == key and name != source:
                    target = name
                    break
            if target is None:
                self.console.print("[red]Invalid choice or same as source.[/red]")

        return source, target

    def _show_menu_panel(
        self,
        title: str,
        subtitle: str,
        options: list[tuple[str, str, str]],
    ) -> None:
        """Display a menu panel with options.

        Args:
            title: Menu title
            subtitle: Menu subtitle/description
            options: List of (key, name, description) tuples
        """
        self.console.print()

        table = Table(
            show_header=False,
            box=None,
            padding=(0, 2),
            expand=False,
        )
        table.add_column("Key", style="cyan bold", width=4)
        table.add_column("Option", style="white bold")
        table.add_column("Description", style="dim")

        for key, name, desc in options:
            table.add_row(f"[{key}]", name, desc)

        panel = Panel(
            table,
            title=f"[bold cyan]{title}[/bold cyan]",
            subtitle=f"[dim]{subtitle}[/dim]",
            border_style="cyan",
            padding=(1, 2),
        )

        self.console.print(panel)
        self.console.print()
