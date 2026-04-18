---
type: parking-lot
title: Needs Improvement — Deferred Ideas
updated: 2026-04-18
---

# Needs Improvement — Parking Lot

Consciously deferred items that are not yet stories. Review periodically and promote when the time is right.

---

## Webhook-Driven Queue Sync

**What:** Replace the scheduler's daily poll for `agent-ready` issues with real-time GitHub webhook delivery. GitHub pushes `issues.labeled` the moment you apply a label; Harvester enqueues immediately.

**Why deferred:** Requires exposing Harvester to the public internet. Troy's preference is to avoid exposure without careful tunnel configuration. Daily polling delivers the same outcome with zero exposure for now.

**When to revisit:** If the cadence needs to drop below daily, or if real-time queue sync becomes important. Set up a dedicated Cloudflare Tunnel with a Cloudflare Access policy restricting `/webhook` to GitHub's published IP ranges, then wire the stubs in `webhook.py` to `queue.enqueue()`.

**Code already in place:** `src/harvester/webhook.py` — signature verification and dispatch stubs. `docs/operational-runbook.md` has setup instructions.

---

## PR State Sync via Polling

**What:** When the overnight agent opens a PR and you merge or close it, Harvester should move the queue item from `pending/` to `completed/` or `rejected/` automatically. Without webhooks this requires polling PR state.

**Why deferred:** Depends on webhook decision above. For now, queue housekeeping can be done manually or via a simple daily poll added to the scheduler tick.

**When to revisit:** Once the loop is running and manual housekeeping becomes friction.
