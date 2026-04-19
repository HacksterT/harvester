import logging

from anthropic import AsyncAnthropic, beta_async_tool

from harvester.config import RepoConfig
from harvester.models import Finding, ScanContext
from harvester.tools import build_tools

logger = logging.getLogger(__name__)


async def run_scanner(
    scanner_module: object,
    repo_config: RepoConfig,
    context: ScanContext,
) -> Finding | None:
    """Drive the Claude tool-calling loop for a single scanner.

    Returns a Finding when Claude calls report_finding, or None on end_turn.
    """
    found: list[Finding] = []

    async def report_finding(
        title: str,
        summary: str,
        evidence: str,
        criteria: list[str],
        domain: str,
        priority: str,
        scanner: str,
        repo: str,
        touches_guarded_paths: bool = False,
    ) -> str:
        """Report a finding. This is the only structured output path. Call this exactly once when you have identified the single most actionable improvement."""
        found.append(
            Finding(
                title=title,
                summary=summary,
                evidence=evidence,
                criteria=criteria,
                domain=domain,
                priority=priority,
                scanner=scanner,
                repo=repo,
                touches_guarded_paths=touches_guarded_paths,
            )
        )
        return "Finding recorded. Scan complete."

    rf_tool = beta_async_tool(report_finding)

    client = AsyncAnthropic()
    tools = build_tools(scanner_module.ENABLED_TOOLS, repo_config.local_path) + [rf_tool]

    system_with_cache = [
        {
            "type": "text",
            "text": scanner_module.SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    logger.info(
        "Starting scanner %s on %s (run_id=%s)",
        scanner_module.__name__ if hasattr(scanner_module, "__name__") else type(scanner_module).__name__,
        repo_config.name,
        context.run_id,
    )

    runner = client.beta.messages.tool_runner(
        model="claude-sonnet-4-6",
        system=system_with_cache,
        tools=tools,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Scan {repo_config.name} at {repo_config.local_path}. "
                    "Explore the repository, identify the single most actionable improvement, "
                    "and call report_finding with your conclusion."
                ),
            }
        ],
        max_tokens=4096,
    )

    await runner.until_done()

    if found:
        logger.info("Scanner produced finding: %s", found[0].title)
    else:
        logger.info("Scanner returned no finding (end_turn)")

    return found[0] if found else None
