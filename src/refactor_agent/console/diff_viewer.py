"""Diff viewer widget for displaying file edits with syntax highlighting.

Shows file changes like Claude Code with:
- Red background for deleted lines
- Green background for added lines
- File path header
- Collapsible diff sections
"""

from __future__ import annotations

import difflib
from typing import List

from rich.text import Text
from rich.panel import Panel
from rich.syntax import Syntax
from textual.widgets import Static

# Import EditOperation from shared models to avoid circular imports
from ..models import EditOperation

# Re-export for backwards compatibility
__all__ = ["EditOperation", "create_diff_text", "create_inline_diff", "DiffBubble", "DiffPanel", "format_edit_for_chat", "format_edit_full", "format_edits_summary"]


def create_diff_text(old_string: str, new_string: str, context_lines: int = 3) -> Text:
    """Create a Rich Text object with colored diff.

    Args:
        old_string: Original text
        new_string: New text
        context_lines: Number of context lines around changes

    Returns:
        Rich Text with red/green highlighting
    """
    old_lines = old_string.splitlines(keepends=True)
    new_lines = new_string.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        lineterm="",
        n=context_lines,
    )

    result = Text()

    for line in diff:
        # Remove the trailing newline for display
        display_line = line.rstrip('\n')

        if line.startswith('+++') or line.startswith('---'):
            # File headers - dim
            result.append(display_line + "\n", style="dim")
        elif line.startswith('@@'):
            # Line numbers - cyan
            result.append(display_line + "\n", style="bold cyan")
        elif line.startswith('+'):
            # Added line - green background
            result.append(display_line + "\n", style="green on #1a3a1a")
        elif line.startswith('-'):
            # Removed line - red background
            result.append(display_line + "\n", style="red on #3a1a1a")
        else:
            # Context line - normal
            result.append(display_line + "\n", style="dim")

    return result


def create_inline_diff(old_string: str, new_string: str) -> Text:
    """Create an inline diff showing old → new.

    For small changes, shows them side by side.

    Args:
        old_string: Original text
        new_string: New text

    Returns:
        Rich Text with inline diff
    """
    result = Text()

    # For short strings, show inline
    if len(old_string) < 100 and len(new_string) < 100 and '\n' not in old_string and '\n' not in new_string:
        result.append(old_string, style="red strike")
        result.append(" → ", style="dim")
        result.append(new_string, style="green")
        return result

    # For longer strings, use unified diff
    return create_diff_text(old_string, new_string)


class DiffBubble(Static):
    """A chat bubble that displays a file diff."""

    DEFAULT_CSS = """
    DiffBubble {
        padding: 1 2;
        margin: 1 2;
        background: #1e1e2e;
        border: solid #3a3a5a;
        height: auto;
    }

    DiffBubble .file-header {
        color: #7aa2f7;
        text-style: bold;
        margin-bottom: 1;
    }

    DiffBubble .diff-content {
        margin-top: 1;
    }

    DiffBubble.success {
        border: solid #50fa7b;
    }

    DiffBubble.error {
        border: solid #ff5555;
    }
    """

    def __init__(
        self,
        edit: EditOperation,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.edit = edit
        self.add_class("success" if edit.success else "error")

    def compose(self):
        """Compose the diff display."""
        pass  # We'll use update() instead

    def on_mount(self) -> None:
        """Build the diff display on mount."""
        content = Text()

        # File header with icon
        icon = "✓" if self.edit.success else "✗"
        icon_style = "green" if self.edit.success else "red"
        content.append(f"{icon} ", style=icon_style)
        content.append("Edit: ", style="dim")
        content.append(self.edit.file_path, style="bold cyan")
        content.append("\n\n")

        if self.edit.error:
            content.append(f"Error: {self.edit.error}", style="red")
        else:
            # Add the diff
            diff_text = create_diff_text(self.edit.old_string, self.edit.new_string)
            content.append_text(diff_text)

        self.update(content)


class DiffPanel(Static):
    """A panel that shows multiple file diffs."""

    DEFAULT_CSS = """
    DiffPanel {
        height: auto;
        padding: 0;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._edits: List[EditOperation] = []

    def add_edit(self, edit: EditOperation) -> None:
        """Add an edit to display.

        Args:
            edit: The edit operation to display
        """
        self._edits.append(edit)
        self._refresh_display()

    def clear_edits(self) -> None:
        """Clear all edits."""
        self._edits.clear()
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the display with all edits."""
        if not self._edits:
            self.update("")
            return

        content = Text()

        for i, edit in enumerate(self._edits):
            if i > 0:
                content.append("\n" + "─" * 50 + "\n\n", style="dim")

            # File header
            icon = "✓" if edit.success else "✗"
            icon_style = "green" if edit.success else "red"
            content.append(f"{icon} ", style=icon_style)
            content.append("Edit: ", style="dim")
            content.append(edit.file_path, style="bold cyan")
            content.append("\n\n")

            if edit.error:
                content.append(f"Error: {edit.error}\n", style="red")
            else:
                diff_text = create_diff_text(edit.old_string, edit.new_string)
                content.append_text(diff_text)

        self.update(content)


def format_edit_for_chat(edit: EditOperation, max_lines: int = 15) -> tuple[Text, bool]:
    """Format an edit operation for display in chat.

    Args:
        edit: The edit operation
        max_lines: Maximum lines to show before truncation

    Returns:
        Tuple of (Formatted Rich Text, is_truncated)
    """
    content = Text()

    # Header with file icon
    icon = "✓" if edit.success else "✗"
    icon_style = "green bold" if edit.success else "red bold"

    content.append(f"\n{icon} ", style=icon_style)
    content.append("Edited: ", style="dim")
    content.append(edit.file_path, style="bold #7aa2f7 underline")
    content.append("\n\n")

    if edit.error:
        content.append(f"   Error: {edit.error}\n", style="red")
        return content, False

    # Create diff with colors preserved
    old_lines = edit.old_string.splitlines(keepends=True)
    new_lines = edit.new_string.splitlines(keepends=True)

    diff = list(difflib.unified_diff(
        old_lines,
        new_lines,
        lineterm="",
        n=1,  # Compact context
    ))

    is_truncated = len(diff) > max_lines
    lines_to_show = diff[:max_lines] if is_truncated else diff

    for line in lines_to_show:
        display_line = line.rstrip('\n')

        if line.startswith('+++') or line.startswith('---'):
            # File headers - skip these for cleaner look
            continue
        elif line.startswith('@@'):
            # Line numbers - cyan
            content.append(f"   {display_line}\n", style="bold cyan")
        elif line.startswith('+'):
            # Added line - bright GREEN text on dark green background
            content.append(f"   {display_line}\n", style="bold green on #0d3d0d")
        elif line.startswith('-'):
            # Removed line - bright RED text on dark red background
            content.append(f"   {display_line}\n", style="bold red on #3d0d0d")
        else:
            # Context line - dim
            content.append(f"   {display_line}\n", style="dim")

    return content, is_truncated


def format_edit_full(edit: EditOperation) -> Text:
    """Format the full edit without truncation.

    Args:
        edit: The edit operation

    Returns:
        Formatted Rich Text with full diff
    """
    content = Text()

    # Create full diff with colors
    old_lines = edit.old_string.splitlines(keepends=True)
    new_lines = edit.new_string.splitlines(keepends=True)

    diff = list(difflib.unified_diff(
        old_lines,
        new_lines,
        lineterm="",
        n=3,  # More context for full view
    ))

    for line in diff:
        display_line = line.rstrip('\n')

        if line.startswith('+++') or line.startswith('---'):
            content.append(f"   {display_line}\n", style="dim")
        elif line.startswith('@@'):
            content.append(f"   {display_line}\n", style="bold cyan")
        elif line.startswith('+'):
            content.append(f"   {display_line}\n", style="bold green on #0d3d0d")
        elif line.startswith('-'):
            content.append(f"   {display_line}\n", style="bold red on #3d0d0d")
        else:
            content.append(f"   {display_line}\n", style="dim")

    return content


def format_edits_summary(edits: List[EditOperation]) -> Text:
    """Format a summary of all edits.

    Args:
        edits: List of edit operations

    Returns:
        Formatted summary text
    """
    if not edits:
        return Text("No files were edited.", style="dim")

    content = Text()

    success_count = sum(1 for e in edits if e.success)
    error_count = len(edits) - success_count

    content.append(f"\n{'─' * 40}\n", style="dim")
    content.append("Files edited: ", style="bold")
    content.append(f"{success_count}", style="green bold")

    if error_count > 0:
        content.append(f" ({error_count} failed)", style="red")

    content.append("\n")

    for edit in edits:
        icon = "  ✓ " if edit.success else "  ✗ "
        icon_style = "green" if edit.success else "red"
        content.append(icon, style=icon_style)
        content.append(edit.file_path + "\n", style="cyan")

    return content
