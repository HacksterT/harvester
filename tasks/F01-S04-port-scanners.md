---
type: story
feature: F01
story: F01-S04
title: Port Ezra Scanners as Harvester Modules
status: backlog
created: 2026-04-18
priority: must-have
---

# F01-S04: Port Ezra Scanners as Harvester Modules

**Feature:** F01 — Harvester Core — Autonomous Improvement Loop
**Priority:** Must-Have

## Summary

Port Ezra's three existing improvement scanners (`skill_gaps`, `memory`, `tokens`) from `src/ezra/improvements/scanners/` into `src/harvester/scanners/` with the Harvester scanner contract. The key adaptation: scanners no longer receive Ezra internals (`BolusStore`, LangGraph state) — they receive a `RepoConfig` and access Ezra's state by reading database files directly from `repo_config.local_path`. A `writer.py` module handles the GitHub issue creation side effect; scanners remain pure (return `Finding | None` only). Original Ezra scanners stay in place throughout F01.

## Acceptance Criteria

- [ ] All three scanners implement `async def scan(repo_config, llm, context) -> Finding | None`
- [ ] Scanners read Ezra state from filesystem paths, not Ezra's API or BolusStore instance
- [ ] `writer.py` accepts a `Finding` and calls `GitHubClient.create_issue()` with the correct structured body format
- [ ] Unit tests pass with mock `RepoConfig` and `MockLLMClient` — no real database, no real GitHub
- [ ] Integration test: point at a real local Ezra checkout, run each scanner, confirm a valid `Finding` is returned
- [ ] Each scanner produces at least one real GitHub issue in `hackstert/ezra-assistant` during development
- [ ] Original Ezra scanners still functional — no changes to `src/ezra/improvements/`
- [ ] `docs/scanner-contract.md` written describing the contract and how to add new scanners

## Tasks

### Backend
- [ ] Implement `scanners/base.py`: `Scanner` protocol with `scan()` signature; `ScanContext` from `models.py`; `LLMClient` ABC wrapping Grok (xAI) and Ollama; `MockLLMClient` for tests
- [ ] Port `scanners/skill_gaps.py`: reads conversation history from Ezra's `data/state/ezra.db` LangGraph checkpointer; reads `docs/skill-inventory.md` from Ezra repo; LLM call to identify gaps
- [ ] Port `scanners/memory.py`: reads `data/memory/boluses.db` directly via sqlite3; computes embedding coverage, stale bolus rate, extraction rate from raw tables
- [ ] Port `scanners/tokens.py`: reads `token_log` table from `data/memory/boluses.db`; computes 7-day spend, cache hit rate, per-call cost
- [ ] Implement `writer.py`: `write_finding(finding, github_client, config)` — formats `Finding` into the structured issue body, calls `create_issue()`, returns GitHub issue URL; logs finding to `data/findings/YYYY-MM-DD.jsonl`

### Testing & Verification
- [ ] Write `tests/scanners/test_skill_gaps.py`, `test_memory.py`, `test_tokens.py`: mock filesystem reads; assert `Finding` fields are non-empty and correctly typed
- [ ] Write `tests/test_writer.py`: assert issue body format matches the contract; mock `GitHubClient`
- [ ] Local Testing: run integration test against real Ezra checkout at `~/Projects/ezra-assistant`; confirm each scanner returns a finding
- [ ] Manual Testing: CHECKPOINT — Run one scanner end-to-end via `python -m harvester scan ezra-assistant skill_gaps`; confirm real GitHub issue appears with correct labels

### Git
- [ ] Commit, fetch/rebase, push

## Technical Notes

Ezra's `improvements/` module state: the existing scanners in `src/ezra/improvements/scanners/` are `skill_gaps.py`, `memory.py`, and `tokens.py`. They depend on `BolusStore` and Ezra's internal `LLMClient`. The ported versions replace these with direct sqlite3 reads and Harvester's own `LLMClient`.

Direct sqlite3 access to Ezra's databases is safe because Harvester only reads — it never writes to Ezra's databases. SQLite WAL mode (which Ezra uses) allows concurrent readers with no locking conflicts.

The Grok API key for scanner LLM calls is `XAI_API_KEY` in Harvester's own `.env`, not shared with Ezra's env. Both services can have their own keys.

Issue body format (from F01 canvas):
```
Title: [IMPROVEMENT] <finding title>
## Summary / ## Evidence / ## Acceptance Criteria / ## Tasks
---
Repo: / Scanner: / Domain: / Priority: / Generated:
```

## Blockers

F01-S02 (GitHubClient for `writer.py`), F01-S03 (queue integration for the scheduler → writer path).
