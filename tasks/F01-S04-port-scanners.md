---
type: story
feature: F01
story: F01-S04
title: Build Scanner Framework with Claude SDK
status: in-progress
created: 2026-04-18
completed: 2026-04-19
priority: must-have
---

# F01-S04: Build Scanner Framework with Claude SDK

**Feature:** F01 — Harvester Core — Autonomous Improvement Loop
**Priority:** Must-Have

## Summary

Build the scanner execution framework using the Anthropic Claude SDK with tool-calling. Scanners are thin prompt modules — a `SYSTEM_PROMPT` string and an `ENABLED_TOOLS` list. A shared `scanner_runner.py` drives the Claude API tool-calling loop for every scanner, routing tool invocations to a shared tool library. The loop ends when Claude calls the `report_finding` tool (structured output) or reaches `end_turn`. This design gives Claude the ability to explore the repo iteratively before committing to a finding — reading files, querying databases, running static analysis — rather than executing a rigid sequence of steps.

The three Ezra-specific scanners (`skill_gaps`, `memory`, `tokens`) are implemented as the first three scanner modules. They access Ezra state by reading its database files and filesystem directly from `repo_config.local_path` — no Ezra process running, no Ezra API, no BolusStore. Original Ezra scanners stay in place throughout F01.

## Acceptance Criteria

- [ ] `scanner_runner.py` drives the Claude tool-calling loop; each scanner is a module with `SYSTEM_PROMPT: str` and `ENABLED_TOOLS: list[str]`
- [ ] Shared tool library in `tools.py` implements: `read_file`, `query_sqlite` (read-only), `run_command` (allowlisted), `list_directory`, `read_git_log`
- [ ] `report_finding` tool schema matches the `Finding` dataclass exactly — it is the only structured output path
- [ ] Prompt caching enabled on scanner system prompts via `cache_control: {"type": "ephemeral"}`
- [ ] All three Ezra scanners implemented: `skill_gaps.py`, `memory.py`, `tokens.py`
- [ ] `writer.py` accepts a `Finding` and calls `GitHubClient.create_issue()` with the structured body format; logs to `data/findings/YYYY-MM-DD.jsonl`
- [ ] Unit tests pass with mocked `anthropic.AsyncAnthropic` — no real API calls, no real filesystem
- [ ] Integration test: point at a real local Ezra checkout, run each scanner end-to-end, confirm a valid `Finding` is returned
- [ ] Each scanner produces at least one real GitHub issue in `hackstert/ezra-assistant` during development
- [ ] Original Ezra scanners still functional — no changes to `src/ezra/improvements/`
- [x] `docs/scanner-contract.md` written: the contract, tool library reference, how to add a new scanner module

## Tasks

### Backend

- [x] Implement `tools.py`: six `@beta_tool` async functions (`read_file`, `query_sqlite`, `run_command`, `list_directory`, `read_git_log`, `report_finding`) using the `anthropic.beta_tool` decorator — the SDK generates tool schemas automatically; `run_command` enforces allowlist on `shlex.split(command)[0]`; `query_sqlite` enforces SELECT-only; `report_finding` parameters match `Finding` dataclass fields exactly
- [x] Implement `build_tools(enabled, target_config)` in `tools.py`: returns the subset of `@beta_tool` functions matching `enabled` names, with filesystem ops scoped to `target_config.local_path`
- [x] Implement `scanner_runner.py`: `async def run_scanner(scanner_module, target_config, context) -> Finding | None`; instantiates `AsyncAnthropic()`; calls `client.beta.messages.tool_runner()` with `SYSTEM_PROMPT`, enabled tools + `report_finding`, model `claude-sonnet-4-6`, `max_tokens=4096`; iterates messages; returns `Finding` when `report_finding` invoked, `None` on `end_turn`
- [x] Implement `scanners/skill_gaps.py`: `SYSTEM_PROMPT` instructs Claude to read conversation history from Ezra's `data/state/ezra.db` LangGraph checkpointer and `docs/skill-inventory.md`; `ENABLED_TOOLS = ["read_file", "query_sqlite", "list_directory"]`
- [x] Implement `scanners/memory.py`: `SYSTEM_PROMPT` instructs Claude to examine `data/memory/boluses.db` for embedding coverage, stale bolus rate, extraction rate; `ENABLED_TOOLS = ["query_sqlite"]`
- [x] Implement `scanners/tokens.py`: `SYSTEM_PROMPT` instructs Claude to read `token_log` table from `data/memory/boluses.db` and compute 7-day spend, cache hit rate, per-call cost; `ENABLED_TOOLS = ["query_sqlite"]`
- [x] Implement `writer.py`: `write_finding(finding, github_client, config)` — formats `Finding` into structured issue body, calls `create_issue()`, returns GitHub issue URL; logs finding to `data/findings/YYYY-MM-DD.jsonl`

### Testing & Verification

- [x] Write `tests/test_scanner_runner.py`: mock `anthropic.AsyncAnthropic`; simulate tool-calling loop with synthetic tool_use blocks; assert `report_finding` input maps to `Finding` correctly; assert loop terminates on `end_turn`
- [x] Write `tests/scanners/test_skill_gaps.py`, `test_memory.py`, `test_tokens.py`: mock tool library responses; assert `SYSTEM_PROMPT` is non-empty and `ENABLED_TOOLS` is a subset of the allowed tool names
- [x] Write `tests/test_writer.py`: assert issue body format matches the contract; mock `GitHubClient`
- [ ] Local Testing: run integration test against real Ezra checkout at `~/Projects/ezra-assistant`; confirm each scanner returns a valid `Finding`
- [ ] Manual Testing: CHECKPOINT — Run `python -m harvester scan ezra-assistant skill_gaps`; confirm a real GitHub issue appears with correct labels and structured body

### Git

- [ ] Commit, fetch/rebase, push

## Technical Notes

Scanner module structure (every scanner is this pattern):
```python
# src/harvester/scanners/skill_gaps.py
SYSTEM_PROMPT = """
You are auditing the Ezra assistant's skill gaps. Read the LangGraph conversation
history from data/state/ezra.db and the skill inventory from docs/skill-inventory.md.
Identify the single most actionable skill gap and report it via report_finding.
"""
ENABLED_TOOLS = ["read_file", "query_sqlite", "list_directory"]
```

Framework in `scanner_runner.py` using the Anthropic Python SDK `tool_runner`:
```python
from anthropic import AsyncAnthropic
from harvester.tools import build_tools, report_finding

async def run_scanner(scanner_module, target_config, context) -> Finding | None:
    client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env
    tools = build_tools(scanner_module.ENABLED_TOOLS, target_config) + [report_finding]

    found: Finding | None = None

    runner = await client.beta.messages.tool_runner(
        model="claude-sonnet-4-6",
        system=scanner_module.SYSTEM_PROMPT,
        tools=tools,
        messages=[{"role": "user", "content": f"Scan {target_config.name} at {target_config.local_path}."}],
        max_tokens=4096,
    )
    async for message in runner:
        if isinstance(message, ToolUseBlock) and message.name == "report_finding":
            found = Finding(**message.input)
            break

    return found
```

Tool definitions in `tools.py` using the `@beta_tool` decorator — the SDK handles schema generation and dispatch automatically:
```python
from anthropic import beta_tool

@beta_tool
async def read_file(path: str) -> str:
    """Read a file from the target repository. path is relative to repo root."""
    ...

@beta_tool
async def query_sqlite(db_path: str, sql: str) -> str:
    """Run a read-only SELECT query against a SQLite database. db_path relative to repo root."""
    # enforce: sql.strip().upper().startswith("SELECT")
    ...

@beta_tool
async def run_command(command: str) -> str:
    """Run a static analysis command. Allowed: ruff, mypy, radon, coverage, git log."""
    # enforce allowlist on shlex.split(command)[0]
    ...
```

`build_tools(enabled: list[str], target: TargetConfig)` returns the subset of `@beta_tool` functions named in `enabled`, with `cwd` scoped to `target.local_path`.

Two auth mechanisms: `ANTHROPIC_API_KEY` for scanner LLM calls (Anthropic REST API); Claude Code CLI subscription for the overnight agent runner. These are separate. Scanner calls consume API credits; the agent runner does not.

Issue body format:
```
Title: [IMPROVEMENT] <finding title>
## Summary / ## Evidence / ## Acceptance Criteria / ## Tasks
---
Repo: / Scanner: / Domain: / Priority: / Generated:
```

## Blockers

F01-S02 (GitHubClient for `writer.py`), F01-S03 (queue integration for the scheduler → writer path).
