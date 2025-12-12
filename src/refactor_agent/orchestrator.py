"""Main orchestrator for the refactoring pipeline.

Coordinates all subagents to perform the complete refactoring workflow:
1. Project scanning
2. Rule interpretation
3. Multi-pass refactoring
4. Compliance verification
5. Build/test execution
6. Report generation

Uses official Claude Agent SDK with:
- Session management for context preservation across agents
- Proper cost tracking by message ID
- setting_sources for skills and CLAUDE.md loading
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .pipeline import (
    BuildRunner,
    ComplianceVerifier,
    ProjectScanner,
    ReportGenerator,
    RuleApplier,
)
from .rules.model import RefactorPlan
from .sdk.client import AgentClient, CostTracker, SessionManager
from .utils.file_ops import FileManager
from .utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


@dataclass
class RefactorResult:
    """Result from a complete refactoring run."""

    success: bool
    summary: str
    tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sessions: dict[str, str] = field(default_factory=dict)


@dataclass
class RefactorOrchestrator:
    """Orchestrates the complete refactoring pipeline.

    Uses official Claude Agent SDK with:
    - Session management: Each agent preserves context across calls
    - Cost tracking: Accurate token/cost tracking by message ID
    - setting_sources: Skills and CLAUDE.md automatically loaded
    """

    project_path: Path
    rules_path: Path
    model: str = "claude-haiku-4-5-20251001"
    dry_run: bool = False
    on_progress: Optional[Callable[[str, int, int], None]] = None
    on_message: Optional[Callable[[Any], None]] = None

    def __post_init__(self) -> None:
        """Initialize components."""
        self.project_path = self.project_path.resolve()
        self.rules_path = self.rules_path.resolve()

        # Initialize the SDK client with session management
        self.client = AgentClient(project_path=self.project_path, model=self.model)

        # Set message callback if provided (for real-time UI updates)
        if self.on_message:
            self.client.set_message_callback(self.on_message)

        # Initialize pipeline components
        self.file_manager = FileManager(project_path=self.project_path)
        self.scanner = ProjectScanner(self.client)
        self.rule_applier = RuleApplier(self.client)
        self.verifier = ComplianceVerifier(self.client)
        self.build_runner = BuildRunner(self.client)
        self.reporter = ReportGenerator(self.client)

        # Progress tracking
        self._current_step = 0
        self._total_steps = 6

    def _emit_progress(self, message: str) -> None:
        """Emit progress update."""
        self._current_step += 1
        if self.on_progress:
            self.on_progress(message, self._current_step, self._total_steps)
        logger.info(f"[{self._current_step}/{self._total_steps}] {message}")

    def get_cost_tracker(self) -> CostTracker:
        """Get the cost tracker for detailed usage info."""
        return self.client.get_cost_tracker()

    def get_session_manager(self) -> SessionManager:
        """Get the session manager for session info."""
        return self.client.get_session_manager()

    async def run_async(self) -> RefactorResult:
        """Run the complete refactoring pipeline asynchronously.

        Returns:
            RefactorResult with overall status including cost tracking
        """
        errors = []
        warnings = []

        # Reset tracking for fresh pipeline run
        self.client.reset_cost_tracking()

        try:
            # Setup
            setup_logging(self.project_path / "logs")
            self.file_manager.ensure_refactor_dir()

            # Step 1: Scan project
            self._emit_progress("Scanning project...")
            scan_result = await self.scanner.scan()

            if not scan_result.success:
                errors.append(f"Scan failed: {scan_result.error}")
                return self._build_result(False, "Pipeline failed at scan stage", errors, warnings)

            logger.info(f"Scan completed. Session: {scan_result.session_id}")

            # Step 2: Interpret rules
            self._emit_progress("Interpreting rules...")
            rules_result = await self.rule_applier.interpret_rules(self.rules_path)

            if not rules_result.success:
                errors.append(f"Rules interpretation failed: {rules_result.error}")
                return self._build_result(False, "Pipeline failed at rules interpretation stage", errors, warnings)

            # Load the plan
            plan_data = self.file_manager.read_json(
                self.project_path / ".refactor" / "refactor_plan.json"
            )
            if plan_data:
                plan = RefactorPlan.from_dict(plan_data)
            else:
                # Create default plan if not found
                plan = self._create_default_plan()

            # Step 3: Apply refactoring passes
            self._emit_progress("Applying refactoring passes...")
            for pass_info in plan.passes:
                # Determine target type from pass targets
                has_frontend = any(
                    ".tsx" in t or ".jsx" in t or ".ts" in t or ".js" in t or "frontend" in t
                    for t in pass_info.targets
                )
                has_backend = any(
                    ".py" in t or "backend" in t
                    for t in pass_info.targets
                )

                if has_frontend:
                    result = await self.rule_applier.apply_pass(
                        pass_info, "frontend", dry_run=self.dry_run
                    )
                    if not result.success:
                        warnings.append(f"Frontend pass '{pass_info.name}' failed: {result.error}")

                if has_backend:
                    result = await self.rule_applier.apply_pass(
                        pass_info, "backend", dry_run=self.dry_run
                    )
                    if not result.success:
                        warnings.append(f"Backend pass '{pass_info.name}' failed: {result.error}")

            # Step 4: Verify compliance
            self._emit_progress("Verifying compliance...")
            verify_result = await self.verifier.verify(pass_count=3)

            if not verify_result.success:
                warnings.append(f"Compliance check had issues: {verify_result.error}")

            # Step 5: Run build/tests
            self._emit_progress("Running build and tests...")
            build_result = await self.build_runner.run()

            if not build_result.success:
                warnings.append(f"Build/tests had issues: {build_result.error}")

            # Step 6: Generate report
            self._emit_progress("Generating report...")
            report_result = await self.reporter.generate()

            # Determine overall success
            success = len(errors) == 0

            return self._build_result(
                success,
                f"Refactoring {'completed' if success else 'completed with issues'}",
                errors,
                warnings,
            )

        except Exception as e:
            logger.exception("Pipeline failed with exception")
            errors.append(str(e))
            return self._build_result(False, f"Pipeline failed: {e}", errors, warnings)

    def _build_result(
        self,
        success: bool,
        summary: str,
        errors: list[str],
        warnings: list[str],
    ) -> RefactorResult:
        """Build RefactorResult with cost tracking and session info."""
        cost_tracker = self.get_cost_tracker()
        session_manager = self.get_session_manager()

        return RefactorResult(
            success=success,
            summary=summary,
            tokens_used=cost_tracker.total_tokens,
            input_tokens=cost_tracker.total_input_tokens,
            output_tokens=cost_tracker.total_output_tokens,
            cost_usd=cost_tracker.total_cost_usd,
            errors=errors,
            warnings=warnings,
            sessions=session_manager._sessions.copy(),
        )

    def run(self) -> RefactorResult:
        """Run the pipeline synchronously.

        Returns:
            RefactorResult with overall status
        """
        return asyncio.run(self.run_async())

    def _create_default_plan(self) -> RefactorPlan:
        """Create a default refactoring plan."""
        from .rules.model import RefactorPass

        return RefactorPlan(
            source_rules=str(self.rules_path),
            passes=[
                RefactorPass(
                    name="structural-cleanup",
                    order=1,
                    targets=["**/*.py", "**/*.ts", "**/*.tsx"],
                    operations=["remove-dead-code", "normalize-imports"],
                    checks=["lint"],
                ),
                RefactorPass(
                    name="local-refactors",
                    order=2,
                    targets=["**/*.py", "**/*.ts", "**/*.tsx"],
                    operations=["improve-naming", "add-type-hints"],
                    checks=["lint", "type-check"],
                ),
            ],
            pre_checks=["backup-exists"],
            post_checks=["build-passes"],
        )
