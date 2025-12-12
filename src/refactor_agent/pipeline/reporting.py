"""Report generation pipeline stage."""

from __future__ import annotations

from ..sdk.client import AgentClient, AgentResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ReportGenerator:
    """Generates summary reports from refactoring results."""

    def __init__(self, client: AgentClient) -> None:
        """Initialize report generator.

        Args:
            client: Agent client for running subagents
        """
        self.client = client

    async def generate(self) -> AgentResponse:
        """Generate final summary report.

        Returns:
            AgentResponse with report content
        """
        logger.info("Generating summary report")

        prompt = """Generate a refactoring summary report.

Read from .refactor/:
- manifest.json
- refactor_plan.json
- logs/*
- compliance_report.json
- build_report.json

Generate:
1. .refactor/summary.md (human-readable)

Report structure:
# Refactor Summary
- Date, Status (SUCCESS/PARTIAL/FAILED)
## Overview
- Files scanned, modified, passes completed
## Changes by Category
- Counts per operation type
## Compliance
- Status, warnings count
## Build Results
- Frontend/backend status
## Recommendations
- Actionable next steps

Keep under 200 lines. Be concise and actionable."""

        response = await self.client.run_agent("summary-reporter", prompt)

        if response.success:
            logger.info(f"Report generated (tokens: {response.tokens_used})")
        else:
            logger.error(f"Report generation failed: {response.error}")

        return response
