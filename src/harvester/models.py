from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Finding:
    title: str
    summary: str
    evidence: str
    criteria: list[str]
    domain: str
    priority: str          # must-have | should-have | nice-to-have
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
    repo_name: str
    issue_number: int
    issue_title: str
    issue_url: str
    queued_at: datetime
    item_path: str


@dataclass
class RunResult:
    item: QueueItem
    success: bool
    pr_url: str | None = None
    error: str | None = None
    duration_seconds: float = 0.0
