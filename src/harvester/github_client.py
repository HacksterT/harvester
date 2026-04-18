import asyncio
import logging

from github import Auth, Github, GithubException
from github.Issue import Issue
from github.Repository import Repository

logger = logging.getLogger(__name__)

MAX_RETRIES = 4

# ---------------------------------------------------------------------------
# Label taxonomy
# ---------------------------------------------------------------------------

LABEL_TAXONOMY: list[dict[str, str]] = [
    # Base
    {"name": "improvement",            "color": "0075ca", "description": "Harvester-generated improvement candidate"},
    # Priority
    {"name": "priority:must-have",     "color": "d73a4a", "description": ""},
    {"name": "priority:should-have",   "color": "e4e669", "description": ""},
    {"name": "priority:nice-to-have",  "color": "cfd3d7", "description": ""},
    # Status
    {"name": "status:triage",          "color": "f9d0c4", "description": "Needs human review before queuing"},
    {"name": "status:blocked",         "color": "b60205", "description": "Blocked — see issue comment"},
    {"name": "agent-ready",            "color": "0e8a16", "description": "Approved for overnight agent run"},
    # Scanners
    {"name": "scanner:skill_gaps",          "color": "bfd4f2", "description": ""},
    {"name": "scanner:memory",              "color": "bfd4f2", "description": ""},
    {"name": "scanner:tokens",              "color": "bfd4f2", "description": ""},
    {"name": "scanner:code_health",         "color": "bfd4f2", "description": ""},
    {"name": "scanner:theology_review",     "color": "bfd4f2", "description": ""},
    {"name": "scanner:cross_repo_patterns", "color": "bfd4f2", "description": ""},
    # Domains
    {"name": "domain:skill-gaps",   "color": "e8d5c4", "description": ""},
    {"name": "domain:memory",       "color": "e8d5c4", "description": ""},
    {"name": "domain:tokens",       "color": "e8d5c4", "description": ""},
    {"name": "domain:code-health",  "color": "e8d5c4", "description": ""},
    {"name": "domain:theology",     "color": "e8d5c4", "description": ""},
    {"name": "domain:patterns",     "color": "e8d5c4", "description": ""},
    # Special
    {"name": "theological-review-required", "color": "7057ff",
     "description": "Requires Troy's manual theological review"},
]


class GitHubClient:
    def __init__(self, token: str, repo_full_name: str) -> None:
        self._gh = Github(auth=Auth.Token(token))
        self._repo_name = repo_full_name
        self._gh_repo: Repository | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_repo(self) -> Repository:
        if self._gh_repo is None:
            self._gh_repo = await self._call(self._gh.get_repo, self._repo_name)
        return self._gh_repo

    async def _call(self, fn, *args, **kwargs):
        for attempt in range(MAX_RETRIES):
            try:
                return await asyncio.to_thread(fn, *args, **kwargs)
            except GithubException as exc:
                if exc.status == 429:
                    wait = 2 ** attempt
                    logger.warning(
                        "GitHub rate limit hit, backing off %ds (attempt %d/%d)",
                        wait, attempt + 1, MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                else:
                    raise
        fn_name = getattr(fn, "__name__", repr(fn))
        raise RuntimeError(f"GitHub rate limit exceeded after {MAX_RETRIES} retries on {fn_name}")

    # ------------------------------------------------------------------
    # Issue operations
    # ------------------------------------------------------------------

    async def create_issue(self, title: str, body: str, labels: list[str]) -> str:
        repo = await self._get_repo()
        issue: Issue = await self._call(repo.create_issue, title=title, body=body, labels=labels)
        logger.info("Created issue #%d: %s", issue.number, issue.html_url)
        return issue.html_url

    async def get_issue(self, number: int) -> Issue:
        repo = await self._get_repo()
        return await self._call(repo.get_issue, number)

    async def list_issues(self, state: str = "open", labels: list[str] | None = None) -> list[Issue]:
        repo = await self._get_repo()
        kwargs: dict = {"state": state}
        if labels:
            kwargs["labels"] = labels
        paginated = await self._call(repo.get_issues, **kwargs)
        return list(paginated)

    async def close_issue(self, number: int) -> None:
        issue = await self.get_issue(number)
        await self._call(issue.edit, state="closed")
        logger.info("Closed issue #%d", number)

    async def comment_on_issue(self, number: int, body: str) -> None:
        issue = await self.get_issue(number)
        await self._call(issue.create_comment, body)
        logger.debug("Commented on issue #%d", number)

    async def apply_labels(self, number: int, labels: list[str]) -> None:
        issue = await self.get_issue(number)
        await self._call(issue.set_labels, *labels)
        logger.debug("Applied labels %s to issue #%d", labels, number)

    # ------------------------------------------------------------------
    # Label management
    # ------------------------------------------------------------------

    async def ensure_labels_exist(self) -> None:
        repo = await self._get_repo()
        existing_labels = await self._call(repo.get_labels)
        existing = {lbl.name for lbl in existing_labels}

        for spec in LABEL_TAXONOMY:
            if spec["name"] in existing:
                continue
            try:
                await self._call(
                    repo.create_label,
                    name=spec["name"],
                    color=spec["color"],
                    description=spec.get("description", ""),
                )
                logger.info("Created label: %s", spec["name"])
            except GithubException as exc:
                if exc.status == 422:
                    # Created between our read and write — treat as success.
                    logger.debug("Label already exists (race): %s", spec["name"])
                else:
                    raise
