from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Finding:
    title: str
    summary: str
    evidence: str
    criteria: list[str]
    domain: str
    priority: str           # must-have | should-have | nice-to-have
    scanner: str
    repo: str
    touches_guarded_paths: bool = False
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ScanContext:
    run_id: str
    dry_run: bool = False


@dataclass
class QueueItem:
    repo_name: str          # short name, e.g. "ezra-assistant"
    github_repo: str        # full name, e.g. "HacksterT/ezra-assistant"
    local_path: str         # absolute path to local checkout
    issue_number: int
    issue_title: str
    issue_url: str
    scanner: str            # which scanner produced the finding
    priority: str           # must-have | should-have | nice-to-have
    branch_prefix: str      # e.g. "improvement/"
    guarded_paths: list[str]
    touches_guarded_paths: bool
    queued_at: datetime
    item_path: str = ""     # set after atomic write

    def to_dict(self) -> dict:
        return {
            "repo_name": self.repo_name,
            "github_repo": self.github_repo,
            "local_path": self.local_path,
            "issue_number": self.issue_number,
            "issue_title": self.issue_title,
            "issue_url": self.issue_url,
            "scanner": self.scanner,
            "priority": self.priority,
            "branch_prefix": self.branch_prefix,
            "guarded_paths": self.guarded_paths,
            "touches_guarded_paths": self.touches_guarded_paths,
            "queued_at": self.queued_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict, item_path: str = "") -> "QueueItem":
        return cls(
            repo_name=data["repo_name"],
            github_repo=data["github_repo"],
            local_path=data["local_path"],
            issue_number=data["issue_number"],
            issue_title=data["issue_title"],
            issue_url=data["issue_url"],
            scanner=data["scanner"],
            priority=data["priority"],
            branch_prefix=data["branch_prefix"],
            guarded_paths=data.get("guarded_paths", []),
            touches_guarded_paths=data.get("touches_guarded_paths", False),
            queued_at=datetime.fromisoformat(data["queued_at"]),
            item_path=item_path,
        )


@dataclass
class RunResult:
    item: QueueItem
    success: bool
    pr_url: str | None = None
    error: str | None = None
    duration_seconds: float = 0.0
