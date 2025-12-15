"""Report Tracker - Updates a single markdown file on each edit.

This module provides live tracking of all edits during a refactoring session,
updating a single report file (.refactor/reports/changes.md) on every edit.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class EditEntry:
    """A single edit entry for the report."""

    file_path: str
    old_string: str
    new_string: str
    timestamp: str
    agent_name: str = ""
    success: bool = True
    error: Optional[str] = None


@dataclass
class ReportTracker:
    """Tracks all edits and updates a single report file.

    Creates .refactor/reports/ folder on first edit.
    Updates .refactor/reports/changes.md on every edit (appends, doesn't recreate).
    """

    project_path: Path
    _initialized: bool = field(default=False, init=False)
    _edit_count: int = field(default=0, init=False)
    _session_id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        """Initialize the tracker."""
        self.project_path = Path(self.project_path).resolve()
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    @property
    def reports_dir(self) -> Path:
        """Get the reports directory path."""
        return self.project_path / ".refactor" / "reports"

    @property
    def report_file(self) -> Path:
        """Get the main report file path."""
        return self.reports_dir / "changes.md"

    def _ensure_initialized(self) -> None:
        """Create reports folder and initialize report file if needed."""
        if self._initialized:
            return

        # Create .refactor/reports/ directory
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Create or append to report file with session header
        if not self.report_file.exists():
            # New file - create with header
            header = self._create_report_header()
            self.report_file.write_text(header, encoding="utf-8")
        else:
            # Existing file - add session separator
            with open(self.report_file, "a", encoding="utf-8") as f:
                f.write(f"\n\n---\n\n## Session: {self._session_id}\n\n")
                f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        self._initialized = True

    def _create_report_header(self) -> str:
        """Create the initial report file header."""
        return f"""# Refactor Changes Report

**Project**: {self.project_path.name}
**Created**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This file tracks all code changes made during refactoring sessions.
Each edit is logged with timestamp, file path, and change details.

---

## Session: {self._session_id}

Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""

    def on_edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        agent_name: str = "",
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Called after EVERY edit - appends to the report file.

        Args:
            file_path: Path to the edited file
            old_string: Original text that was replaced
            new_string: New text that replaced it
            agent_name: Name of the agent that made the edit
            success: Whether the edit was successful
            error: Error message if edit failed
        """
        self._ensure_initialized()
        self._edit_count += 1

        timestamp = datetime.now().strftime("%H:%M:%S")

        # Build the edit entry
        entry = self._format_edit_entry(
            edit_num=self._edit_count,
            timestamp=timestamp,
            file_path=file_path,
            old_string=old_string,
            new_string=new_string,
            agent_name=agent_name,
            success=success,
            error=error,
        )

        # Append to report file
        with open(self.report_file, "a", encoding="utf-8") as f:
            f.write(entry)

    def _format_edit_entry(
        self,
        edit_num: int,
        timestamp: str,
        file_path: str,
        old_string: str,
        new_string: str,
        agent_name: str,
        success: bool,
        error: Optional[str],
    ) -> str:
        """Format a single edit entry for the report."""
        status_icon = "✅" if success else "❌"
        agent_info = f" by `{agent_name}`" if agent_name else ""

        # Truncate strings for readability
        old_preview = self._truncate(old_string, 200)
        new_preview = self._truncate(new_string, 200)

        # Make file path relative
        try:
            rel_path = Path(file_path).relative_to(self.project_path)
        except ValueError:
            rel_path = file_path

        entry = f"""### Edit #{edit_num} {status_icon} [{timestamp}]{agent_info}

**File**: `{rel_path}`

"""

        if error:
            entry += f"**Error**: {error}\n\n"

        entry += f"""<details>
<summary>View changes</summary>

**Before**:
```
{old_preview}
```

**After**:
```
{new_preview}
```

</details>

"""
        return entry

    def _truncate(self, text: str, max_length: int = 200) -> str:
        """Truncate text for display."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "... (truncated)"

    def add_summary(self, summary: str) -> None:
        """Add a summary section to the report."""
        self._ensure_initialized()

        with open(self.report_file, "a", encoding="utf-8") as f:
            f.write(f"\n### Summary\n\n{summary}\n\n")

    def finalize(self, total_tokens: int = 0, cost_usd: float = 0.0) -> str:
        """Finalize the session and add closing stats.

        Returns:
            Path to the report file
        """
        self._ensure_initialized()

        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        closing = f"""
---

### Session Complete

- **Ended**: {end_time}
- **Total Edits**: {self._edit_count}
- **Tokens Used**: {total_tokens:,}
- **Estimated Cost**: ${cost_usd:.4f}

"""

        with open(self.report_file, "a", encoding="utf-8") as f:
            f.write(closing)

        return str(self.report_file)

    @property
    def edit_count(self) -> int:
        """Get the number of edits in this session."""
        return self._edit_count


# Global tracker instance (initialized per session)
_current_tracker: Optional[ReportTracker] = None


def get_tracker(project_path: Path) -> ReportTracker:
    """Get or create a report tracker for the project."""
    global _current_tracker

    if _current_tracker is None or _current_tracker.project_path != Path(project_path).resolve():
        _current_tracker = ReportTracker(project_path=project_path)

    return _current_tracker


def reset_tracker() -> None:
    """Reset the global tracker (for testing or new sessions)."""
    global _current_tracker
    _current_tracker = None
