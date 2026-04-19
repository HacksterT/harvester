import hashlib
import hmac
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from harvester.models import QueueItem
from harvester.queue import QueueRefusedError, enqueue, move_to
from harvester.writer import append_findings_record

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_signature(body: bytes, signature: str) -> bool:
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET not set — rejecting all webhook requests")
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def github_webhook(request: Request) -> dict[str, str]:
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not signature:
        logger.warning("Webhook request missing X-Hub-Signature-256 header")
        raise HTTPException(status_code=401, detail="Missing signature")

    if not _verify_signature(body, signature):
        logger.warning("Webhook signature mismatch — request rejected")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("Webhook payload is not valid JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = request.headers.get("X-GitHub-Event", "unknown")
    action = payload.get("action", "")
    delivery_id = request.headers.get("X-GitHub-Delivery", "?")

    logger.info("Webhook received: event=%s action=%s delivery=%s", event, action, delivery_id)

    await _dispatch(event, action, payload)
    return {"status": "ok"}


async def _dispatch(event: str, action: str, payload: dict) -> None:
    key = f"{event}.{action}"
    match key:
        case "issues.labeled":
            await _on_issue_labeled(payload)
        case "issues.closed":
            await _on_issue_closed(payload)
        case "pull_request.opened":
            await _on_pr_opened(payload)
        case "pull_request.closed":
            await _on_pr_closed(payload)
        case _:
            logger.debug("No handler for %s — ignored", key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_config_for(repo_full_name: str):
    """Return the RepoConfig for a GitHub full_name, or None if not configured."""
    from harvester.main import _config
    if _config is None:
        return None
    repo_name = repo_full_name.split("/")[-1]
    for cfg in _config.repos:
        if cfg.name == repo_name or cfg.github == repo_full_name:
            return cfg
    return None


def _queue_path() -> Path:
    from harvester.main import _config
    if _config is None:
        return Path("data/queue")
    return Path(_config.settings.queue_path)


def _findings_path() -> Path:
    from harvester.main import _config
    if _config is None:
        return Path("data/findings")
    return Path(_config.settings.findings_log_path)


def _repo_name(full_name: str) -> str:
    return full_name.split("/")[-1]


def _extract_label_value(labels: list[dict], prefix: str) -> str:
    """Return the suffix of the first label matching `prefix:*`, or empty string."""
    for lbl in labels:
        name = lbl.get("name", "")
        if name.startswith(f"{prefix}:"):
            return name[len(prefix) + 1:]
    return ""


def _find_pending_item(repo_name: str, issue_number: int) -> Path | None:
    pending = _queue_path() / "pending" / f"{repo_name}-{issue_number}.json"
    return pending if pending.exists() else None


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

async def _on_issue_labeled(payload: dict) -> None:
    label_name = payload.get("label", {}).get("name", "")
    if label_name != "agent-ready":
        logger.debug("Issue labeled '%s' — not agent-ready, ignoring", label_name)
        return

    issue = payload.get("issue", {})
    issue_number = issue.get("number")
    issue_title = issue.get("title", "")
    issue_url = issue.get("html_url", "")
    repo_full_name = payload.get("repository", {}).get("full_name", "")
    repo_name = _repo_name(repo_full_name)
    issue_labels = issue.get("labels", [])

    repo_cfg = _repo_config_for(repo_full_name)
    if repo_cfg is None:
        logger.warning(
            "Received agent-ready for unconfigured repo %s — ignored", repo_full_name
        )
        return

    # Resolve scanner and priority from existing issue labels
    scanner = _extract_label_value(issue_labels, "scanner") or "unknown"
    priority = _extract_label_value(issue_labels, "priority") or "should-have"

    item = QueueItem(
        repo_name=repo_name,
        github_repo=repo_full_name,
        local_path=repo_cfg.local_path,
        issue_number=issue_number,
        issue_title=issue_title,
        issue_url=issue_url,
        scanner=scanner,
        priority=priority,
        branch_prefix=repo_cfg.branch_prefix,
        guarded_paths=repo_cfg.guarded_paths,
        touches_guarded_paths=False,  # agent runner diff check is the real gate
        queued_at=datetime.now(UTC),
    )

    try:
        path = enqueue(item, _queue_path(), repo_cfg)
        logger.info(
            "Enqueued #%s (%s) from agent-ready label → %s",
            issue_number, repo_name, path.name,
        )
    except QueueRefusedError as exc:
        logger.warning("Enqueue refused for #%s: %s", issue_number, exc)


async def _on_issue_closed(payload: dict) -> None:
    issue = payload.get("issue", {})
    issue_number = issue.get("number")
    repo_full_name = payload.get("repository", {}).get("full_name", "")
    repo_name = _repo_name(repo_full_name)

    # state_reason: "completed" = closed via merged PR; "not_planned" = manual close
    state_reason = issue.get("state_reason", "not_planned")

    item_path = _find_pending_item(repo_name, issue_number)
    if item_path is None:
        logger.debug(
            "Issue #%s closed in %s — no pending queue item, nothing to move",
            issue_number, repo_name,
        )
        return

    if state_reason == "completed":
        move_to(str(item_path), "completed", _queue_path())
        logger.info("Issue #%s completed — queue item moved to completed/", issue_number)
        append_findings_record(
            {
                "event": "issue_closed_completed",
                "repo": repo_full_name,
                "issue_number": issue_number,
                "state_reason": state_reason,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            _findings_path(),
        )
    else:
        move_to(str(item_path), "rejected", _queue_path())
        logger.info(
            "Issue #%s closed (%s) — queue item moved to rejected/",
            issue_number, state_reason,
        )
        append_findings_record(
            {
                "event": "issue_closed_rejected",
                "repo": repo_full_name,
                "issue_number": issue_number,
                "state_reason": state_reason,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            _findings_path(),
        )


async def _on_pr_opened(payload: dict) -> None:
    pr = payload.get("pull_request", {})
    pr_number = pr.get("number")
    pr_url = pr.get("html_url", "")
    pr_title = pr.get("title", "")
    repo_full_name = payload.get("repository", {}).get("full_name", "")

    logger.info("PR #%s opened in %s: %s", pr_number, repo_full_name, pr_title)
    append_findings_record(
        {
            "event": "pr_opened",
            "repo": repo_full_name,
            "pr_number": pr_number,
            "pr_url": pr_url,
            "pr_title": pr_title,
            "timestamp": datetime.now(UTC).isoformat(),
        },
        _findings_path(),
    )


async def _on_pr_closed(payload: dict) -> None:
    pr = payload.get("pull_request", {})
    pr_number = pr.get("number")
    pr_url = pr.get("html_url", "")
    merged = pr.get("merged", False)
    repo_full_name = payload.get("repository", {}).get("full_name", "")

    outcome = "merged" if merged else "closed_without_merge"
    logger.info("PR #%s %s in %s", pr_number, outcome, repo_full_name)
    append_findings_record(
        {
            "event": f"pr_{outcome}",
            "repo": repo_full_name,
            "pr_number": pr_number,
            "pr_url": pr_url,
            "timestamp": datetime.now(UTC).isoformat(),
        },
        _findings_path(),
    )
