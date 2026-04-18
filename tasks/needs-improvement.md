---
type: parking-lot
title: Needs Improvement — Deferred Ideas
updated: 2026-04-18
---

# Needs Improvement — Parking Lot

Ideas and enhancements that are consciously deferred. Not backlog — these require a deliberate decision before picking up. Review periodically and promote to a story when the time is right.

---

## Webhook-Driven Queue Sync

**What:** Replace the scheduler's nightly poll for `agent-ready` issues with real-time GitHub webhook delivery. GitHub pushes `issues.labeled` events to Harvester the moment you apply a label; Harvester enqueues immediately rather than waiting for the next scheduled check.

**Current approach:** Scheduler polls GitHub for `agent-ready` issues once per day (or configured tick). For a system running agents at 02:00, this latency is irrelevant.

**Why deferred:** Requires exposing Harvester to the public internet via Cloudflare Tunnel or Tailscale Funnel. Troy's preference is to avoid exposure without careful configuration. The polling approach delivers the same functional outcome with zero network exposure.

**When to revisit:** If the cadence needs to drop below daily, or if you want queue state to update in under an hour. At that point, set up a dedicated Cloudflare Tunnel with a Cloudflare Access policy restricting `/webhook` to GitHub's published IP ranges, then wire the stub handlers already in `webhook.py` to `queue.enqueue()`.

**Code already in place:** `src/harvester/webhook.py` — signature verification and dispatch stubs for `issues.labeled`, `issues.closed`, `pull_request.opened`, `pull_request.closed`. `docs/operational-runbook.md` has the Cloudflare Tunnel setup instructions.

---

## PR State Sync via Polling

**What:** When the overnight agent opens a PR and you merge or close it, Harvester should move the queue item from `pending/` to `completed/` or `rejected/`. Without webhooks this requires polling PR state.

**Current approach:** Not yet implemented. For now, queue housekeeping is manual — move files between subdirectories as needed.

**When to revisit:** After F01-S06 is scoped. Could be as simple as a daily GitHub API call checking open PRs linked to pending queue items.

---

## Telegram Notifications

**What:** Notify Troy via Telegram when: a scanner produces a finding, an agent run completes (with PR link), a run fails, or a guarded-path violation is detected.

**Current approach:** `python-telegram-bot` is already a dependency but not wired to anything.

**When to revisit:** F02 or whenever the loop is stable enough that notifications are signal rather than noise.

---

## Web UI

**What:** Minimal Jinja-rendered dashboard at `localhost:8500` showing queue state, recent findings, scanner cadence status, and run logs. F02-S01 in the feature canvas.

**Current approach:** No UI. Operational visibility via CLI (`python -m harvester queue list`) and log files.

**When to revisit:** After F01 loop is confirmed working end-to-end.

---

## Selah Onboarding

**What:** Add Selah to Harvester's watch list with the theology-review scanner and four-layer guarded-path protection. F02-S02 in the feature canvas.

**Dependency:** Selah repo needs its own `CLAUDE.md` before this story can complete.

---

## Cross-Repo Pattern Scanner

**What:** Monthly scanner that mines closed issue history to identify what's working and what isn't — the self-annealing mechanism. F02-S04.

**Hard gate:** Requires 30+ closed issues across all watched repos before it produces signal. Do not start until 60+ days after F01 is stable.
