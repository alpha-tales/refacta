"""Project scanning pipeline stage."""

from __future__ import annotations

from pathlib import Path

from ..sdk.client import AgentClient, AgentResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ProjectScanner:
    """Scans project and generates manifest using project-scanner agent."""

    def __init__(self, client: AgentClient) -> None:
        """Initialize scanner.

        Args:
            client: Agent client for running subagents
        """
        self.client = client

    async def scan(self) -> AgentResponse:
        """Scan the project and generate manifest.

        Returns:
            AgentResponse with scan results
        """
        logger.info("Starting project scan")

        prompt = """Scan the project and generate a structured manifest.

Tasks:
1. Use Glob to discover all source files (*.py, *.ts, *.tsx, *.js, *.jsx)
2. Classify files by language and layer (frontend/backend/shared)
3. Identify key modules, components, and services
4. Save manifest to .refactor/manifest.json

Ignore: node_modules, .git, __pycache__, .venv, dist, build, .refactor

Output a JSON manifest with:
- scan_timestamp
- summary (total_files, by_language)
- frontend (nextjs: pages, app_routes, components)
- backend (api, services, repositories)
- shared
- config_files

Be concise. Only include essential file information."""

        response = await self.client.run_agent("project-scanner", prompt)

        if response.success:
            logger.info(f"Project scan completed (tokens: {response.tokens_used})")
        else:
            logger.error(f"Project scan failed: {response.error}")

        return response
