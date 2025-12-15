"""Main Textual application for AlphaTales Refactor Agent.

Claude Code-style TUI:
- Centered logo and title
- Clean chat interface
- Input box with send button
- @ file autocomplete
- Dark black background with indigo accents
- Integrated with Claude Agent SDK
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional, List, Iterable

from enum import Enum
from rich.text import Text

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static
from textual_autocomplete import AutoComplete, DropdownItem, TargetState

from ..sdk.client import AgentClient
from .diff_viewer import EditOperation, format_edit_for_chat, format_edit_full, format_edits_summary


class ScopeType(Enum):
    """Scope type for refactoring target."""
    ALL_PROJECT = "all"      # Work on entire project, no @ autocomplete
    FOLDER = "folder"        # Select folders only
    FILES = "files"          # Select files only


# AlphaTales Logo ASCII Art
ALPHATALES_LOGO = """
      ▄▄▄▄▄▄
     ████████
    ██      ██
   ██   ██   ██
  ██████████████
 ██     ██     ██
██      ██      ██
"""


class FileCandidate:
    """File candidate with searchable path."""
    def __init__(self, rel_path: str, is_folder: bool = False):
        self.rel_path = rel_path
        self.is_folder = is_folder
        # Add trailing slash for folders to make it clear
        display_path = f"{rel_path}/" if is_folder else rel_path
        self.display = f"@{display_path}"
        self.dropdown_item = DropdownItem(main=self.display)


def get_file_candidates(
    project_path: Path,
    scope: ScopeType = ScopeType.FILES
) -> List[FileCandidate]:
    """Get files or folders in project as autocomplete candidates.

    Args:
        project_path: Root project path
        scope: What to return - FILES (files only), FOLDER (folders only), ALL_PROJECT (empty)

    Returns:
        List of FileCandidate objects
    """
    # ALL_PROJECT scope means no autocomplete needed
    if scope == ScopeType.ALL_PROJECT:
        return []

    candidates = []
    # Directories to ignore in autocomplete
    ignored_dirs = {
        'node_modules', '__pycache__', 'venv', 'myvenv', '.venv',
        '.git', 'dist', 'build', '.refactor', '.claude',
        'env', 'virtualenv', '.env', 'site-packages', '.next',
        'coverage', '.nyc_output', '.cache', 'out'
    }
    # File extensions to ignore
    ignored_extensions = {'.md', '.txt', '.log', '.pyc', '.pyo', '.map', '.lock'}

    # Limits - collect more internally, display limit applied after sorting
    collection_limit = 2000  # Collect up to 2000 items
    display_limit = 300      # Show max 300 in autocomplete

    try:
        for root, dirs, filenames in os.walk(project_path):
            # Skip hidden and common ignored directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in ignored_dirs]

            rel_root = os.path.relpath(root, project_path)

            if scope == ScopeType.FOLDER:
                # Add folders only
                for d in dirs:
                    if rel_root == '.':
                        rel_path = d
                    else:
                        rel_path = os.path.join(rel_root, d)
                    candidates.append(FileCandidate(rel_path, is_folder=True))
            else:
                # Add files only (ScopeType.FILES)
                for f in filenames:
                    if f.startswith('.'):
                        continue
                    # Skip ignored file extensions
                    ext = os.path.splitext(f)[1].lower()
                    if ext in ignored_extensions:
                        continue
                    if rel_root == '.':
                        rel_path = f
                    else:
                        rel_path = os.path.join(rel_root, f)
                    candidates.append(FileCandidate(rel_path, is_folder=False))

            # Only break at very high limit to ensure both frontend and backend are included
            if len(candidates) >= collection_limit:
                break
    except Exception:
        pass

    # Sort candidates: prioritize by depth (shallow first), then by name
    priority_names = {'src', 'app', 'components', 'pages', 'lib', 'utils', 'hooks',
                      'styles', 'api', 'services', 'models', 'types', 'interfaces',
                      'frontend', 'backend', 'web', 'client', 'server'}

    def sort_key(c):
        path = c.rel_path
        depth = path.count(os.sep) + path.count('/')  # Count path separators
        name = os.path.basename(path).lower()
        # Sort by: 1) depth (shallow first), 2) priority name, 3) alphabetical
        is_priority = 0 if name in priority_names else 1
        return (depth, is_priority, path.lower())

    candidates.sort(key=sort_key)

    # Apply final display limit
    return candidates[:display_limit]


class MessageBubble(Static):
    """Chat message - minimal style."""

    DEFAULT_CSS = """
    MessageBubble {
        padding: 1 2;
        margin: 1 4;
        height: auto;
        background: transparent;
    }

    MessageBubble .sender {
        text-style: bold;
        margin-bottom: 0;
    }

    MessageBubble.user .sender {
        color: #94a3b8;
    }

    MessageBubble.assistant .sender {
        color: #6366f1;
    }

    MessageBubble .content {
        color: #e2e8f0;
        margin-top: 1;
    }
    """

    def __init__(self, content: str, sender: str = "assistant", **kwargs) -> None:
        super().__init__(**kwargs, classes=sender)
        self.content = content
        self.sender = sender

    def compose(self) -> ComposeResult:
        sender_label = "You" if self.sender == "user" else "AlphaTales"
        yield Static(f"● {sender_label}", classes="sender")
        yield Static(self.content, classes="content")


class DiffBubble(Static):
    """Chat bubble that displays file edit diffs with syntax highlighting.

    Shows truncated diff by default with "More" button for long diffs.
    Click the button to expand and see full diff.
    """

    DEFAULT_CSS = """
    DiffBubble {
        padding: 1 2;
        margin: 1 4;
        height: auto;
        background: transparent;
        border: solid #3a3a5a;
    }

    DiffBubble.success {
        border: solid #50fa7b;
    }

    DiffBubble.error {
        border: solid #ff5555;
    }

    DiffBubble .diff-content {
        height: auto;
    }

    DiffBubble .button-row {
        width: 100%;
        height: auto;
        align: right middle;
    }

    DiffBubble .more-button {
        width: auto;
        min-width: 10;
        height: 3;
        margin-top: 1;
        background: #2a2a3a;
        color: #7aa2f7;
        border: round #3a3a5a;
        padding: 0 2;
    }

    DiffBubble .more-button:hover {
        background: #3a3a4a;
        color: #99b2ff;
        border: round #5a5a7a;
    }
    """

    def __init__(self, edit: EditOperation, **kwargs) -> None:
        super().__init__(**kwargs)
        self.edit = edit
        self._expanded = False
        self._is_truncated = False
        self.add_class("success" if edit.success else "error")

    def compose(self) -> ComposeResult:
        yield Static(id="diff-content", classes="diff-content")
        with Horizontal(classes="button-row"):
            yield Button("▼ More", id="more-btn", classes="more-button")

    def on_mount(self) -> None:
        """Build the diff display on mount."""
        self._update_display()

    def _update_display(self) -> None:
        """Update the diff content display."""
        content_widget = self.query_one("#diff-content", Static)
        more_btn = self.query_one("#more-btn", Button)

        if self._expanded:
            # Show full diff
            from rich.text import Text
            header = Text()
            icon = "✓" if self.edit.success else "✗"
            icon_style = "green bold" if self.edit.success else "red bold"
            header.append(f"\n{icon} ", style=icon_style)
            header.append("Edited: ", style="dim")
            header.append(self.edit.file_path, style="bold #7aa2f7 underline")
            header.append("\n\n")

            full_diff = format_edit_full(self.edit)
            header.append_text(full_diff)
            content_widget.update(header)
            more_btn.label = "▲ Less"
        else:
            # Show truncated diff
            diff_content, self._is_truncated = format_edit_for_chat(self.edit)
            content_widget.update(diff_content)
            more_btn.label = "▼ More"

        # Hide button if not truncated
        more_btn.display = self._is_truncated or self._expanded

    @on(Button.Pressed, "#more-btn")
    def on_more_pressed(self) -> None:
        """Toggle between truncated and full view."""
        self._expanded = not self._expanded
        self._update_display()


class StreamingTextBubble(Static):
    """Chat bubble that shows streaming AI response text.

    Text is appended live as it streams from the API.
    """

    DEFAULT_CSS = """
    StreamingTextBubble {
        padding: 1 2;
        margin: 1 4;
        height: auto;
        background: transparent;
    }

    StreamingTextBubble .sender {
        text-style: bold;
        margin-bottom: 0;
        color: #6366f1;
    }

    StreamingTextBubble .content {
        color: #e2e8f0;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._text_parts: List[str] = []

    def compose(self) -> ComposeResult:
        yield Static("● AlphaTales", classes="sender")
        yield Static("", classes="content", id="stream-content")

    def append_text(self, text: str) -> None:
        """Append text to the streaming content."""
        self._text_parts.append(text)
        try:
            content_widget = self.query_one("#stream-content", Static)
            content_widget.update("".join(self._text_parts))
        except Exception:
            pass

    def get_text(self) -> str:
        """Get the full text content."""
        return "".join(self._text_parts)


class LoadingBubble(Static):
    """Animated loading indicator while AI is processing."""

    LOADING_PHRASES = [
        "Thinking...",
        "Analyzing...",
        "Cooking...",
        "Processing...",
        "Smashing...",
        "Building...",
        "Crafting...",
    ]

    DEFAULT_CSS = """
    LoadingBubble {
        padding: 1 2;
        margin: 1 4;
        height: auto;
        background: transparent;
    }

    LoadingBubble .sender {
        text-style: bold;
        margin-bottom: 0;
        color: #6366f1;
    }

    LoadingBubble .loading-text {
        color: #9ca3af;
        margin-top: 1;
        text-style: italic;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.phrase_index = 0
        self._timer = None

    def compose(self) -> ComposeResult:
        yield Static("● AlphaTales", classes="sender")
        yield Static(self.LOADING_PHRASES[0], classes="loading-text", id="loading-text")

    def on_mount(self) -> None:
        """Start the animation timer."""
        self._timer = self.set_interval(2.0, self._update_phrase)  # Slower animation (2 sec)

    def _update_phrase(self) -> None:
        """Cycle through loading phrases."""
        self.phrase_index = (self.phrase_index + 1) % len(self.LOADING_PHRASES)
        loading_text = self.query_one("#loading-text", Static)
        loading_text.update(self.LOADING_PHRASES[self.phrase_index])

    def stop(self) -> None:
        """Stop the animation."""
        if self._timer:
            self._timer.stop()


class WelcomeScreen(Screen):
    """Welcome screen with operation selection."""

    DEFAULT_CSS = """
    WelcomeScreen {
        align: center middle;
        background: #1a1a1a;
    }

    WelcomeScreen > Vertical {
        width: auto;
        height: auto;
        padding: 2 4;
        align: center middle;
    }

    WelcomeScreen .logo {
        color: #6366f1;
        text-align: center;
        margin-bottom: 1;
    }

    WelcomeScreen .title {
        text-align: center;
        color: #6366f1;
        text-style: bold;
        margin-bottom: 0;
    }

    WelcomeScreen .subtitle {
        text-align: center;
        color: #64748b;
        margin-bottom: 3;
    }

    WelcomeScreen .button-row {
        width: auto;
        height: auto;
        align: center middle;
    }

    WelcomeScreen Button {
        margin: 0 1;
        min-width: 16;
        height: 3;
        background: #252525;
        color: #e2e8f0;
        border: round #6366f1;
    }

    WelcomeScreen Button:hover {
        background: #6366f1;
        color: #ffffff;
    }

    WelcomeScreen Button:focus {
        background: #4f46e5;
        color: #ffffff;
    }

    WelcomeScreen Button.-primary {
        background: #6366f1;
        color: #ffffff;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(ALPHATALES_LOGO, classes="logo")
            yield Static("AlphaTales", classes="title")
            yield Static("AI-Powered Code Refactoring", classes="subtitle")
            with Horizontal(classes="button-row"):
                yield Button("Refactor", id="btn-refactor", variant="primary")
                yield Button("Migrate", id="btn-migrate")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses on welcome screen."""
        button_id = event.button.id

        if button_id == "btn-refactor":
            self.app.operation = "refactor"
            self.app.push_screen("scope")
        elif button_id == "btn-migrate":
            self.app.operation = "migrate"
            self.app.push_screen("scope")


class ScopeSelectionScreen(Screen):
    """Scope selection screen - choose All Project, Folder, or Files."""

    DEFAULT_CSS = """
    ScopeSelectionScreen {
        align: center middle;
        background: #1a1a2e;
    }

    ScopeSelectionScreen > Vertical {
        width: 60;
        height: auto;
        padding: 2 4;
        background: #16213e;
        border: round #6366f1;
    }

    ScopeSelectionScreen .header-box {
        width: 100%;
        height: auto;
        background: #6366f1;
        color: #ffffff;
        padding: 1 2;
        text-align: center;
        text-style: bold;
        margin-bottom: 2;
    }

    ScopeSelectionScreen .subtitle {
        text-align: center;
        color: #94a3b8;
        margin-bottom: 2;
    }

    ScopeSelectionScreen .scope-btn {
        width: 100%;
        margin: 1 0;
        height: 3;
        background: #252545;
        color: #e2e8f0;
        border: solid #6366f1;
    }

    ScopeSelectionScreen .scope-btn:hover {
        background: #6366f1;
        color: #ffffff;
    }

    ScopeSelectionScreen .scope-btn:focus {
        background: #4f46e5;
        color: #ffffff;
    }

    ScopeSelectionScreen .btn-desc {
        color: #64748b;
        text-align: center;
        margin-bottom: 1;
    }

    ScopeSelectionScreen .back-btn {
        margin-top: 2;
        background: transparent;
        color: #64748b;
        border: none;
    }

    ScopeSelectionScreen .back-btn:hover {
        color: #6366f1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Select Scope", classes="header-box")
            yield Static("What do you want to work on?", classes="subtitle")

            yield Button("All Project", id="btn-scope-all", classes="scope-btn")
            yield Static("Work on entire codebase", classes="btn-desc")

            yield Button("Folder", id="btn-scope-folder", classes="scope-btn")
            yield Static("Select specific folders", classes="btn-desc")

            yield Button("Files", id="btn-scope-files", classes="scope-btn")
            yield Static("Select individual files", classes="btn-desc")

            yield Button("← Back", id="btn-scope-back", classes="back-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses on scope selection screen."""
        button_id = event.button.id

        if button_id == "btn-scope-all":
            self.app.scope = ScopeType.ALL_PROJECT
            self.app.push_screen("main")
        elif button_id == "btn-scope-folder":
            self.app.scope = ScopeType.FOLDER
            self.app.push_screen("main")
        elif button_id == "btn-scope-files":
            self.app.scope = ScopeType.FILES
            self.app.push_screen("main")
        elif button_id == "btn-scope-back":
            self.app.pop_screen()


class MainScreen(Screen):
    """Main chat screen - Claude Code style."""

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+n", "new_session", "New Session"),
        Binding("escape", "focus_input", "Focus Input"),
    ]

    DEFAULT_CSS = """
    MainScreen {
        background: #1a1a1a;
    }

    MainScreen > Vertical {
        height: 100%;
    }

    /* Back button - top left corner */
    MainScreen .back-button {
        dock: top;
        width: auto;
        height: 3;
        margin: 1 0 0 2;
        background: transparent;
        color: #64748b;
        border: none;
    }

    MainScreen .back-button:hover {
        color: #6366f1;
    }

    /* AutoComplete dropdown styling */
    AutoComplete {
        background: #252525;
        border: round #3a3a3a;
        max-height: 15;
    }

    AutoComplete > .autocomplete--highlight-match {
        color: #6366f1;
        text-style: bold;
    }

    AutoComplete > .autocomplete--selection-cursor {
        background: #6366f1;
        color: #ffffff;
    }

    /* Centered header with logo - hidden when has messages */
    MainScreen .header-area {
        height: auto;
        width: 100%;
        padding: 2 0 1 0;
        align: center top;
    }

    MainScreen .header-area.hidden {
        display: none;
    }

    MainScreen .header-content {
        width: 100%;
        height: auto;
        align: center middle;
    }

    MainScreen .header-logo {
        color: #6366f1;
        text-align: center;
        content-align: center middle;
        width: 100%;
    }

    MainScreen .header-title {
        color: #6366f1;
        text-style: bold;
        text-align: center;
        content-align: center middle;
        width: 100%;
    }

    /* Messages area - transparent, no border */
    MainScreen #messages {
        height: 1fr;
        background: transparent;
        border: none;
        padding: 0 4;
        scrollbar-color: #6366f1;
        scrollbar-background: #252525;
    }

    /* Input area at bottom - centered, more padding at bottom */
    MainScreen .input-area {
        height: auto;
        dock: bottom;
        padding: 1 4 4 4;
        background: #1a1a1a;
        align: center bottom;
    }

    MainScreen .input-wrapper {
        height: auto;
        width: 80%;
        max-width: 80;
        align: center middle;
    }

    /* Input box - subtle border when idle, highlighted on focus */
    MainScreen .input-box {
        background: #1f1f1f;
        border: round #2a2a2a;
        height: auto;
        padding: 0 1;
        width: 100%;
    }

    MainScreen .input-box:focus-within {
        background: #242424;
        border: round #6366f1;
    }

    /* Input field area - compact */
    MainScreen .input-field-row {
        height: 3;
        width: 100%;
    }

    MainScreen .input-field-row Input {
        background: transparent;
        border: none;
        padding: 0 1;
        height: 3;
        width: 100%;
        color: #e5e7eb;
    }

    MainScreen .input-field-row Input.-placeholder {
        color: #4a4a4a;
    }

    MainScreen .input-field-row Input:focus {
        border: none;
    }

    /* Footer row: hint + button on same line */
    MainScreen .input-footer {
        width: 100%;
        height: 3;
        align: left middle;
    }

    MainScreen .input-hint {
        color: #4a5568;
        padding: 0 1;
        width: 1fr;
        text-style: dim;
    }

    /* Send button - subtle hover */
    MainScreen .send-button {
        width: 5;
        height: 3;
        min-width: 5;
        background: #2a2a2a;
        color: #9ca3af;
        border: round #3a3a3a;
        content-align: center middle;
    }

    MainScreen .send-button:hover {
        background: #333333;
        color: #e5e7eb;
        border: round #4a4a4a;
    }

    MainScreen .send-button:focus {
        background: #3a3a3a;
        color: #e5e7eb;
        border: round #6366f1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._file_candidates: List[FileCandidate] = []
        self._cached_scope: Optional[ScopeType] = None  # Track which scope was cached

    def compose(self) -> ComposeResult:
        # Back button at top left
        yield Button("← Back", id="btn-back", classes="back-button")

        with Vertical():
            # Centered header with logo - hidden when messages exist
            with Container(classes="header-area", id="header"):
                with Vertical(classes="header-content"):
                    yield Static(ALPHATALES_LOGO, classes="header-logo")
                    yield Static("AlphaTales", classes="header-title")

            # Messages area (scrollable, transparent)
            yield ScrollableContainer(id="messages")

            # Input area at bottom
            with Container(classes="input-area"):
                with Vertical(classes="input-wrapper"):
                    # Input box
                    with Container(classes="input-box"):
                        with Container(classes="input-field-row"):
                            chat_input = Input(placeholder="Type a message...", id="chat-input")
                            yield chat_input
                        with Horizontal(classes="input-footer"):
                            yield Static("", classes="input-hint", id="input-hint")
                            yield Button("↑", id="send-btn", classes="send-button")

        # AutoComplete for file selection (attached to input)
        yield AutoComplete(
            Input,
            candidates=self._get_candidates,
            id="file-autocomplete"
        )

    def _get_candidates(self, state: TargetState) -> Iterable[DropdownItem]:
        """Get file/folder candidates when @ is typed (based on scope)."""
        # Check scope - if ALL_PROJECT, no autocomplete
        scope = getattr(self.app, 'scope', ScopeType.FILES)
        if scope == ScopeType.ALL_PROJECT:
            return []

        value = state.text
        cursor = state.cursor_position

        # Find the @ symbol before cursor
        text_before_cursor = value[:cursor]
        if "@" not in text_before_cursor:
            return []

        # Find the start of the @ reference
        at_pos = text_before_cursor.rfind("@")
        query = text_before_cursor[at_pos + 1:]

        # If there's a space after @, don't show autocomplete
        if " " in query:
            return []

        # Load candidates based on scope (lazy load with scope tracking)
        # Reload if scope changed or cache is empty
        if not self._file_candidates or self._cached_scope != scope:
            project_path = getattr(self.app, "project_path", Path.cwd())
            self._file_candidates = get_file_candidates(project_path, scope)
            self._cached_scope = scope

        # Filter candidates based on query and return DropdownItems
        if query:
            return [
                item.dropdown_item for item in self._file_candidates
                if query.lower() in item.display.lower()
            ]
        return [item.dropdown_item for item in self._file_candidates]

    def on_mount(self) -> None:
        # Reset file candidates cache (in case scope changed)
        self._file_candidates = []
        self._cached_scope = None
        self.query_one("#chat-input", Input).focus()
        self._update_input_hint()
        self._update_placeholder()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses on main screen."""
        if event.button.id == "btn-back":
            self.app.pop_screen()

    def _update_input_hint(self) -> None:
        """Update the input hint based on current scope."""
        hint_widget = self.query_one("#input-hint", Static)
        scope = getattr(self.app, 'scope', ScopeType.FILES)

        if scope == ScopeType.ALL_PROJECT:
            hint_widget.update("Working on entire project • /help for commands")
        elif scope == ScopeType.FOLDER:
            hint_widget.update("@ for folders • /help for commands")
        else:
            hint_widget.update("@ for files • /help for commands")

    def _update_placeholder(self) -> None:
        """Update input placeholder based on scope."""
        input_widget = self.query_one("#chat-input", Input)
        scope = getattr(self.app, 'scope', ScopeType.FILES)

        if scope == ScopeType.ALL_PROJECT:
            input_widget.placeholder = "Describe what to refactor in the project..."
        elif scope == ScopeType.FOLDER:
            input_widget.placeholder = "Type @ to select folders, then describe changes..."
        else:
            input_widget.placeholder = "Type @ to select files, then describe changes..."

    @on(Input.Submitted, "#chat-input")
    def on_chat_submitted(self, event: Input.Submitted) -> None:
        self._send_message()

    @on(Button.Pressed, "#send-btn")
    def on_send_clicked(self) -> None:
        self._send_message()

    def _send_message(self) -> None:
        input_widget = self.query_one("#chat-input", Input)
        message = input_widget.value.strip()

        if not message:
            return

        input_widget.value = ""

        if message.startswith("/"):
            self._handle_command(message)
        else:
            self._add_user_message(message)
            self._process_message(message)

    def _hide_header(self) -> None:
        """Hide the header when messages are shown."""
        header = self.query_one("#header", Container)
        header.add_class("hidden")

    def _add_user_message(self, content: str) -> None:
        self._hide_header()
        messages = self.query_one("#messages", ScrollableContainer)
        messages.mount(MessageBubble(content, sender="user"))
        messages.scroll_end()

    def _add_assistant_message(self, content: str) -> None:
        self._hide_header()
        messages = self.query_one("#messages", ScrollableContainer)
        messages.mount(MessageBubble(content, sender="assistant"))
        messages.scroll_end()

    def _add_diff_bubble(self, edit: EditOperation) -> None:
        """Add a diff bubble showing the file edit."""
        self._hide_header()
        messages = self.query_one("#messages", ScrollableContainer)
        messages.mount(DiffBubble(edit))
        messages.scroll_end()

    def _handle_command(self, command: str) -> None:
        cmd = command.lower().strip()

        if cmd == "/help":
            help_text = (
                "Available commands:\n\n"
                "/help - Show this help\n"
                "/clear - Clear chat history\n"
                "/new - Start new session\n"
                "/quit - Exit application\n\n"
                "Tips:\n"
                "• Type @ to autocomplete file names\n"
                "• Describe changes in natural language"
            )
            self._add_assistant_message(help_text)

        elif cmd == "/clear":
            messages = self.query_one("#messages", ScrollableContainer)
            messages.remove_children()

        elif cmd == "/new":
            self.app.push_screen("welcome")

        elif cmd == "/quit":
            self.app.exit()

        else:
            self._add_assistant_message(f"Unknown command: {cmd}\nType /help for available commands.")

    def _show_loading(self) -> None:
        """Show loading indicator."""
        self._hide_header()
        messages = self.query_one("#messages", ScrollableContainer)
        messages.mount(LoadingBubble(id="loading-bubble"))
        messages.scroll_end()

    def _remove_loading(self) -> None:
        """Remove loading indicator."""
        try:
            loading = self.query_one("#loading-bubble", LoadingBubble)
            loading.stop()
            loading.remove()
        except Exception:
            pass

    def _add_streaming_bubble(self) -> StreamingTextBubble:
        """Add a streaming text bubble and return it."""
        self._hide_header()
        messages = self.query_one("#messages", ScrollableContainer)
        bubble = StreamingTextBubble(id="streaming-bubble")
        messages.mount(bubble)
        messages.scroll_end()
        return bubble

    def _get_streaming_bubble(self) -> Optional[StreamingTextBubble]:
        """Get the current streaming bubble if exists."""
        try:
            return self.query_one("#streaming-bubble", StreamingTextBubble)
        except Exception:
            return None

    def _remove_streaming_bubble(self) -> Optional[str]:
        """Remove streaming bubble and return its text content."""
        try:
            bubble = self.query_one("#streaming-bubble", StreamingTextBubble)
            text = bubble.get_text()
            bubble.remove()
            return text
        except Exception:
            return None

    def _finalize_streaming_bubble(self) -> None:
        """Convert streaming bubble to a regular message (keeps text visible)."""
        try:
            bubble = self.query_one("#streaming-bubble", StreamingTextBubble)
            text = bubble.get_text()
            if text.strip():
                # Remove the streaming bubble
                bubble.remove()
                # Add as a regular message to keep it visible
                messages = self.query_one("#messages", ScrollableContainer)
                messages.mount(MessageBubble(text, sender="assistant"))
                messages.scroll_end()
        except Exception:
            pass

    def _append_to_streaming(self, text: str) -> None:
        """Append text to the streaming bubble."""
        bubble = self._get_streaming_bubble()
        if bubble:
            bubble.append_text(text)
            messages = self.query_one("#messages", ScrollableContainer)
            messages.scroll_end()

    @work(thread=True)
    def _process_message(self, message: str) -> None:
        """Process user message with Claude Agent SDK - TRUE LIVE streaming.

        Shows responses in order as they happen:
        1. AI text appears as it streams
        2. Edit diffs appear immediately when Edit tool is called
        3. More AI text after edits
        4. Final summary with token count
        """
        # Show initial loading while connecting
        self.app.call_from_thread(self._show_loading)

        shown_edits = set()  # Track shown edits to avoid duplicates
        has_streaming_bubble = False  # Track if we've started streaming text

        def on_text(text: str) -> None:
            """Callback to show text in real-time."""
            nonlocal has_streaming_bubble
            # Remove loading on first text
            self.app.call_from_thread(self._remove_loading)
            # Create streaming bubble if needed
            if not has_streaming_bubble:
                self.app.call_from_thread(self._add_streaming_bubble)
                has_streaming_bubble = True
            # Append text to streaming bubble
            self.app.call_from_thread(self._append_to_streaming, text)

        def on_edit(edit: EditOperation) -> None:
            """Callback to show edit diff in real-time."""
            nonlocal has_streaming_bubble
            if edit.file_path not in shown_edits:
                shown_edits.add(edit.file_path)
                # Remove loading if showing
                self.app.call_from_thread(self._remove_loading)
                # If we had streaming text, KEEP it visible (convert to message)
                if has_streaming_bubble:
                    # Finalize streaming bubble as regular message (text stays visible)
                    self.app.call_from_thread(self._finalize_streaming_bubble)
                    has_streaming_bubble = False
                # Show the edit diff
                self.app.call_from_thread(self._add_diff_bubble, edit)

        try:
            client = self._get_agent_client()

            if client is None:
                response = (
                    "Error: Could not initialize AI agent.\n\n"
                    "Please check your ANTHROPIC_API_KEY in .env file."
                )
                self.app.call_from_thread(self._remove_loading)
                self.app.call_from_thread(self._add_assistant_message, response)
                return

            # Determine mode: auto-selection (default) or manual
            use_auto_selection = self._should_use_auto_selection(message)

            # Build prompt with context
            prompt = self._build_prompt(message, use_full_preset=True)

            # Run with LIVE UPDATES - both text and edits stream in order
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if use_auto_selection:
                    # 2-STEP SMART ROUTING (Token Efficient!)
                    # Step 1: Route (~400 tokens) - Claude picks agents from descriptions
                    # Step 2: Execute (~2-3k tokens) - Run with selected agent + skills
                    # Total: ~3k tokens vs ~10k for loading all agents (70% savings!)
                    result = loop.run_until_complete(
                        client.run_with_smart_routing(
                            prompt,
                            on_edit=on_edit,
                            on_text=on_text,
                            resume_session=True,
                            track_report=True,  # Track edits in .refactor/reports/changes.md
                        )
                    )
                else:
                    # Fallback: Manual agent selection (old method)
                    agent_name = self._select_agent(message)
                    use_full_preset, minimal_tools = self._select_mode(message)
                    result = loop.run_until_complete(
                        client.run_agent_with_live_updates(
                            agent_name, prompt,
                            on_edit=on_edit,
                            on_text=on_text,
                            resume_session=True,
                            use_full_preset=use_full_preset,
                            minimal_tools=minimal_tools,
                        )
                    )
            finally:
                loop.close()

            # Build final response
            if result.success:
                had_text = has_streaming_bubble  # Remember if we had streaming text

                # If we still have a streaming bubble, finalize it (keep text visible)
                if has_streaming_bubble:
                    self.app.call_from_thread(self._finalize_streaming_bubble)
                    has_streaming_bubble = False

                self.app.call_from_thread(self._remove_loading)

                # Finalize the report tracker and get report path
                report_path = None
                if result.edits and client:
                    tracker = client.get_report_tracker()
                    report_path = tracker.finalize(
                        total_tokens=result.tokens_used,
                        cost_usd=result.cost_usd,
                    )

                # Show final summary
                if result.edits:
                    # Had edits - show completion message with report link
                    token_info = f"Done! Edited {len(result.edits)} file(s)."
                    if result.tokens_used > 0:
                        token_info += f" [Tokens: {result.tokens_used:,}]"
                    if report_path:
                        token_info += f"\n\nReport saved: .refactor/reports/changes.md"
                    self.app.call_from_thread(self._add_assistant_message, token_info)
                elif not had_text:
                    # No edits and no streaming text seen - show full response
                    response = result.content
                    if result.tokens_used > 0:
                        response += f"\n\n[Tokens: {result.tokens_used:,}]"
                    self.app.call_from_thread(self._add_assistant_message, response)
                else:
                    # Had streaming text (now finalized as message), just show tokens
                    if result.tokens_used > 0:
                        self.app.call_from_thread(self._add_assistant_message, f"[Tokens: {result.tokens_used:,}]")
            else:
                self.app.call_from_thread(self._remove_loading)
                self.app.call_from_thread(self._add_assistant_message, f"Error: {result.error}")

        except Exception as e:
            self.app.call_from_thread(self._remove_loading)
            self.app.call_from_thread(self._add_assistant_message, f"Error: {str(e)}")

    def _get_agent_client(self) -> Optional[AgentClient]:
        """Get or create the AgentClient."""
        if not hasattr(self.app, '_agent_client') or self.app._agent_client is None:
            try:
                self.app._agent_client = AgentClient(
                    project_path=self.app.project_path,
                    model=self.app.model,
                )
            except Exception:
                return None
        return self.app._agent_client

    def _should_use_auto_selection(self, message: str) -> bool:
        """Determine if we should use 2-step smart routing.

        Smart routing is TOKEN EFFICIENT:
        - Step 1: Route (~400 tokens) - Claude picks agents from descriptions
        - Step 2: Execute (~2-3k tokens) - Run with selected agent + skills only
        - Total: ~3k tokens vs ~10k for loading all agents (70% savings!)

        Returns:
            True to use smart routing (default), False to use manual selection
        """
        message_lower = message.lower()

        # Force manual selection if user explicitly specifies an agent
        manual_triggers = [
            "use python-refactorer", "use nextjs-refactorer",
            "use project-scanner", "use build-runner",
            "manual mode", "specific agent"
        ]
        if any(trigger in message_lower for trigger in manual_triggers):
            return False

        # Default: Use auto-selection (FREE and smart!)
        return True

    def _select_mode(self, message: str) -> tuple[bool, bool]:
        """Dynamically select mode based on user message to optimize cost.

        Returns:
            (use_full_preset, minimal_tools)
            - (True, False): Full mode with skills (~20k tokens) - for complex refactoring
            - (False, False): Agent prompt only (~2-5k tokens) - for standard refactoring
            - (False, True): Minimal mode (~1-2k tokens) - for simple edits
        """
        message_lower = message.lower()

        # FULL MODE: User mentions skills, rules, guidelines, best practices
        full_mode_triggers = [
            "skill", "rules", "guidelines", "best practices", "architecture",
            "refactor_rules", "migration_patterns", "compliance",
            "apply all", "full refactor", "comprehensive"
        ]
        if any(trigger in message_lower for trigger in full_mode_triggers):
            return (True, False)  # use_full_preset=True, minimal_tools=False

        # MINIMAL MODE: Simple quick edits
        minimal_triggers = [
            "add docstring", "add comment", "rename", "fix typo",
            "remove unused", "format", "add type hint"
        ]
        if any(trigger in message_lower for trigger in minimal_triggers):
            return (False, True)  # use_full_preset=False, minimal_tools=True

        # DEFAULT: Agent prompt mode (loads .claude/agents/<name>.md)
        return (False, False)  # use_full_preset=False, minimal_tools=False

    def _select_agent(self, message: str) -> str:
        """Select appropriate agent based on message and operation."""
        operation = getattr(self.app, 'operation', 'refactor')

        if operation == 'migrate':
            return 'rules-interpreter'

        # Check for file extensions in message to determine agent
        message_lower = message.lower()
        if any(ext in message_lower for ext in ['.py', 'python', 'backend']):
            return 'python-refactorer'
        elif any(ext in message_lower for ext in ['.tsx', '.ts', '.jsx', '.js', 'react', 'next', 'frontend']):
            return 'nextjs-refactorer'

        # Default to python-refactorer
        return 'python-refactorer'

    def _build_prompt(self, user_message: str, use_full_preset: bool = False) -> str:
        """Build context-aware prompt for the agent.

        Args:
            user_message: The user's request
            use_full_preset: If True, add instructions for comprehensive refactoring
        """
        operation = getattr(self.app, 'operation', 'refactor')
        scope = getattr(self.app, 'scope', ScopeType.ALL_PROJECT)
        project_path = self.app.project_path

        parts = []

        if operation == 'refactor':
            parts.append("You are helping refactor code to improve quality.")
        else:
            parts.append("You are helping migrate code between frameworks.")

        parts.append(f"Project directory: {project_path}")

        # Add scope context
        if scope == ScopeType.ALL_PROJECT:
            parts.append("Scope: ENTIRE PROJECT - Work on all files in the project.")
        elif scope == ScopeType.FOLDER:
            parts.append("Scope: SPECIFIC FOLDERS - User will specify folders using @folder syntax.")
        else:
            parts.append("Scope: SPECIFIC FILES - User will specify files using @file syntax.")

        parts.append(f"\nUser request: {user_message}")

        if use_full_preset:
            # FULL MODE: Comprehensive refactoring with skills
            parts.append("""
IMPORTANT - FULL REFACTORING MODE:
You must apply changes to the ENTIRE file, not just the top/imports section.

Instructions:
1. First, use the Skill tool to load refactor_rules and architecture_guidelines
2. Read the ENTIRE file from top to bottom
3. Apply ALL applicable refactoring rules throughout the ENTIRE file:
   - Imports section: normalize imports, remove unused
   - Functions: add type hints, add docstrings, simplify conditionals
   - Classes: improve naming, add type hints
   - Variables: remove unused, improve naming
   - Modern syntax: use f-strings, pathlib, etc.
4. Make MULTIPLE Edit calls as needed - one for each section/function
5. Do NOT stop after just the imports - continue through the entire file
6. Explain what you changed in each section
""")
        else:
            # STANDARD MODE: Simple edits
            parts.append("""
Instructions:
1. Read the relevant files using the file paths mentioned (@ paths are relative to project root)
2. Analyze the code and understand the user's request
3. Make the requested changes using Edit tool
4. Explain what you changed and why
5. Be concise but thorough
""")

        return "\n".join(parts)

    def action_quit(self) -> None:
        self.app.exit()

    def action_new_session(self) -> None:
        self.app.push_screen("welcome")

    def action_focus_input(self) -> None:
        self.query_one("#chat-input", Input).focus()


class RefactorAgentApp(App):
    """AlphaTales Refactor Agent - Claude Code style.

    Integrated with Claude Agent SDK for actual AI processing.
    """

    TITLE = "AlphaTales"

    CSS = """
    /* Global dark black theme with indigo accents */
    Screen {
        background: #1a1a1a;
    }

    /* Scrollbar styling */
    ScrollableContainer {
        scrollbar-color: #6366f1;
        scrollbar-background: #252525;
    }

    Button {
        background: #252525;
        color: #e2e8f0;
        border: round #6366f1;
    }

    Button:hover {
        background: #6366f1;
    }

    Button.-primary {
        background: #6366f1;
        color: #ffffff;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+n", "new_session", "New Session"),
    ]

    # Register screens with names
    SCREENS = {
        "welcome": WelcomeScreen,
        "scope": ScopeSelectionScreen,
        "main": MainScreen,
    }

    def __init__(
        self,
        project_path: Optional[Path] = None,
        model: str = "claude-sonnet-4-5-20250929",
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.project_path = project_path or Path.cwd()
        self.model = model
        self.operation: str = "refactor"
        self.scope: ScopeType = ScopeType.ALL_PROJECT  # Default scope
        self._agent_client: Optional[AgentClient] = None

    def on_mount(self) -> None:
        self.push_screen("welcome")

    def action_quit(self) -> None:
        self.exit()

    def action_new_session(self) -> None:
        self.push_screen("welcome")


def run_app(project_path: Optional[Path] = None, model: str = "claude-sonnet-4-5-20250929") -> None:
    """Run the Textual application."""
    app = RefactorAgentApp(project_path=project_path, model=model)
    app.run()


if __name__ == "__main__":
    run_app()
