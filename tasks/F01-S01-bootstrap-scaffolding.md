---
type: story
feature: F01
story: F01-S01
title: Bootstrap and Scaffolding
status: complete
created: 2026-04-18
completed: 2026-04-18
priority: must-have
---

# F01-S01: Bootstrap and Scaffolding

**Feature:** F01 — Harvester Core — Autonomous Improvement Loop
**Priority:** Must-Have
**Status:** Complete — merged to `main`

## Summary

Create the `hackstert/harvester` repository with complete project structure, working CLI entry points, and a validated config system. This story delivers the skeleton that every subsequent story builds on. The service must start cleanly, validate its config, and expose a working HTTP server before any scanner or GitHub integration is built. Config validation at startup is a hard gate — a malformed `harvester-config.yaml` must refuse to start with a clear error, not silently misbehave.

## Acceptance Criteria

- [x] `uv sync` produces a working environment with no errors
- [x] `python -m harvester validate` passes on a well-formed config and prints a structured summary
- [x] `python -m harvester validate` rejects a malformed config with a specific, actionable error message (not a raw pydantic stack trace)
- [x] `python -m harvester serve` starts and logs "Harvester ready on port 8500" with no errors
- [x] `GET /healthz` returns `{"status": "ok", "version": "..."}` while the server is running
- [x] `python -m harvester queue list` prints queue state (empty at this point, gracefully)
- [x] `CLAUDE.md` in the repo root accurately describes the Harvester microservice (not Ezra)
- [x] `.gitignore` excludes `data/`, `workspaces/`, `.env`, `__pycache__`, `.venv`

## Tasks

### Backend
- [x] Initialize repo with `uv init`, configure `pyproject.toml` with the minimum dependency set (fastapi, uvicorn, pydantic, PyYAML, PyGithub, click, httpx, python-telegram-bot, jinja2, anthropic)
- [x] Implement `config.py`: `GlobalConfig` and `RepoConfig` pydantic models; `load_config(path) -> GlobalConfig` that wraps pydantic's validation errors in human-readable output
- [x] Implement `models.py`: `Finding`, `ScanContext`, `RunResult` dataclasses
- [x] Implement `__main__.py` with Click: `serve`, `validate`, `scan`, `queue list`, `queue clear` commands
- [x] Implement `main.py`: FastAPI app, lifespan (creates operational dirs, loads config), `GET /healthz` route, startup log
- [x] Create directory layout: `src/harvester/`, `src/harvester/scanners/`, `src/harvester/ui/`, `scripts/`, `data/queue/{pending,completed,failed,rejected}/`, `data/findings/`, `data/logs/`, `docs/`
- [x] Write `harvester-config.yaml` with Ezra-assistant as the single configured repo

### Testing & Verification
- [x] Write `tests/test_config.py`: valid config loads correctly, missing required fields produce clear errors, invalid cadence values rejected — 10 tests, all passing
- [x] Local Testing: `uv run pytest tests/test_config.py -x` passes; `python -m harvester validate` and `python -m harvester serve` work as specified
- [x] Manual Testing: CHECKPOINT — Server starts, `/healthz` returns `{"status":"ok","version":"0.1.0"}`

### Convenience Scripts
- [x] `start.sh` — sources `.env`, PID-guarded background launch, confirms `/healthz` responds
- [x] `stop.sh` — graceful SIGTERM with 5s wait, SIGKILL fallback, PID file cleanup

### Git
- [x] Committed as `feat: F01-S01 bootstrap and scaffolding` — pushed to `hackstert/harvester` main

## Technical Notes

Dependency list is intentionally minimal. Do not add LangGraph, LangChain, vector libraries, or anything not in the F01 canvas list. The `data/` directory is gitignored but its subdirectory structure is created on startup by the queue module (F01-S03), not here — here we just `mkdir -p` them as part of initial setup to allow the server to start cleanly.

The `CLAUDE.md` committed to this repo should match the one already at `~/Projects/harvester/CLAUDE.md`. Copy it in rather than rewriting.

Config validation errors should surface the YAML path of the bad field (e.g., "repos[0].scanners[1].cadence_days: must be positive integer") not the raw pydantic `ValidationError`. Wrap with a `try/except ValidationError` in `load_config()`.

## Blockers

None. This story has no dependencies.
