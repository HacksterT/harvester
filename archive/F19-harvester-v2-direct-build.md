---
type: feature-canvas
feature: F19
title: Harvester — Improvement-as-a-Service for Personal Repos
version: 2.0 (direct-build)
created: 2026-04-18
status: proposed
priority: should-have
domain: infrastructure
depends_on: []
supersedes: F18 (absorbed into F19-S02)
---

# F19: Harvester — Improvement-as-a-Service

**Owner:** HacksterT
**Context:** Standalone microservice for autonomous repository improvement, built greenfield without an Ezra-internal predecessor.
**Decision rationale:** The architectural target is clear (standalone service watching multiple repos). Building inside Ezra first and extracting later incurs migration cost without corresponding derisking benefit. Going direct.

---

## Name Rationale

**Harvester** — gathers signal from codebases, proposes improvements, harvests overnight work as morning PRs. Ministry-adjacent without being religious; descriptive, memorable, distinct from Ezra, Selah, and Voice of Repentance. The name describes a role, not a brand.

---

## Purpose

Build a standalone long-lived service on HacksterT's Mac that:

1. Observes multiple personal repositories on a configurable schedule
2. Runs scanners against each repo to detect improvement opportunities
3. Creates GitHub Issues for high-value findings
4. Executes human-approved improvements overnight via Claude Code (subscription-authenticated)
5. Produces draft Pull Requests for morning review

Harvester is infrastructure. It has no chat interface, no AI personality, no user model. It's a cron daemon with a minimal HTTP surface for operational visibility. It runs for months without attention and produces work that HacksterT reviews and merges.

---

## Design Principles

**One service, many repos, zero tenant coupling.** Harvester is single-user infrastructure that happens to watch multiple repos. Do not introduce tenancy, user models, access control, or abstractions that imply multiple humans being served.

**Configuration is a file.** Harvester's behavior is defined in `harvester-config.yaml`. No database of configuration, no admin UI. Editing the YAML is how you change behavior.

**Scanners are importable modules, not plugins.** Each scanner is a Python module the config references by name. No dynamic loading, no plugin discovery, no manifest systems.

**Boring infrastructure is the goal.** No LangGraph, no LangChain, no framework larger than the service itself. Harvester is a cron daemon, not a platform. If it ever starts feeling Ezra-shaped, that's drift.

**Human gates are sacred.** Triage (apply `agent-ready` label) and judgment (PR review) are the only mandatory human steps. Everything else is automatic. These gates are non-negotiable and cannot be configured away.

**Reversibility over speed.** Every automated action is undoable. Issues without merged PRs stay open indefinitely. PRs can be closed without merging. Merges can be reverted. The system favors slow-and-undoable over fast-and-permanent.

---

## Scope

**In scope:**

- Multi-repo observation and improvement for personal codebases (Ezra, Selah, Voice of Repentance, future)
- Overnight execution on HacksterT's Mac using Claude Code with subscription authentication
- Per-repo scanner configuration with independent cadences
- Guarded-path protection for theologically-significant content in Selah
- Minimal web UI on `localhost:8500` for operational visibility
- Telegram notifications for findings, runs, and failures
- GitHub Issues as the durable work queue

**Out of scope:**

- AI Labor Solutions productization, multi-tenant architecture, client-facing workflows
- High-stakes domains (finance, clinical production systems, safety-critical code)
- Public-repo automation (all watched repos stay private)
- Chat interface, AI persona, or any conversational surface
- Automatic merge or auto-deploy — human approval is mandatory
- Multi-agent orchestration, parallel agent execution, complex workflow DAGs

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Harvester Service (your Mac, always on)                    │
│  ~/Projects/harvester/                                      │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Config loader (PyYAML + pydantic validation)         │ │
│  │  harvester-config.yaml → RepoConfig[] at startup      │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Scanner scheduler (asyncio loop, hourly tick)        │ │
│  │  per-(repo, scanner) cadence tracking                 │ │
│  │  state in data/harvester-state.json                   │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Scanners (importable modules, common contract)       │ │
│  │  scanners/code_health.py                              │ │
│  │  scanners/skill_gaps.py                               │ │
│  │  scanners/memory_health.py                            │ │
│  │  scanners/token_economics.py                          │ │
│  │  scanners/dependency_freshness.py                     │ │
│  │  scanners/test_coverage.py                            │ │
│  │  scanners/theology_review.py        (Selah)           │ │
│  │  scanners/content_gap.py            (VoR)             │ │
│  │  scanners/cross_repo_patterns.py    (meta)            │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  GitHub client (PyGithub)                             │ │
│  │  issue creation, label management, webhook handler    │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  FastAPI server on port 8500                          │ │
│  │  POST /webhook — signed GitHub events                 │ │
│  │  GET  /        — minimal web UI                       │ │
│  │  GET  /healthz — liveness for Ezra cross-monitoring   │ │
│  │  GET  /api/*   — queue, findings, repos, runs         │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Queue (directory-based, JSON files)                  │ │
│  │  data/queue/pending/    — awaiting overnight run      │ │
│  │  data/queue/completed/  — successfully processed      │ │
│  │  data/queue/failed/     — errored, awaiting review    │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Agent runner (scripts/agent-runner.sh)               │ │
│  │  invoked by launchd at 02:00 local time               │ │
│  │  drains queue, invokes Claude Code per item           │ │
│  │  uses subscription login (no API key)                 │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

      creates issues                    receives webhooks
           │                                    ▲
           ▼                                    │
┌─────────────────────────────────────────────────────────────┐
│  GitHub (cloud)                                             │
│  hackstert/ezra-assistant                                   │
│  hackstert/selah                                            │
│  hackstert/voice-of-repentance                              │
└─────────────────────────────────────────────────────────────┘

      clones/commits to local workspaces
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│  ~/agent-workspaces/ (gitignored, ephemeral per run)       │
│  ezra-assistant-47/    — one workspace per issue           │
│  selah-12/                                                  │
│  voice-of-repentance-3/                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## The Contract Between Service and GitHub

Since Harvester and the overnight agent communicate only through GitHub, the contract is a structured markdown format for issues and PRs. This section defines it.

### Issue Format (Harvester writes, overnight agent reads)

```markdown
Title: [IMPROVEMENT] <finding title>

## Summary
<2-3 sentence description>

## Evidence
<raw metrics and observations that motivated the finding>

## Acceptance Criteria
- [ ] <criterion 1>
- [ ] <criterion 2>

## Tasks
- [ ] <concrete task 1>
- [ ] <concrete task 2>

---
**Repo:** <github/repo>
**Scanner:** <scanner_name>
**Domain:** <domain>
**Priority:** <must-have|should-have|nice-to-have>
**Generated:** <timestamp> by Harvester

Labels: improvement, scanner:<name>, priority:<level>
```

### PR Format (overnight agent writes, Harvester reads)

```markdown
Title: Closes #<N>: <issue title>

## What changed
- <file>: <summary>
- <file>: <summary>

## Plan followed
<brief explanation of the agent's approach>

## Testing
- [x] Existing tests pass
- [x] New tests added where appropriate
- [x] Manual verification: <specifics>

## Follow-up noted
<any adjacent work the agent identified but did not do>

Closes #<N>
```

The `Closes #N` syntax is what causes GitHub to auto-close the issue on merge, which fires the `issues.closed` webhook, which tells Harvester to move the queue item to `completed/`.

---

## Repository Configuration

`harvester-config.yaml` is the single source of truth for Harvester's behavior.

```yaml
global:
  queue_path: data/queue
  state_path: data/harvester-state.json
  workspaces_path: ~/agent-workspaces
  findings_log_path: data/findings
  run_logs_path: data/logs
  default_max_turns: 50
  default_timeout_minutes: 30
  scheduler_tick_seconds: 3600       # Hourly check for overdue scanners
  agent_run_time: "02:00"            # Local time for launchd schedule
  telegram_chat_id: ${TELEGRAM_ALLOWED_CHAT_ID}
  webhook_port: 8500
  claude_code_auth: subscription     # subscription | api
  # If claude_code_auth=api, expect ANTHROPIC_API_KEY in env

repos:
  - name: ezra-assistant
    github: hackstert/ezra-assistant
    local_path: ~/Projects/ezra-assistant
    claude_md_path: CLAUDE.md
    scanners:
      - name: code_health
        cadence_days: 7
      - name: skill_gaps
        cadence_days: 9
      - name: memory_health
        cadence_days: 9
      - name: token_economics
        cadence_days: 9
      - name: dependency_freshness
        cadence_days: 30
      - name: test_coverage
        cadence_days: 14
    label_prefix: improvement
    priority_labels: [must-have, should-have, nice-to-have]
    guarded_paths: []
    min_reviewers_on_merge: 1
    branch_prefix: improvement/
    draft_pr_default: true

  - name: selah
    github: hackstert/selah
    local_path: ~/Projects/selah
    claude_md_path: CLAUDE.md
    scanners:
      - name: code_health
        cadence_days: 14
      - name: theology_review
        cadence_days: 30
      - name: prompt_quality
        cadence_days: 14
      - name: training_data_hygiene
        cadence_days: 30
      - name: dependency_freshness
        cadence_days: 30
    label_prefix: improvement
    priority_labels: [must-have, should-have, nice-to-have]
    guarded_paths:
      - "theology/**"
      - "training/**"
      - "prompts/**"
      - "doctrine/**"
    guarded_path_policy: never_execute    # scanner findings touching these paths are flagged, not automated
    min_reviewers_on_merge: 1
    extra_labels_on_guarded: [theological-review-required]
    telegram_flag_on_guarded: true
    branch_prefix: improvement/
    draft_pr_default: true

  - name: voice-of-repentance
    github: hackstert/voice-of-repentance
    local_path: ~/Projects/voice-of-repentance
    claude_md_path: CLAUDE.md
    scanners:
      - name: code_health
        cadence_days: 14
      - name: content_gap
        cadence_days: 14
    label_prefix: improvement
    priority_labels: [must-have, should-have, nice-to-have]
    guarded_paths:
      - "content/original-songs/**"
    min_reviewers_on_merge: 1
    branch_prefix: improvement/
    draft_pr_default: true
```

Adding a new repo: append an entry, restart Harvester. Config validation runs on startup and refuses to start with a malformed file.

---

## The Scanner Contract

All scanners implement one async function:

```python
async def scan(
    repo_config: RepoConfig,
    llm: LLMClient,
    context: ScanContext,
) -> Finding | None:
    """
    Analyze this repo and return one high-value finding, or None.

    repo_config — full config entry for the repo being scanned
    llm — LLM client (Grok by default, configurable per scanner)
    context — prior findings, scanner history, current state
    """
```

The `Finding` structure:

```python
@dataclass
class Finding:
    repo: str              # "hackstert/ezra-assistant"
    scanner: str           # "token_economics"
    domain: str            # "tokens"
    title: str
    summary: str
    evidence: str
    criteria: list[str]
    tasks: list[str]
    priority: Literal["must-have", "should-have", "nice-to-have"]
    touches_guarded_paths: bool = False
    metadata: dict = field(default_factory=dict)
```

Scanners are pure: they do not create issues, write files, or send notifications. They return structured data. The framework handles side effects. Scanners are testable in isolation — call `scan()` with mock data, assert on the returned Finding.

---

## Stories

### F19-S01: Repository Bootstrap and Scaffolding

**Priority:** must-have
**Dependencies:** none
**Estimated effort:** 2-3 sessions

Create `hackstert/harvester` repository with complete project scaffolding.

**Structure:**

```
harvester/
├── src/harvester/
│   ├── __init__.py
│   ├── __main__.py              # CLI entry: `python -m harvester`
│   ├── main.py                  # FastAPI app + lifespan
│   ├── config.py                # RepoConfig, GlobalConfig via pydantic
│   ├── scheduler.py             # Main asyncio loop, cadence logic
│   ├── queue.py                 # Directory-based queue operations
│   ├── github_client.py         # PyGithub wrapper
│   ├── webhook.py               # Webhook handler + signature verify
│   ├── writer.py                # Finding → issue + local log
│   ├── runner.py                # Invoked by agent-runner.sh
│   ├── models.py                # Finding, Scan Context, RunResult
│   ├── llm.py                   # Grok + Ollama + optional Claude client
│   ├── ui/
│   │   ├── app.py              # FastAPI routes for web UI
│   │   └── templates/          # Minimal Jinja templates
│   └── scanners/
│       ├── __init__.py
│       └── base.py              # Scanner protocol + helpers
├── scripts/
│   ├── agent-runner.sh
│   ├── install-launchd.sh
│   └── validate-config.py
├── data/                        # gitignored
│   ├── queue/{pending,completed,failed}/
│   ├── logs/
│   └── findings/
├── tests/
│   └── ...
├── harvester-config.yaml        # Initial config with ezra-assistant only
├── CLAUDE.md                    # System prompt for agents working on Harvester itself
├── README.md
├── pyproject.toml
└── .gitignore
```

**Dependencies in `pyproject.toml`:**

Minimum viable set — keep this list small.

```toml
[project]
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "PyYAML>=6.0",
    "PyGithub>=2.4",
    "click>=8.1",
    "httpx>=0.27",
    "python-telegram-bot>=21.6",
    "jinja2>=3.1",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "ruff>=0.7",
    "mypy>=1.11",
]
```

Notably absent: LangGraph, LangChain, any agent framework, any vector DB, any embedding library. Harvester has no memory, no graph, no agent state. It schedules things and talks to GitHub.

**CLI entry:**

```bash
python -m harvester serve              # starts FastAPI server + scheduler
python -m harvester validate           # validates config file
python -m harvester scan <repo> <scanner>   # run one scanner on-demand
python -m harvester queue list         # list queue contents
python -m harvester queue clear failed  # clear failed items after review
```

**Acceptance criteria:**

- [ ] Repository created at `hackstert/harvester`
- [ ] Project structure matches specification
- [ ] `uv sync` produces a working environment
- [ ] `python -m harvester validate` validates a correct config
- [ ] `python -m harvester validate` rejects a malformed config with helpful error
- [ ] `python -m harvester serve` starts and logs "Harvester ready" with no errors
- [ ] Web UI at `http://localhost:8500/` renders empty state (no repos yet reporting)
- [ ] CLAUDE.md drafted and accurate for the Harvester codebase itself
- [ ] README explains the service's purpose, install, and config

---

### F19-S02: GitHub Integration Layer

**Priority:** must-have
**Dependencies:** F19-S01
**Estimated effort:** 3-4 sessions

Implement the complete GitHub integration: issue creation, label management, webhook handling, and signature verification. This is the foundation everything else sits on.

**Components:**

**`github_client.py`:**

```python
class GitHubClient:
    async def create_issue(
        self,
        repo: str,
        title: str,
        body: str,
        labels: list[str],
        assignees: list[str] | None = None,
    ) -> Issue

    async def get_issue(self, repo: str, number: int) -> Issue
    async def list_issues(self, repo: str, state: str, labels: list[str]) -> list[Issue]
    async def close_issue(self, repo: str, number: int, reason: str = "completed") -> None
    async def comment_on_issue(self, repo: str, number: int, body: str) -> None
    async def apply_labels(self, repo: str, number: int, labels: list[str]) -> None
    async def ensure_labels_exist(self, repo: str, labels: list[LabelSpec]) -> None
```

All methods are async, all use PyGithub under the hood, all handle rate limiting with exponential backoff.

**`webhook.py`:**

- FastAPI route `POST /webhook`
- Signature verification via `X-Hub-Signature-256` header and `GITHUB_WEBHOOK_SECRET`
- Event dispatch: `issues.labeled` → enqueue; `issues.closed` → complete; `pull_request.opened` → record; `pull_request.closed` (merged) → record
- Rejects unsigned requests with 401
- Logs every event received for audit

**Webhook exposure:**

Cloudflare Tunnel on your Mac at `harvester.<your-domain>`. Configuration documented in README. This is infrastructure you already have from LAN-Central-Command.

**Label taxonomy (auto-created per repo on startup):**

```
improvement              — all scanner-generated issues
scanner:<name>           — which scanner produced it
domain:<value>           — tokens | memory | skills | code | theology | content
priority:must-have       — stack-ranked priority
priority:should-have
priority:nice-to-have
status:triage            — default for new issues
agent-ready              — applied by human to trigger overnight run
status:blocked           — pauses any agent work
theological-review-required  — Selah guarded-path flag
```

**Acceptance criteria:**

- [ ] `GitHubClient` supports all listed operations
- [ ] Rate limiting handled gracefully with backoff
- [ ] Webhook endpoint verifies signatures correctly
- [ ] Unsigned webhook requests rejected with 401
- [ ] Label taxonomy auto-created on Harvester startup for each configured repo
- [ ] Issue creation tested end-to-end against real `hackstert/ezra-assistant` repo
- [ ] Webhook receiving tested via GitHub's "Redeliver" feature on a test event
- [ ] Cloudflare Tunnel configuration documented

---

### F19-S03: Scheduler and Queue System

**Priority:** must-have
**Dependencies:** F19-S01
**Estimated effort:** 2-3 sessions

Build the per-(repo, scanner) scheduler and the directory-based queue.

**Scheduler:**

- Runs as asyncio task inside the FastAPI lifespan
- Wakes every hour (configurable via `scheduler_tick_seconds`)
- Iterates all (repo, scanner) pairs from config
- For each pair: checks `harvester-state.json` for `last_run`; if `now - last_run > cadence_days`, schedules a scan
- Runs scans one at a time (no concurrency) to avoid LLM rate issues
- Updates state file after each scan, success or failure
- Consecutive `None` results increment a `consecutive_skips` counter; at 3 skips, emits a Telegram note suggesting cadence review

**Queue:**

Directory structure:

```
data/queue/
├── pending/      # Enqueued by webhook, awaiting run
├── completed/    # Agent run succeeded, PR merged
└── failed/       # Something went wrong
```

Each queue item is a JSON file named `<repo-name>-<issue-num>.json`:

```json
{
  "issue_number": 47,
  "repo": "hackstert/ezra-assistant",
  "repo_name": "ezra-assistant",
  "repo_local_path": "~/Projects/ezra-assistant",
  "issue_title": "Reduce repeated system prompt via previous_response_id caching",
  "issue_url": "https://github.com/hackstert/ezra-assistant/issues/47",
  "enqueued_at": "2026-04-25T14:32:11Z",
  "agent_config": {
    "claude_code_auth": "subscription",
    "max_turns": 50,
    "timeout_minutes": 30,
    "claude_md_path": "CLAUDE.md"
  },
  "guarded_check": {
    "required": false,
    "paths": []
  }
}
```

Directory-based queues are intentional: trivially inspectable (`ls`), safe across restarts, don't need a separate database.

**Enqueue logic:**

The webhook handler enqueues on `issues.labeled` with `label.name == "agent-ready"`. It reads the issue's labels to determine repo-specific policies, checks guarded-path policy if applicable, and writes the JSON file. If the issue's body (or scanner metadata) indicates guarded paths and the repo's `guarded_path_policy` is `never_execute`, enqueue is refused with a comment on the issue explaining why.

**Drain logic:**

The agent runner script (F19-S05) reads items from `pending/`, processes one at a time, moves to `completed/` or `failed/` based on outcome.

**Acceptance criteria:**

- [ ] Scheduler wakes hourly and correctly identifies overdue (repo, scanner) pairs
- [ ] State file is read on startup and written after each scan
- [ ] Consecutive-skips counter works; Telegram note fires at 3
- [ ] Queue items are written atomically (write to `.tmp`, then rename)
- [ ] Guarded-path enqueue refusal tested with a mock finding
- [ ] Queue directories created on startup if missing
- [ ] `python -m harvester queue list` shows accurate state

---

### F19-S04: Port F15 Scanners as Harvester Modules

**Priority:** must-have
**Dependencies:** F19-S03
**Estimated effort:** 3-4 sessions

Port the three existing F15 scanners (`skill_gaps`, `memory_health`, `token_economics`) from Ezra's `src/ezra/improvements/scanners/` into Harvester's `src/harvester/scanners/` with the new signature.

**Key adaptations:**

- Scanners no longer receive a `BolusStore` instance or any Ezra internals
- Instead, they receive `RepoConfig` and access Ezra's state by reading files from `repo_config.local_path` — specifically `data/memory/boluses.db`, `data/state/ezra.db`, and `data/improvement-state.json`
- LLM access via a Harvester-owned `LLMClient` that wraps Grok (default), Ollama, or Claude based on scanner declaration
- Logging via Harvester's logger, not Ezra's

**Original Ezra scanners stay in place during F19 development.** Removal happens in F19-S11 after Harvester proves stable.

**Finding output unchanged** — the dict contract matches the new `Finding` dataclass. The framework writes issues; the scanner only returns data.

**Test strategy:**

- Unit tests with mock repo config and mock LLM
- Integration test: point Harvester at a local Ezra checkout, run each scanner, verify it produces a valid Finding
- One end-to-end test per scanner: run → finding → GitHub issue created → issue visible in `hackstert/ezra-assistant`

**Acceptance criteria:**

- [ ] All three scanners ported with updated signatures
- [ ] Unit tests pass
- [ ] Integration tests pass against a real local Ezra repo
- [ ] Each scanner produces at least one real GitHub issue during development
- [ ] Original Ezra scanners still functional (no breaking changes to Ezra)
- [ ] `scanners/README.md` documents the contract and how to add new scanners

---

### F19-S05: Agent Runner with Subscription Authentication

**Priority:** must-have
**Dependencies:** F19-S03, F19-S04
**Estimated effort:** 3-4 sessions

The overnight agent runner. This is the single most operationally important piece of Harvester — it's what turns approved issues into PRs.

**File: `scripts/agent-runner.sh`**

Bash script that runs the full drain cycle. Invoked by launchd at `agent_run_time` (default 02:00 local).

Responsibilities:

1. Preflight: verify `claude` command is on PATH, verify `gh` CLI is authenticated, verify subscription session is live (`claude --version` returns without auth error)
2. Iterate `data/queue/pending/*.json` in oldest-first order
3. For each item:
    - Prepare workspace: `~/agent-workspaces/<repo-name>-<issue-num>/`
    - Fresh clone or hard reset to origin/main
    - Check out new branch per `branch_prefix` from config
    - Fetch issue body via `gh issue view`
    - Build task spec combining issue body and repo's `CLAUDE.md`
    - Invoke `claude --task-file /tmp/task.md --max-turns <N>`
    - On success: push branch, `gh pr create --draft --title "Closes #N: ..."`
    - On failure: comment on issue with log location
    - Move queue item to `completed/` or `failed/`
4. Post-run: Telegram summary (N succeeded, M failed)

**Guarded-path enforcement (second layer):**

Before pushing, the runner computes the diff of changed files. If any changed file matches a guarded path from the repo's config and the repo's policy is `never_execute`, the run is aborted:

- Branch is deleted locally
- Queue item moves to `failed/` with reason `guarded_path_violation`
- Issue receives a comment: "Agent run aborted — proposed changes touched guarded paths. Manual implementation required."
- Loud Telegram alert fires (this shouldn't happen; if it does, it's a Selah incident)

**The third layer of guarded-path protection** is GitHub branch protection rules. Configure these once per repo, not Harvester's job to maintain them.

**Subscription session health:**

Claude Code's subscription session can expire after long inactivity. Mitigations:

- Preflight checks session and exits early with Telegram alert if stale
- Weekly calendar reminder (in Apple Calendar via Ezra) to run `claude` interactively to refresh session
- When session is refreshed, that's your cue to also review any queued items that failed from stale-auth

**launchd integration:**

`scripts/install-launchd.sh` writes `~/Library/LaunchAgents/com.hackstert.harvester.plist` and loads it. The plist specifies:

- `StartCalendarInterval` → 02:00 local time
- `ProgramArguments` → `[bash, /path/to/agent-runner.sh]`
- `StandardOutPath` + `StandardErrorPath` → Harvester's logs dir
- `EnvironmentVariables` → `PATH` that includes Homebrew, `gh`, `claude`

**Acceptance criteria:**

- [ ] `agent-runner.sh` drains queue correctly
- [ ] Fresh workspace per run, no state leaks between runs
- [ ] Subscription auth preflight works, fails loudly on stale auth
- [ ] Guarded-path enforcement tested with a mock violation
- [ ] launchd installation script works
- [ ] One full end-to-end cycle completed on a real Ezra issue: finding → issue → label → enqueue → overnight run → PR → review → merge → complete
- [ ] Failed-run path tested: injected failure produces clean `failed/` state + issue comment
- [ ] Telegram summary fires at end of each run

---

### F19-S06: Webhook-Driven State Synchronization

**Priority:** must-have
**Dependencies:** F19-S02, F19-S03, F19-S05
**Estimated effort:** 2 sessions

Complete the webhook handler's behavior so Harvester's local state stays synchronized with GitHub state.

**Events handled:**

| Event | Action |
|---|---|
| `issues.labeled` (agent-ready) | Enqueue work item |
| `issues.closed` (via PR merge) | Move queue item to `completed/`, log to findings |
| `issues.closed` (manual, no merge) | Move queue item to `rejected/` (new folder), log reason |
| `pull_request.opened` | Record PR URL in local findings log |
| `pull_request.closed` (merged) | Record successful cycle, update metrics |
| `pull_request.closed` (not merged) | Record rejected cycle, flag for pattern miner |
| `issue_comment.created` | If commenter is not HacksterT, forward to Telegram |

**New folder: `data/queue/rejected/`** — issues closed without a merged PR. Preserved for the cross-repo pattern scanner (F19-S10) to mine for signal.

**Reconciliation on startup:**

On every Harvester restart, the scheduler runs a reconciliation pass:

- Lists GitHub issues with `label:improvement` in each repo
- Lists queue items in `pending/` + `completed/` + `failed/`
- Identifies drift: issues closed on GitHub but still in `pending/`, issues with no corresponding queue item, etc.
- Logs drift to Telegram with counts, does not auto-resolve
- CLI command `python -m harvester reconcile --apply` resolves drift manually

**Acceptance criteria:**

- [ ] All listed event types handled correctly
- [ ] `rejected/` folder created when needed
- [ ] Reconciliation logic accurate, tested with seeded drift
- [ ] `reconcile --apply` works idempotently
- [ ] Telegram drift notifications fire on Harvester startup

---

### F19-S07: Minimal Web UI

**Priority:** should-have
**Dependencies:** F19-S03
**Estimated effort:** 2-3 sessions

Operational visibility at `http://localhost:8500/`. Not pretty; functional. You need this at 2am when something broke.

**Pages:**

**`/` — Dashboard:**

- Repo list with status per scanner (last run, next expected, consecutive skips)
- Queue summary (pending/completed/failed counts for last 7 days)
- Recent findings (last 10, with link to GitHub issue)
- Recent runs (last 10 agent executions with outcome and duration)
- Failed items (with log links)
- System health (disk, memory, Ollama connectivity, Claude Code auth status)

**`/repos/<name>` — Repo detail:**

- Per-scanner cadence settings and history
- Issues created, grouped by scanner
- Recent PRs produced
- Guarded-path violations (should always be zero)

**`/scanners/<name>` — Scanner detail:**

- Runs across all repos
- Findings produced (recent)
- Skip history (useful when deciding whether to retire a scanner)
- Button: "Rescan now on <repo>" (bypasses cadence)

**`/queue` — Queue detail:**

- All three folders as tables
- Click to view queue item JSON
- Button: "Retry" for failed items (moves back to `pending/`)

**`/logs/<run-id>` — Run log viewer:**

- Renders the log file for a specific run
- Monospace, scrollable

**Auth:**

None. Localhost-only. Not exposed beyond your Mac.

**Framework:**

Server-rendered Jinja templates. No SPA. No React. Pages render in <100ms with no JavaScript. Simple to maintain, works even when you're tired.

**Acceptance criteria:**

- [ ] All pages render with real data
- [ ] "Rescan now" bypasses cadence correctly
- [ ] "Retry" moves failed items back to pending
- [ ] Log viewer handles logs up to a few MB without browser issues
- [ ] Localhost-only binding verified (not accessible from other machines on LAN without explicit tunneling)

---

### F19-S08: Selah Theology Review Scanner and Guardrails

**Priority:** should-have
**Dependencies:** F19-S04, F19-S05, Selah repo having initial content
**Estimated effort:** 3-4 sessions

A Selah-specific scanner that examines theological content for consistency, completeness, and doctrinal alignment. Unlike other scanners, this one is explicitly non-actionable — it produces findings as review requests, not change proposals.

**What it examines:**

- Prompts under `selah/prompts/` for Nicene Creed alignment
- Training data samples for doctrinal consistency (sampling, not exhaustive)
- Denominational configuration for orthodoxy boundaries
- Recent commits touching theological paths

**What it produces:**

Findings framed as "flag for human review," never as "make this change." The issue body explicitly states:

> This finding is a request for theological review, not a proposal for automated change. The agent runner will not execute changes to guarded paths in this repo. HacksterT's manual review and implementation are required.

Priority defaults to `must-have`. Labels include `theological-review-required`.

**Guardrail defense in depth (three layers):**

1. **Scanner layer:** The scanner's output format makes change-oriented findings impossible by construction for guarded paths. It can only produce review-request findings for theological content. Code-quality findings about the Selah repo (which are fine to automate) come from other scanners like `code_health`, not from `theology_review`.

2. **Enqueue layer:** Harvester's enqueue logic (F19-S03) checks the finding's `touches_guarded_paths` flag and the repo's `guarded_path_policy`. If policy is `never_execute`, enqueue is refused with a comment explaining.

3. **Runner layer:** Even if an issue somehow made it through enqueue, the agent runner (F19-S05) computes the diff before pushing and refuses to proceed if any changed file matches a guarded path.

If all three layers failed simultaneously, GitHub branch protection would still require human review before merge. Four layers total. For theologically-significant content, this is appropriate discipline.

**Acceptance criteria:**

- [ ] `scanners/theology_review.py` implements the contract
- [ ] All output framed as review requests, not change proposals
- [ ] `touches_guarded_paths` flag set correctly when finding references theological content
- [ ] Three-layer defense tested: each layer independently refuses a mock violation
- [ ] Documented clearly in `docs/selah-guardrails.md`
- [ ] First real finding reviewed and approved (manually implemented, not via agent)

---

### F19-S09: Generic Code Health Scanner

**Priority:** should-have
**Dependencies:** F19-S04
**Estimated effort:** 2-3 sessions

A scanner applicable to any repo. Runs static analysis and produces findings for:

- Files over a size threshold (candidates for decomposition)
- TODO/FIXME comments older than 30 days
- Functions with cyclomatic complexity above a threshold
- Missing type hints in public APIs
- Dead code (imports with no uses, unreferenced functions)
- Test coverage gaps by module

Uses off-the-shelf tools where possible: `ruff`, `mypy`, `coverage.py`, `radon`. The scanner invokes these as subprocesses, parses output, and formulates a finding.

Ships with sensible defaults. Thresholds overridable per repo via config:

```yaml
- name: code_health
  cadence_days: 7
  thresholds:
    max_file_lines: 400
    max_function_complexity: 10
    min_coverage_pct: 80
    todo_staleness_days: 30
```

**Acceptance criteria:**

- [ ] Runs against all three personal repos
- [ ] Produces a Finding dict matching the contract
- [ ] Thresholds configurable per repo
- [ ] Tests cover static analysis parsing
- [ ] Three real findings produced and reviewed during development

---

### F19-S10: Cross-Repo Pattern Scanner

**Priority:** nice-to-have
**Dependencies:** F19-S04, F19-S08, F19-S09, 30+ closed issues across all repos
**Estimated effort:** 2-3 sessions

Once enough history accumulates, add a scanner that mines the cross-repo corpus for patterns. Refinement of the self-annealing loop.

**What it reads:**

- All closed issues labeled `improvement` across all repos from the last 90 days
- Their linked PRs (merged vs. not)
- Rejection reasons for issues closed without merge
- Run logs for any failed or slow runs

**What it produces:**

- "Pattern: the `dependency_freshness` scanner has proposed the same dependency bump across 3 repos, all closed as won't-fix — retire or re-tune"
- "Pattern: Selah has had 0 merges and 4 rejections in 60 days — its scanner cadence or thresholds need review"
- "Pattern: Ezra's `token_economics` scanner proposals are being merged but no measurable cost reduction is observed — proposal quality is the bottleneck, not execution"

Runs once per month (configurable). One finding maximum per run. This scanner is the system reflecting on itself.

**Why this matters:**

This is where Harvester becomes genuinely self-annealing. The first-generation scanners have no feedback loop. F19-S10 provides the feedback. Over time, it will propose improvements to the improvement system itself — which is the original F15 canvas goal finally realized.

**Acceptance criteria:**

- [ ] Runs against all configured repos
- [ ] Gated: requires corpus > 30 closed issues
- [ ] Produces at most 1 finding per month
- [ ] First real finding reviewed and actioned

---

### F19-S11: Remove Ezra's Native Improvement System

**Priority:** should-have
**Dependencies:** F19-S01 through F19-S09 stable for 30 days
**Estimated effort:** 1 session

Once Harvester has reliably handled Ezra's improvement cycle for 30 days, remove the native improvement system from Ezra to eliminate duplication.

**What gets removed from Ezra:**

- `src/ezra/improvements/` directory entirely
- Cron registration for `improvement_scan` in `main.py`
- Related routes and UI panels in Mission Control
- `tasks/improvements/` directory (Harvester owns this concern now)

**What stays in Ezra:**

- CLAUDE.md (Harvester reads it, and it's useful for local Claude Code use)
- The github_issues skill *if* it exists as part of F18 work (but in direct-to-F19 path, it was never built in Ezra)

**Migration note:**

Before deletion, run one reconciliation pass to confirm no in-flight items. If any exist, complete them manually before removal.

**Mission Control updates:**

- Remove "Improvements" tab
- Add a link to `http://localhost:8500/` for Harvester's UI
- Update `docs/technical-guide.md` to point to Harvester for improvement-system documentation

**Acceptance criteria:**

- [ ] 30-day stable period passed with zero rejected-as-should-not-have-been-proposed findings from Harvester
- [ ] All F15/F16 code removed from Ezra in a single PR
- [ ] Ezra tests all pass after removal
- [ ] Mission Control points to Harvester UI
- [ ] Ezra docs updated to reflect the change

---

## Milestones

### M1: Working End-to-End on Ezra (6-8 weeks from start)

- F19-S01: Bootstrap
- F19-S02: GitHub integration
- F19-S03: Scheduler and queue
- F19-S04: Port F15 scanners
- F19-S05: Agent runner with subscription auth
- F19-S06: Webhook state sync
- F19-S07: Web UI

**Exit criterion:** Harvester is running continuously. Ezra scanners produce GitHub issues. Applying `agent-ready` to an issue produces a draft PR overnight. Full cycle completed at least 3 times end to end. Ezra's native improvement system still running in parallel (dual-run period).

### M2: Additional Scanners and Selah Onboarding (3-4 weeks after M1)

- F19-S08: Selah theology review + guardrails
- F19-S09: Generic code health scanner
- Selah added to `harvester-config.yaml`
- Voice of Repentance added if ready; deferred otherwise

**Exit criterion:** All three scanners (theology_review, code_health, and the ported F15 set) produce findings across the configured repos. Selah guardrails tested with a mock violation — all three defense layers refuse correctly. First real theology finding reviewed and handled manually.

### M3: Cleanup and Steady State (30 days after M2)

- F19-S11: Remove Ezra's native improvement system

**Exit criterion:** Ezra no longer contains improvement-system code. Harvester is the sole improvement mechanism for all watched repos.

### M4: Voice of Repentance Integration (when VoR is substantive)

- Content-oriented scanners added
- Custom CLAUDE.md for VoR
- VoR added to Harvester's watch list

**Exit criterion:** VoR receives at least 3 useful findings per month on average.

### M5: Self-Annealing (open-ended, corpus-triggered)

- F19-S10: Cross-repo pattern scanner

**Exit criterion:** First cross-repo pattern finding produced and either acted upon or consciously deferred.

---

## Data Locations

```
~/Projects/harvester/
├── src/                          # Source code (gitted)
├── data/                         # Operational data (gitignored)
│   ├── queue/
│   │   ├── pending/
│   │   ├── completed/
│   │   ├── failed/
│   │   └── rejected/
│   ├── findings/                 # Historical findings log (JSONL per day)
│   ├── logs/                     # Per-run logs (rotated monthly)
│   └── harvester-state.json      # Scanner rotation state
├── workspaces/                   # Agent workspaces (gitignored)
│   ├── ezra-assistant-47/
│   ├── selah-12/
│   └── voice-of-repentance-3/
└── harvester-config.yaml         # Runtime configuration (gitted)
```

Watched repos stay clean. The only thing Harvester needs from them is a `CLAUDE.md` file, which is useful for local Claude Code use regardless.

---

## Security Model

**Secret scope:**

| Secret | Location | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | `.env` | Fine-grained PAT, limited to watched repos, issues + PRs write |
| `GITHUB_WEBHOOK_SECRET` | `.env` + GitHub webhook settings | Signature verification |
| `XAI_API_KEY` | `.env` | Scanner LLM calls (default provider) |
| `OLLAMA_URL` | `.env` | Local model access (nomic, gemma2:2b, selah-q8) |
| `TELEGRAM_BOT_TOKEN` | `.env` | Notification delivery |
| `TELEGRAM_ALLOWED_CHAT_ID` | `.env` | Single allowed chat, reused from Ezra |

Notably absent: `ANTHROPIC_API_KEY`. Claude Code uses subscription login on your Mac. If you ever want to run Harvester-equivalent logic in CI (not the plan), you'd need the API key, but this canvas assumes subscription auth throughout.

**Webhook security:**

- Signature verification mandatory; unsigned requests rejected
- Exposed only via Cloudflare Tunnel; no direct port forwarding
- TLS terminated at Cloudflare edge
- Rate limiting at the Cloudflare layer if needed

**Agent workspace isolation:**

- Every run uses a fresh workspace (hard reset if exists, clone if new)
- Workspaces are gitignored from Harvester
- Workspaces never shared between runs
- If a workspace is ever in a weird state, deleting `~/agent-workspaces/` and restarting is safe

**Guarded-path enforcement:**

Four layers, enumerated earlier:

1. Scanner: can't produce change-oriented findings for guarded paths
2. Enqueue: refuses work items touching guarded paths
3. Runner: refuses to push diffs touching guarded paths
4. GitHub: branch protection requires human review for guarded paths

Each layer is independently effective. Any one of them should prevent a violation. All four together make it virtually impossible.

---

## Cross-Monitoring with Ezra

Ezra and Harvester are both long-lived services on the same Mac. They should cross-monitor:

**Ezra pings Harvester:**

- Hourly HTTP GET to `http://localhost:8500/healthz`
- If unreachable for 3+ consecutive hours, Ezra sends Telegram alert: "Harvester unreachable since <time>"
- Ezra does not attempt to restart Harvester; restart is a human decision

**Harvester pings Ezra:**

- Hourly HTTP GET to `http://localhost:8400/api/status`
- If Ezra is unreachable, some scanners (specifically the ported F15 set that read Ezra's databases) will skip their runs — Ezra's state may be stale or inconsistent if the process is down
- Telegram alert if Ezra is unreachable for 3+ hours

This is lightweight mutual awareness, not a health-checking framework. Both services exit gracefully if the other is missing.

---

## Observability

| Channel | What you see |
|---|---|
| Harvester web UI (`localhost:8500`) | Real-time queue, findings, runs, failures |
| Telegram | Findings created, runs completed, failures, drift alerts |
| GitHub | Issues, PRs, merge history per repo |
| GitHub Actions (unused) | No Actions in this architecture |
| Logs (`data/logs/`) | Per-run detail with stdout/stderr |
| Cloudflare Analytics | Webhook traffic patterns if you care |

For a solo operator, this is complete visibility. You can be on your phone and see the full state of the improvement loop across all repos in under a minute.

---

## Risks and Mitigations

**Claude Code subscription session expires.** Mitigations: preflight check before each run, loud Telegram alert on stale auth, weekly calendar reminder to refresh manually.

**Scanner produces nonsense findings, floods GitHub with noise.** Mitigations: consecutive-skips counter flags scanners that aren't producing value; cross-repo pattern scanner eventually surfaces over-triggering as its own finding; manual cadence tuning in config.

**A guarded-path change slips through.** Four-layer defense makes this nearly impossible. If it ever happens, it's a Selah incident: immediate review of all four layers, investigation of how it got through, likely requires a canvas for remediation.

**Harvester crashes and nobody notices.** Ezra cross-monitoring alerts within 3 hours.

**Dependency sprawl in Harvester.** Quarterly review of `pyproject.toml`; the bar for adding a new dependency is high and explicit. If in doubt, keep using the standard library.

**Cloudflare Tunnel goes down.** Webhook events queue up at GitHub and retry. You may miss some real-time state sync. Reconciliation on restart catches everything that was missed.

**Your Mac is offline for days.** Scanners don't run. Webhook events queue at GitHub. When you come back: Harvester resumes, reconciliation handles drift, catch-up scans run on their normal cadence.

**An agent run damages something important.** Mitigations: all changes are in branches, never on main; PRs require human approval before merge; branch protection is load-bearing.

---

## What This Is Not

**Not a SaaS or productized service.** No user accounts, no tenant boundaries. Personal infrastructure only.

**Not an AI Labor Solutions prototype.** Decisions here reflect personal use only. Any future ALS product work would be a separate canvas.

**Not a replacement for Ezra.** Harvester observes Ezra from outside. Ezra remains the primary interactive personal AI.

**Not a general-purpose workflow engine.** Archon occupies that space. Harvester is purpose-built for one specific workflow: scanner → issue → triage → overnight agent → PR → review → merge. Trying to generalize would reproduce Archon and lose the simplicity.

---

## Honorable Mention: Archon

Archon is a thoughtful reference point. Its workflow engine model — deterministic YAML phases composed of AI and bash nodes — is genuinely appealing for teams with many workflow types.

Harvester's overnight runner is conceptually close to one Archon workflow: plan → implement → test → commit → push → PR. The difference is that Harvester hardcodes this workflow because it only does one thing. Archon's YAML becomes justified once you have many workflow types (quick fix, deep refactor, security patch, documentation pass, etc.) with different phase structures.

If Harvester ever grows to support multiple workflow types, revisit Archon. For now, one workflow, hardcoded, is correct.

---

## Success Criteria

F19 is successful when, 6 months after M2 completes:

- Harvester has run continuously with zero unplanned downtime exceeding 24 hours
- All three personal repos receive at least one useful finding per month on average
- Zero guarded-path changes have been merged without explicit Troy review
- Ezra's native improvement system has been cleanly removed
- At least 15 cycles have completed (issue → PR → merge)
- Merge rate on agent PRs is above 50% (low rate signals scanner quality issues)
- Adding a new repo to Harvester's watch list takes under 30 minutes of configuration

---

## Related Documentation

| File | Purpose |
|---|---|
| `harvester-config.yaml` | Runtime configuration |
| `CLAUDE.md` (Harvester repo) | System prompt for agents working on Harvester itself |
| `docs/selah-guardrails.md` | Theological content safety design |
| `docs/scanner-contract.md` | How to write a new scanner |
| `docs/operational-runbook.md` | Common operations, failure recovery |
| `~/Projects/ezra-assistant/CLAUDE.md` | System prompt for agents working on Ezra |
| `~/Projects/selah/CLAUDE.md` | System prompt for agents working on Selah (stricter) |
| `~/Projects/voice-of-repentance/CLAUDE.md` | System prompt for agents working on VoR |

---

*Created: 2026-04-18 | Status: Proposed | Version: 2.0 (direct-build)*
