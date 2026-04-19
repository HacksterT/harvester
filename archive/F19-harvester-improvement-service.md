---
type: feature-canvas
feature: F19
title: Harvester — Improvement-as-a-Service for Personal Repos
created: 2026-04-18
status: proposed
priority: should-have
domain: infrastructure
depends_on: [F15, F16, F18]
---

# F19: Harvester — Improvement-as-a-Service for Personal Repos

**Owner:** HacksterT
**Context:** Evolution of the F15/F18 improvement loop into a standalone service that can observe and improve multiple repositories
**Relationship to F18:** F18 builds the improvement loop inside Ezra. F19 extracts it into its own service. F18 is the proof of concept; F19 is the productization for personal use.
**Out of scope:** AI Labor Solutions productization, client-facing workflows, multi-tenant architecture

---

## Name Rationale

**Harvester** — gathers signal from codebases, proposes improvements, harvests the fruit of overnight work as morning PRs. The name is ministry-adjacent without being religious, descriptive of function, memorable, and distinct from Ezra, Selah, and Voice of Repentance. It names a role, not a brand.

If you prefer something else: Cultivator, Steward, Tender, Janitor, Gardener, Sexton are all valid. The service doesn't care. I'll use Harvester throughout this canvas.

---

## Purpose

Extract the F15/F16/F18 improvement loop from inside Ezra and run it as a dedicated long-lived service that observes multiple personal repositories, produces GitHub Issues for proposed improvements, and executes approved improvements overnight via Claude Code with subscription authentication.

The shift from F18 to F19 is architectural inversion. In F18, Ezra contains the improvement system. In F19, Harvester *is* the improvement system, and Ezra is one of several repos it observes. Voice of Repentance is another. Selah is a third (with guardrails). Future repos are trivial to add.

---

## Why Extract This From Ezra

Five reasons the extraction is worth doing, beyond general "microservices are nice."

**Decoupling failure domains.** If Ezra has a bug that breaks scanner output, Ezra can't propose its own fix because the broken scanner won't fire. Harvester as a separate service is stable infrastructure that observes Ezra from outside, unaffected by Ezra's state.

**Per-repo configuration.** Each repo has different improvement concerns. Ezra needs token cost scanners and skill gap scanners. Selah needs theological consistency scanners and prompt quality scanners. Voice of Repentance needs content-oriented scanners (liturgical alignment, song availability, production status). Harvester's per-repo config makes this clean; a one-size-fits-all Ezra scanner does not.

**Repo-independent cadence.** Ezra's scanner runs every 9 days because that matches Ezra's development pace. Voice of Repentance might benefit from weekly scans tied to service planning cycles. Selah might warrant monthly deep scans. Harvester can run each repo's scanners on its own schedule.

**Clean boundary for the agent workspace.** Overnight agent runs currently work in `~/agent-workspaces/` (F18-S03-ALT). Harvester owns that directory; neither Ezra nor Selah need to know it exists. The separation of "the thing being improved" from "the thing doing the improving" is architecturally clean.

**Reusability of the pattern.** Once Harvester exists, new repos get the improvement loop for free. Add a repo to `harvester-config.yaml`, define its scanners, point Claude Code at its CLAUDE.md — done. No per-repo setup beyond configuration.

---

## Design Principles

**One service, many repos, zero tenant coupling.** Harvester is not a multi-tenant platform. It is a single-user service that happens to watch multiple repos belonging to the same user. Do not introduce tenancy, user models, access control, or any abstraction that implies more than one human is served. That complexity belongs to a productized service, which this is not.

**Configuration is a file.** Harvester's behavior is defined in one YAML file per environment. No database of configuration, no admin UI. Editing the YAML is how you change behavior. Git-tracked, reviewable, portable.

**Scanners are importable modules, not plugins.** Harvester doesn't do plugin discovery or dynamic loading. Each scanner is a Python module in `src/harvester/scanners/` that the config references by name. Adding a scanner means adding a file and referencing it. No manifest systems, no entry points, no registry lookups.

**The service is boring infrastructure.** Harvester should run for months without attention. No UI beyond logs and GitHub. No chat interface. No AI personality. It observes, proposes, executes, records. Ezra is the fun part of the stack; Harvester is the kitchen appliance that quietly does its job.

**Human gates stay intact.** F18's triage gate (label application) and judgment gate (PR review) work identically in F19. The extraction does not change the human role in the loop.

---

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│  Harvester Service (new, on your Mac)                         │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Config loader                                          │ │
│  │  harvester-config.yaml → RepoConfig[]                   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Scanner scheduler                                      │ │
│  │  per-repo rotation, per-scanner cadence                 │ │
│  │  persists state to data/harvester-state.json            │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Scanners (same contract as F15, importable modules)    │ │
│  │  scanners/code_health.py                                │ │
│  │  scanners/token_economics.py  (Ezra-specific)           │ │
│  │  scanners/content_gap.py      (VoR-specific)            │ │
│  │  scanners/theology_review.py  (Selah-specific)          │ │
│  │  scanners/dependency_freshness.py                       │ │
│  │  scanners/test_coverage.py                              │ │
│  │  scanners/patterns.py         (cross-repo, from F18-S08)│ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  GitHub integration                                     │ │
│  │  creates issues with target_repo from finding           │ │
│  │  applies labels per repo config                         │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Webhook receiver                                       │ │
│  │  POST /webhook — enqueues on agent-ready label          │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Queue + agent runner                                   │ │
│  │  data/queue/{pending,completed,failed}                  │ │
│  │  launchd fires at 02:00, drains queue                   │ │
│  │  uses Claude Code CLI with subscription login           │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Observability                                          │ │
│  │  minimal web UI on port 8500 showing: repo list,        │ │
│  │  queue depth, recent findings, recent runs, failures    │ │
│  │  Telegram notifications for: finding, run, failure      │ │
│  └─────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘

                    observes/reads                writes to
                         │                             │
                         ▼                             ▼
┌───────────────────────────────────────────────────────────────┐
│  GitHub repos                                                 │
│  hackstert/ezra-assistant                                     │
│  hackstert/selah                                              │
│  hackstert/voice-of-repentance                                │
│  hackstert/<future>                                           │
└───────────────────────────────────────────────────────────────┘
```

---

## Repo Configuration Model

`harvester-config.yaml` in the Harvester repo root defines every watched repo.

```yaml
# Global settings
global:
  queue_path: data/queue
  state_path: data/harvester-state.json
  workspaces_path: ~/agent-workspaces
  claude_code_version: latest
  default_max_turns: 50
  default_timeout_minutes: 30
  telegram_chat_id: ${TELEGRAM_ALLOWED_CHAT_ID}

# Per-repo configuration
repos:
  - name: ezra-assistant
    github: hackstert/ezra-assistant
    local_path: ~/Projects/ezra-assistant
    claude_md_path: CLAUDE.md
    scanners:
      - name: code_health
        cadence_days: 7
      - name: token_economics
        cadence_days: 9
      - name: skill_gaps
        cadence_days: 9
      - name: memory_health
        cadence_days: 9
      - name: dependency_freshness
        cadence_days: 30
      - name: test_coverage
        cadence_days: 14
    label_prefix: improvement
    priority_labels: [must-have, should-have, nice-to-have]
    guarded_paths: []
    min_reviewers_on_merge: 1

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
      - "selah/theology/**"
      - "selah/training/**"
      - "selah/prompts/**"
      - "selah/doctrine/**"
    min_reviewers_on_merge: 1
    extra_labels_on_guarded: [theological-review-required]
    telegram_flag_on_guarded: true

  - name: voice-of-repentance
    github: hackstert/voice-of-repentance
    local_path: ~/Projects/voice-of-repentance
    claude_md_path: CLAUDE.md
    scanners:
      - name: code_health
        cadence_days: 14
      - name: content_gap
        cadence_days: 14
      - name: liturgical_alignment
        cadence_days: 30
    label_prefix: improvement
    priority_labels: [must-have, should-have, nice-to-have]
    guarded_paths:
      - "content/**"
    min_reviewers_on_merge: 1
```

Adding a new repo: append an entry, restart Harvester, done. The service validates the config on startup and refuses to start if a config is malformed — fail loud early.

---

## Scanner Contract

Scanners are Python modules. Each implements one function:

```python
async def scan(
    repo_config: RepoConfig,
    llm: LLMClient,
    context: ScanContext,
) -> Finding | None:
    """
    Analyze this repo and return one high-value finding, or None if
    no finding is appropriate.

    repo_config — the repo's config entry (local_path, github, etc.)
    llm — the LLM client (default: Grok, configurable per scanner)
    context — prior findings, scanner history, other metadata
    """
```

Return type is the same `Finding` dict contract from F15. Harvester's story writer handles local file persistence and GitHub issue creation based on the finding's `target_repo` (derived from the scanner's repo context).

Scanners are pure: they do not create issues, write files, or send notifications. They return structured data. Harvester's framework handles the side effects. This makes scanners easy to test — call `scan()` in isolation, assert on the returned finding.

---

## Scheduling Model

Each repo has its own rotation through its configured scanners. Each scanner has its own cadence within its repo. Harvester's scheduler wakes every hour and asks: "for any scanner in any repo, is it overdue past its cadence?" If yes, run it. If multiple are overdue, run the most-overdue first. If none are overdue, sleep another hour.

State is persisted per (repo, scanner) pair in `data/harvester-state.json`:

```json
{
  "ezra-assistant:token_economics": {
    "last_run": "2026-04-16T14:30:00Z",
    "last_finding_issue": 47,
    "consecutive_skips": 0
  },
  "ezra-assistant:skill_gaps": {
    "last_run": "2026-04-13T14:30:00Z",
    "last_finding_issue": 45,
    "consecutive_skips": 0
  },
  "selah:theology_review": {
    "last_run": "2026-04-01T14:30:00Z",
    "last_finding_issue": 12,
    "consecutive_skips": 0
  }
}
```

Consecutive skips increment when a scanner returns `None` (no finding). After 3 consecutive skips for the same scanner, Harvester emits a Telegram notification suggesting the scanner may be misconfigured or the metric healthy enough to extend the cadence. Self-observation of the self-observer.

---

## The Agent Runner

Single script, same pattern as F18-S03-ALT but operating across repos based on queue item metadata. The queue item now includes `repo_local_path` and `repo_github` so the runner clones/updates the right workspace.

```bash
# Pseudocode of the runner loop
for item in queue/pending/*.json:
    repo_path = item.repo_local_path
    workspace = f"{WORKSPACES}/{item.repo}-{item.issue_num}"

    # Ensure fresh clone or update
    if workspace exists:
        cd workspace && git fetch && git checkout main && git reset --hard origin/main
    else:
        git clone item.repo_github workspace

    cd workspace
    git checkout -b f"improvement/{item.issue_num}"

    # Build task spec from issue body + repo's CLAUDE.md
    spec = fetch_issue_body(item.issue_num, item.repo)

    # Invoke Claude Code (uses subscription login on your Mac)
    claude --task "$spec" --max-turns item.max_turns

    # Push + open draft PR
    git push -u origin HEAD
    gh pr create --draft --title "Closes #{num}: ..." --body ...

    mv item queue/completed/
```

One runner, many repos. No code changes needed to support a new repo — the runner reads everything it needs from the queue item, which was populated from the repo's config at enqueue time.

---

## Stories

### F19-S01: Harvester Repo Bootstrap

**Priority:** must-have
**Dependencies:** F18 completion

Create a new repository `hackstert/harvester` with initial scaffolding: project structure, `pyproject.toml`, `harvester-config.yaml` template, README, CLAUDE.md for the Harvester repo itself (so Harvester can eventually improve Harvester).

Initial structure:

```
harvester/
├── src/harvester/
│   ├── __main__.py
│   ├── config.py
│   ├── scheduler.py
│   ├── queue.py
│   ├── github_client.py
│   ├── writer.py
│   └── scanners/
│       └── __init__.py
├── scripts/
│   ├── agent-runner.sh
│   └── install-launchd.sh
├── data/                 # gitignored
│   ├── queue/
│   └── harvester-state.json
├── harvester-config.yaml
├── pyproject.toml
├── CLAUDE.md
└── README.md
```

**Acceptance criteria:**

- [ ] Repo created at `hackstert/harvester`
- [ ] Project structure matches above
- [ ] `uv sync` produces a working environment
- [ ] `python -m harvester --validate-config` validates the config file
- [ ] CLAUDE.md present and accurate for the Harvester codebase
- [ ] README explains the service's purpose and config model

---

### F19-S02: Port F15 Scanners to Harvester

**Priority:** must-have
**Dependencies:** F19-S01

Port the three existing F15 scanners (`skill_gaps`, `memory_health`, `token_economics`) from Ezra into Harvester's scanner module directory. Adapt them to the new contract (take `RepoConfig`, return `Finding | None`).

The original scanners in Ezra remain in place during the migration period. F19-S07 (later story) removes them once Harvester has proven stable.

Ezra-specific scanners stay Ezra-specific — they're in Harvester's module but configured to run only on the ezra-assistant repo via `harvester-config.yaml`. This is the pattern: Harvester's scanner library grows to cover all repos; each repo's config selects which scanners apply.

**Acceptance criteria:**

- [ ] `scanners/skill_gaps.py`, `scanners/memory_health.py`, `scanners/token_economics.py` exist in Harvester
- [ ] Each scanner operates on a local clone of ezra-assistant (reads checkpointer DB, BolusStore, etc. from the local path, not an active Ezra server)
- [ ] Tests port over from Ezra's improvement test suite
- [ ] One end-to-end run produces a finding that creates a GitHub issue in ezra-assistant

---

### F19-S03: Generic Code Health Scanner

**Priority:** should-have
**Dependencies:** F19-S01

A new scanner that applies to any repo: `scanners/code_health.py`. Analyzes:

- Test coverage trends
- Files over a size threshold (candidates for refactor)
- TODO/FIXME comments older than 30 days
- Functions with cyclomatic complexity above a threshold
- Missing type hints in public APIs
- Dependency version drift

Emits a single finding per run per repo, matching the contract. Usable on all three personal repos immediately.

**Acceptance criteria:**

- [ ] `scanners/code_health.py` implements the contract
- [ ] Ships with sensible default thresholds
- [ ] Thresholds overridable per repo via config
- [ ] Tested against all three personal repos
- [ ] Produces actionable findings (verified by generating 3 real issues and reviewing them)

---

### F19-S04: Selah Theology Review Scanner

**Priority:** should-have
**Dependencies:** F19-S01, Selah repo having initial content

A Selah-specific scanner that examines theological content for consistency, completeness, and alignment with stated doctrinal commitments. This is where the scanner must be exceptionally conservative — the goal is to flag potential concerns for human review, not to propose changes.

**What it examines:**

- Prompts in `selah/prompts/` for Nicene Creed alignment
- Training data samples for doctrinal consistency
- Denominational configuration files for orthodoxy boundaries
- Recent commits touching theological paths

**What it produces:**

- Findings that are always framed as "flag for review" rather than "make this change"
- Evidence sections include specific citations (which prompt, which training example)
- Priority defaults to `must-have` for any theology finding
- Issue labels include `theological-review-required`

**Guardrails:**

- If the scanner produces a finding that proposes code changes to any file under a guarded path, the issue body explicitly states: "This finding proposes changes to theologically-significant content. The agent runner will NOT execute this even if `agent-ready` is applied. HacksterT's manual review and implementation required."
- Triple-check at the agent-runner level: guarded-path changes are filtered out before any `claude` invocation

The scanner is useful because it surfaces questions worth thinking about, not because it should be automated.

**Acceptance criteria:**

- [ ] `scanners/theology_review.py` implements the contract
- [ ] Scanner output always frames findings as review requests, not change proposals
- [ ] Guarded paths configured in `harvester-config.yaml` for Selah
- [ ] Agent runner has explicit safeguard against executing guarded-path changes
- [ ] Documented clearly in `docs/selah-guardrails.md` in the Harvester repo

---

### F19-S05: Voice of Repentance Content Scanners

**Priority:** nice-to-have
**Dependencies:** F19-S01, Voice of Repentance repo established

Scanners specific to ministry/content work:

- `scanners/content_gap.py` — identifies gaps in content catalog (missing song metadata, production notes, scheduling information)
- `scanners/liturgical_alignment.py` — flags content that doesn't fit the liturgical calendar context where it's scheduled

These may be deferred until Voice of Repentance's codebase is more established. Listed here so the architecture accommodates them when ready.

**Acceptance criteria:**

- [ ] Deferred until Voice of Repentance repo has substantive content
- [ ] When implemented, follows the scanner contract
- [ ] Produces findings useful to ministry workflow, not just code quality

---

### F19-S06: Minimal Web UI for Harvester

**Priority:** should-have
**Dependencies:** F19-S01, F19-S02

A minimal FastAPI web UI at port 8500 for operational visibility. No chat, no complex dashboards. Just:

- Repo list with status per scanner (last run, next expected)
- Queue depth (pending/completed/failed counts)
- Recent findings (last 10 across all repos)
- Recent runs (last 10 agent executions with outcome)
- Failed items (with logs link)
- A "Rescan now" button per (repo, scanner) pair — bypasses cadence for testing

Single-page React or even just server-rendered Jinja templates. The priority is being useful at 2am when you're debugging a failed run, not being pretty.

**Acceptance criteria:**

- [ ] UI at `http://localhost:8500/`
- [ ] All listed views functional
- [ ] "Rescan now" bypasses cadence check
- [ ] Logs link works (opens the relevant log file)
- [ ] No auth required (it's localhost-only)

---

### F19-S07: Ezra Deprecation of Native Improvement System

**Priority:** should-have
**Dependencies:** F19-S01 through F19-S04 stable for 30 days

Once Harvester is running reliably and has demonstrably handled Ezra's improvement cycle for at least 30 days, remove the native improvement system from Ezra.

**What gets removed from Ezra:**

- `src/ezra/improvements/` directory
- Cron registration for `improvement_scan` in `main.py`
- Corresponding routes and UI panels in Mission Control
- `tasks/improvements/` directory (migrated to Harvester's queue view)

**What stays in Ezra:**

- The `github_issues` skill (useful independently)
- The webhook handler (Harvester uses it? Or Harvester has its own? See F19-S08)

**Acceptance criteria:**

- [ ] 30-day cooling period passed with zero Harvester-produced PRs rejected as "should not have been proposed"
- [ ] Migration plan documented before removal
- [ ] Ezra's `docs/improvement-system.md` updated to point to Harvester
- [ ] Removal done in a single commit with clear message
- [ ] All Ezra tests still pass after removal

---

### F19-S08: Cross-Repo Pattern Scanner

**Priority:** nice-to-have
**Dependencies:** 50+ closed issues across all repos

Once enough issues have closed across the three-repo portfolio, add a scanner that mines the historical corpus *across repos* for patterns. Refinement of F18-S08.

**What this enables:**

- "Both Ezra and Selah have had issues closed as wontfix for dependency freshness in the last 30 days — dependency_freshness scanner may be too aggressive"
- "Code-health scanner has proposed the same TODO cleanup five times across repos — consider promoting to an auto-fix workflow or retiring it"
- "Voice of Repentance has had 0 issues in 60 days — scanner cadence may be under-tuned"

This scanner runs against all repos simultaneously, which is easy for Harvester (it already has the data) but was impossible for the per-repo F18 architecture.

**Acceptance criteria:**

- [ ] `scanners/cross_repo_patterns.py` runs against all configured repos
- [ ] Produces findings that reference multiple repos when appropriate
- [ ] Gated: only runs if corpus > 50 closed issues
- [ ] One finding per month maximum (avoid noise)

---

## Milestones

### M1 — Harvester MVP (4-6 weeks after F18-S03-ALT is working)

- F19-S01: Repo bootstrap
- F19-S02: Port F15 scanners
- F19-S06: Minimal web UI

**Exit criterion:** Harvester runs side-by-side with Ezra's native improvement system, producing equivalent output. Both systems fire their scanners; both create issues. This dual-run confirms Harvester has parity before we cut over.

### M2 — Multi-Repo Expansion (2-3 weeks after M1)

- F19-S03: Generic code health scanner
- F19-S04: Selah theology scanner with guardrails
- Selah and Voice of Repentance repos added to `harvester-config.yaml`

**Exit criterion:** Harvester produces findings for all three repos. Selah guardrails tested with a dummy guarded-path finding — runner correctly refuses to execute.

### M3 — Cutover and Cleanup (30 days after M2)

- F19-S07: Remove Ezra's native improvement system
- Documentation updated across all three repos
- Mission Control in Ezra points to Harvester's UI for improvement visibility

**Exit criterion:** Ezra no longer contains improvement-system code. All three repos are served by Harvester.

### M4 — Voice of Repentance Specifics (when VoR is ready)

- F19-S05: Content scanners for ministry work
- Custom CLAUDE.md for the Voice of Repentance repo

**Exit criterion:** VoR receives at least 3 useful findings per month on average.

### M5 — Cross-Repo Intelligence (open-ended, corpus-triggered)

- F19-S08: Cross-repo pattern mining

**Exit criterion:** First cross-repo finding produced and reviewed.

---

## Data Locations

Harvester's operational data lives in its own repo or a sibling data directory, not inside any watched repo:

```
~/Projects/harvester/
├── data/
│   ├── queue/                    # Agent work queue
│   ├── harvester-state.json      # Scanner rotation state
│   ├── findings/                 # Historical findings log
│   └── logs/                     # Per-run logs
├── workspaces/                   # Agent workspaces (gitignored)
│   ├── ezra-assistant-47/
│   ├── selah-12/
│   └── ...
```

Watched repos stay clean. Nothing Harvester-specific gets committed to Ezra, Selah, or Voice of Repentance. The only coupling is that each watched repo has a `CLAUDE.md` file — which is useful for local Claude Code use regardless of Harvester.

---

## Dependency Strategy

Harvester should be thin. Dependencies to include:

- `PyGithub` or `gh` CLI for GitHub interaction
- `PyYAML` for config
- `pydantic` for config validation
- `click` for CLI
- `fastapi` + `uvicorn` for the minimal web UI
- `anthropic` only if Harvester's own scanners use the Anthropic API directly (most scanners should use local Ollama or Grok, which Ezra-style scanners already do)

Do NOT include:

- LangGraph (this service is not a graph runtime)
- LangChain (not needed; scanner LLM calls are single-shot)
- Any framework larger than the service itself

If Harvester ever feels like it's adopting Ezra's weight, that's a sign it's drifting from purpose. Harvester is a cron daemon with an HTTP interface. Keep it that small.

---

## Security Model

Same principles as F18, applied to the multi-repo surface.

**Secrets scope:**

- `GITHUB_TOKEN` — fine-grained PAT with issues + PRs write access to only the watched repos
- `TELEGRAM_BOT_TOKEN` — reused from Ezra's bot or a dedicated Harvester bot
- `XAI_API_KEY` — for scanner LLM calls
- `GITHUB_WEBHOOK_SECRET` — shared between repos and Harvester
- No `ANTHROPIC_API_KEY` — the overnight runner uses Claude Code's subscription login

**Webhook security:**

- Signature verification on every request
- Separate webhook endpoints per repo would be cleaner, but a single endpoint with repo-routing in the handler is acceptable

**Agent workspace isolation:**

- Every run gets a fresh clone (or hard reset) in `~/agent-workspaces/`
- Workspaces never share state between runs
- Workspaces are gitignored from Harvester itself

**Guarded paths enforcement:**

- Three-layer check for Selah and any future guarded-path repo:
  1. Scanner declares guarded paths it touches (or better: scanner knows it touches them and refuses to produce a change-oriented finding)
  2. Agent runner refuses to execute findings that touch guarded paths — diff check before push
  3. Branch protection rules in the repo itself require explicit approval for guarded paths

---

## Observability

**Where to look:**

- Harvester web UI at `localhost:8500` — real-time queue and finding state
- Telegram — scanner findings, run starts/completions, failures
- GitHub — issues, PRs, closed-issue history (same as F18)
- Logs in `data/logs/` — per-run detailed logs

**What gets logged:**

- Every scanner invocation (start, end, finding emitted or skipped, duration)
- Every agent run (queue item, workspace, exit code, duration, PR created)
- Every webhook received (event type, repo, action taken)
- Every GitHub API call that errors

**What does NOT get logged:**

- Full issue bodies or PR bodies (they're in GitHub; no need to duplicate)
- Secrets, tokens, API keys, authentication state
- Full LLM responses (just tokens in/out counts)

---

## Risks and Mitigations

**Harvester becomes too Ezra-shaped.** If scanners proliferate and state management grows, Harvester starts to look like Ezra-lite. Mitigation: strict scope — any feature that would require more than the listed dependencies is a signal to stop and reconsider. Harvester is a cron daemon, not a platform.

**Claude Code subscription session expires overnight.** The runner fails silently if Claude Code can't authenticate. Mitigation: health check at the start of every runner invocation (`claude --version` or `claude status`) that aborts early with a loud Telegram alert if auth is stale.

**Multiple repos produce findings simultaneously and overwhelm the queue.** Unlikely at the cadence (one finding per scanner per cadence period), but possible. Mitigation: queue cap of 10 pending items; scanner emits warning if queue is saturated and skips producing new findings until it drains.

**A guarded-path finding slips through.** The triple-layer defense (scanner awareness, runner diff check, branch protection) should prevent this. If it ever happens, it's a Selah emergency — the incident triggers an immediate review of all three layers. Mitigation: the scanner's output format makes the violation impossible by construction (it doesn't produce change-oriented findings for guarded paths), not merely improbable.

**Harvester crashes and isn't noticed.** Mitigation: Ezra pings Harvester's health endpoint hourly; if Harvester is unreachable for more than 3 hours, Ezra sends a Telegram alert. Cross-monitoring between the two services.

**Dependency sprawl.** Mitigation: quarterly review of `pyproject.toml`; any new dependency added in the last quarter must be justified or removed.

---

## Relationship to Ezra's Long-Term Evolution

Harvester is not the only extraction candidate from Ezra. Over time, other services might emerge:

- A separate knowledge ingestion service (take the F12 Knowledge Center and make it standalone)
- A separate research service (take the research skill and let it run against multiple data sources continuously)
- A separate content generation service (for Voice of Repentance and Selah)

F19 doesn't commit to any of these. But establishing the pattern with Harvester — one well-defined concern, config-driven, boring infrastructure — makes future extractions easier to evaluate. The principle is: extract when the concern is genuinely separate, stay integrated when the coupling is essential.

---

## What This Is Not

**Not a SaaS.** No user accounts, no tenant boundaries, no billing integration. This is personal infrastructure.

**Not an AI Labor Solutions prototype.** F19 explicitly excludes any design decisions aimed at productization. If a future ALS offering wants to draw on F19 as prior art, that's fine — but F19 is built for Troy's personal environment, and design decisions reflect that.

**Not a replacement for Ezra.** Harvester is a service *adjacent to* Ezra. Ezra remains the primary personal AI system. Harvester handles a specific concern (improvement proposals) that was previously inside Ezra and is now outside.

**Not a general-purpose workflow engine.** That's what Archon is. Harvester is purpose-built for one workflow: scanner → issue → triage → overnight agent → PR → review → merge. Trying to generalize it would reproduce Archon and lose the simplicity.

---

## Honorable Mention (Again): Archon

As in F18's canvas, Archon remains a thoughtful reference point. Harvester's overnight-runner logic is conceptually close to an Archon workflow: plan → implement → test → commit → push → PR. The difference is that Harvester's workflow is hardcoded because it only ever does one thing. Archon's workflow is YAML-defined because it does many things.

If Harvester ever grows to support multiple workflow types (a quick fix path, a deep refactor path, a documentation path), revisiting Archon makes sense at that point. For now, one workflow, hardcoded, is correct.

---

## Success Criteria

F19 is successful when:

- Harvester runs continuously for 90+ days with zero unplanned downtime
- All three personal repos receive at least one useful finding per month on average
- Zero guarded-path changes have been merged without explicit Troy review
- Ezra's native improvement system has been cleanly removed
- At least one cross-repo pattern has been identified by F19-S08
- Adding a new repo to Harvester's watch list takes under 30 minutes of configuration

---

## Related Documentation

| File | Purpose |
|---|---|
| `F18-github-improvement-loop.md` | Predecessor; the single-repo loop Harvester generalizes |
| `F18-technical-guide.md` | Details on GitHub integration patterns reused here |
| `F18-addendum-subscription-overnight.md` | The execution model Harvester adopts wholesale |
| `harvester-config.yaml` (new, in Harvester repo) | The runtime configuration |
| `docs/selah-guardrails.md` (new, in Harvester repo) | Theological content safety design |

---

*Created: 2026-04-18 | Status: Proposed*
