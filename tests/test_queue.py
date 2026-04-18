import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from harvester.models import QueueItem
from harvester.queue import (
    QueueRefusedError,
    enqueue,
    init_queue,
    list_queue,
    load_pending,
    move_to,
)


def _tmp_queue() -> Path:
    d = Path(tempfile.mkdtemp())
    init_queue(d)
    return d


def _repo_cfg(guarded_paths: list[str] | None = None, policy: str = "never_execute"):
    cfg = MagicMock()
    cfg.guarded_paths = guarded_paths or []
    cfg.guarded_path_policy = policy
    return cfg


def _item(repo_name: str = "ezra-assistant", issue_number: int = 1, touches_guarded: bool = False) -> QueueItem:
    return QueueItem(
        repo_name=repo_name,
        github_repo=f"HacksterT/{repo_name}",
        local_path=f"~/Projects/{repo_name}",
        issue_number=issue_number,
        issue_title="Test finding",
        issue_url=f"https://github.com/HacksterT/{repo_name}/issues/{issue_number}",
        scanner="skill_gaps",
        priority="should-have",
        branch_prefix="improvement/",
        guarded_paths=[],
        touches_guarded_paths=touches_guarded,
        queued_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# enqueue — happy path
# ---------------------------------------------------------------------------

def test_enqueue_writes_json_file() -> None:
    q = _tmp_queue()
    item = _item()
    path = enqueue(item, q, _repo_cfg())
    assert path.exists()
    assert path.suffix == ".json"
    assert path.parent.name == "pending"


def test_enqueue_filename_convention() -> None:
    q = _tmp_queue()
    item = _item(repo_name="ezra-assistant", issue_number=42)
    path = enqueue(item, q, _repo_cfg())
    assert path.name == "ezra-assistant-42.json"


def test_enqueue_atomic_no_tmp_leftover() -> None:
    q = _tmp_queue()
    item = _item()
    enqueue(item, q, _repo_cfg())
    tmp_files = list((q / "pending").glob("*.tmp"))
    assert tmp_files == []


def test_enqueue_json_roundtrip() -> None:
    q = _tmp_queue()
    item = _item(issue_number=7)
    path = enqueue(item, q, _repo_cfg())
    data = json.loads(path.read_text())
    assert data["issue_number"] == 7
    assert data["repo_name"] == "ezra-assistant"


def test_enqueue_sets_item_path() -> None:
    q = _tmp_queue()
    item = _item()
    path = enqueue(item, q, _repo_cfg())
    assert item.item_path == str(path)


# ---------------------------------------------------------------------------
# enqueue — guarded path refusal
# ---------------------------------------------------------------------------

def test_enqueue_refuses_guarded_path_never_execute() -> None:
    q = _tmp_queue()
    item = _item(touches_guarded=True)
    with pytest.raises(QueueRefusedError):
        enqueue(item, q, _repo_cfg(guarded_paths=["theology/**"], policy="never_execute"))


def test_enqueue_allows_guarded_path_if_policy_not_never_execute() -> None:
    q = _tmp_queue()
    item = _item(touches_guarded=True)
    path = enqueue(item, q, _repo_cfg(guarded_paths=["theology/**"], policy="warn_only"))
    assert path.exists()


def test_enqueue_unguarded_item_always_succeeds() -> None:
    q = _tmp_queue()
    item = _item(touches_guarded=False)
    path = enqueue(item, q, _repo_cfg(guarded_paths=["theology/**"], policy="never_execute"))
    assert path.exists()


# ---------------------------------------------------------------------------
# move_to
# ---------------------------------------------------------------------------

def test_move_to_completed() -> None:
    q = _tmp_queue()
    item = _item()
    path = enqueue(item, q, _repo_cfg())
    new_path = move_to(str(path), "completed", q)
    assert new_path.parent.name == "completed"
    assert not path.exists()


def test_move_to_failed() -> None:
    q = _tmp_queue()
    item = _item()
    path = enqueue(item, q, _repo_cfg())
    new_path = move_to(str(path), "failed", q)
    assert new_path.parent.name == "failed"


def test_move_to_rejected() -> None:
    q = _tmp_queue()
    item = _item()
    path = enqueue(item, q, _repo_cfg())
    new_path = move_to(str(path), "rejected", q)
    assert new_path.parent.name == "rejected"


# ---------------------------------------------------------------------------
# load_pending — sorted oldest-first
# ---------------------------------------------------------------------------

def test_load_pending_returns_items() -> None:
    q = _tmp_queue()
    enqueue(_item(issue_number=1), q, _repo_cfg())
    enqueue(_item(issue_number=2), q, _repo_cfg())
    items = load_pending(q)
    assert len(items) == 2


def test_load_pending_oldest_first() -> None:
    import time
    q = _tmp_queue()
    enqueue(_item(issue_number=1), q, _repo_cfg())
    time.sleep(0.01)
    enqueue(_item(issue_number=2), q, _repo_cfg())
    items = load_pending(q)
    assert items[0].issue_number == 1
    assert items[1].issue_number == 2


# ---------------------------------------------------------------------------
# list_queue
# ---------------------------------------------------------------------------

def test_list_queue_counts() -> None:
    q = _tmp_queue()
    enqueue(_item(issue_number=1), q, _repo_cfg())
    enqueue(_item(issue_number=2), q, _repo_cfg())
    status = list_queue(q)
    assert status["pending"]["count"] == 2
    assert status["completed"]["count"] == 0


def test_list_queue_pending_shows_filenames() -> None:
    q = _tmp_queue()
    enqueue(_item(issue_number=5), q, _repo_cfg())
    status = list_queue(q)
    assert "ezra-assistant-5.json" in status["pending"]["items"]


def test_list_queue_non_pending_no_filenames() -> None:
    q = _tmp_queue()
    status = list_queue(q)
    assert status["completed"]["items"] == []
