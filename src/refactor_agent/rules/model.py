"""Data models for refactoring rules and plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RefactorPass:
    """A single pass in the refactoring plan."""

    name: str
    order: int
    targets: list[str] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "order": self.order,
            "targets": self.targets,
            "operations": self.operations,
            "checks": self.checks,
        }


@dataclass
class RefactorPlan:
    """Complete refactoring plan with multiple passes."""

    version: str = "1.0"
    source_rules: str = ""
    passes: list[RefactorPass] = field(default_factory=list)
    pre_checks: list[str] = field(default_factory=list)
    post_checks: list[str] = field(default_factory=list)
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Set creation timestamp if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "plan_version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "source_rules": self.source_rules,
            "passes": [p.to_dict() for p in self.passes],
            "validation": {
                "pre_checks": self.pre_checks,
                "post_checks": self.post_checks,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> RefactorPlan:
        """Create a RefactorPlan from a dictionary."""
        passes = [
            RefactorPass(
                name=p["name"],
                order=p.get("order", i),
                targets=p.get("targets", []),
                operations=p.get("operations", []),
                checks=p.get("checks", []),
            )
            for i, p in enumerate(data.get("passes", []))
        ]

        validation = data.get("validation", {})

        return cls(
            version=data.get("plan_version", "1.0"),
            source_rules=data.get("source_rules", ""),
            passes=passes,
            pre_checks=validation.get("pre_checks", []),
            post_checks=validation.get("post_checks", []),
        )

    def get_frontend_passes(self) -> list[RefactorPass]:
        """Get passes targeting frontend files."""
        return [
            p for p in self.passes
            if any(
                t for t in p.targets
                if "frontend" in t or ".tsx" in t or ".jsx" in t or ".ts" in t or ".js" in t
            )
        ]

    def get_backend_passes(self) -> list[RefactorPass]:
        """Get passes targeting backend files."""
        return [
            p for p in self.passes
            if any(
                t for t in p.targets
                if "backend" in t or ".py" in t
            )
        ]
