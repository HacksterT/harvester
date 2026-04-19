---
type: story
feature: F01
story: F01-S02
title: GitHub Integration Layer
status: complete
created: 2026-04-18
completed: 2026-04-18
priority: must-have
---

# F01-S02: GitHub Integration Layer

**Feature:** F01 — Harvester Core — Autonomous Improvement Loop
**Priority:** Must-Have

## Summary

Build the complete GitHub integration: a `GitHubClient` wrapper around PyGithub for issue creation and label management, a webhook handler that receives and verifies signed GitHub events, and a startup routine that auto-creates the full label taxonomy on each configured repo. This is the communication layer that connects every other Harvester component to GitHub. Without it, scanners have nowhere to write findings and the queue has no input.

## Acceptance Criteria

- [x] `GitHubClient` supports: create issue, get issue, list issues, close issue, comment on issue, apply labels, ensure labels exist
- [x] Rate limiting handled with exponential backoff; a 429 response does not crash Harvester
- [x] `POST /webhook` verifies `X-Hub-Signature-256` using HMAC-SHA256; unsigned requests return 401
- [x] Label taxonomy auto-created on startup for each configured repo (idempotent — existing labels not duplicated)
- [ ] Issue creation tested end-to-end: a real issue appears in `hackstert/ezra-assistant` (manual — HT-07)
- [ ] Webhook receiving tested via GitHub's "Redeliver" feature on a real event (manual — HT-13)
- [x] Webhook secret mismatch logged at WARNING level and rejected cleanly

## Tasks

### Backend
- [ ] Implement `github_client.py`: async `GitHubClient` wrapping PyGithub with the full method set; exponential backoff on 429 using `asyncio.sleep`; `ensure_labels_exist()` idempotent label creation
- [ ] Define label taxonomy constants in `github_client.py`: `improvement`, `scanner:<name>`, `domain:<value>`, `priority:must-have`, `priority:should-have`, `priority:nice-to-have`, `status:triage`, `agent-ready`, `status:blocked`, `theological-review-required`
- [ ] Implement `webhook.py`: FastAPI `POST /webhook` route; signature verification function using `hmac.compare_digest`; event dispatch stubs for `issues.labeled`, `issues.closed`, `pull_request.opened`, `pull_request.closed`
- [ ] Wire label auto-creation into `main.py` lifespan startup — call `ensure_labels_exist()` for each repo in config
- [ ] Document Cloudflare Tunnel setup for webhook exposure in `docs/operational-runbook.md` (one-time, not automated)

### Dependencies
- [ ] PyGithub is already in pyproject.toml from S01; no new packages needed
- [ ] Confirm `GITHUB_TOKEN` and `GITHUB_WEBHOOK_SECRET` documented in `.env.example`

### Testing & Verification
- [ ] Write `tests/test_github_client.py`: mock PyGithub responses; test rate limit backoff logic; test `ensure_labels_exist` idempotency
- [ ] Write `tests/test_webhook.py`: valid signature accepted; invalid signature returns 401; malformed payload returns 400
- [ ] Local Testing: Run `uv run pytest tests/test_github_client.py tests/test_webhook.py -x`; manually create one test issue via `GitHubClient` and confirm it appears on GitHub
- [ ] Manual Testing: CHECKPOINT — Configure GitHub webhook pointing to Cloudflare Tunnel URL; use "Redeliver" on a ping event; confirm Harvester logs receipt

### Git
- [ ] Commit, fetch/rebase, push

## Technical Notes

The webhook endpoint must be exposed via the existing Cloudflare Tunnel infrastructure from LAN-Central-Command, not direct port forwarding. The tunnel URL format is `https://harvester.<domain>/webhook`. This is a one-time infrastructure configuration, not code.

`GitHubClient` wraps PyGithub synchronously via `asyncio.to_thread()` since PyGithub is not async-native. All public methods on the client class should be `async def` to maintain Harvester's consistent async interface. Internally, they call `asyncio.to_thread(self._gh_repo.create_issue, ...)`.

The `ensure_labels_exist()` method reads existing repo labels before creating. GitHub's label create API returns 422 if the label already exists — catch this and treat as success (idempotent).

## Blockers

F01-S01 must be complete (FastAPI app structure, config loading, `.env` loading).
