import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, HTTPException, Request

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


async def _on_issue_labeled(payload: dict) -> None:
    label = payload.get("label", {}).get("name", "")
    issue_number = payload.get("issue", {}).get("number")
    repo = payload.get("repository", {}).get("full_name", "?")
    logger.info("Issue #%s labeled '%s' in %s — stub (F01-S03 wires queue enqueue)", issue_number, label, repo)


async def _on_issue_closed(payload: dict) -> None:
    issue_number = payload.get("issue", {}).get("number")
    repo = payload.get("repository", {}).get("full_name", "?")
    logger.info("Issue #%s closed in %s — stub (F01-S06 wires queue rejection)", issue_number, repo)


async def _on_pr_opened(payload: dict) -> None:
    pr_number = payload.get("pull_request", {}).get("number")
    repo = payload.get("repository", {}).get("full_name", "?")
    logger.info("PR #%s opened in %s — stub (F01-S06 wires queue completion)", pr_number, repo)


async def _on_pr_closed(payload: dict) -> None:
    pr_number = payload.get("pull_request", {}).get("number")
    merged = payload.get("pull_request", {}).get("merged", False)
    repo = payload.get("repository", {}).get("full_name", "?")
    outcome = "merged" if merged else "closed without merge"
    logger.info("PR #%s %s in %s — stub (F01-S06 wires rejection corpus)", pr_number, outcome, repo)
