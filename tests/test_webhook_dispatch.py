"""
Tests for webhook event dispatch logic — handler behavior independent of
HTTP signature verification (that lives in test_webhook.py).
"""
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harvester.models import QueueItem
from harvester.queue import init_queue
from harvester.webhook import _dispatch


def _tmp_queue() -> Path:
    d = Path(tempfile.mkdtemp())
    init_queue(d)
    return d


def _repo_cfg(name="ezra-assistant", github="hackstert/ezra-assistant"):
    cfg = MagicMock()
    cfg.name = name
    cfg.github = github
    cfg.local_path = "/tmp/ezra"
    cfg.branch_prefix = "improvement/"
    cfg.guarded_paths = ["theology/**"]
    cfg.guarded_path_policy = "never_execute"
    return cfg


def _mock_config(queue_path: Path, repo_cfg=None):
    cfg = MagicMock()
    cfg.settings.queue_path = str(queue_path)
    cfg.settings.findings_log_path = str(queue_path / "findings")
    cfg.repos = [repo_cfg or _repo_cfg()]
    return cfg


def _agent_ready_payload(issue_number=42, repo="hackstert/ezra-assistant"):
    return {
        "action": "labeled",
        "label": {"name": "agent-ready"},
        "issue": {
            "number": issue_number,
            "title": "Fix memory leak in skill handler",
            "html_url": f"https://github.com/{repo}/issues/{issue_number}",
            "labels": [
                {"name": "improvement"},
                {"name": "agent-ready"},
                {"name": "scanner:skill_gaps"},
                {"name": "priority:should-have"},
                {"name": "domain:skill-gaps"},
            ],
        },
        "repository": {"full_name": repo},
    }


# ---------------------------------------------------------------------------
# issues.labeled — agent-ready → enqueue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_ready_label_enqueues_item(tmp_path) -> None:
    q = _tmp_queue()
    cfg = _mock_config(q)

    with patch("harvester.main._config", cfg):
        await _dispatch("issues", "labeled", _agent_ready_payload(issue_number=42))

    pending = list((q / "pending").glob("*.json"))
    assert len(pending) == 1
    assert pending[0].name == "ezra-assistant-42.json"

    data = json.loads(pending[0].read_text())
    assert data["issue_number"] == 42
    assert data["scanner"] == "skill_gaps"
    assert data["priority"] == "should-have"
    assert data["github_repo"] == "hackstert/ezra-assistant"


@pytest.mark.asyncio
async def test_non_agent_ready_label_ignored(tmp_path) -> None:
    q = _tmp_queue()
    cfg = _mock_config(q)

    payload = _agent_ready_payload()
    payload["label"]["name"] = "status:triage"  # not agent-ready

    with patch("harvester.main._config", cfg):
        await _dispatch("issues", "labeled", payload)

    pending = list((q / "pending").glob("*.json"))
    assert len(pending) == 0


@pytest.mark.asyncio
async def test_unconfigured_repo_ignored(tmp_path) -> None:
    q = _tmp_queue()
    cfg = _mock_config(q)  # only has ezra-assistant

    payload = _agent_ready_payload(repo="hackstert/some-other-repo")

    with patch("harvester.main._config", cfg):
        await _dispatch("issues", "labeled", payload)

    pending = list((q / "pending").glob("*.json"))
    assert len(pending) == 0


# ---------------------------------------------------------------------------
# issues.closed — completed vs rejected
# ---------------------------------------------------------------------------

def _seed_pending(q: Path, issue_number: int = 42) -> Path:
    item = QueueItem(
        repo_name="ezra-assistant",
        github_repo="hackstert/ezra-assistant",
        local_path="/tmp/ezra",
        issue_number=issue_number,
        issue_title="Test issue",
        issue_url=f"https://github.com/hackstert/ezra-assistant/issues/{issue_number}",
        scanner="skill_gaps",
        priority="should-have",
        branch_prefix="improvement/",
        guarded_paths=[],
        touches_guarded_paths=False,
        queued_at=datetime.now(UTC),
    )
    dest = q / "pending" / f"ezra-assistant-{issue_number}.json"
    dest.write_text(json.dumps(item.to_dict()))
    return dest


def _closed_payload(issue_number=42, state_reason="completed"):
    return {
        "action": "closed",
        "issue": {
            "number": issue_number,
            "state_reason": state_reason,
        },
        "repository": {"full_name": "hackstert/ezra-assistant"},
    }


@pytest.mark.asyncio
async def test_issue_closed_completed_moves_to_completed() -> None:
    q = _tmp_queue()
    cfg = _mock_config(q)
    _seed_pending(q, 42)

    with patch("harvester.main._config", cfg):
        await _dispatch("issues", "closed", _closed_payload(42, "completed"))

    assert not (q / "pending" / "ezra-assistant-42.json").exists()
    assert (q / "completed" / "ezra-assistant-42.json").exists()


@pytest.mark.asyncio
async def test_issue_closed_not_planned_moves_to_rejected() -> None:
    q = _tmp_queue()
    cfg = _mock_config(q)
    _seed_pending(q, 42)

    with patch("harvester.main._config", cfg):
        await _dispatch("issues", "closed", _closed_payload(42, "not_planned"))

    assert not (q / "pending" / "ezra-assistant-42.json").exists()
    assert (q / "rejected" / "ezra-assistant-42.json").exists()


@pytest.mark.asyncio
async def test_issue_closed_no_queue_item_is_noop() -> None:
    q = _tmp_queue()
    cfg = _mock_config(q)
    # No pending item seeded

    with patch("harvester.main._config", cfg):
        await _dispatch("issues", "closed", _closed_payload(99, "completed"))

    assert list((q / "completed").glob("*.json")) == []


# ---------------------------------------------------------------------------
# pull_request events — logged to findings JSONL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pr_opened_logs_to_findings() -> None:
    q = _tmp_queue()
    cfg = _mock_config(q)
    findings_dir = q / "findings"

    payload = {
        "action": "opened",
        "pull_request": {
            "number": 7,
            "html_url": "https://github.com/hackstert/ezra-assistant/pull/7",
            "title": "Closes #42: Fix skill gap",
        },
        "repository": {"full_name": "hackstert/ezra-assistant"},
    }

    with patch("harvester.main._config", cfg):
        await _dispatch("pull_request", "opened", payload)

    jsonl_files = list(findings_dir.glob("*.jsonl"))
    assert len(jsonl_files) == 1
    records = [json.loads(l) for l in jsonl_files[0].read_text().splitlines()]
    assert any(r["event"] == "pr_opened" and r["pr_number"] == 7 for r in records)


@pytest.mark.asyncio
async def test_pr_closed_merged_logs_correct_event() -> None:
    q = _tmp_queue()
    cfg = _mock_config(q)
    findings_dir = q / "findings"

    payload = {
        "action": "closed",
        "pull_request": {
            "number": 7,
            "html_url": "https://github.com/hackstert/ezra-assistant/pull/7",
            "merged": True,
        },
        "repository": {"full_name": "hackstert/ezra-assistant"},
    }

    with patch("harvester.main._config", cfg):
        await _dispatch("pull_request", "closed", payload)

    jsonl_files = list(findings_dir.glob("*.jsonl"))
    records = [json.loads(l) for l in jsonl_files[0].read_text().splitlines()]
    assert any(r["event"] == "pr_merged" for r in records)


@pytest.mark.asyncio
async def test_pr_closed_without_merge_logs_correct_event() -> None:
    q = _tmp_queue()
    cfg = _mock_config(q)
    findings_dir = q / "findings"

    payload = {
        "action": "closed",
        "pull_request": {
            "number": 7,
            "html_url": "https://github.com/hackstert/ezra-assistant/pull/7",
            "merged": False,
        },
        "repository": {"full_name": "hackstert/ezra-assistant"},
    }

    with patch("harvester.main._config", cfg):
        await _dispatch("pull_request", "closed", payload)

    jsonl_files = list(findings_dir.glob("*.jsonl"))
    records = [json.loads(l) for l in jsonl_files[0].read_text().splitlines()]
    assert any(r["event"] == "pr_closed_without_merge" for r in records)
