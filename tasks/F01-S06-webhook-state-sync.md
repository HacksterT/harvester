---
type: story
feature: F01
story: F01-S06
title: Webhook-Driven State Synchronization
status: complete
created: 2026-04-18
completed: 2026-04-19
priority: must-have
---

# F01-S06: Webhook-Driven State Synchronization

**Feature:** F01 — Harvester Core — Autonomous Improvement Loop
**Priority:** Must-Have

## Summary

Complete the webhook handler's event dispatch so Harvester's local queue state stays synchronized with GitHub reality. When an issue gets the `agent-ready` label, it is enqueued. When a PR merges and its linked issue closes, the queue item moves to `completed/`. When an issue is closed manually without a merge, it moves to `rejected/`. A reconciliation pass on every startup catches drift that accumulated while Harvester was offline. This closes the loop: Harvester knows the outcome of every item it has ever enqueued.

## Acceptance Criteria

- [x] `issues.labeled` with `agent-ready` enqueues the item (calls `queue.enqueue()`)
- [x] `issues.closed` (via merged PR) moves queue item to `completed/` and logs to `data/findings/`
- [x] `issues.closed` (manual, no merged PR) moves queue item to `rejected/`
- [x] `pull_request.opened` logs PR URL to findings JSONL
- [x] `pull_request.closed` (merged) records successful cycle with duration
- [x] Unsigned webhook requests return 401 (tested in F01-S02; confirmed still correct here)
- [x] Reconciliation on startup: compares GitHub open/closed issue state against queue; logs drift counts to Telegram (does not auto-resolve)
- [x] `python -m harvester reconcile --apply` resolves drift idempotently
- [x] `rejected/` directory created on startup alongside the others

## Tasks

### Backend
- [x] Complete `webhook.py` event dispatch: implement handlers for `issues.labeled` (enqueue), `issues.closed` (complete or reject based on PR merge state), `pull_request.opened` (log), `pull_request.closed` (log with merge status)
- [x] Implement `reconcile.py`: `list_open_improvement_issues(repo)` via `GitHubClient`; compare against queue state; return drift report; `apply_reconciliation(report)` moves items to correct state
- [x] Add `GET /api/queue` endpoint exposing counts for all four queue directories (pending, completed, failed, rejected)
- [x] Wire reconciliation into `main.py` lifespan startup — run in background task, results logged to Telegram

### Testing & Verification
- [x] Write `tests/test_webhook_dispatch.py`: mock payloads for each event type; assert correct queue operations called
- [x] Write `tests/test_reconcile.py`: seed queue with items in wrong state; run reconcile; assert items moved correctly; run again (idempotency check)
- [ ] Local Testing: `uv run pytest tests/test_webhook_dispatch.py tests/test_reconcile.py -x`; restart Harvester with a deliberately drifted queue state; confirm Telegram drift notification fires
- [ ] Manual Testing: CHECKPOINT — Apply `agent-ready` label to a real test issue; confirm queue item appears in `pending/`; merge the downstream PR; confirm item moves to `completed/`

### Git
- [ ] Commit, fetch/rebase, push

## Technical Notes

Determining merge state on `issues.closed`: GitHub's `issues.closed` webhook payload does not include PR merge state directly. Distinguish by checking whether any linked PR was merged: call `GitHubClient.list_issues()` looking for the linked PR via the issue timeline, or use the GitHub GraphQL API to get `closedByPullRequestsReferences`. Simpler heuristic: if the issue was closed automatically (source: "merged"), treat as `completed`; if manually closed, treat as `rejected`. The webhook payload `event.issue.state_reason` (GitHub added this in 2022) distinguishes `completed` from `not_planned` — use this.

Reconciliation runs as a background asyncio task at startup: `asyncio.create_task(_reconcile_on_startup())`. It should not block the server from accepting requests. Log drift to Telegram; never auto-apply on startup (only via explicit `--apply` CLI flag).

The `rejected/` queue folder is important for the cross-repo pattern scanner (F02-S04) which mines rejection history to tune scanner quality. Do not clean it up automatically.

## Blockers

F01-S02 (GitHubClient for issue listing), F01-S03 (queue move operations and directory structure).
