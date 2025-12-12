"""Rules loader for reading and parsing refactor rule files."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class RulesLoader:
    """Loads and parses refactoring rule files."""

    def __init__(self, rules_dir: Path) -> None:
        """Initialize the rules loader.

        Args:
            rules_dir: Directory containing rule files
        """
        self.rules_dir = rules_dir

    def load_rules(self, language: Optional[str] = None) -> str:
        """Load rules for a specific language or all rules.

        Args:
            language: Language to load rules for (e.g., 'python', 'javascript')
                     If None, loads general rules.

        Returns:
            Combined rules content as a string
        """
        rules_content = []

        # Always load general rules
        general_rules = self.rules_dir / "general-rules.md"
        if general_rules.exists():
            rules_content.append(self._read_rule_file(general_rules))

        # Load language-specific rules
        if language:
            lang_rules = self.rules_dir / f"{language}-rules.md"
            if lang_rules.exists():
                rules_content.append(self._read_rule_file(lang_rules))
            else:
                logger.warning(f"No rules file found for language: {language}")

        return "\n\n---\n\n".join(rules_content)

    def _read_rule_file(self, path: Path) -> str:
        """Read a rule file with error handling.

        Args:
            path: Path to the rule file

        Returns:
            File contents
        """
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read rule file {path}: {e}")
            return ""

    def list_available_rules(self) -> list[str]:
        """List all available rule files.

        Returns:
            List of rule file names (without extension)
        """
        if not self.rules_dir.exists():
            return []

        return [
            f.stem.replace("-rules", "")
            for f in self.rules_dir.glob("*-rules.md")
        ]

    def get_rules_summary(self) -> str:
        """Get a concise summary of available rules.

        Returns:
            Summary string for token-efficient prompts
        """
        rules = self.list_available_rules()
        if not rules:
            return "No rules available"

        return f"Available rules: {', '.join(rules)}"
