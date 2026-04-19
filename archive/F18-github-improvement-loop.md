---
type: feature-canvas
feature: F18
title: GitHub-Native Improvement Loop
created: 2026-04-18
status: proposed
priority: should-have
domain: improvements
depends_on: [F15, F16]
---

# F18: GitHub-Native Improvement Loop

**Owner:** HacksterT
**Context:** Personal / Voice of Repentance / Selah development
**Out of scope:** AI Labor Solutions tenant work, client-facing harnesses

---

## Purpose

Close the self-annealing loop in Ezra's improvement system by routing scanner findings through GitHub Issues, automating implementation via GitHub Actions, and using Pull Requests as the human judgment gate. The goal is a development loop where the only required human action is merging — everything before that (problem discovery, story authoring, implementation, test execution, PR drafting) runs autonomously.

This PRD covers the local-environment improvement loop for the Ezra and Selah codebases. It explicitly does not address AI Labor Solutions workflows, client deliverables, or multi-tenant orchestration.

---

## Why This Matters

F15 built the scanners. F16 surfaced them in Cron Center. Together they produce one finding every nine days, written as a markdown file to `tasks/improvements/active/`. The loop stops there. Files on disk are not work items — they can't be tracked, assigned, linked to commits, or picked up by an automated agent.

The scanners are observing a system that has no mechanism to respond to their observations. That gap is what F18 closes.

Two project contexts motivate this beyond general engineering quality:

**Voice of Repentance** — music ministry project that will accumulate its own codebase and content (lyrics, recordings metadata, scheduling, website). Having the improvement loop established here means ministry work benefits from the same discipline without additional overhead.

**Selah** — the theologically fine-tuned AI assistant for church ministry. Selah's codebase is where the highest-stakes development happens (Christian belief system AI, Nicene Creed orthodoxy at weights, denominational distinctives at RAG). A rigorous loop with mandatory human review is the right operational model for that project. F18 builds the pattern once; Selah inherits it.

---

## Design Principles

Five principles govern every decision in this PRD.

**Human judgment is the only mandatory step.** Every automated action before merge is recoverable. Every automated action after merge does not exist — merging is a human decision, full stop. This is load-bearing for Selah: theologically significant changes cannot be auto-approved by any scanner, agent, or workflow.

**GitHub primitives over custom infrastructure.** Use issues, labels, Actions, PRs, and reviews as they exist. Do not rebuild queue semantics, approval flows, or CI orchestration. GitHub Pro is already paid for and integrated.

**Evidence travels with work items.** Scanner findings include the raw metric snapshot in the issue body. PRs reference the issue. Commits reference the PR. The entire causal chain from "metric observed" to "code merged" is auditable in one place months later without rerunning anything.

**One finding, one issue, one PR.** No batching, no bundling, no multi-issue PRs. This keeps the blast radius of any automated change narrow and reviewable in a single sitting.

**Reversibility over speed.** Every automated action can be undone. Issues can be closed without PRs. PRs can be closed without merging. Merges can be reverted. The design prefers a slower loop with high reversibility over a faster loop with irreversible steps.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│  Ezra Server (existing)                                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Improvement Scanner (F15)                             │ │
│  │  skill_gaps | memory | tokens (rotating)               │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           │                                  │
│                   finding dict                               │
│                           │                                  │
│  ┌────────────────────────▼───────────────────────────────┐ │
│  │  Story Writer (existing)                               │ │
│  │  writes: tasks/improvements/active/IMP-*.md            │ │
│  │  NEW: also invokes github_issues skill                 │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           │                                  │
│  ┌────────────────────────▼───────────────────────────────┐ │
│  │  github_issues Tier 1 skill (NEW in F18-S01)           │ │
│  │  creates issue, applies labels, links to story file    │ │
│  └────────────────────────┬───────────────────────────────┘ │
└───────────────────────────┼──────────────────────────────────┘
                            │ gh api / PyGithub
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  GitHub (repo: ezra-assistant, later selah, voice-of-rep.)   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Issue lands with labels:                              │ │
│  │    improvement, domain:skill_gaps, priority:should-have│ │
│  │  Status: open, assignee: hackstert                     │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           │                                  │
│                  HUMAN TRIAGE GATE                           │
│                  Troy reviews, applies agent-ready label     │
│                           │                                  │
│  ┌────────────────────────▼───────────────────────────────┐ │
│  │  GitHub Action: .github/workflows/agent-execute.yml    │ │
│  │  trigger: issues.labeled (agent-ready)                 │ │
│  │  runs: Claude Code SDK with issue body as input        │ │
│  │  produces: branch + PR linked to issue                 │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           │                                  │
│  ┌────────────────────────▼───────────────────────────────┐ │
│  │  Pull Request                                          │ │
│  │  title: "Closes #N: ..."                               │ │
│  │  body: plan, changes, test results                     │ │
│  │  status: draft (initially) or ready                    │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           │                                  │
│                  HUMAN JUDGMENT GATE                         │
│                  Troy reviews, approves or rejects           │
│                           │                                  │
│  ┌────────────────────────▼───────────────────────────────┐ │
│  │  Merge closes issue (via "Closes #N" in PR body)       │ │
│  └────────────────────────┬───────────────────────────────┘ │
└───────────────────────────┼──────────────────────────────────┘
                            │ webhook
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  Ezra Server — GitHub Webhook Handler (F18-S04)              │
│  on issue close: move story file active/ → completed/        │
│  on PR merge: record in improvement-state.json               │
│  on issue open from scanner: no-op (already tracked)         │
└──────────────────────────────────────────────────────────────┘
```

Two human gates, five automated transitions. Issues that never receive `agent-ready` sit in the backlog indefinitely — that is correct behavior. Issues that receive `agent-ready` but produce bad PRs stall at the review gate — also correct behavior. The loop can only advance through explicit human choice.

---

## Stories

### F18-S01: `github_issues` Tier 1 Skill

**Priority:** must-have
**Dependencies:** none

Build a new Tier 1 primitive tool that lets Ezra create, read, comment on, label, and close GitHub issues across Troy's repositories.

**Tool contract:**

```python
@tool
async def github_issues(
    action: Literal["create", "get", "list", "comment", "label", "close"],
    repo: str,           # "hackstert/ezra-assistant"
    issue_number: int | None = None,
    title: str | None = None,
    body: str | None = None,
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    comment: str | None = None,
    state: Literal["open", "closed"] | None = None,
) -> str: ...
```

**Transport:** PyGithub library (`pip install PyGithub`) or the `gh` CLI shelled via `local_shell`. PyGithub is preferred for typed error handling and structured responses.

**Authentication:** `GITHUB_TOKEN` in `.env`, generated as a fine-grained PAT scoped to the specific repositories the skill may act on. The token is never logged or exposed in tool responses.

**Safety:** The `close` action triggers an `interrupt()` for human confirmation, consistent with the three-tier safety model in `local_shell`. Creating and commenting do not interrupt.

**Acceptance criteria:**

- [ ] Tool registered in `chat.py` `TOOLS` list, visible in manifest
- [ ] `GITHUB_TOKEN` loaded from `.env`, validated at startup
- [ ] All six actions (create, get, list, comment, label, close) implemented and tested
- [ ] `close` action respects HITL interrupt pattern
- [ ] Tool schema documented in `docs/skill-inventory.md` under Tier 1
- [ ] Unit tests in `tests/skills/github_issues/test_tool.py` cover happy path and error handling

---

### F18-S02: Scanner-to-Issue Bridge

**Priority:** must-have
**Dependencies:** F18-S01

Extend `write_improvement_story()` in `src/ezra/improvements/writer.py` to also create a GitHub issue when a scanner produces a finding. Dual-write: the local markdown file is preserved exactly as it is today, and a GitHub issue is created alongside it.

**Issue structure:**

```
Title: [IMPROVEMENT] {finding.title}

Body:
## Summary
{finding.summary}

## Evidence
{finding.evidence}

## Acceptance Criteria
{finding.criteria as checklist}

## Tasks
{finding.tasks as checklist}

---
**Domain:** {finding.domain}
**Priority:** {finding.priority}
**Story file:** `tasks/improvements/active/IMP-YYYYMMDD-{domain}.md`
**Generated:** {timestamp} by Ezra improvement scanner

Labels: improvement, domain:{skill_gaps|memory|tokens}, priority:{must-have|should-have|nice-to-have}
Assignee: hackstert
```

**Repository targeting:** Scanner findings about Ezra go to `hackstert/ezra-assistant`. Future scanners in other domains will target their respective repos via a `target_repo` field in the finding dict.

**Failure mode:** If GitHub is unreachable or the API call fails, the local markdown file is still written and the Telegram notification still fires. The GitHub issue creation is fire-and-forget with a warning log on failure. A backfill script (F18-S06) can reconcile missing issues later.

**Acceptance criteria:**

- [ ] Finding dict gains optional `target_repo` field (defaults to `hackstert/ezra-assistant`)
- [ ] `write_improvement_story()` calls `github_issues.create` after local file write
- [ ] GitHub failure does not break local story writing or Telegram notification
- [ ] Story file gains a `github_issue: <URL>` frontmatter field on success
- [ ] Telegram notification format updated to include GitHub issue URL
- [ ] Logged warning if GitHub sync fails, no exception raised

---

### F18-S03: GitHub Actions Agent Executor

**Priority:** must-have
**Dependencies:** F18-S02

Create a GitHub Actions workflow that fires when an issue receives the `agent-ready` label. The workflow checks out the repository, invokes Claude Code via the Anthropic SDK with the issue body as the work specification, and produces a draft pull request linked to the issue.

**File:** `.github/workflows/agent-execute.yml`

**Trigger:** `issues` event, filtered to `types: [labeled]` where the label is `agent-ready`.

**Steps:**

1. Checkout the repository on a GitHub-hosted runner
2. Install Python 3.12 + project dependencies
3. Install Claude Code or the Anthropic SDK (pinned version)
4. Read the issue body via `gh issue view --json body,title,number,labels`
5. Invoke the coding agent with a system prompt derived from the repo's `CLAUDE.md` + the issue body as the task
6. Let the agent create a branch, implement, run tests, and commit
7. Push the branch and open a draft PR linked to the issue with `gh pr create --draft --title "Closes #$ISSUE_NUM: ..."`
8. Comment on the issue with a link to the draft PR

**Secrets required:**

- `ANTHROPIC_API_KEY` — for the coding agent
- `GH_PAT` — for branch push and PR creation (if the default `GITHUB_TOKEN` has insufficient scope)

**Execution bounds:**

- Timeout: 30 minutes per run
- Concurrency: one agent per issue; if the same issue gets `agent-ready` re-applied, the second run is skipped

**Why Claude Code, not Grok:** This is the scenario where the Anthropic SDK ecosystem is genuinely more polished than a custom approach. The Claude Code CLI handles agent harness concerns (tool use, error recovery, file editing, test running) that would require significant custom work to replicate against the xAI Responses API. The cost delta is acceptable at the volume F18 produces (one PR per week or two). Grok remains Ezra's primary runtime model; Claude Code is used specifically for this coding-agent role in Actions.

**Acceptance criteria:**

- [ ] Workflow file exists at `.github/workflows/agent-execute.yml`
- [ ] Secrets `ANTHROPIC_API_KEY` and optionally `GH_PAT` set in repo
- [ ] Workflow triggers only on `agent-ready` label, not other labels
- [ ] Agent run produces a branch with commits and a draft PR on success
- [ ] PR references the issue with `Closes #N` syntax so merge auto-closes
- [ ] Failed runs comment on the issue with the error summary
- [ ] Workflow tested on at least one low-risk token-domain issue before enabling for other domains

---

### F18-S04: GitHub Webhook Handler in Ezra

**Priority:** should-have
**Dependencies:** F18-S02, F18-S03

Add a webhook receiver to Ezra's FastAPI server that listens for GitHub events and keeps local state synchronized with GitHub state.

**Endpoint:** `POST /api/webhooks/github`

**Events handled:**

| Event                          | Action in Ezra                                                    |
| ------------------------------ | ----------------------------------------------------------------- |
| `issues.closed` (via merge)  | Move story file `active/` → `completed/`, log to state.json |
| `issues.closed` (manual)     | Move story file `active/` → `rejected/` (new folder)         |
| `pull_request.opened`        | Record PR URL in story file frontmatter                           |
| `pull_request.closed` merged | Mark improvement as successful in state.json                      |
| `issue_comment.created`      | Forward to Telegram if commenter is not hackstert                 |

**Security:** GitHub webhook signature verification via `X-Hub-Signature-256` header and the shared secret stored in `GITHUB_WEBHOOK_SECRET`. Reject any request with invalid signature.

**Exposure:** Ezra runs locally on port 8400. The webhook endpoint is exposed via Cloudflare Tunnel (already set up in LAN-Central-Command infrastructure) at a dedicated subdomain. No port forwarding, no public IP exposure.

**Fallback:** If the webhook is unreachable, a reconciliation job (F18-S06) can run on demand or on a schedule to close the gap.

**Acceptance criteria:**

- [ ] `POST /api/webhooks/github` endpoint in `routes/webhooks.py`
- [ ] Signature verification implemented and tested
- [ ] Cloudflare Tunnel configured with dedicated subdomain for webhook traffic
- [ ] Webhook secret stored in repo settings and in `.env`
- [ ] Story file lifecycle (active → completed / rejected) driven by webhook events
- [ ] Manual reconciliation script documented for gap recovery

---

### F18-S05: Issue Template and Triage Conventions

**Priority:** should-have
**Dependencies:** F18-S02

Standardize issue formats across repositories so scanner-created issues and human-created issues share structure, and so the `agent-execute` workflow can rely on consistent input.

**Files:**

- `.github/ISSUE_TEMPLATE/scanner-improvement.yml` — matches F18-S02 output exactly
- `.github/ISSUE_TEMPLATE/manual-improvement.yml` — human-authored version with the same sections
- `.github/ISSUE_TEMPLATE/bug.yml` — for runtime issues discovered during use
- `.github/ISSUE_TEMPLATE/config.yml` — disables blank issues, sets default labels

**Label taxonomy:**

```
type:*          improvement | bug | enhancement | question
domain:*        skill_gaps | memory | tokens | skills | infrastructure | theology
priority:*      must-have | should-have | nice-to-have
status:*        triage | agent-ready | in-review | blocked
```

**Workflow gates:**

- Issues land with `type:*` and `domain:*` labels from the template
- `priority:*` is applied at creation by scanner or human
- `status:triage` is the default state; `status:agent-ready` triggers F18-S03
- `status:blocked` halts any agent work until cleared

**Acceptance criteria:**

- [ ] Issue templates created in `.github/ISSUE_TEMPLATE/` for each category
- [ ] Label taxonomy created in the repo with descriptions
- [ ] Scanner-created issues use the scanner template structure
- [ ] Documented in `docs/improvement-system.md` under a new "GitHub Integration" section

---

### F18-S06: Reconciliation and Backfill

**Priority:** nice-to-have
**Dependencies:** F18-S02, F18-S04

Handle drift between local state and GitHub state. Drift can occur when: the webhook is unreachable, the GitHub API is rate-limited, Ezra is offline when a scanner would have created an issue, or manual changes happen on one side without the other knowing.

**CLI commands added to `python -m ezra`:**

```
/improvement sync           # list active/ files without issues, closed issues without completed/ files
/improvement sync --apply   # create missing issues, move story files for closed issues
/improvement retire <id>    # manually close an issue and move story to rejected/
```

**Background task:** `improvement_reconcile` cron job runs once daily, reports drift via Telegram but does not auto-apply changes. Auto-apply requires explicit `--apply` flag, human-invoked.

**Acceptance criteria:**

- [ ] CLI subcommands implemented
- [ ] Cron job registered with reporting-only default
- [ ] Drift report delivered via Telegram if any detected
- [ ] Documented in `docs/improvement-system.md`

---

### F18-S07: Extend to Selah and Voice of Repentance Repos

**Priority:** should-have
**Dependencies:** F18-S01 through F18-S05

Once the pattern is stable in `ezra-assistant`, replicate it into `selah` and `voice-of-repentance` repositories.

**Per-repo work:**

- Copy `.github/workflows/agent-execute.yml` with repo-specific adjustments
- Copy `.github/ISSUE_TEMPLATE/*` templates
- Create label taxonomy in the new repo
- Add the new repo to the `allowed_repos` list in `github_issues` skill
- For Selah: add a `theology` domain to the label taxonomy and a stricter review gate (see Selah Guardrails below)

**Selah guardrails:** The `agent-execute` workflow in the Selah repo includes an additional check: if the diff touches any file under `selah/theology/`, `selah/training/`, or `selah/prompts/`, the PR is created in draft mode with a mandatory "theological review required" label, and a Telegram notification specifically flags the change for manual review. No automated merge path exists for these files regardless of other settings.

**Acceptance criteria:**

- [ ] `selah` and `voice-of-repentance` repos have issue templates and workflows installed
- [ ] Selah theology guardrails tested with a dummy change to a guarded path
- [ ] `github_issues` skill's `allowed_repos` list includes all three
- [ ] `docs/improvement-system.md` updated with per-repo conventions

---

### F18-S08: Pattern Mining from Historical Issues

**Priority:** nice-to-have
**Dependencies:** 30+ closed issues in the corpus

Once enough issues have been closed, add a scanner that mines the historical corpus for patterns. This is the "system models its own improvement history" goal from the F15 canvas.

**New scanner:** `improvements/scanners/patterns.py`

**What it reads:**

- All closed issues with label `improvement` from the last 90 days
- Their linked PRs and merge outcomes
- Rejection reasons from issues closed without a PR

**What it produces:** A `PatternFinding` like any other scanner. Example outputs:

- "Three memory-domain issues closed with no action in 60 days — scanner may be over-triggering on normal embedding coverage fluctuation"
- "Token-domain recommendations have 100% merge rate but 0 measurable cost reduction — rec quality needs revision"
- "Skill-gap scanner has proposed `apple_reminders` improvements four times; consider consolidating into one feature canvas"

**Why this matters for Selah:** Over time, the pattern scanner will surface which domains benefit most from automation and which require manual care. For theological content, expect high rejection rates — that data informs whether the scanner should even touch those domains.

**Acceptance criteria:**

- [ ] `scan_patterns()` function returns a `PatternFinding` or `None`
- [ ] Added to `_DOMAINS` rotation in `scheduler.py`
- [ ] Gated: only runs if closed-issue corpus > 30 items
- [ ] Produces at most one finding per cycle, same contract as other scanners

---

## Milestones

### M1 — Working end-to-end on Ezra (target: 2-3 weeks)

- F18-S01: `github_issues` skill
- F18-S02: Scanner-to-issue bridge
- F18-S05: Issue templates and labels

**Exit criterion:** Next scanner finding creates a GitHub issue automatically. No agent execution yet.

### M2 — Agent execution on Ezra (target: 1-2 weeks after M1)

- F18-S03: GitHub Actions agent executor
- F18-S04: Webhook handler

**Exit criterion:** Applying `agent-ready` label to a scanner-created issue produces a draft PR within 30 minutes. One full cycle completed (issue → PR → merge → file moved to completed/).

### M3 — Expansion to Selah and Voice of Repentance (target: 2 weeks after M2)

- F18-S07: Extend to additional repos with Selah guardrails
- F18-S06: Reconciliation tooling

**Exit criterion:** All three repos have the pattern installed. Selah guardrails tested. Reconciliation script runs clean.

### M4 — Self-modeling (target: open-ended, triggered by corpus size)

- F18-S08: Pattern mining scanner

**Exit criterion:** Pattern scanner runs on a corpus of 30+ closed issues and produces its first finding.

---

## Dependencies

**Existing Ezra components:**

- F15 improvement scanners (complete) — source of findings
- F16 Cron Center (complete) — operational visibility
- `send_email` skill (F17 complete) — not required but available for PR notifications
- Cloudflare Tunnels in LAN-Central-Command — webhook ingress

**External:**

- GitHub Pro subscription (active) — Actions minutes, private repos
- Anthropic API key — Claude Code in Actions
- PyGithub library — Python GitHub API client

**Not required:**

- Archon workflow engine (see Honorable Mention below)
- MCP server infrastructure
- Any multi-agent orchestration platform

---

## Risks and Mitigations

**Agent produces a bad PR and merges itself.** Impossible by construction. Merge is a human action; the agent cannot merge PRs. Even if the agent opens a PR with `auto-merge: true` set, GitHub's branch protection rules (enforced as a repo-level setting in M1) require explicit review approval.

**Scanner over-triggers, GitHub fills with noise.** Mitigated by: (1) F15's "one finding per run" rule, (2) F18-S08 pattern scanner surfaces over-triggering as a finding itself, (3) issues sitting in `status:triage` without action are visible drift.

**Anthropic API cost creeps up.** Bounded by the scanner cadence (one finding per ~9 days). Even with generous token usage per agent run, one PR every 1-2 weeks produces costs in the low tens of dollars per month, well below the Grok savings Ezra is already capturing elsewhere.

**Selah changes get automated when they shouldn't.** Mitigated by F18-S07 guardrails: path-based triggers block automation on theological content. The Telegram flag ensures Troy sees every Selah change, regardless of scanner confidence.

**Webhook endpoint gets probed or attacked.** Mitigated by signature verification, Cloudflare Tunnel (no public IP exposure), and rate limiting at the Cloudflare layer.

**GitHub Actions runs consume the Pro monthly allocation.** At one PR every 1-2 weeks with 30-minute timeout, annual consumption is under 800 minutes, well within the 2,000-minute Pro allowance. Monitored via GitHub's built-in usage dashboard.

---

## Out of Scope

**Public-repo workflows.** F18 targets private repos only. If Voice of Repentance or Selah eventually have public components (e.g., a static site for ministry content), public-repo automation is a separate canvas.

**AI Labor Solutions client workflows.** Explicitly out of scope. This is personal-environment tooling for Troy's three repos. Any future productization for ALS clients is a separate product canvas.

**Multi-agent orchestration.** One agent per workflow run. No supervisor, no delegation, no parallel agents. Archon's value proposition includes this; F18 does not.

**Automatic merge or auto-deploy.** Human approval is mandatory at the merge gate. Any future auto-merge proposal requires a separate PRD with explicit risk analysis.

---

## Honorable Mention: Archon

Archon is a recently-rewritten open-source workflow engine for AI coding agents. It encodes development processes as deterministic YAML workflows (plan → implement → test → review → PR), runs each workflow in an isolated git worktree, and supports multi-interface triggering from CLI, Web UI, Slack, Telegram, and GitHub.

Archon is genuinely impressive for its intended use case: teams running multiple parallel coding agents across many workflow types, needing shareable and versioned workflow definitions.

**Why F18 uses GitHub-native primitives instead:**

At Troy's scale (one scanner finding every 9 days, one PR every 1-2 weeks), GitHub Actions provides everything Archon provides at the workflow level: deterministic YAML execution, isolated runners, composable steps mixing bash and AI, secrets management, and triggering from issues. The integration with GitHub Issues, PRs, and reviews is native rather than bridged. No additional service to run, no additional config layer to maintain, no beta-quality software in the critical path.

**When to revisit Archon:**

1. If parallel agent execution becomes necessary (multiple issues worked simultaneously with conflict-free isolation)
2. If the workflow catalog grows beyond what a single Actions file can express cleanly (e.g., separate workflows for bug fixes, features, refactors, security patches, each with different phase structures)
3. If non-GitHub triggers become important (Slack-based workflow dispatch, Telegram-initiated runs, workflows that run against local repos not yet pushed)
4. If AI Labor Solutions clients ever request a workflow harness as a product — Archon would be a strong candidate for that business case, but that is explicitly out of scope for F18

For now: GitHub Actions is the right tool. Archon is respected and filed away for when scale or scope demands it.

---

## Success Criteria

F18 is successful when, six months after M2 completes:

- At least 15 scanner-to-PR cycles have completed successfully
- Merge rate on scanner-created PRs is above 50% (low-quality proposals are a scanner problem, not a workflow problem)
- No Selah theological content has been merged without explicit Troy review
- The improvement loop has produced at least one measurable system improvement (reduced token cost, higher embedding coverage, new skill that resolved a recurring conversation pattern)
- Troy's manual effort per improvement cycle is: review the PR, merge or reject. Nothing else required.

---

## Related Documentation

| Document                                       | Relationship to F18                               |
| ---------------------------------------------- | ------------------------------------------------- |
| `docs/improvement-system.md`                 | F15/F16 foundation; F18 extends it                |
| `docs/skill-inventory.md`                    | `github_issues` added under Tier 1              |
| `docs/memory-guide.md`                       | Unchanged; BolusStore is not involved in F18      |
| `docs/cron-config.md`                        | New `improvement_reconcile` background task     |
| `selah/docs/theology-guardrails.md` (new)    | Expand in M3 for F18-S07 Selah-specific concerns  |

---

*Created: 2026-04-18 | Status: Proposed*
