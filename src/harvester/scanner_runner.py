from harvester.config import RepoConfig
from harvester.models import Finding, ScanContext

# Stub — fully implemented in F01-S04.
# Returns None so the scheduler skip-counter logic is exercised
# before the real Claude SDK tool-calling loop is wired in.


async def run_scanner(
    scanner_module: object,
    repo_config: RepoConfig,
    context: ScanContext,
) -> Finding | None:
    return None
