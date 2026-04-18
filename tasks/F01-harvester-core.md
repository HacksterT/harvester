---
type: feature-canvas
feature: F01
title: Harvester Core — Autonomous Improvement Loop
status: active
created: 2026-04-18
priority: must-have
---

# F01: Harvester Core — Autonomous Improvement Loop

## Overview

**Feature:** Harvester Core Service
**Problem:** Personal repositories accumulate quality debt, skill gaps, and optimization opportunities that are never addressed because discovery and implementation require time Troy doesn't allocate during active work.
**Goal:** A continuously running Mac service that observes personal repos on a schedule, creates GitHub issues for high-value findings, and executes approved improvements overnight via Claude Code — producing draft PRs for morning review with no manual developer effort between triage and review.

## Context

Harvester applies the Karpathy autoresearch loop to code improvement: scanner identifies a change to try (hypothesis), GitHub issue records it (commit), applying `agent-ready` decides to run it (experiment dispatch), the overnight agent implements it within a 30-minute budget (experiment execution), and merge-or-close is keep-or-discard. The loop accumulates a history that later enables self-annealing.

This feature builds the minimum viable loop end-to-end on a single repo (Ezra). It does not include the web UI, additional scanners, or Selah onboarding — those are F02. F01 is done when a finding travels from scanner to merged PR at least three times without manual intervention beyond triage and review.

The architecture is intentionally boring: a FastAPI server with an asyncio scheduler, a directory-based queue, PyGithub, and a bash script invoked by launchd. No LangGraph, no agent framework, no vector store.

## Stories

| ID | Title | Priority | Status |
|----|-------|----------|--------|
| F01-S01 | Bootstrap and Scaffolding | Must-Have | Complete |
| F01-S02 | GitHub Integration Layer | Must-Have | Backlog |
| F01-S03 | Scheduler and Queue System | Must-Have | Complete |
| F01-S04 | Build Scanner Framework with Claude SDK | Must-Have | Backlog |
| F01-S05 | Agent Runner with Subscription Auth | Must-Have | Backlog |
| F01-S06 | Webhook-Driven State Synchronization | Must-Have | Backlog |

## Non-Goals

- Web UI for operational visibility (F02-S01)
- Selah onboarding and theology review scanner (F02)
- Voice of Repentance integration (future)
- Generic code health scanner (F02-S03)
- Cross-repo pattern mining (F02-S04)
- Removal of Ezra's native improvement system (F02-S05, after 30-day stable period)
- Multi-agent parallel execution
- GitHub Actions-based runner (launchd + subscription auth, not API key)
- Any chat interface, AI persona, or conversational surface

## Dependencies

- `hackstert/ezra-assistant` repo exists and has `CLAUDE.md` (confirmed)
- Claude Code CLI installed on Troy's Mac with active subscription session
- `gh` CLI authenticated
- Cloudflare Tunnel active (existing LAN-Central-Command infrastructure)
- GitHub fine-grained PAT with issues + PRs write scope on `ezra-assistant`
- Anthropic API key for scanner LLM calls (`ANTHROPIC_API_KEY`)
- Telegram bot token (reused from Ezra)

## Success Metrics

- Three full cycles completed end-to-end: scanner finding → GitHub issue → `agent-ready` label → overnight agent run → draft PR → Troy review → merge
- Merge rate on agent PRs above 50% (low rate = scanner quality problem)
- Zero guarded-path violations
- Harvester runs continuously for 30 days without unplanned downtime exceeding 24 hours
- Adding Ezra to the watch list takes under 30 minutes of config (demonstrated by initial setup)

## Open Design Decisions

- **Subscription session expiry mitigation.** Claude Code subscription sessions expire after extended inactivity. Current plan: preflight check in agent-runner.sh, weekly Apple Calendar reminder to refresh manually, loud Telegram alert on stale auth. If this proves too fragile in practice, fallback to API key auth is configurable (`claude_code_auth: api` in config).
- **Scanner LLM.** Scanners use the Anthropic Claude SDK (`anthropic.AsyncAnthropic`) with tool-calling for iterative repo exploration. Each scanner is a thin prompt module; `scanner_runner.py` drives the tool-calling loop. The `report_finding` tool is the structured output path — its input schema matches the `Finding` dataclass. Prompt caching is enabled on scanner system prompts via `cache_control`. Ezra does not need to be running for scans — scanners read its database files and filesystem directly from `local_path`. Requires `ANTHROPIC_API_KEY` in `.env`.
- **Premortem — webhook delivery gap.** If the Mac is offline when a webhook fires, GitHub retries for ~72 hours. When Harvester comes back online, startup reconciliation (F01-S06) catches events missed during downtime. No data is lost; there may be a delay in queue state.
- **Premortem — agent workspace contamination.** A failed agent run could leave a workspace in a dirty state. Mitigation: agent-runner.sh hard-resets the workspace to `origin/main` before every run, regardless of prior state.
- **Premortem — scanner produces no findings for weeks.** If a scanner returns `None` three consecutive runs, Harvester logs a Telegram note suggesting cadence review. This is tracked via `consecutive_skips` in `harvester-state.json`.

---

*Created: 2026-04-18 | Supersedes: F19-harvester-v2-direct-build.md (archived)*
