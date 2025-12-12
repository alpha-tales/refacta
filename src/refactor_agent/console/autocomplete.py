"""File and folder autocomplete for the interactive console.

Provides @ triggered autocomplete for files and folders in the project.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


# Directories to ignore during autocomplete
IGNORED_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".env",
    "dist",
    "build",
    ".refactor",
    ".claude",
    ".idea",
    ".vscode",
    "egg-info",
}

# File extensions to show
CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".cpp", ".c",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".r",
    ".sql", ".sh", ".bash", ".ps1", ".bat",
    ".html", ".css", ".scss", ".sass", ".less",
    ".json", ".yaml", ".yml", ".toml", ".xml", ".md",
}


class FileCompleter(Completer):
    """Autocomplete for files and folders triggered by @ symbol."""

    def __init__(
        self,
        root_path: str | Path,
        *,
        show_hidden: bool = False,
        max_suggestions: int = 20,
    ) -> None:
        """Initialize the file completer.

        Args:
            root_path: Root directory for file discovery
            show_hidden: Whether to show hidden files/folders
            max_suggestions: Maximum number of suggestions to show
        """
        self.root_path = Path(root_path).resolve()
        self.show_hidden = show_hidden
        self.max_suggestions = max_suggestions
        self._file_cache: list[Path] = []
        self._cache_valid = False

    def _should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        name = path.name

        # Check if in ignored directories
        if name in IGNORED_DIRS:
            return True

        # Check hidden files/folders
        if not self.show_hidden and name.startswith("."):
            return True

        return False

    def _scan_directory(self, directory: Path, depth: int = 0, max_depth: int = 4) -> Iterable[Path]:
        """Recursively scan directory for files and folders."""
        if depth > max_depth:
            return

        try:
            for item in directory.iterdir():
                if self._should_ignore(item):
                    continue

                yield item

                if item.is_dir():
                    yield from self._scan_directory(item, depth + 1, max_depth)
        except PermissionError:
            pass

    def refresh_cache(self) -> None:
        """Refresh the file cache."""
        self._file_cache = list(self._scan_directory(self.root_path))
        self._cache_valid = True

    def get_completions(
        self,
        document: Document,
        complete_event,
    ) -> Iterable[Completion]:
        """Get completions for the current document.

        Triggered when @ is typed.
        """
        text = document.text_before_cursor

        # Find @ trigger
        at_pos = text.rfind("@")
        if at_pos == -1:
            return

        # Get the partial path after @
        partial = text[at_pos + 1:]

        # Refresh cache if needed
        if not self._cache_valid:
            self.refresh_cache()

        # Score and filter matches
        matches: list[tuple[int, Path]] = []

        for path in self._file_cache:
            try:
                rel_path = path.relative_to(self.root_path)
                rel_str = str(rel_path).replace("\\", "/")

                # Calculate match score
                score = self._calculate_score(rel_str, partial)
                if score > 0:
                    matches.append((score, path))
            except ValueError:
                continue

        # Sort by score (descending) and take top matches
        matches.sort(key=lambda x: (-x[0], str(x[1])))
        top_matches = matches[:self.max_suggestions]

        # Generate completions
        for score, path in top_matches:
            rel_path = path.relative_to(self.root_path)
            rel_str = str(rel_path).replace("\\", "/")

            # Add trailing slash for directories
            display = rel_str + "/" if path.is_dir() else rel_str

            # Determine file type for display
            file_type = self._get_file_type(path)

            yield Completion(
                text=rel_str,
                start_position=-len(partial),
                display=display,
                display_meta=file_type,
            )

    def _calculate_score(self, path: str, query: str) -> int:
        """Calculate match score for a path against a query."""
        if not query:
            return 1

        path_lower = path.lower()
        query_lower = query.lower()

        # Exact match
        if path_lower == query_lower:
            return 100

        # Starts with query
        if path_lower.startswith(query_lower):
            return 80

        # Filename starts with query
        filename = path.split("/")[-1].lower()
        if filename.startswith(query_lower):
            return 70

        # Contains query
        if query_lower in path_lower:
            return 50

        # Fuzzy match (all characters present in order)
        if self._fuzzy_match(path_lower, query_lower):
            return 30

        return 0

    def _fuzzy_match(self, text: str, query: str) -> bool:
        """Check if all query characters appear in order in text."""
        query_idx = 0
        for char in text:
            if query_idx < len(query) and char == query[query_idx]:
                query_idx += 1
        return query_idx == len(query)

    def _get_file_type(self, path: Path) -> str:
        """Get display file type for a path."""
        if path.is_dir():
            return "folder"

        ext = path.suffix.lower()
        type_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".jsx": "React JSX",
            ".ts": "TypeScript",
            ".tsx": "React TSX",
            ".java": "Java",
            ".cs": "C#",
            ".cpp": "C++",
            ".c": "C",
            ".go": "Go",
            ".rs": "Rust",
            ".rb": "Ruby",
            ".php": "PHP",
            ".swift": "Swift",
            ".kt": "Kotlin",
            ".json": "JSON",
            ".yaml": "YAML",
            ".yml": "YAML",
            ".md": "Markdown",
            ".html": "HTML",
            ".css": "CSS",
            ".sql": "SQL",
        }
        return type_map.get(ext, ext[1:].upper() if ext else "file")
