---
type: story
feature: F01
story: F01-S03
title: Scheduler and Queue System
status: complete
created: 2026-04-18
completed: 2026-04-18
priority: must-have
---

# F01-S03: Scheduler and Queue System

**Feature:** F01 — Harvester Core — Autonomous Improvement Loop
**Priority:** Must-Have
**Status:** Complete — merged to `main`

## Summary

Build the per-(repo, scanner) scheduler that tracks cadence state and decides when to run each scanner, and the directory-based queue that holds approved work items between triage and overnight execution. The scheduler runs as an asyncio task inside the FastAPI lifespan. The queue is intentionally primitive — JSON files in four directories — because inspectability and restart safety matter more than throughput. All writes are atomic (write-then-rename) to prevent partial files.

## Acceptance Criteria

- [x] Scheduler wakes on the configured tick interval and correctly identifies overdue (repo, scanner) pairs based on `harvester-state.json`
- [x] `harvester-state.json` is read on startup and written atomically after each scan attempt (success or None result)
- [x] Consecutive-skips counter increments when a scanner returns `None`; Telegram notification fires when it reaches 3
- [x] Queue items are written atomically (write to `.tmp` then `os.replace()`)
- [x] Queue directory structure (`pending/`, `completed/`, `failed/`, `rejected/`) is created on startup if missing
- [x] `python -m harvester queue list` shows counts per directory and filenames in `pending/`
- [x] Guarded-path enqueue refusal: if `touches_guarded_paths=True` and repo policy is `never_execute`, enqueue is refused and raises `QueueRefusedError`

## Tasks

### Backend
- [x] Implement `scheduler.py`: asyncio loop, overdue check, skip counter, Telegram alert stub
- [x] Implement `queue.py`: `enqueue()`, `load_pending()`, `move_to()`, `list_queue()`, `init_queue()`
- [x] Implement `notifier.py`: stub (logs only) — upgraded to real Telegram in F02-S06
- [x] Implement `scanner_runner.py`: stub (returns None) — upgraded to Claude SDK in F01-S04
- [x] Update `QueueItem` in `models.py` with all fields agent-runner needs; add `to_dict()` / `from_dict()`
- [x] Wire scheduler into `main.py` lifespan via `asyncio.create_task()`; cancel cleanly on shutdown
- [x] Update `queue list` CLI to show pending filenames

### Testing & Verification
- [x] Write `tests/test_queue.py`: atomic write, guarded-path refusal, move operations, load order, list output — 15 tests
- [x] Write `tests/test_scheduler.py`: overdue detection, skip counter, Telegram alert threshold, reset on finding — 13 tests
- [x] Full suite: 56 passed

### Git
- [x] Committed as `feat: F01-S03 scheduler and queue system` — pushed to `hackstert/harvester` main

## Notes

Telegram notifier is a log-only stub. Real delivery implemented in F02-S06. The scheduler accepts the notifier via module import — upgrading the module upgrades all callers with no scheduler changes.

Webhook-driven queue enqueue deferred to parking lot — scheduler polls GitHub for `agent-ready` issues instead (implemented in F01-S06).

## Blockers

None — Telegram stub unblocks the skip-counter requirement without needing F02-S06.
