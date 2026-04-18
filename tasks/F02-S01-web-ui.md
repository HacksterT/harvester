---
type: story
feature: F02
story: F02-S01
title: Minimal Web UI
status: backlog
created: 2026-04-18
priority: should-have
---

# F02-S01: Minimal Web UI

**Feature:** F02 — Harvester Completion — Expansion and Steady State
**Priority:** Should-Have

## Summary

Operational visibility at `http://localhost:8500/`. Server-rendered Jinja templates, no JavaScript framework, no SPA. The goal is a dashboard that gives complete situational awareness of the improvement loop in under 30 seconds — queue state, scanner health, recent findings, recent runs, and system health. Also includes a "Rescan now" button and a failed-item retry function. This is the UI you check at 2am when something broke; clarity beats aesthetics.

## Acceptance Criteria

- [ ] Dashboard (`/`) renders repo scanner status, queue counts, 10 most recent findings, 10 most recent agent runs, and failed items
- [ ] Repo detail (`/repos/<name>`) shows per-scanner cadence history and guarded-path violation count (must be zero)
- [ ] Queue page (`/queue`) shows all four folders as tables with clickable JSON view
- [ ] "Rescan now" on `/scanners/<name>` triggers an immediate scan bypassing cadence
- [ ] "Retry" on a failed queue item moves it back to `pending/`
- [ ] Log viewer at `/logs/<run-id>` renders multi-MB logs without browser crash (streamed, not loaded fully into DOM)
- [ ] UI is localhost-only — not accessible from other LAN machines without explicit tunneling
- [ ] All pages render in under 100ms with real data from a populated queue

## Tasks

### Backend
- [ ] Implement `ui/app.py`: FastAPI router mounted at `/`; routes for `/`, `/repos/<name>`, `/scanners/<name>`, `/queue`, `/logs/<run-id>`
- [ ] Implement "Rescan now" endpoint: `POST /api/scanners/<name>/rescan?repo=<name>` — bypasses cadence by setting `last_run = null` in `harvester-state.json` and waking the scheduler
- [ ] Implement "Retry" endpoint: `POST /api/queue/retry/<filename>` — moves item from `failed/` to `pending/`
- [ ] Implement log streaming: `GET /logs/<run-id>` reads log file in chunks with `StreamingResponse`
- [ ] Write Jinja templates in `ui/templates/`: `base.html`, `dashboard.html`, `repo.html`, `scanner.html`, `queue.html`, `log.html` — minimal HTML, no external CSS framework; inline `<style>` using system fonts and monospace for data

### Testing & Verification
- [ ] Write `tests/ui/test_ui_routes.py`: each route returns 200 with expected content markers; rescan endpoint updates state file; retry moves queue item
- [ ] Local Testing: `uv run pytest tests/ui/ -x`; start server, open browser, navigate all pages with a populated queue
- [ ] Manual Testing: CHECKPOINT — Click "Rescan now" for a scanner; confirm it appears in the scheduler log within the tick; click "Retry" on a failed item; confirm it moves to `pending/`; load a large log file and confirm the browser does not hang

### Git
- [ ] Commit, fetch/rebase, push

## Technical Notes

Use Jinja2 (already in pyproject.toml). Templates live at `src/harvester/ui/templates/`. Mount static files if needed at `/static/` but prefer inline CSS to minimize the asset surface.

Localhost binding: FastAPI `uvicorn` is configured with `host="127.0.0.1"` not `"0.0.0.0"`. This makes the UI inaccessible from other LAN machines by default. Document this in the operational runbook so Troy knows how to temporarily expose it via the Cloudflare Tunnel if needed remotely.

Log streaming: use `fastapi.responses.StreamingResponse` with a generator that reads the log file in 4KB chunks. Cap at 10MB before returning a truncation notice. This avoids loading a full log into memory or the browser DOM.

## Blockers

F01 complete (real data must exist to test pages meaningfully).
