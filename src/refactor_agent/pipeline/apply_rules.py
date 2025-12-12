"""Rule application pipeline stage."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..rules.model import RefactorPass, RefactorPlan
from ..sdk.client import AgentClient, AgentResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RuleApplier:
    """Applies refactoring rules using appropriate agents."""

    def __init__(self, client: AgentClient) -> None:
        """Initialize rule applier.

        Args:
            client: Agent client for running subagents
        """
        self.client = client

    async def interpret_rules(self, rules_path: Path) -> AgentResponse:
        """Convert rules file to structured plan.

        Args:
            rules_path: Path to the rules file

        Returns:
            AgentResponse from rules-interpreter
        """
        logger.info(f"Interpreting rules from: {rules_path}")

        prompt = f"""Read the refactor rules at '{rules_path}' and create a structured plan.

Tasks:
1. Parse the rules file
2. Create a multi-pass refactoring plan
3. Define targets (glob patterns) for each pass
4. Specify allowed operations per pass
5. Save plan to .refactor/refactor_plan.json

Output JSON with:
- plan_version
- source_rules
- passes (name, order, targets, operations, checks)
- validation (pre_checks, post_checks)

Standard passes:
1. structural-cleanup: remove dead code, normalize imports
2. local-refactors: extract helpers, improve naming
3. cross-file-consistency: align patterns

Be concise. Focus on actionable operations."""

        response = await self.client.run_agent("rules-interpreter", prompt)

        if response.success:
            logger.info(f"Rules interpreted (tokens: {response.tokens_used})")
        else:
            logger.error(f"Rules interpretation failed: {response.error}")

        return response

    async def apply_pass(
        self,
        pass_info: RefactorPass,
        target_type: str = "all",
        *,
        dry_run: bool = False,
    ) -> AgentResponse:
        """Apply a single refactoring pass.

        Args:
            pass_info: Pass definition
            target_type: 'frontend', 'backend', or 'all'
            dry_run: If True, don't modify files

        Returns:
            AgentResponse from the refactorer agent
        """
        logger.info(f"Applying pass: {pass_info.name} (target: {target_type})")

        # Determine which agent to use
        agent_name = self._select_agent(pass_info, target_type)

        # Build concise prompt
        prompt = self._build_apply_prompt(pass_info, dry_run)

        response = await self.client.run_agent(agent_name, prompt)

        if response.success:
            logger.info(f"Pass '{pass_info.name}' completed (tokens: {response.tokens_used})")
        else:
            logger.error(f"Pass '{pass_info.name}' failed: {response.error}")

        return response

    def _select_agent(self, pass_info: RefactorPass, target_type: str) -> str:
        """Select appropriate agent for the pass."""
        if target_type == "frontend":
            return "nextjs-refactorer"
        elif target_type == "backend":
            return "python-refactorer"

        # Infer from targets
        targets = " ".join(pass_info.targets).lower()
        if ".py" in targets or "backend" in targets:
            return "python-refactorer"
        return "nextjs-refactorer"

    def _build_apply_prompt(self, pass_info: RefactorPass, dry_run: bool) -> str:
        """Build concise prompt for refactoring pass."""
        mode = "PLAN ONLY (dry run)" if dry_run else "APPLY CHANGES"

        return f"""Execute refactoring pass: {pass_info.name}
Mode: {mode}

Targets: {', '.join(pass_info.targets)}
Operations: {', '.join(pass_info.operations)}

Tasks:
1. Read .refactor/manifest.json for file list
2. For each matching file:
   - Read content
   - Apply allowed operations only
   - {'Log planned changes' if dry_run else 'Edit file'}
3. Log changes to .refactor/logs/

Keep changes minimal and focused. Document each change briefly."""
