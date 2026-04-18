# Harvester Repo Onboarding Guide

**Purpose:** How to bring a new repository under Harvester's watch — from first assessment through active improvement cycling.
**Audience:** Troy (the human operator) and the agent conducting the assessment.
**Future skill:** This guide is the specification for a Claude Code skill (`repo-onboard`) that will automate the assessment phase. See the skill-creator reference at the end.

---

## What Onboarding Means

Adding a repo to Harvester is not just appending an entry to `harvester-config.yaml`. Before Harvester can run useful scanners, you need to understand the repo well enough to answer three questions:

1. What does this repo actually do, and what are its quality constraints?
2. Which Harvester scanners apply, and at what cadence?
3. What should the agents working on this repo be told in `CLAUDE.md`?

Onboarding is a structured assessment that answers all three. It produces two artifacts: a `CLAUDE.md` for the repo (the agent system prompt every overnight improvement agent will read) and a `harvester-config.yaml` entry (the scanner configuration). Without both, Harvester cannot safely dispatch agents.

---

## When to Onboard

Onboard a repo when:
- It has enough code or content to produce meaningful improvement findings
- Troy is actively working on it and will actually review PRs
- A `CLAUDE.md` can be written that meaningfully constrains agent behavior

Do not onboard a repo that is a placeholder, a template copy, or something you have not touched in months. Harvester is an active improvement system, not a monitoring dashboard.

**Current watch list:** Ezra (`ezra-assistant`), Selah, Voice of Repentance.

---

## What Troy Provides

Before the assessment begins, Troy provides:
- Local path to the repo (`~/Projects/<repo-name>/`)
- GitHub repo slug (`hackstert/<repo-name>`)
- One paragraph describing what the repo is and what it does
- Any constraints that are non-negotiable (theological content, clinical content, security surface)
- Whether this is an **agent repo** (a repo that itself runs AI agents) or a **standard repo** (code, content, infrastructure without embedded LLM orchestration)

The agent-vs-standard distinction matters because agent repos carry additional assessment dimensions — memory system design, prompt architecture, LLM provider conventions — that standard repos do not.

---

## The Assessment Process

The onboarding agent reads the repo, then produces a written assessment before touching any config. The assessment is not a PR — it is a structured document that Troy reviews before anything gets committed to `harvester-config.yaml` or the repo's `CLAUDE.md`.

### Phase 1: Structural Survey (read-only)

Read these files in order, building a mental model of the codebase:

1. `README.md` — what the repo claims to be
2. `pyproject.toml` / `package.json` — runtime stack, dependencies, scripts
3. Top-level directory structure — understand the layout before reading code
4. Entry points (`__main__.py`, `main.py`, `index.ts`, `server.ts`, etc.)
5. Existing `CLAUDE.md` if present — what has already been said to agents
6. Any `docs/` folder — look for technical guides, architecture docs, ADRs

Do not read every file. Build a representation from the skeleton first.

### Phase 2: Dimension Assessment

Assess each dimension below. Not every dimension applies to every repo — skip ones that are clearly irrelevant and note why.

#### 2.1 Code Structure and Organization

- Does the directory layout have a clear logic? Can you predict where things are?
- Are there files that are doing too much (god modules, oversized files)?
- Are there obvious dead code candidates (imports with no uses, files that are never referenced)?
- Is there a consistent naming convention, or has it drifted?
- Are there multiple competing patterns for the same concern (e.g., two different ways to handle config)?

#### 2.2 Documentation Quality

- Does `README.md` accurately describe the current state, or is it outdated?
- Is there a technical guide or architecture document? If yes, is it accurate?
- Are functions and modules self-documenting (good naming) or do they require comments to be understood?
- If there is a `CLAUDE.md`, does it accurately describe the codebase, or does it contain stale information that would mislead an agent?
- What documentation is missing that an overnight agent would need to work safely?

#### 2.3 Test Coverage

- Does a test suite exist? If yes, what framework?
- Are there obvious gaps — public APIs with no tests, critical paths untested?
- Are tests meaningful (test behavior) or shallow (test that functions exist)?
- Does the CI/CD pipeline (if any) run tests automatically?
- What would a failing agent test look like in this repo — would it be caught?

#### 2.4 Dependency Health

- How many dependencies? Is the list reasonable for what the project does?
- Are any dependencies unpinned (latest, `^version`) creating instability risk?
- Are there dependencies that appear unused?
- Are there dependencies with known security advisories (check PyPI advisory database or npm audit)?
- When was the most recent dependency update? Stale dependency sets accumulate risk.

#### 2.5 Technical Debt Indicators

- TODO/FIXME comments — how many, how old (check git blame), in what areas?
- Commented-out code blocks — these are usually accidents waiting to be cleaned up
- Functions with cyclomatic complexity above 10 (branching logic that is difficult to reason about)
- Copy-paste patterns — the same logic appearing in multiple places without abstraction

#### 2.6 Security Surface

- Are secrets ever hardcoded or logged? (Search for API key patterns, passwords, tokens in non-env files)
- Are there file path operations that accept user input without sanitization?
- Are there subprocess calls that construct shell commands from variables?
- Is there any web-facing surface (FastAPI endpoints, HTTP routes)? If yes, is input validation present?
- For repos with databases: are there parameterized queries, or string-formatted SQL?

#### 2.7 Agent-Repo Specific Dimensions

**Only applicable to repos that run AI agents (Ezra, Selah, future agent systems).**

**Memory system design:**
- How is long-term memory structured? Is there a clear schema?
- Are there invariants that must be maintained across memory operations (embedding models, namespace rules, decay behavior)?
- What happens if an agent modifies memory incorrectly — is it recoverable?
- Is there a test strategy for memory operations, or is memory largely untested?

**Prompt and system prompt architecture:**
- Where does the system prompt live, and how is it assembled?
- Are there hardcoded assumptions in the prompt that conflict with current behavior?
- Is the persona clearly separated from the operational instructions?
- What would happen if an agent modified the system prompt incorrectly?

**LLM provider conventions:**
- What providers are in use? Are they swappable or tightly coupled?
- Are there cost controls (token limits, caching, model fallbacks)?
- Is there a clear mechanism for adding or switching models?

**Skill or tool architecture:**
- How are skills/tools organized? Is the pattern consistent?
- Are skills self-contained, or do they have hidden dependencies on each other?
- Is there a clear process for adding a new skill without breaking existing ones?

**Context and state management:**
- How is conversation state managed? Is it durable across restarts?
- Are there race conditions possible if multiple requests come in simultaneously?
- What is the recovery path if the state database gets corrupted?

---

### Phase 3: Scanner Selection

Based on the assessment, recommend which Harvester scanners to activate and at what cadence. Available scanners:

| Scanner | What it finds | Applies when |
|---|---|---|
| `skill_gaps` | Conversation vs. skill inventory gaps | Agent repos only |
| `memory` | BolusStore metrics, embedding coverage, stale facts | Ezra-compatible memory system only |
| `tokens` | 7-day LLM spend, cache hit rate, per-call cost | Any repo with LLM API usage |
| `code_health` | Oversized files, high complexity, stale TODOs, missing type hints | Any Python repo |
| `theology_review` | Theological content consistency and doctrinal alignment | Selah and VoR only |
| `dependency_freshness` | Unpinned or stale dependencies | Any repo with a lock file |
| `test_coverage` | Coverage gaps by module | Any repo with a test suite |
| `cross_repo_patterns` | Meta: patterns across all repos | Runs on Harvester itself, not per-repo |

Cadence guidelines:
- Code quality scanners (`code_health`, `test_coverage`): 7-14 days
- Domain-specific scanners (`skill_gaps`, `memory`, `tokens`): 9-14 days
- Slow-moving concerns (`dependency_freshness`, `theology_review`): 21-30 days

---

### Phase 4: Assessment Report

The assessment agent writes a structured report before touching any config. Format:

```markdown
# Onboarding Assessment: <repo-name>

**Date:** YYYY-MM-DD
**Repo:** <github-slug>
**Type:** Agent repo | Standard repo

## Executive Summary
[2-3 sentences: overall health, top 3 concerns, recommended scanner set]

## Dimension Findings

### Code Structure
[findings or "No issues identified"]

### Documentation
[findings — especially any CLAUDE.md gaps]

### Test Coverage
[findings]

### Dependency Health
[findings]

### Technical Debt
[findings]

### Security Surface
[findings]

### Agent-Repo Dimensions (if applicable)
[findings per sub-dimension]

## Recommended Scanner Configuration

| Scanner | Cadence |
|---|---|
| scanner_name | X days |

## Guarded Paths

[List any paths that should be `never_execute`, or "None"]

## CLAUDE.md Gaps

[What is missing or stale in the current CLAUDE.md, or what the new one should cover]

## Recommended First Issues

[3-5 specific, concrete findings that would make good initial GitHub issues — these are the first things Harvester should surface]

## Open Questions for Troy

[Anything the assessment cannot resolve without human input]
```

Troy reviews this report before any `harvester-config.yaml` entry or `CLAUDE.md` is written.

---

## Phase 5: Configuration Artifacts

After Troy approves the assessment, produce two artifacts:

### 5.1 `CLAUDE.md` for the repo

Every repo that Harvester dispatches agents to needs a `CLAUDE.md` at its root. The file does three things:

1. **Orients the agent** — what this repo is, what it is not, the agent's role
2. **Constrains agent behavior** — coding conventions, what not to touch, commit format
3. **Names invariants** — any rules that, if violated, corrupt data or break behavior

For agent repos, the `CLAUDE.md` must additionally cover memory system invariants, skill patterns, and LLM provider conventions — because agents working on agent code can do significant damage if they violate these without knowing they exist.

Use `docs/ezra-technical-guide.md` and the Ezra `CLAUDE.md` as a reference for what a well-formed agent-repo `CLAUDE.md` looks like.

### 5.2 `harvester-config.yaml` entry

```yaml
- name: <repo-name>
  github: hackstert/<repo-name>
  local_path: ~/Projects/<repo-name>
  claude_md_path: CLAUDE.md
  scanners:
    - name: <scanner>
      cadence_days: <N>
  label_prefix: improvement
  priority_labels: [must-have, should-have, nice-to-have]
  guarded_paths:
    - "<path>/**"             # if applicable
  guarded_path_policy: never_execute   # if guarded paths exist
  branch_prefix: improvement/
  draft_pr_default: true
```

---

## GitHub Setup Per Repo

When a repo is added to Harvester, several one-time GitHub configurations are required. These are manual steps — Harvester does not automate them (it does create labels automatically on startup, but the rest require clicking in GitHub settings).

### Required manual steps (in order)

**1. Fine-grained PAT scope**
Ensure the `GITHUB_TOKEN` in Harvester's `.env` has Issues (read + write) and Pull Requests (read + write) access to the new repo. Edit the token in GitHub → Settings → Developer Settings → Personal Access Tokens → Fine-grained tokens.

**2. Webhook**
GitHub → repo → Settings → Webhooks → Add webhook:
- Payload URL: your Cloudflare Tunnel URL + `/webhook`
- Content type: `application/json`
- Secret: the value in Harvester's `GITHUB_WEBHOOK_SECRET` env var
- Events: select "Issues" and "Pull requests"

**3. Branch protection on `main`**
GitHub → repo → Settings → Branches → Add rule for `main`:
- Require a pull request before merging
- Require at least 1 approving review
- Require status checks to pass (if CI exists)
- Do not allow bypassing the above settings

For Selah, add: require 2 approving reviews for PRs touching guarded paths (requires GitHub branch protection paths feature or enforcement via the runner layer).

**4. Label verification**
Start Harvester (`python -m harvester serve`) and confirm the label taxonomy was created in the new repo. Check GitHub → repo → Issues → Labels. You should see the full set including `agent-ready`, `improvement`, `scanner:*`, `domain:*`, `priority:*`.

---

## Onboarding Checklist

Before marking a repo as onboarded:

- [ ] Assessment report written and reviewed by Troy
- [ ] Open questions from assessment resolved
- [ ] `CLAUDE.md` written or updated in the repo
- [ ] `harvester-config.yaml` entry added and validated (`python -m harvester validate`)
- [ ] Fine-grained PAT includes the new repo
- [ ] GitHub webhook configured and tested (ping event received)
- [ ] Branch protection on `main` configured
- [ ] Labels created (verified in GitHub → Issues → Labels)
- [ ] At least one scanner run manually: `python -m harvester scan <repo-name> <scanner>`
- [ ] First real finding reviewed by Troy

---

## Future: Repo Onboard Skill

This guide will be formalized as a Claude Code skill (`repo-onboard`) that automates Phase 1-4 of the assessment. The skill will:

- Accept a local repo path and GitHub slug
- Conduct the structural survey and dimension assessment autonomously
- Produce the assessment report for Troy's review
- On approval, generate the `CLAUDE.md` draft and `harvester-config.yaml` entry
- Walk Troy through the GitHub manual steps

**Skill format reference:** `/Users/hackstert/Atlas/.atlas/skills/skill-creator/SKILL.md`

The skill will live at `~/.claude/skills/repo-onboard/` following the Claude Code skill convention. It will not be built until the onboarding workflow has been exercised manually at least once (with Selah as the test case) so the skill captures real-world refinements rather than theoretical steps.

---

*Created: 2026-04-18 | Status: Draft — to be refined after first manual onboarding (Selah)*
