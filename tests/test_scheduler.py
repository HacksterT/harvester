import json
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from harvester.scheduler import (
    SKIP_ALERT_THRESHOLD,
    _load_state,
    _save_state,
    _scanner_state,
    is_overdue,
)


def _state_file() -> Path:
    f = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    f.close()
    return Path(f.name)


# ---------------------------------------------------------------------------
# is_overdue
# ---------------------------------------------------------------------------

def test_overdue_when_never_run() -> None:
    assert is_overdue({"last_run": None, "consecutive_skips": 0}, cadence_days=7)


def test_overdue_when_past_cadence() -> None:
    old_ts = time.time() - (8 * 86400)  # 8 days ago
    assert is_overdue({"last_run": old_ts, "consecutive_skips": 0}, cadence_days=7)


def test_not_overdue_when_recent() -> None:
    recent_ts = time.time() - (3 * 86400)  # 3 days ago
    assert not is_overdue({"last_run": recent_ts, "consecutive_skips": 0}, cadence_days=7)


def test_exactly_at_cadence_is_overdue() -> None:
    ts = time.time() - (7 * 86400)
    assert is_overdue({"last_run": ts, "consecutive_skips": 0}, cadence_days=7)


# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------

def test_load_state_returns_empty_when_missing() -> None:
    state = _load_state(Path("/nonexistent/state.json"))
    assert state == {}


def test_save_and_load_state_roundtrip() -> None:
    p = _state_file()
    state = {"ezra-assistant": {"skill_gaps": {"last_run": 12345.0, "consecutive_skips": 0}}}
    _save_state(p, state)
    loaded = _load_state(p)
    assert loaded["ezra-assistant"]["skill_gaps"]["last_run"] == 12345.0


def test_save_state_atomic_no_tmp_leftover() -> None:
    p = _state_file()
    _save_state(p, {"test": True})
    tmp = p.with_suffix(".tmp")
    assert not tmp.exists()


def test_scanner_state_creates_default_entry() -> None:
    state: dict = {}
    s = _scanner_state(state, "ezra-assistant", "skill_gaps")
    assert s["last_run"] is None
    assert s["consecutive_skips"] == 0


def test_scanner_state_returns_existing_entry() -> None:
    state = {"ezra-assistant": {"skill_gaps": {"last_run": 999.0, "consecutive_skips": 2}}}
    s = _scanner_state(state, "ezra-assistant", "skill_gaps")
    assert s["last_run"] == 999.0
    assert s["consecutive_skips"] == 2


# ---------------------------------------------------------------------------
# Scheduler loop — skip counter and Telegram alert
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_config():
    from unittest.mock import MagicMock
    cfg = MagicMock()
    cfg.settings.state_path = str(_state_file())
    cfg.settings.scheduler_tick_seconds = 0.01
    repo = MagicMock()
    repo.name = "test-repo"
    scanner = MagicMock()
    scanner.name = "skill_gaps"
    scanner.cadence_days = 0  # always overdue
    repo.scanners = [scanner]
    cfg.repos = [repo]
    return cfg


async def test_skip_counter_increments_on_none_result(minimal_config) -> None:
    from harvester.scheduler import run_scheduler

    notify_calls = []

    async def fake_notify(msg: str) -> None:
        notify_calls.append(msg)

    with (
        patch("harvester.scanner_runner.run_scanner", new_callable=AsyncMock, return_value=None),
        patch("harvester.notifier.send", side_effect=fake_notify),
    ):
        task = __import__("asyncio").create_task(run_scheduler(minimal_config))
        await __import__("asyncio").sleep(0.05)
        task.cancel()
        try:
            await task
        except __import__("asyncio").CancelledError:
            pass

    state = _load_state(Path(minimal_config.settings.state_path))
    skips = state.get("test-repo", {}).get("skill_gaps", {}).get("consecutive_skips", 0)
    assert skips >= 1


async def test_telegram_alert_fires_at_threshold(minimal_config) -> None:
    from harvester.scheduler import run_scheduler

    state_path = Path(minimal_config.settings.state_path)
    # Pre-seed state so the next skip hits the threshold.
    pre_state = {
        "test-repo": {
            "skill_gaps": {
                "last_run": None,
                "consecutive_skips": SKIP_ALERT_THRESHOLD - 1,
            }
        }
    }
    _save_state(state_path, pre_state)

    notify_calls: list[str] = []

    async def fake_notify(msg: str) -> None:
        notify_calls.append(msg)

    with (
        patch("harvester.scanner_runner.run_scanner", new_callable=AsyncMock, return_value=None),
        patch("harvester.notifier.send", side_effect=fake_notify),
    ):
        task = __import__("asyncio").create_task(run_scheduler(minimal_config))
        await __import__("asyncio").sleep(0.05)
        task.cancel()
        try:
            await task
        except __import__("asyncio").CancelledError:
            pass

    assert any("skill_gaps" in msg for msg in notify_calls)


async def test_skip_counter_resets_on_finding(minimal_config) -> None:
    from harvester.models import Finding
    from harvester.scheduler import run_scheduler
    from datetime import UTC, datetime

    state_path = Path(minimal_config.settings.state_path)
    pre_state = {
        "test-repo": {
            "skill_gaps": {"last_run": None, "consecutive_skips": 2}
        }
    }
    _save_state(state_path, pre_state)

    fake_finding = Finding(
        title="Test", summary="s", evidence="e", criteria=[],
        domain="code-health", priority="should-have", scanner="skill_gaps", repo="test-repo",
    )

    with (
        patch("harvester.scheduler._load_scanner_module", return_value=object()),
        patch("harvester.scanner_runner.run_scanner", new_callable=AsyncMock, return_value=fake_finding),
        patch("harvester.notifier.send", new_callable=AsyncMock),
    ):
        task = __import__("asyncio").create_task(run_scheduler(minimal_config))
        await __import__("asyncio").sleep(0.05)
        task.cancel()
        try:
            await task
        except __import__("asyncio").CancelledError:
            pass

    state = _load_state(state_path)
    skips = state["test-repo"]["skill_gaps"]["consecutive_skips"]
    assert skips == 0
