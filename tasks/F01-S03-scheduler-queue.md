---
type: story
feature: F01
story: F01-S03
title: Scheduler and Queue System
status: backlog
created: 2026-04-18
priority: must-have
---

# F01-S03: Scheduler and Queue System

**Feature:** F01 — Harvester Core — Autonomous Improvement Loop
**Priority:** Must-Have

## Summary

Build the per-(repo, scanner) scheduler that tracks cadence state and decides when to run each scanner, and the directory-based queue that holds approved work items between triage and overnight execution. The scheduler runs as an asyncio task inside the FastAPI lifespan. The queue is intentionally primitive — JSON files in three directories — because inspectability and restart safety matter more than throughput. All writes are atomic (write-then-rename) to prevent partial files.

## Acceptance Criteria

- [ ] Scheduler wakes on the configured tick interval and correctly identifies overdue (repo, scanner) pairs based on `harvester-state.json`
- [ ] `harvester-state.json` is read on startup and written atomically after each scan attempt (success or None result)
- [ ] Consecutive-skips counter increments when a scanner returns `None`; Telegram notification fires when it reaches 3
- [ ] Queue items are written atomically (write to `.tmp` then `os.replace()`)
- [ ] Queue directory structure (`pending/`, `completed/`, `failed/`, `rejected/`) is created on startup if missing
- [ ] `python -m harvester queue list` shows counts per directory and filenames in `pending/`
- [ ] Guarded-path enqueue refusal: if `touches_guarded_paths=True` and repo policy is `never_execute`, enqueue is refused and logs the refusal

## Tasks

### Backend
- [ ] Implement `scheduler.py`: `run_scheduler(config, github_client, telegram)` asyncio coroutine; hourly wake loop; per-(repo, scanner) overdue check against `harvester-state.json`; calls scanner module, updates state, handles None result with skip counter
- [ ] Implement `queue.py`: `enqueue(item)` with atomic write; `list_queue()` returning counts and pending filenames; `move_to(item, destination)` for completed/failed/rejected; `load_pending()` sorted oldest-first; guarded-path policy check in `enqueue()`
- [ ] Define `QueueItem` dataclass in `models.py` with all fields from the F01 canvas queue contract
- [ ] Wire scheduler into `main.py` lifespan as `asyncio.create_task(run_scheduler(...))`

### Testing & Verification
- [ ] Write `tests/test_scheduler.py`: overdue detection with mocked state; skip counter increment; Telegram alert at threshold (mock Telegram)
- [ ] Write `tests/test_queue.py`: atomic write verified (file appears only after complete write); guarded-path refusal; move operations; list output format
- [ ] Local Testing: `uv run pytest tests/test_scheduler.py tests/test_queue.py -x`; start server and confirm scheduler log messages appear on expected intervals
- [ ] Manual Testing: CHECKPOINT — Manually write a queue item JSON and confirm `queue list` reflects it correctly

### Git
- [ ] Commit, fetch/rebase, push

## Technical Notes

The scheduler runs scans sequentially — one (repo, scanner) pair at a time. This is intentional. Concurrent scanner runs create LLM rate-limit pressure and make failures harder to attribute. The `asyncio.create_task()` pattern ensures the scheduler does not block request handling, but the scanner invocations inside it are awaited sequentially.

State file path: `data/harvester-state.json`. Structure:
```json
{
  "ezra-assistant": {
    "skill_gaps": {"last_run": 1714000000.0, "consecutive_skips": 0},
    "memory": {"last_run": null, "consecutive_skips": 0},
    "tokens": {"last_run": null, "consecutive_skips": 0}
  }
}
```

`null` last_run means never run — treat as immediately overdue.

Queue item filename convention: `<repo-name>-<issue-num>.json`. The issue number is known only after the GitHub issue is created (in F01-S04/S02), so the writer module (not the queue module) determines the filename.

## Blockers

F01-S01 (config loading, models), F01-S02 (GitHub client for Telegram notifications via bot).
