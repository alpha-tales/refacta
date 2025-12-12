"""Build and test execution pipeline stage."""

from __future__ import annotations

from typing import Optional

from ..sdk.client import AgentClient, AgentResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


class BuildRunner:
    """Runs build and test commands to verify refactoring."""

    def __init__(self, client: AgentClient) -> None:
        """Initialize build runner.

        Args:
            client: Agent client for running subagents
        """
        self.client = client

    async def run(
        self,
        *,
        frontend: bool = True,
        backend: bool = True,
        commands: Optional[list[str]] = None,
    ) -> AgentResponse:
        """Run build and test commands.

        Args:
            frontend: Run frontend build commands
            backend: Run backend test commands
            commands: Custom commands to run (overrides frontend/backend)

        Returns:
            AgentResponse with build results
        """
        logger.info("Running build and tests")

        # Build command list
        if commands:
            cmd_list = commands
        else:
            cmd_list = []
            if frontend:
                cmd_list.extend([
                    "npm run lint (if package.json exists)",
                    "npm run build (if package.json exists)",
                ])
            if backend:
                cmd_list.extend([
                    "pytest (if pytest is available)",
                    "ruff check . (if ruff is available)",
                ])

        prompt = f"""Run build and test commands.

Commands to run:
{chr(10).join(f'- {cmd}' for cmd in cmd_list)}

Tasks:
1. Check which commands are available
2. Run each available command
3. Capture exit codes and output (first/last 50 lines)
4. Save report to .refactor/build_report.json

Output JSON with:
- overall_status (success/failure)
- commands (command, exit_code, status, output_summary)
- summary (total, passed, failed)

SAFETY: Refuse destructive commands (rm -rf, git push --force, etc.)
Timeout: 5 minutes per command."""

        response = await self.client.run_agent("build-runner", prompt)

        if response.success:
            logger.info(f"Build completed (tokens: {response.tokens_used})")
        else:
            logger.error(f"Build failed: {response.error}")

        return response
