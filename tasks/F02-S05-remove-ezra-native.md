---
type: story
feature: F02
story: F02-S05
title: Remove Ezra Native Improvement System
status: backlog
created: 2026-04-18
priority: should-have
---

# F02-S05: Remove Ezra Native Improvement System

**Feature:** F02 — Harvester Completion — Expansion and Steady State
**Priority:** Should-Have

## Summary

Once Harvester has reliably handled Ezra's improvement cycle for 30 consecutive days without incident, remove the duplicate native improvement system from Ezra. The native system (`src/ezra/improvements/`) and its cron registration were the precursor to Harvester — they are now superseded. Removing them reduces Ezra's surface area, eliminates the dual-run overlap, and confirms Harvester as the sole improvement mechanism. This is a cleanup story: one PR, no new behavior, all tests still pass.

## Acceptance Criteria

- [ ] 30-day stability gate confirmed: zero unplanned Harvester downtime exceeding 24h; at least 3 merged improvement cycles; no rejected-as-should-not-have-been-proposed findings
- [ ] Reconciliation pass run before deletion confirms no in-flight items
- [ ] `src/ezra/improvements/` directory removed entirely from Ezra
- [ ] Cron registration for `improvement_scan` removed from Ezra's `main.py`
- [ ] Ezra's full test suite passes after removal (`uv run pytest` in Ezra repo)
- [ ] Mission Control "Improvements" tab removed; link to `http://localhost:8500/` added in its place
- [ ] `docs/technical-guide.md` in Ezra updated to note Harvester handles improvement scanning
- [ ] `docs/self-improvement-system.md` in Ezra archived (moved to `docs/archive/`)

## Tasks

### Backend (in Ezra repo, dispatched as a Harvester improvement issue)
- [ ] Pre-deletion: run `python -m harvester reconcile` to confirm zero pending Ezra items; record confirmation in PR body
- [ ] Delete `src/ezra/improvements/` directory
- [ ] Remove `asyncio.create_task(run_improvement_loop(...))` and its import from `main.py`
- [ ] Remove `improvement_scan` entry from cron registry (if present in `cron/` config)
- [ ] Remove `data/improvement-state.json` from Ezra (Harvester owns this state now at its own path)

### Frontend (in Ezra repo, Mission Control)
- [ ] Remove "Improvements" tab from Mission Control navigation
- [ ] Add external link card pointing to `http://localhost:8500/` labeled "Harvester — Improvement Loop"

### Documentation (in Ezra repo)
- [ ] Update `docs/technical-guide.md` section 12 (Background Tasks): remove `improvement_scan` entry; add one-line note pointing to Harvester
- [ ] Move `docs/self-improvement-system.md` to `docs/archive/self-improvement-system-pre-harvester.md`

### Testing & Verification
- [ ] Local Testing: `uv run pytest` in Ezra repo — all tests pass; `python -m ezra` starts cleanly with no errors referencing the removed module
- [ ] Manual Testing: CHECKPOINT — Start Ezra server; confirm no cron logs referencing improvement scan; open Mission Control; confirm Improvements tab is gone and Harvester link is present; open Harvester UI at `localhost:8500` and confirm it shows active Ezra monitoring

### Git
- [ ] Commit in Ezra repo, push, open PR in `hackstert/ezra-assistant`; do not merge until Troy reviews

## Technical Notes

This story creates a PR in the `ezra-assistant` repo, not the Harvester repo. It should be dispatched as a Harvester improvement issue in `hackstert/ezra-assistant` rather than implemented directly by Troy. This is the first self-referential moment: Harvester generates the issue that removes Harvester's predecessor from Ezra.

The 30-day stability gate is tracked manually. When the gate is met, Troy creates the GitHub issue in `hackstert/ezra-assistant`, labels it `agent-ready`, and Harvester dispatches the overnight agent to execute the cleanup.

`data/improvement-state.json` in Ezra is safe to delete once Harvester is running. Harvester maintains its own `data/harvester-state.json` at `~/Projects/harvester/data/`. No migration needed.

## Blockers

Hard dependency on F01 stable for 30 consecutive days. F02-S01 (Web UI) should be complete first so the replacement link in Mission Control is ready. Independent of F02-S02, F02-S03, F02-S04.
