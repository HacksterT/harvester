"""
Startup reconciliation: compare GitHub open improvement issues against the local
queue state and report drift. Never auto-applies on startup — explicit
`python -m harvester reconcile --apply` is required.
"""
import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from harvester.config import HarvesterConfig
from harvester.github_client import GitHubClient
from harvester.queue import move_to

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------

def _load_pending_index(queue_path: Path) -> dict[tuple[str, int], Path]:
    """Return {(repo_name, issue_number): path} for all pending items."""
    index: dict[tuple[str, int], Path] = {}
    pending_dir = queue_path / "pending"
    if not pending_dir.exists():
        return index
    for p in pending_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text())
            key = (data["repo_name"], int(data["issue_number"]))
            index[key] = p
        except Exception as exc:
            logger.warning("Skipping malformed queue item %s: %s", p.name, exc)
    return index


async def build_drift_report(config: HarvesterConfig) -> dict:
    """
    Compare GitHub open improvement issues against the local pending queue.

    Returns a dict with:
      - open_not_pending:  issues open on GitHub with agent-ready but not in pending/
      - pending_not_open:  items in pending/ whose GitHub issue is now closed
      - checked_at:        ISO timestamp
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("GITHUB_TOKEN not set — reconciliation skipped")
        return {"error": "GITHUB_TOKEN not set", "checked_at": datetime.now(UTC).isoformat()}

    queue_path = Path(config.settings.queue_path)
    pending_index = _load_pending_index(queue_path)

    open_not_pending: list[dict] = []
    pending_not_open: list[dict] = []

    for repo_cfg in config.repos:
        client = GitHubClient(token=token, repo_full_name=repo_cfg.github)

        # Fetch all open issues with agent-ready label
        try:
            open_issues = await client.list_issues(state="open", labels=["agent-ready"])
        except Exception as exc:
            logger.warning("Could not list issues for %s: %s", repo_cfg.github, exc)
            continue

        open_keys = {(repo_cfg.name, issue.number) for issue in open_issues}

        # Issues that are open+agent-ready on GitHub but not in pending/
        for issue in open_issues:
            key = (repo_cfg.name, issue.number)
            if key not in pending_index:
                open_not_pending.append({
                    "repo": repo_cfg.name,
                    "issue_number": issue.number,
                    "issue_title": issue.title,
                    "issue_url": issue.html_url,
                })

        # Items in pending/ for this repo whose issue is no longer open+agent-ready
        for (r, n), path in pending_index.items():
            if r != repo_cfg.name:
                continue
            if (r, n) not in open_keys:
                pending_not_open.append({
                    "repo": r,
                    "issue_number": n,
                    "item_path": str(path),
                })

    report = {
        "open_not_pending": open_not_pending,
        "pending_not_open": pending_not_open,
        "checked_at": datetime.now(UTC).isoformat(),
    }
    return report


# ---------------------------------------------------------------------------
# Drift resolution
# ---------------------------------------------------------------------------

def apply_reconciliation(report: dict, config: HarvesterConfig) -> dict[str, int]:
    """
    Apply the drift report: move items that are pending but whose issue is
    closed into rejected/. Does not auto-enqueue open_not_pending items —
    that is a human decision (re-apply the label to re-enqueue).

    Returns counts of actions taken.
    """
    queue_path = Path(config.settings.queue_path)
    moved = 0

    for item in report.get("pending_not_open", []):
        item_path = item.get("item_path")
        if item_path and Path(item_path).exists():
            move_to(item_path, "rejected", queue_path)
            logger.info(
                "Reconcile: moved %s#%s to rejected/ (issue no longer open+agent-ready)",
                item["repo"], item["issue_number"],
            )
            moved += 1

    return {"moved_to_rejected": moved}


# ---------------------------------------------------------------------------
# Startup background task
# ---------------------------------------------------------------------------

async def reconcile_on_startup(config: HarvesterConfig) -> None:
    """Run drift detection at startup; log results but do not auto-apply."""
    from harvester.notifier import send as notify

    logger.info("Running startup reconciliation...")
    try:
        report = await build_drift_report(config)
    except Exception as exc:
        logger.error("Reconciliation failed: %s", exc)
        return

    if "error" in report:
        logger.warning("Reconciliation skipped: %s", report["error"])
        return

    open_not_pending = report["open_not_pending"]
    pending_not_open = report["pending_not_open"]

    if not open_not_pending and not pending_not_open:
        logger.info("Reconciliation: queue is in sync with GitHub")
        return

    msg_parts = ["*Harvester queue drift detected*"]
    if open_not_pending:
        msg_parts.append(
            f"{len(open_not_pending)} issue(s) open+agent-ready on GitHub but not in pending/"
        )
        for item in open_not_pending[:5]:
            msg_parts.append(f"  • #{item['issue_number']} {item['issue_title']} ({item['repo']})")
    if pending_not_open:
        msg_parts.append(
            f"{len(pending_not_open)} item(s) in pending/ whose GitHub issue is no longer open"
        )
        for item in pending_not_open[:5]:
            msg_parts.append(f"  • #{item['issue_number']} ({item['repo']})")
    msg_parts.append("Run `python -m harvester reconcile --apply` to resolve.")

    message = "\n".join(msg_parts)
    logger.warning(message)
    await notify(message)
