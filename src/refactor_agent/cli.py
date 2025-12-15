"""Command-line interface for the AlphaTales Refactor Agent.

Modern CLI with Typer, Rich console output, and best practices:
- Interactive console with menus
- @ triggered file autocomplete
- Natural language conversation
- Progress indicators and structured output
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.theme import Theme

from . import __version__

# Custom theme for consistent styling
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red bold",
    "success": "green bold",
    "muted": "dim",
})

console = Console(theme=custom_theme)
app = typer.Typer(
    name="refactor-agent",
    help="AI-powered code refactoring system using Claude Agent SDK",
    invoke_without_command=True,
    rich_markup_mode="rich",
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"[info]AlphaTales Refactor Agent[/info] v{__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def default_command(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(
        None,
        "--project", "-p",
        help="Path to the project directory (default: current directory)",
    ),
    model: str = typer.Option(
        "claude-sonnet-4-5-20250929",
        "--model", "-m",
        help="Claude model to use",
    ),
    classic: bool = typer.Option(
        False,
        "--classic", "-c",
        help="Use classic Rich-based console instead of Textual TUI",
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version", "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Start the interactive refactoring console.

    When run without a subcommand, opens the Claude Code-style TUI with:
    - Split panel layout (chat + file tree + progress)
    - Visual diff viewer with red/green highlighting
    - Menu-based operation selection (refactor / migrate)
    - @ triggered file autocomplete
    - Real-time progress tracking

    Examples:
        refactor-agent                     # Start Textual TUI in current directory
        refactor-agent -p ./my-project     # Start with specific project
        refactor-agent --classic           # Use classic Rich console UI
    """
    if ctx.invoked_subcommand is None:
        # Run interactive mode
        project_path = Path(project) if project else Path.cwd()

        if not project_path.exists():
            console.print(f"[error]Project path does not exist:[/error] {project_path}")
            raise typer.Exit(1)

        try:
            if classic:
                # Use classic Rich-based console
                from .console.session import run_interactive_session
                asyncio.run(run_interactive_session(
                    project_path=project_path,
                    model=model,
                ))
            else:
                # Use Textual TUI (default)
                from .console.session import run_textual_app
                run_textual_app(
                    project_path=project_path,
                    model=model,
                )
        except KeyboardInterrupt:
            console.print("\n[cyan]Goodbye![/cyan]")
        except Exception as e:
            console.print(f"[error]Error:[/error] {e}")
            raise typer.Exit(1)


@app.command()
def run(
    project: str = typer.Argument(
        ...,
        help="Path to the project root directory",
    ),
    rules: str = typer.Argument(
        ...,
        help="Path to the refactor rules file (YAML/MD)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run", "-n",
        help="Plan and log changes without modifying files",
    ),
    model: str = typer.Option(
        "claude-sonnet-4-5-20250929",
        "--model", "-m",
        help="Claude model to use",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet", "-q",
        help="Suppress banner and verbose output",
    ),
) -> None:
    """Run the full automated refactoring pipeline.

    This runs the complete pipeline: scan -> plan -> refactor -> verify -> build -> report

    Examples:
        refactor-agent run ./my-project ./rules/python-rules.md
        refactor-agent run ./my-project ./rules/general-rules.md --dry-run
    """
    from .orchestrator import RefactorOrchestrator

    project_path = Path(project)
    rules_path = Path(rules)

    # Validate paths
    if not project_path.exists():
        console.print(f"[error]Project path does not exist:[/error] {project_path}")
        raise typer.Exit(1)

    if not rules_path.exists():
        console.print(f"[error]Rules file does not exist:[/error] {rules_path}")
        raise typer.Exit(1)

    # Show banner unless quiet
    if not quiet:
        _show_banner()
        console.print()

    # Progress display
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Refactoring...", total=6)

        def on_progress(message: str, current: int, total: int) -> None:
            progress.update(task, completed=current, description=message)

        # Create and run orchestrator
        orchestrator = RefactorOrchestrator(
            project_path=project_path,
            rules_path=rules_path,
            model=model,
            dry_run=dry_run,
            on_progress=on_progress,
        )

        result = orchestrator.run()

    # Show results
    _show_result(result)

    # Report location
    summary_path = project_path / ".refactor" / "summary.md"
    if summary_path.exists():
        console.print()
        console.print(f"[info]Full report:[/info] {summary_path}")

    # Exit code
    raise typer.Exit(0 if result.success else 1)


@app.command()
def scan(
    project: str = typer.Argument(
        ...,
        help="Path to the project root directory",
    ),
) -> None:
    """Scan a project and generate a file manifest.

    This runs only the scanning phase without any refactoring.
    Useful for previewing what files will be analyzed.
    """
    from .sdk.client import AgentClient
    from .pipeline import ProjectScanner
    from .utils.file_ops import FileManager

    project_path = Path(project)

    if not project_path.exists():
        console.print(f"[error]Project path does not exist:[/error] {project_path}")
        raise typer.Exit(1)

    _show_banner()
    console.print()
    console.print(f"[info]Scanning project:[/info] {project_path}")

    file_manager = FileManager(project_path=project_path)
    file_manager.ensure_refactor_dir()

    client = AgentClient(project_path=project_path)
    scanner = ProjectScanner(client)

    with console.status("Scanning..."):
        result = asyncio.run(scanner.scan())

    if result.success:
        console.print("[success]Scan completed![/success]")
        console.print(f"[info]Manifest saved to:[/info] {project_path / '.refactor' / 'manifest.json'}")
        console.print(f"[muted]Tokens used: {result.tokens_used:,}[/muted]")
    else:
        console.print(f"[error]Scan failed:[/error] {result.error}")
        raise typer.Exit(1)


@app.command()
def list_rules(
    rules_dir: str = typer.Argument(
        "./rules",
        help="Path to the rules directory",
    ),
) -> None:
    """List available refactoring rule files."""
    from .rules.loader import RulesLoader

    rules_path = Path(rules_dir)

    if not rules_path.exists():
        console.print(f"[error]Rules directory does not exist:[/error] {rules_path}")
        raise typer.Exit(1)

    loader = RulesLoader(rules_path)
    rules = loader.list_available_rules()

    if not rules:
        console.print("[warning]No rule files found[/warning]")
        return

    table = Table(title="Available Rules", show_header=True)
    table.add_column("Language", style="cyan")
    table.add_column("File", style="dim")

    for rule in rules:
        table.add_row(rule, f"{rule}-rules.md")

    console.print(table)


def _show_banner() -> None:
    """Display the application banner."""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║           AlphaTales Refactor Agent v2.0                  ║
║        AI-Powered Code Refactoring System                 ║
╚═══════════════════════════════════════════════════════════╝
    """
    console.print(Panel(banner.strip(), border_style="cyan"))


def _show_result(result) -> None:
    """Display refactoring result in a formatted table."""
    # Status panel
    status_style = "success" if result.success else "error"
    status_text = "SUCCESS" if result.success else "FAILED"
    console.print()
    console.print(Panel(
        f"[{status_style}]{status_text}[/{status_style}]",
        title="Refactoring Result",
        border_style=status_style,
    ))

    # Summary table
    table = Table(title="Summary", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Value")

    table.add_row("Status", status_text)
    table.add_row("Total Tokens", f"{result.tokens_used:,}")
    table.add_row("Input Tokens", f"{result.input_tokens:,}")
    table.add_row("Output Tokens", f"{result.output_tokens:,}")
    if result.cost_usd > 0:
        table.add_row("Estimated Cost", f"${result.cost_usd:.4f}")
    table.add_row("Errors", str(len(result.errors)))
    table.add_row("Warnings", str(len(result.warnings)))

    console.print(table)

    # Session info
    if result.sessions:
        console.print()
        console.print("[info]Active Sessions:[/info]")
        for agent, session_id in result.sessions.items():
            console.print(f"  [dim]•[/dim] {agent}: {session_id[:16]}...")

    # Errors
    if result.errors:
        console.print()
        console.print("[error]Errors:[/error]")
        for error in result.errors:
            console.print(f"  [error]•[/error] {error}")

    # Warnings
    if result.warnings:
        console.print()
        console.print("[warning]Warnings:[/warning]")
        for warning in result.warnings:
            console.print(f"  [warning]•[/warning] {warning}")


def main() -> None:
    """Entry point for the CLI."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[warning]Interrupted by user[/warning]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[error]Unexpected error:[/error] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
