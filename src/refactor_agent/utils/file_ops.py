"""File operations with safety features and backup support.

Provides safe file I/O with automatic backups, size limits, and
structured error handling.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class FileManager:
    """Manages file operations with safety features."""

    project_path: Path
    backup_dir: Optional[Path] = None
    max_file_size_mb: int = 10
    backup_enabled: bool = True

    def __post_init__(self) -> None:
        """Initialize backup directory."""
        if self.backup_dir is None:
            self.backup_dir = self.project_path / ".refactor" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    @property
    def max_file_size_bytes(self) -> int:
        """Maximum file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    def read_file(
        self,
        file_path: Path,
        *,
        max_lines: Optional[int] = None,
    ) -> Optional[str]:
        """Read a file with size and line limits.

        Args:
            file_path: Path to the file
            max_lines: Maximum number of lines to read (for token efficiency)

        Returns:
            File contents or None if file doesn't exist/too large
        """
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return None

        file_size = file_path.stat().st_size
        if file_size > self.max_file_size_bytes:
            logger.warning(f"File too large ({file_size} bytes): {file_path}")
            return None

        try:
            content = file_path.read_text(encoding="utf-8")

            if max_lines:
                lines = content.split("\n")
                if len(lines) > max_lines:
                    content = "\n".join(lines[:max_lines])
                    content += f"\n... (truncated, {len(lines) - max_lines} more lines)"

            return content

        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return None

    def write_file(
        self,
        file_path: Path,
        content: str,
        *,
        backup: bool = True,
    ) -> bool:
        """Write content to a file with optional backup.

        Args:
            file_path: Path to the file
            content: Content to write
            backup: Whether to create a backup first

        Returns:
            True if successful
        """
        try:
            # Create backup if file exists
            if backup and self.backup_enabled and file_path.exists():
                self.create_backup(file_path)

            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            file_path.write_text(content, encoding="utf-8")
            logger.debug(f"Wrote {len(content)} bytes to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to write {file_path}: {e}")
            return False

    def create_backup(self, file_path: Path) -> Optional[Path]:
        """Create a timestamped backup of a file.

        Args:
            file_path: Path to the file to backup

        Returns:
            Path to the backup file or None if failed
        """
        if not file_path.exists():
            return None

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            relative_path = file_path.relative_to(self.project_path)
            backup_path = self.backup_dir / f"{relative_path.stem}_{timestamp}{relative_path.suffix}"

            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, backup_path)

            logger.debug(f"Created backup: {backup_path}")
            return backup_path

        except Exception as e:
            logger.error(f"Failed to create backup for {file_path}: {e}")
            return None

    def write_json(self, file_path: Path, data: Any) -> bool:
        """Write JSON data to a file.

        Args:
            file_path: Path to the file
            data: Data to serialize as JSON

        Returns:
            True if successful
        """
        try:
            content = json.dumps(data, indent=2, ensure_ascii=False)
            return self.write_file(file_path, content, backup=False)
        except Exception as e:
            logger.error(f"Failed to write JSON to {file_path}: {e}")
            return False

    def read_json(self, file_path: Path) -> Optional[dict]:
        """Read and parse a JSON file.

        Args:
            file_path: Path to the JSON file

        Returns:
            Parsed JSON data or None if failed
        """
        content = self.read_file(file_path)
        if content is None:
            return None

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
            return None

    def ensure_refactor_dir(self) -> Path:
        """Ensure the .refactor directory exists.

        Returns:
            Path to the .refactor directory
        """
        refactor_dir = self.project_path / ".refactor"
        refactor_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (refactor_dir / "logs" / "nextjs").mkdir(parents=True, exist_ok=True)
        (refactor_dir / "logs" / "python").mkdir(parents=True, exist_ok=True)

        return refactor_dir
