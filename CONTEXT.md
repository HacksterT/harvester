---
project: harvester
updated: 2026-05-15
description: "Autonomous repository improvement service that runs scanners on a schedule, creates GitHub issues for findings, and executes approved changes overnight via Claude Code."
path: /Users/hackstert/Projects/harvester/CONTEXT.md
---

## Overview

Harvester is a self-improving code maintenance service for personal repositories running on HacksterT's Mac. It applies the Karpathy autoresearch loop to code improvement: scanners surface findings as GitHub issues, the `agent-ready` label dispatches an overnight agent run, and the resulting draft PR is reviewed the next morning. Two human decisions per cycle — triage and review — everything else is automatic. F01 (core loop on Ezra) is code complete — all six stories implemented, 112 tests passing — and in manual testing (HT-01 through HT-14); F02 (web UI, Selah onboarding, cross-repo patterns) is backlog pending 30-day stability after F01's end-to-end cycle is confirmed.

## Architecture

- **FastAPI server** (`src/harvester/main.py`) — webhook ingestion, queue status endpoints, web UI; runs via launchd KeepAlive plist on port 8500
- **asyncio scheduler** (`scheduler.py`) — fires scanners per `(repo, scanner)` cadence; single-threaded, no concurrency
- **Scanner framework** (`scanner_runner.py`, `tools.py`, `scanners/`) — thin prompt modules (`SYSTEM_PROMPT` + `ENABLED_TOOLS`); `scanner_runner.py` drives `AsyncAnthropic` `tool_runner` loop with `@beta_async_tool` definitions; `report_finding` is the only structured output path
- **Directory queue** (`queue.py`) — JSON files in `data/queue/{pending,completed,failed,rejected}/`; atomic writes via `os.replace()`; no database, no locking
- **Webhook handler** (`webhook.py`) — HMAC-verified GitHub events; `issues.labeled` enqueues on `agent-ready`; `issues.closed` routes to `completed/` or `rejected/` via `state_reason`
- **Agent runner** (`scripts/agent-runner.sh`) — bash script invoked by launchd at 02:00; drains pending queue with `claude -p < task_file --max-turns N`; uses Claude Code subscription, not API key
- **Reconciliation** (`reconcile.py`) — startup background task and `reconcile` CLI command; compares GitHub open+agent-ready issues against local pending; Telegram notification on drift; `--apply` moves stale items to `rejected/`
- **Writer** (`writer.py`) — formats and posts GitHub issues for scanner findings; shared `append_findings_record()` JSONL write primitive
- **Notifier** (`notifier.py`) — Telegram notification stub; all call sites use `await send(message)`; real wiring deferred to F02-S06
- **Web UI** (`ui/`) — Jinja2 server-rendered templates; no SPA, no React
- **Scanners** (current): `skill_gaps`, `memory`, `tokens` for Ezra; `theology_review`, `code_health`, `cross_repo_patterns` are F02

## Key Conventions

- **Package manager:** `uv` — `uv sync`, `uv add <pkg>`, `uv run pytest`. Never edit `pyproject.toml` by hand for deps.
- **Type hints:** all function signatures; `X | None` not `Optional[X]`; `Path` from `pathlib` everywhere; `datetime.now(UTC)`, never naive datetimes
- **Async pattern:** `async def` for all I/O; `asyncio.to_thread()` for sync library calls (PyGithub)
- **Imports:** stdlib → third-party → local, each block alphabetized; absolute imports only (`from harvester.models import Finding`); no wildcards
- **Queue atomicity:** write to `.tmp`, then `os.replace()` to final path — never leave partial files in queue dirs
- **Scanner modules:** two constants only — `SYSTEM_PROMPT: str` and `ENABLED_TOOLS: list[str]`; no side effects; testable by mocking `AsyncAnthropic`
- **Config is the interface:** behavior changes go in `harvester-config.yaml`, not code; malformed config is a hard startup failure with field-specific errors
- **Logging:** `logging` module only (not `print` except CLI); INFO for state changes, DEBUG for tracing, WARNING for recoverable issues
- **No concurrency in scheduler or runner:** one scanner at a time, one agent run at a time — intentional, not configurable
- **Human gates cannot be configured away:** triage (`agent-ready`) and PR review are mandatory

## Dependencies

- **Runtime:** Python 3.12+, FastAPI, uvicorn, Pydantic, PyYAML, PyGithub, Click, httpx, python-telegram-bot, Jinja2, anthropic SDK
- **Infrastructure:** macOS launchd (two plists — KeepAlive server + nightly runner), Cloudflare Tunnel for webhook delivery, GitHub webhooks + labels + PRs
- **External APIs:** GitHub API (PyGithub), Anthropic API (scanner LLM calls, ~$0.05-0.10/scan), Telegram Bot API (drift notifications)
- **Sibling systems:** Ezra (`localhost:8400/api/status`) — scanners treat Ezra's SQLite databases as read-only external sources; Ezra pings Harvester `localhost:8500/healthz` hourly
- **Auth:** `GITHUB_TOKEN` (env), `ANTHROPIC_API_KEY` (env, scanner calls), `GITHUB_WEBHOOK_SECRET` (env, webhook HMAC verification), Claude Code CLI subscription (agent runner overnight)
- **Paths:** `~/Projects/harvester` (this repo), `~/Projects/ezra-assistant` (Ezra, read-only target)

## Active Work

- **F01 manual testing** — all six stories implemented, 112 tests passing; 14 checkpoints (HT-01 through HT-14) in `tasks/human-test.md`; next: run `scripts/agent-runner.sh` manually against one real pending item and confirm draft PR opens (HT-10 is the F01 exit criterion)
- **Integration test: scanners** — run each scanner against real Ezra checkout at `~/Projects/ezra-assistant`; confirm valid Finding returned (F01-S04)
- **Guarded-path enforcement test** — mock queue item with `guarded_check.required=true` touching a guarded path; confirm run aborts and item moves to `failed/` (F01-S05)
- **F01-S01** — complete; moved to `tasks/completed/`
- **F02 backlog** — web UI (F02-S01), Selah guardrails (F02-S02), code health scanner (F02-S03), cross-repo pattern scanner (F02-S04), remove Ezra native improvement system (F02-S05), Telegram notifications (F02-S06); F02 opens after 30-day F01 stability gate
- **`scan` CLI command** — `python -m harvester scan <repo> <scanner>` is a stub (`sys.exit(1)`); first deferred follow-up after F01 manual testing completes
