"""Compliance verification pipeline stage."""

from __future__ import annotations

from ..sdk.client import AgentClient, AgentResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ComplianceVerifier:
    """Verifies that refactoring complies with rules."""

    def __init__(self, client: AgentClient) -> None:
        """Initialize verifier.

        Args:
            client: Agent client for running subagents
        """
        self.client = client

    async def verify(self, pass_count: int = 3) -> AgentResponse:
        """Run compliance verification rounds.

        Args:
            pass_count: Number of verification rounds (1-3)

        Returns:
            AgentResponse with compliance report
        """
        logger.info(f"Running {pass_count} compliance verification rounds")

        rounds_desc = []
        if pass_count >= 1:
            rounds_desc.append("1. Coverage: Verify all targets were processed")
        if pass_count >= 2:
            rounds_desc.append("2. Side-effects: Check for unintended changes")
        if pass_count >= 3:
            rounds_desc.append("3. Sampling: Deep review of random files")

        prompt = f"""Run compliance verification.

Rounds to execute:
{chr(10).join(rounds_desc)}

Tasks:
1. Read .refactor/refactor_plan.json for expected changes
2. Read .refactor/logs/ for actual changes
3. For each round, check compliance
4. Save report to .refactor/compliance_report.json

Output JSON with:
- overall_status (pass/fail/warnings)
- rounds (name, status, findings)
- summary (files_checked, violations)

Report only violations, not passing checks. Be concise."""

        response = await self.client.run_agent("compliance-checker", prompt)

        if response.success:
            logger.info(f"Compliance check completed (tokens: {response.tokens_used})")
        else:
            logger.error(f"Compliance check failed: {response.error}")

        return response
