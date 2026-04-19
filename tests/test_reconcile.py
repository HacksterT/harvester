"""
Tests for reconcile.py drift detection and resolution.
"""
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harvester.queue import init_queue
from harvester.reconcile import apply_reconciliation, build_drift_report


def _tmp_queue() -> Path:
    d = Path(tempfile.mkdtemp())
    init_queue(d)
    return d


def _mock_config(queue_path: Path, repos=None):
    cfg = MagicMock()
    cfg.settings.queue_path = str(queue_path)
    cfg.repos = repos or []
    return cfg


def _mock_repo_cfg(name="ezra-assistant", github="hackstert/ezra-assistant"):
    r = MagicMock()
    r.name = name
    r.github = github
    return r


def _mock_issue(number: int, title="Test issue", html_url=None):
    issue = MagicMock()
    issue.number = number
    issue.title = title
    issue.html_url = html_url or f"https://github.com/hackstert/ezra-assistant/issues/{number}"
    return issue


def _seed_pending(q: Path, repo_name: str, issue_number: int) -> Path:
    data = {
        "repo_name": repo_name,
        "github_repo": f"hackstert/{repo_name}",
        "local_path": "/tmp/repo",
        "issue_number": issue_number,
        "issue_title": "Test",
        "issue_url": f"https://github.com/hackstert/{repo_name}/issues/{issue_number}",
        "scanner": "skill_gaps",
        "priority": "should-have",
        "branch_prefix": "improvement/",
        "guarded_paths": [],
        "touches_guarded_paths": False,
        "queued_at": datetime.now(UTC).isoformat(),
    }
    dest = q / "pending" / f"{repo_name}-{issue_number}.json"
    dest.write_text(json.dumps(data))
    return dest


# ---------------------------------------------------------------------------
# build_drift_report
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_drift_when_in_sync() -> None:
    q = _tmp_queue()
    repo = _mock_repo_cfg()
    cfg = _mock_config(q, repos=[repo])

    # Seed one pending item that matches one open GitHub issue
    _seed_pending(q, "ezra-assistant", 42)
    open_issue = _mock_issue(42)

    mock_client = AsyncMock()
    mock_client.list_issues.return_value = [open_issue]

    with (
        patch("os.environ.get", return_value="fake-token"),
        patch("harvester.reconcile.GitHubClient", return_value=mock_client),
    ):
        report = await build_drift_report(cfg)

    assert report["open_not_pending"] == []
    assert report["pending_not_open"] == []


@pytest.mark.asyncio
async def test_detects_open_not_pending() -> None:
    q = _tmp_queue()
    repo = _mock_repo_cfg()
    cfg = _mock_config(q, repos=[repo])
    # No pending items seeded
    open_issue = _mock_issue(99)

    mock_client = AsyncMock()
    mock_client.list_issues.return_value = [open_issue]

    with (
        patch("os.environ.get", return_value="fake-token"),
        patch("harvester.reconcile.GitHubClient", return_value=mock_client),
    ):
        report = await build_drift_report(cfg)

    assert len(report["open_not_pending"]) == 1
    assert report["open_not_pending"][0]["issue_number"] == 99


@pytest.mark.asyncio
async def test_detects_pending_not_open() -> None:
    q = _tmp_queue()
    repo = _mock_repo_cfg()
    cfg = _mock_config(q, repos=[repo])

    # Seed item in pending but GitHub returns no open issues
    _seed_pending(q, "ezra-assistant", 42)

    mock_client = AsyncMock()
    mock_client.list_issues.return_value = []

    with (
        patch("os.environ.get", return_value="fake-token"),
        patch("harvester.reconcile.GitHubClient", return_value=mock_client),
    ):
        report = await build_drift_report(cfg)

    assert len(report["pending_not_open"]) == 1
    assert report["pending_not_open"][0]["issue_number"] == 42


@pytest.mark.asyncio
async def test_missing_github_token_returns_error() -> None:
    q = _tmp_queue()
    cfg = _mock_config(q)

    with patch("os.environ.get", return_value=""):
        report = await build_drift_report(cfg)

    assert "error" in report


# ---------------------------------------------------------------------------
# apply_reconciliation
# ---------------------------------------------------------------------------

def test_apply_moves_pending_not_open_to_rejected() -> None:
    q = _tmp_queue()
    cfg = _mock_config(q)
    item_path = _seed_pending(q, "ezra-assistant", 42)

    report = {
        "open_not_pending": [],
        "pending_not_open": [
            {"repo": "ezra-assistant", "issue_number": 42, "item_path": str(item_path)},
        ],
    }

    counts = apply_reconciliation(report, cfg)

    assert counts["moved_to_rejected"] == 1
    assert not item_path.exists()
    assert (q / "rejected" / "ezra-assistant-42.json").exists()


def test_apply_is_idempotent() -> None:
    q = _tmp_queue()
    cfg = _mock_config(q)
    item_path = _seed_pending(q, "ezra-assistant", 42)

    report = {
        "open_not_pending": [],
        "pending_not_open": [
            {"repo": "ezra-assistant", "issue_number": 42, "item_path": str(item_path)},
        ],
    }

    apply_reconciliation(report, cfg)
    # Second apply — item_path no longer exists, should not crash
    counts = apply_reconciliation(report, cfg)
    assert counts["moved_to_rejected"] == 0


def test_apply_empty_report_is_noop() -> None:
    q = _tmp_queue()
    cfg = _mock_config(q)
    report = {"open_not_pending": [], "pending_not_open": []}
    counts = apply_reconciliation(report, cfg)
    assert counts["moved_to_rejected"] == 0
