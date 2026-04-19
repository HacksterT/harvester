import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from harvester.github_client import GitHubClient
from harvester.models import Finding

logger = logging.getLogger(__name__)

_DOMAIN_LABELS = {
    "skill-gaps": "domain:skill-gaps",
    "memory": "domain:memory",
    "tokens": "domain:tokens",
    "code-health": "domain:code-health",
    "theology": "domain:theology",
    "patterns": "domain:patterns",
}

_PRIORITY_LABELS = {
    "must-have": "priority:must-have",
    "should-have": "priority:should-have",
    "nice-to-have": "priority:nice-to-have",
}


def _format_issue_body(finding: Finding) -> str:
    criteria_md = "\n".join(f"- [ ] {c}" for c in finding.criteria)
    return f"""\
## Summary

{finding.summary}

## Evidence

{finding.evidence}

## Acceptance Criteria

{criteria_md}

## Tasks

- [ ] Implement the improvement described above
- [ ] Add or update tests
- [ ] Confirm acceptance criteria are met

---

| Field | Value |
|---|---|
| Repo | `{finding.repo}` |
| Scanner | `{finding.scanner}` |
| Domain | `{finding.domain}` |
| Priority | `{finding.priority}` |
| Generated | {finding.generated_at.strftime("%Y-%m-%d %H:%M UTC")} |
"""


def _build_labels(finding: Finding) -> list[str]:
    labels = ["improvement", "status:triage"]
    if p := _PRIORITY_LABELS.get(finding.priority):
        labels.append(p)
    if d := _DOMAIN_LABELS.get(finding.domain):
        labels.append(d)
    labels.append(f"scanner:{finding.scanner}")
    if finding.touches_guarded_paths:
        labels.append("theological-review-required")
    return labels


def append_findings_record(record: dict, findings_dir: Path) -> None:
    """Append one JSON record to today's findings JSONL log."""
    findings_dir.mkdir(parents=True, exist_ok=True)
    log_path = findings_dir / f"{datetime.now(UTC).strftime('%Y-%m-%d')}.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")
    logger.debug("Appended findings record to %s", log_path)


def _log_finding(finding: Finding, issue_url: str, findings_dir: Path) -> None:
    append_findings_record(
        {
            "title": finding.title,
            "summary": finding.summary,
            "scanner": finding.scanner,
            "repo": finding.repo,
            "domain": finding.domain,
            "priority": finding.priority,
            "touches_guarded_paths": finding.touches_guarded_paths,
            "generated_at": finding.generated_at.isoformat(),
            "issue_url": issue_url,
        },
        findings_dir,
    )


async def write_finding(
    finding: Finding,
    github_client: GitHubClient,
    findings_dir: str | Path = "data/findings",
) -> str:
    """Create a GitHub issue for finding and log it. Returns the issue URL."""
    title = f"[IMPROVEMENT] {finding.title}"
    body = _format_issue_body(finding)
    labels = _build_labels(finding)

    issue_url = await github_client.create_issue(title=title, body=body, labels=labels)
    logger.info("Created issue for finding %r: %s", finding.title, issue_url)

    _log_finding(finding, issue_url, Path(findings_dir))

    return issue_url
