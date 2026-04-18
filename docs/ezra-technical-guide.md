# Ezra Technical Guide

**Purpose:** Reference architecture for Harvester agents dispatched to implement improvements in the `hackstert/ezra-assistant` repository.
**Audience:** Overnight agents receiving an Ezra improvement issue from Harvester.
**Authoritative agent context:** `~/Projects/ezra-assistant/CLAUDE.md` — read that first when you land in the repo.
**Authoritative architecture doc:** `~/Projects/ezra-assistant/docs/technical-guide.md` — this document summarizes it; that one is definitive.

This document is maintained in the Harvester repo as a cross-system reference. When Ezra's architecture changes substantially, update this file. If this doc conflicts with `ezra-assistant/CLAUDE.md` or `ezra-assistant/docs/technical-guide.md`, those win.

---

## 1. What Ezra Is

Ezra Assistant is HacksterT's personal AI system — a long-lived FastAPI server running on his Mac. It has two interfaces (Mission Control web UI on ports 5180/8400 and a Telegram bot) feeding a single LangGraph `ChatGraph`. One graph, one memory store, two interfaces. Not a product; personal infrastructure.

You are not Ezra. You are an ephemeral agent dispatched overnight to improve Ezra's code.

---

## 2. Runtime Stack

| Component | Details |
|---|---|
| Language | Python 3.12+ |
| Graph execution | LangGraph (`AsyncSqliteSaver` checkpointer) |
| HTTP server | FastAPI on port 8400 |
| Databases | SQLite — three categories (see section 4) |
| Primary LLM | Grok via xAI Responses API |
| Secondary LLM | Selah-Q8 (Gemma 4 Q8 quantization via Ollama) |
| Embeddings | `nomic-embed-text:v1.5` via Ollama |
| Fact extraction | `gemma2:2b` via Ollama |
| Frontend | React + Vite — `mission-control/` — dev port 5180, prod on 8400 |
| Telegram | `python-telegram-bot` v21 (async) |
| Package manager | `uv` — use `uv sync`, `uv add`, `uv run pytest` |

Grok models available (from `config.py`):
- `grok-4-1-fast-reasoning` (default) — $0.20/M input, $0.50/M output
- `grok-4.20-reasoning-latest` — $2.60/M input, $2.60/M output
- `grok-4-1-fast-non-reasoning-latest`

Selah-Q8 is `selah-q8:latest` in Ollama. Ollama runs at `localhost:11434`.

Ezra never calls Anthropic's API. Do not add OpenAI, Anthropic, or other LLM providers.

---

## 3. Directory Map

```
src/ezra/
├── __main__.py          CLI entry point
├── config.py            Settings from .env + AVAILABLE_MODELS dict
├── context.py           RuntimeContext dataclass (thread_id, project, credentials)
├── manifest.py          ManifestConfig from agents/ezra/manifest.yaml (@lru_cache)
├── factory.py           create_ezra_graph() — wires everything together
├── checkpointer.py      AsyncSqliteSaver setup
├── graphs/
│   ├── base.py          BaseGraph + BaseGraphState; fact extraction trigger
│   └── chat.py          ChatGraph: two-tier skill dispatch topology; TOOLS list
├── memory/
│   ├── types.py         KnowledgeBolus dataclass
│   ├── store.py         BolusStore: hybrid search, salience, token log
│   ├── extractor.py     Fire-and-forget fact extraction (gemma2:2b)
│   ├── ingest.py        Markdown/PDF/text ingestion pipeline
│   ├── summarizer.py    maybe_summarize()
│   └── embeddings.py    EmbeddingProvider ABC + Ollama/OpenAI/Null impls
├── providers/
│   ├── base.py          LLMProvider ABC + registry (@register_provider)
│   ├── xai.py           Grok via xAI Responses API (server-side tools)
│   └── ollama.py        ChatOllama for Selah-Q8
├── routes/
│   ├── chat.py          WS /ws/chat + GET /api/chat/history
│   ├── memory.py        /api/memory/*
│   ├── tokens.py        /api/tokens/*
│   ├── status.py        /api/status, /api/model, /api/stats/today
│   ├── knowledge.py     /api/knowledge/* (Knowledge Center)
│   └── context.py       /api/context/* (project context seeding)
├── skills/
│   ├── web_fetch/       Tier 1: @tool
│   ├── local_shell/     Tier 1: @tool
│   ├── text_editor/     Tier 1: read/write/edit/list @tools
│   ├── code_execution/  Tier 1: execute_python @tool
│   ├── email/           Tier 1: send_email (iCloud SMTP)
│   ├── manage_todo/     Tier 1: project to-do lists
│   ├── apple/           Shared JXA executor
│   ├── apple_notes/     Tier 2: workflow
│   ├── apple_reminders/ Tier 2: workflow
│   ├── apple_calendar/  Tier 2: workflow
│   ├── youtube_digest/  Tier 2: workflow
│   ├── skill_creator/   Tier 2: workflow
│   └── research/        Tier 2: workflow
├── improvements/        Native improvement system (being replaced by Harvester in F02-S05)
│   ├── scheduler.py     run_improvement_loop() — domain rotation, 12h check interval
│   ├── writer.py        write_improvement_story() — formats finding to Markdown
│   └── scanners/
│       ├── skill_gaps.py
│       ├── memory.py
│       └── tokens.py
├── portfolio/
│   ├── context_aggregator.py  CONTEXT.md filesystem scanner (5-min cache)
│   └── managed_store.py       portfolio-managed.json I/O
└── telegram_bot.py      Telegram interface

agents/ezra/
├── manifest.yaml        Model, temperature, system_prompt_path
└── system_prompt.md     Full persona prompt

mission-control/         React + Vite frontend
data/
├── state/ezra.db        LangGraph checkpointer (session state)
├── memory/boluses.db    BolusStore (long-term memory)
└── knowledge/           Six partitioned SQLite category stores

docs/
├── technical-guide.md   Master reference (authoritative)
├── memory-guide.md      Memory system deep-dive
├── adding-skills.md     Skill implementation patterns
├── skill-inventory.md   Per-skill specs and build status
├── grok-caching-strategy.md  xAI Responses API caching details
├── self-improvement-system.md  Improvement scanner architecture
└── cron-config.md       Background task registry
```

---

## 4. Three SQLite Databases

| Database | Path | Purpose |
|---|---|---|
| Session state | `data/state/ezra.db` | LangGraph checkpointer, per-turn conversation state |
| Long-term memory | `data/memory/boluses.db` | BolusStore: boluses, boluses_fts, token_log, conflicts, documents |
| Knowledge stores | `data/knowledge/<category>.db` (6 files) | Partitioned knowledge by category |

Harvester scanners access `boluses.db` and `ezra.db` directly via sqlite3 (read-only). SQLite WAL mode allows safe concurrent reads.

---

## 5. Memory System Invariants

These are load-bearing. Violating any of them corrupts retrieval quality or crashes Ezra.

1. All embeddings use `nomic-embed-text:v1.5` via Ollama. Never mix models.
2. Task prefixes: `document` at storage time, `query` at retrieval time, `clustering` for conflict detection. Wrong prefix silently degrades results.
3. Conflict detection re-embeds at check time with `clustering`. It does NOT use stored BLOB vectors.
4. `boluses_fts` is maintained by SQLite triggers. Never write to it directly.
5. `scope="project"` requires non-NULL `project`. `scope="universal"` requires NULL `project`.
6. `NullEmbedder` is for tests only — never in production paths.
7. Preferences are exempt from salience decay (stable user facts must not fade).

If your issue touches any of these, double-check before committing.

---

## 6. Skill System

**Tier 1 primitive tool** — `@tool`-decorated async function bound directly to the LLM. One bounded action per tool. Follow `skills/web_fetch/tool.py` or `skills/email/tool.py`.

**Tier 2 dispatcher workflow skill** — multi-step procedure invoked through `use_skill(skill, request)`. Follow `skills/youtube_digest/workflow.py` or `skills/research/workflow.py`.

Adding either type:
1. Create `skills/<name>/` with `__init__.py` and `tool.py` (Tier 1) or `workflow.py` (Tier 2)
2. Add tests in `tests/skills/<name>/`
3. Tier 1: import in `graphs/chat.py`, add to `TOOLS` list
4. Tier 2: add to `_DISPATCHER_SKILLS`, add routing branch in `use_skill()`, update docstring
5. Update `docs/skill-inventory.md`

Use `scripts/init_skill.py` to scaffold. Use `scripts/validate_skill.py` to verify wiring.

---

## 7. Native Improvement System (Harvester Precursor)

The native system in `src/ezra/improvements/` is Harvester's predecessor:

- `scheduler.py`: `run_improvement_loop(store, llm)` asyncio coroutine; wakes every 12 hours; rotates through `skill_gaps → memory → tokens`; domain rotation based on most-overdue wins; state in `data/improvement-state.json`
- `writer.py`: `write_improvement_story(finding)` — formats finding to Markdown, writes to `tasks/improvements/active/IMP-*.md`, fires Telegram notification
- `scanners/skill_gaps.py`, `scanners/memory.py`, `scanners/tokens.py` — the three domain scanners

**Do not modify this system.** It runs in parallel with Harvester during the dual-run period. Removal happens in F02-S05 after 30 days of stable Harvester operation.

---

## 8. Test Strategy

Run `uv run pytest` for the full suite. `uv run pytest tests/path/to/file.py -x` for a single file.

Test locations:
- Skills: `tests/skills/<name>/test_tool.py`
- Memory: `tests/memory/test_<area>.py`
- Routes: `tests/routes/test_<area>.py`

Tests must pass before committing. Never `@pytest.mark.skip` a failing test to get a green run.

---

## 9. The Harvester-Ezra Dispatch Interface

When Harvester dispatches an agent to an Ezra issue:

1. A Harvester scanner reads Ezra's database files directly from `local_path` — not via Ezra's API
2. Scanner produces a `Finding`; `writer.py` creates a GitHub issue in `hackstert/ezra-assistant`
3. HacksterT applies `agent-ready`
4. Harvester's `agent-runner.sh` clones a fresh workspace, reads the issue body and Ezra's `CLAUDE.md`, invokes `claude --task-file /tmp/task.md --max-turns 50`
5. You implement the changes, run tests, commit, exit
6. Runner pushes branch, opens draft PR

The issue body is your complete task specification. Satisfy the Acceptance Criteria and stop.

**Issue body format:**
```
## Summary
## Evidence
## Acceptance Criteria (checkboxes — your definition of done)
## Tasks (suggested path — criteria win if conflict)
---
Repo: / Scanner: / Domain: / Priority: / Generated:
```

---

## 10. Commit and PR Conventions

```
<type>: <short description>

<body — why, not just what>

Closes #<issue number>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`. Draft PR by default. Do not mark ready for review.

PR body must include: what changed (file-level), how verified, decisions not in the issue, follow-up work deferred, `Closes #N`.

---

## 11. What Not To Do in Ezra

- Do not add LLM providers (Anthropic, OpenAI, etc.)
- Do not modify `src/ezra/improvements/` — Harvester reads these scanners' output patterns
- Do not delete `tasks/completed/` or `tasks/improvements/completed/` entries
- Do not commit `.env` files or secrets
- Do not merge your own PR

---

## 12. Related Files

| File | Purpose |
|---|---|
| `~/Projects/ezra-assistant/CLAUDE.md` | Authoritative agent operating guide — read first |
| `~/Projects/ezra-assistant/docs/technical-guide.md` | Full architecture reference |
| `~/Projects/ezra-assistant/docs/memory-guide.md` | Memory system deep-dive |
| `~/Projects/ezra-assistant/docs/adding-skills.md` | Skill implementation patterns |
| `~/Projects/ezra-assistant/docs/skill-inventory.md` | All skills catalogued with build status |
| `~/Projects/ezra-assistant/docs/self-improvement-system.md` | Improvement scanner architecture |
| `~/Projects/harvester/tasks/F01-harvester-core.md` | Harvester feature canvas — Ezra integration |
| `~/Projects/harvester/tasks/F02-S05-remove-ezra-native.md` | Cleanup story (30-day gate) |

---

*Maintained in: `~/Projects/harvester/docs/ezra-technical-guide.md`*
*Confirmed against: `~/Projects/ezra-assistant/docs/technical-guide.md` (April 2026)*
*Update this file when Ezra's architecture changes substantially.*
