"""Textual-based TUI components for Claude Code-style interface.

This module provides modern terminal UI components using Textual framework:
- DiffViewer: Shows file changes with red/green highlighting
- ChatInput: Styled input box with border
- MessageDisplay: Chat message bubbles
- FileTree: Collapsible file tree with status indicators
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from rich.syntax import Syntax
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Static, Tree
from textual.widgets.tree import TreeNode


class LineChangeType(Enum):
    """Type of change for a diff line."""
    ADDED = "added"
    REMOVED = "removed"
    CONTEXT = "context"
    HEADER = "header"


@dataclass
class DiffLine:
    """A single line in a diff."""
    content: str
    change_type: LineChangeType
    old_line_num: Optional[int] = None
    new_line_num: Optional[int] = None


class DiffViewer(Static):
    """Widget to display file diffs with syntax highlighting.

    Shows added lines in green, removed lines in red, similar to Claude Code.
    """

    DEFAULT_CSS = """
    DiffViewer {
        background: $surface;
        border: solid $primary;
        padding: 1;
        height: auto;
        max-height: 20;
    }

    DiffViewer .diff-header {
        color: $text-muted;
        text-style: bold;
    }

    DiffViewer .diff-added {
        background: #1a3d1a;
        color: #4ade80;
    }

    DiffViewer .diff-removed {
        background: #3d1a1a;
        color: #f87171;
    }

    DiffViewer .diff-context {
        color: $text;
    }

    DiffViewer .line-number {
        color: $text-muted;
        width: 4;
    }
    """

    def __init__(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.file_path = file_path
        self.old_content = old_content
        self.new_content = new_content
        self._diff_lines: list[DiffLine] = []

    def compose(self) -> ComposeResult:
        """Build the diff display."""
        self._diff_lines = self._compute_diff()
        yield from self._render_diff()

    def _compute_diff(self) -> list[DiffLine]:
        """Compute diff between old and new content."""
        import difflib

        old_lines = self.old_content.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)

        diff_lines: list[DiffLine] = []

        # Add header
        diff_lines.append(DiffLine(
            content=f"─── {self.file_path} ───",
            change_type=LineChangeType.HEADER
        ))

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        old_num = 1
        new_num = 1

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                # Context lines - show first 2 and last 2
                equal_lines = old_lines[i1:i2]
                if len(equal_lines) <= 6:
                    for line in equal_lines:
                        diff_lines.append(DiffLine(
                            content=line.rstrip("\n"),
                            change_type=LineChangeType.CONTEXT,
                            old_line_num=old_num,
                            new_line_num=new_num,
                        ))
                        old_num += 1
                        new_num += 1
                else:
                    # Show first 2
                    for line in equal_lines[:2]:
                        diff_lines.append(DiffLine(
                            content=line.rstrip("\n"),
                            change_type=LineChangeType.CONTEXT,
                            old_line_num=old_num,
                            new_line_num=new_num,
                        ))
                        old_num += 1
                        new_num += 1
                    # Separator
                    diff_lines.append(DiffLine(
                        content=f"  ··· {len(equal_lines) - 4} lines hidden ···",
                        change_type=LineChangeType.HEADER,
                    ))
                    old_num += len(equal_lines) - 4
                    new_num += len(equal_lines) - 4
                    # Show last 2
                    for line in equal_lines[-2:]:
                        diff_lines.append(DiffLine(
                            content=line.rstrip("\n"),
                            change_type=LineChangeType.CONTEXT,
                            old_line_num=old_num,
                            new_line_num=new_num,
                        ))
                        old_num += 1
                        new_num += 1

            elif tag == "replace":
                for line in old_lines[i1:i2]:
                    diff_lines.append(DiffLine(
                        content=line.rstrip("\n"),
                        change_type=LineChangeType.REMOVED,
                        old_line_num=old_num,
                    ))
                    old_num += 1
                for line in new_lines[j1:j2]:
                    diff_lines.append(DiffLine(
                        content=line.rstrip("\n"),
                        change_type=LineChangeType.ADDED,
                        new_line_num=new_num,
                    ))
                    new_num += 1

            elif tag == "delete":
                for line in old_lines[i1:i2]:
                    diff_lines.append(DiffLine(
                        content=line.rstrip("\n"),
                        change_type=LineChangeType.REMOVED,
                        old_line_num=old_num,
                    ))
                    old_num += 1

            elif tag == "insert":
                for line in new_lines[j1:j2]:
                    diff_lines.append(DiffLine(
                        content=line.rstrip("\n"),
                        change_type=LineChangeType.ADDED,
                        new_line_num=new_num,
                    ))
                    new_num += 1

        return diff_lines

    def _render_diff(self) -> ComposeResult:
        """Render diff lines as widgets."""
        for diff_line in self._diff_lines:
            line_text = Text()

            if diff_line.change_type == LineChangeType.HEADER:
                line_text.append(diff_line.content, style="bold dim")
            elif diff_line.change_type == LineChangeType.ADDED:
                line_num = str(diff_line.new_line_num or "").rjust(4)
                line_text.append(f"{line_num} ", style="dim")
                line_text.append("+ ", style="bold green")
                line_text.append(diff_line.content, style="green")
            elif diff_line.change_type == LineChangeType.REMOVED:
                line_num = str(diff_line.old_line_num or "").rjust(4)
                line_text.append(f"{line_num} ", style="dim")
                line_text.append("- ", style="bold red")
                line_text.append(diff_line.content, style="red")
            else:
                line_num = str(diff_line.new_line_num or "").rjust(4)
                line_text.append(f"{line_num} ", style="dim")
                line_text.append("  ", style="dim")
                line_text.append(diff_line.content, style="")

            yield Static(line_text, classes="diff-line")


class ChatInput(Widget):
    """Styled input box with border, similar to Claude Code.

    Features:
    - Bordered input area
    - Placeholder text
    - @ trigger for file autocomplete
    - Submit on Enter
    """

    DEFAULT_CSS = """
    ChatInput {
        height: auto;
        padding: 0 1;
        margin: 1 0;
    }

    ChatInput > Container {
        background: $surface;
        border: solid $primary;
        border-title-color: $text;
        padding: 0 1;
        height: auto;
    }

    ChatInput Input {
        background: transparent;
        border: none;
        padding: 0;
        height: 1;
    }

    ChatInput Input:focus {
        border: none;
    }

    ChatInput .hint {
        color: $text-muted;
        text-style: italic;
        height: 1;
    }
    """

    class Submitted(Message):
        """Message sent when input is submitted."""
        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    def __init__(
        self,
        placeholder: str = "Type a message... (use @ for files)",
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Container() as container:
            container.border_title = "Message"
            yield Input(placeholder=self.placeholder, id="chat-input")
            yield Label("Press Enter to send • @ for files • /help for commands", classes="hint")

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.value.strip():
            self.post_message(self.Submitted(event.value))
            event.input.value = ""


class MessageBubble(Static):
    """A chat message bubble."""

    DEFAULT_CSS = """
    MessageBubble {
        padding: 1;
        margin: 0 0 1 0;
        height: auto;
    }

    MessageBubble.user {
        background: $primary-darken-2;
        border: solid $primary;
        margin-left: 10;
    }

    MessageBubble.assistant {
        background: $surface;
        border: solid $secondary;
        margin-right: 10;
    }

    MessageBubble .sender {
        text-style: bold;
        margin-bottom: 1;
    }

    MessageBubble.user .sender {
        color: $primary-lighten-2;
    }

    MessageBubble.assistant .sender {
        color: $secondary;
    }
    """

    def __init__(
        self,
        content: str,
        sender: str = "assistant",
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=sender)
        self.content = content
        self.sender = sender

    def compose(self) -> ComposeResult:
        sender_label = "You" if self.sender == "user" else "AlphaTales Agent"
        yield Static(f"● {sender_label}", classes="sender")
        yield Static(self.content)


class FileChangeStatus(Enum):
    """Status of a file in the refactoring."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    MODIFIED = "modified"
    VERIFIED = "verified"
    ERROR = "error"


class FileTreeWidget(Widget):
    """File tree widget showing files being refactored with status indicators."""

    DEFAULT_CSS = """
    FileTreeWidget {
        height: 100%;
        border: solid $primary;
        background: $surface;
    }

    FileTreeWidget Tree {
        padding: 1;
    }

    FileTreeWidget .status-pending {
        color: $text-muted;
    }

    FileTreeWidget .status-in-progress {
        color: $warning;
    }

    FileTreeWidget .status-modified {
        color: $success;
    }

    FileTreeWidget .status-verified {
        color: $primary;
    }

    FileTreeWidget .status-error {
        color: $error;
    }
    """

    def __init__(
        self,
        root_path: Path,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.root_path = root_path
        self._file_status: dict[str, FileChangeStatus] = {}

    def compose(self) -> ComposeResult:
        tree: Tree[dict] = Tree(str(self.root_path.name), id="file-tree")
        tree.root.expand()
        yield tree

    def add_file(self, file_path: str, status: FileChangeStatus = FileChangeStatus.PENDING) -> None:
        """Add a file to the tree with status."""
        self._file_status[file_path] = status
        tree = self.query_one("#file-tree", Tree)

        # Get status icon
        status_icons = {
            FileChangeStatus.PENDING: "○",
            FileChangeStatus.IN_PROGRESS: "◐",
            FileChangeStatus.MODIFIED: "●",
            FileChangeStatus.VERIFIED: "✓",
            FileChangeStatus.ERROR: "✗",
        }

        status_colors = {
            FileChangeStatus.PENDING: "dim",
            FileChangeStatus.IN_PROGRESS: "yellow",
            FileChangeStatus.MODIFIED: "green",
            FileChangeStatus.VERIFIED: "cyan",
            FileChangeStatus.ERROR: "red",
        }

        icon = status_icons.get(status, "○")
        color = status_colors.get(status, "")

        label = Text()
        label.append(f"{icon} ", style=color)
        label.append(file_path)

        tree.root.add_leaf(label, data={"path": file_path, "status": status})

    def update_status(self, file_path: str, status: FileChangeStatus) -> None:
        """Update status of a file in the tree."""
        self._file_status[file_path] = status
        # Tree would need refresh - simplified for now


class ProgressPanel(Static):
    """Panel showing refactoring progress."""

    DEFAULT_CSS = """
    ProgressPanel {
        height: auto;
        padding: 1;
        background: $surface;
        border: solid $primary;
    }

    ProgressPanel .title {
        text-style: bold;
        color: $primary;
    }

    ProgressPanel .stat {
        margin-top: 1;
    }

    ProgressPanel .stat-label {
        color: $text-muted;
    }

    ProgressPanel .stat-value {
        color: $text;
        text-style: bold;
    }
    """

    files_total: reactive[int] = reactive(0)
    files_processed: reactive[int] = reactive(0)
    tokens_used: reactive[int] = reactive(0)
    current_phase: reactive[str] = reactive("Ready")

    def compose(self) -> ComposeResult:
        yield Static("📊 Progress", classes="title")
        yield Static("", id="progress-stats")

    def watch_files_processed(self, value: int) -> None:
        self._update_display()

    def watch_tokens_used(self, value: int) -> None:
        self._update_display()

    def watch_current_phase(self, value: str) -> None:
        self._update_display()

    def _update_display(self) -> None:
        """Update the progress display."""
        stats = self.query_one("#progress-stats", Static)
        text = Text()
        text.append("\nPhase: ", style="dim")
        text.append(f"{self.current_phase}\n", style="bold")
        text.append("Files: ", style="dim")
        text.append(f"{self.files_processed}/{self.files_total}\n", style="bold")
        text.append("Tokens: ", style="dim")
        text.append(f"{self.tokens_used:,}", style="bold yellow")
        stats.update(text)


class ActionButton(Button):
    """Styled action button."""

    DEFAULT_CSS = """
    ActionButton {
        margin: 0 1;
        min-width: 12;
    }

    ActionButton.primary {
        background: $primary;
    }

    ActionButton.secondary {
        background: $surface;
        border: solid $primary;
    }

    ActionButton.danger {
        background: $error;
    }
    """


class OperationSelector(Widget):
    """Widget for selecting operation type (Refactor/Migrate)."""

    DEFAULT_CSS = """
    OperationSelector {
        height: auto;
        padding: 1;
        background: $surface;
        border: solid $primary;
    }

    OperationSelector .title {
        text-style: bold;
        margin-bottom: 1;
    }

    OperationSelector Horizontal {
        height: auto;
    }
    """

    class OperationSelected(Message):
        """Sent when an operation is selected."""
        def __init__(self, operation: str) -> None:
            super().__init__()
            self.operation = operation

    def compose(self) -> ComposeResult:
        yield Static("Select Operation", classes="title")
        with Horizontal():
            yield ActionButton("🔧 Refactor", id="btn-refactor", classes="primary")
            yield ActionButton("🔄 Migrate", id="btn-migrate", classes="secondary")

    @on(Button.Pressed, "#btn-refactor")
    def on_refactor_pressed(self) -> None:
        self.post_message(self.OperationSelected("refactor"))

    @on(Button.Pressed, "#btn-migrate")
    def on_migrate_pressed(self) -> None:
        self.post_message(self.OperationSelected("migrate"))


class ScopeSelector(Widget):
    """Widget for selecting target scope."""

    DEFAULT_CSS = """
    ScopeSelector {
        height: auto;
        padding: 1;
        background: $surface;
        border: solid $primary;
    }

    ScopeSelector .title {
        text-style: bold;
        margin-bottom: 1;
    }

    ScopeSelector Vertical {
        height: auto;
    }
    """

    class ScopeSelected(Message):
        """Sent when a scope is selected."""
        def __init__(self, scope: str) -> None:
            super().__init__()
            self.scope = scope

    def compose(self) -> ComposeResult:
        yield Static("Select Scope", classes="title")
        with Vertical():
            yield ActionButton("📁 All Project", id="btn-all", classes="primary")
            yield ActionButton("📂 Specific Modules", id="btn-modules", classes="secondary")
            yield ActionButton("📄 Specific Files", id="btn-files", classes="secondary")

    @on(Button.Pressed, "#btn-all")
    def on_all_pressed(self) -> None:
        self.post_message(self.ScopeSelected("all"))

    @on(Button.Pressed, "#btn-modules")
    def on_modules_pressed(self) -> None:
        self.post_message(self.ScopeSelected("modules"))

    @on(Button.Pressed, "#btn-files")
    def on_files_pressed(self) -> None:
        self.post_message(self.ScopeSelected("files"))
