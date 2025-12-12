"""Interactive console UI components.

This module provides two UI options:
1. Classic Rich-based console (ConsoleUI, MenuSelector, FileCompleter)
2. Modern Textual TUI (RefactorAgentApp, DiffViewer, ChatInput)

The Textual TUI provides a Claude Code-style interface with split panels,
visual diff viewer, and real-time progress tracking.
"""

from .ui import ConsoleUI
from .autocomplete import FileCompleter
from .menu import MenuSelector
from .session import run_interactive_session, run_textual_app

__all__ = [
    # Classic UI
    "ConsoleUI",
    "FileCompleter",
    "MenuSelector",
    # Session runners
    "run_interactive_session",
    "run_textual_app",
]
