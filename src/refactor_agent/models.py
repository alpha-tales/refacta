"""Shared data models for the refactor agent.

This module contains dataclasses and types that are shared across multiple
modules to avoid circular import issues.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class EditOperation:
    """Represents a single file edit operation."""

    file_path: str
    old_string: str
    new_string: str
    success: bool = True
    error: Optional[str] = None
