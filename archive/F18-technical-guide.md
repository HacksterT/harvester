# F18 Technical Guide: GitHub-Native Improvement Workflow

**Companion to:** `F18-github-improvement-loop.md` (feature canvas)
**Purpose:** Explain the runtime architecture, compute topology, data flow, and operational semantics of the improvement loop so the pattern can be understood, debugged, and extended.
**Audience:** Troy (HacksterT), future contributors to the Ezra ecosystem, and any agent working on F18 implementation.

---

## 1. The Mental Model

This system has two runtimes that never talk to each other directly. They are coordinated by a shared medium — the GitHub repository — and a shared contract — the structure of issues and pull requests.

**Runtime A: Ezra.** Runs continuously on your Mac. Observes the system. Produces findings. Creates issues. Handles webhooks.

**Runtime B: Claude Code.** Runs ephemerally in GitHub's cloud. Reads one issue. Writes code. Opens one PR. Disappears.

**The medium: GitHub.** Holds issues, labels, branches, PRs, reviews, merge state, and audit history.

**The contract:** An issue created by Ezra has a predictable structure (title, body, labels). A PR opened by Claude Code references the issue with `Closes #N` syntax. That's the entire protocol between the two runtimes.

This separation is the architectural point. Once you see it, everything else falls into place.

---

## 2. Compute Topology

Understanding where each piece runs makes the whole system easier to reason about, debug, and budget.

### 2.1 Your Mac (Ezra's home)

The Ezra FastAPI server runs here as a long-lived process. It is always on (or at least on whenever you're working). Components that live on your Mac:

- FastAPI server on port 8400
- BolusStore SQLite database (`data/memory/boluses.db`)
- LangGraph checkpointer database (`data/state/ezra.db`)
- Knowledge store databases (`data/knowledge/*.db`)
- Ollama server for embeddings and Selah-Q8
- Background tasks: memory decay, improvement scans, improvement reconcile
- New in F18: webhook handler endpoint

Ezra never calls Anthropic's API. Ezra uses Grok (xAI) as its primary LLM and Selah-Q8 (local via Ollama) as its secondary. This stays unchanged in F18.

### 2.2 GitHub's Cloud (where coding happens)

When you apply the `agent-ready` label to an issue, GitHub immediately allocates a fresh virtual machine from its hosted runner pool. The specifications of that VM (as of April 2026):

- Ubuntu 24.04 LTS
- 4-core CPU
- 16 GB RAM
- 14 GB SSD
- 30-minute default timeout (configurable up to 6 hours)
- Network access to the public internet including Anthropic's API

This VM is ephemeral. It exists only for the duration of your workflow run. Once the workflow completes (success or failure), the VM is destroyed. Nothing persists. The next run gets a completely fresh VM.

**What runs on the runner:**

1. `git checkout` of your repository at the current default branch
2. Python 3.12 installation (via `actions/setup-python`)
3. Your project dependencies (`pip install -e .` or `uv sync`)
4. Node.js installation (for Claude Code CLI)
5. Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
6. The actual agent execution — this is where Claude Code reads the issue, edits files, runs tests, and commits
7. `git push` of the new branch
8. `gh pr create` to open the pull request

All of this happens on GitHub's infrastructure. Your Mac, your home internet, your local resources — none are involved.

### 2.3 Anthropic's Cloud (where the LLM actually runs)

Claude itself runs on Anthropic's servers. The Claude Code CLI on the GitHub runner makes HTTPS calls to `api.anthropic.com`. The CLI is a client; Claude is the server.

The `ANTHROPIC_API_KEY` secret stored in your repo settings is passed to the runner as an environment variable at run time. The CLI uses it to authenticate. Tokens are billed against your Anthropic account normally. The fact that the calls originate from a GitHub runner rather than your Mac is invisible to Anthropic's billing — it's the same API, same pricing, same rate limits.

### 2.4 xAI's Cloud (where Grok lives)

Grok runs on xAI's servers. Ezra's server on your Mac makes HTTPS calls to `api.x.ai` via the xAI Responses API. This is orthogonal to F18 and unchanged. Grok is only used by Ezra, never by Claude Code.

### 2.5 The Complete Picture

```
┌──────────────────────────────────────────────────────────────┐
│  Your Mac (home, always on)                                  │
│                                                              │
│  Ezra Server                                                 │
│   │                                                          │
│   ├─→ Grok (xAI cloud) ────────── chat, memory, scanners     │
│   │                                                          │
│   ├─→ Ollama (localhost) ──────── embeddings, Selah-Q8       │
│   │                                                          │
│   └─→ GitHub API ──────────────── create issues, webhooks    │
│                                                              │
└──────────────────┬───────────────────────────────────────────┘
                   │ issues, comments
                   ▼
┌──────────────────────────────────────────────────────────────┐
│  GitHub (cloud)                                              │
│                                                              │
│  Repository: ezra-assistant                                  │
│   ├─ Issues (where scanner findings land)                    │
│   ├─ Labels (triage state)                                   │
│   ├─ Workflows (.github/workflows/*.yml)                     │
│   ├─ Actions (runner allocation and orchestration)           │
│   └─ Pull Requests (agent output)                            │
│                                                              │
│  When `agent-ready` label applied:                           │
│   GitHub allocates → Runner VM (ephemeral)                   │
│                       │                                      │
│                       │ checkouts code, installs deps        │
│                       │ invokes Claude Code CLI              │
│                       │                                      │
│                       └─→ Anthropic API ── writes code       │
│                           (Claude model runs here)           │
│                                                              │
│  Runner terminates, PR exists, issue linked                  │
│                                                              │
└──────────────────┬───────────────────────────────────────────┘
                   │ webhook events
                   ▼
┌──────────────────────────────────────────────────────────────┐
│  Cloudflare Tunnel (edge)                                    │
│   │ signature-verified webhook forwarded                     │
│   ▼                                                          │
│  Your Mac → Ezra webhook handler → story file lifecycle      │
└──────────────────────────────────────────────────────────────┘
```

Three clouds, one local machine, one edge tunnel, four independent billing relationships. No single point of total failure. Any of the clouds can be down and the others continue functioning with graceful degradation.

---

## 3. The Contract Between Runtimes

Since Ezra and Claude Code never talk directly, everything they need to communicate must be encoded in what they share: the GitHub issue.

### 3.1 Issue Structure (Ezra writes, Claude Code reads)

```markdown
Title: [IMPROVEMENT] Reduce repeated system prompt via previous_response_id caching

## Summary
7-day cache hit rate is 12%. Target is 40%+. Implementing previous_response_id
chaining in the xAI provider will reduce input token costs substantially.

## Evidence
- Total input tokens (7d): 2.4M
- Cached tokens (7d): 290K (12.1%)
- Total cost (7d): $4.82
- Target cache rate: 40% (projected savings: $1.90/week)

Raw metric snapshot:
{
  "avg_input_tokens_per_call": 8421,
  "calls_per_day": 42,
  "cached_ratio": 0.121
}

## Acceptance Criteria
- [ ] previous_response_id chained across conversation turns in xai.py
- [ ] Cache hit rate measurable via new metric in token_log
- [ ] 7-day cache rate exceeds 35% on subsequent scanner run
- [ ] No regression in response quality (manual spot check)

## Tasks
- [ ] Modify src/ezra/providers/xai.py to track and pass previous_response_id
- [ ] Add cached_from_previous field to token_log schema
- [ ] Update scanner to include cache rate trend in future findings
- [ ] Test with conversation of 10+ turns, verify caching behavior

---
**Domain:** tokens
**Priority:** should-have
**Story file:** tasks/improvements/active/IMP-20260425-tokens.md
**Generated:** 2026-04-25 14:30 by Ezra improvement scanner

Labels: improvement, domain:tokens, priority:should-have
```

This structure is the protocol. Every field has a purpose:

- **Title** — the PR title template derives from this ("Closes #N: <title without prefix>")
- **Summary** — tells Claude Code what problem to solve in plain language
- **Evidence** — gives Claude Code enough data to verify the problem is real and scope the solution
- **Acceptance Criteria** — the definition of done, used by Claude Code to know when to stop
- **Tasks** — concrete steps, useful as a checklist for the agent's self-review
- **Domain / Priority / Story file** — metadata for the workflow router and the audit trail
- **Labels** — structured filtering for the workflow trigger

Claude Code does not need to understand Ezra's internal architecture. It only needs to read this issue format and produce a PR that addresses it.

### 3.2 PR Structure (Claude Code writes, Ezra reads)

```markdown
Title: Closes #47: Reduce repeated system prompt via previous_response_id caching

## What changed
- `src/ezra/providers/xai.py`: Added previous_response_id state tracking on the
  ChatGraph instance, threaded through the xAI Responses API calls
- `src/ezra/memory/store.py`: Added cached_from_previous column to token_log
- `alembic/versions/...`: Migration for the new column
- `tests/providers/test_xai.py`: Tests covering the new caching behavior

## Plan followed
1. Explored xai.py and identified the request construction point
2. Added a thread-local previous_response_id attribute on the provider
3. Wrote tests first to verify the cache-hit path
4. Implemented the change
5. Ran full test suite: 247 passed, 0 failed
6. Spot-checked cache hit rate in manual conversation: 48% over 8 turns

## Testing
- [x] All existing tests pass
- [x] New tests added for caching behavior
- [x] Manual verification of cache hit rate on test conversation

Closes #47
```

Again, every element has a purpose. The `Closes #47` syntax at the bottom is what tells GitHub to auto-close the issue when the PR merges. The "What changed" section lets Troy review without reading every line of the diff. The "Plan followed" section is the agent's reasoning — valuable for the F18-S08 pattern miner that will eventually mine historical PRs for signal.

### 3.3 Why This Contract Is Durable

Because the contract is structured markdown in a GitHub issue, it survives:

- Changes to Ezra's internal architecture (swap Grok for any other LLM — issue format unchanged)
- Changes to the coding agent (swap Claude Code for any other SDK-based agent — it just needs to read markdown)
- Changes to GitHub's UI or API (the core entities of issue/label/PR are stable)
- Changes to your local file structure (Ezra's story format can evolve; the issue is a projection)

This is the kind of decoupling that makes systems age gracefully. Neither runtime has a deep dependency on the other. Both depend on a simple text contract.

---

## 4. Data Flow, End to End

Let's trace a single improvement cycle from scanner to merge to file system.

### 4.1 Scanner Fires (T+0 minutes, on your Mac)

The improvement scheduler wakes at its scheduled interval. It's the `tokens` domain's turn. The scanner:

1. Queries `BolusStore.get_token_stats(days=7)` and `get_tokens_daily(days=7)`
2. Computes cache hit rate: 12.1%
3. Builds an evidence block with the raw metrics
4. Calls Grok with a structured-output prompt asking for the highest-value finding
5. Receives a finding dict

### 4.2 Story Writer Persists Locally (T+0.5 minutes)

`write_improvement_story(finding)` in `src/ezra/improvements/writer.py`:

1. Formats the finding into markdown
2. Writes `tasks/improvements/active/IMP-20260425-tokens.md`
3. **New in F18:** Calls the `github_issues` skill with the finding data

### 4.3 GitHub Issue Created (T+1 minute)

The `github_issues` skill:

1. Reads `GITHUB_TOKEN` from env
2. Constructs the issue body from the finding
3. Calls the GitHub REST API: `POST /repos/hackstert/ezra-assistant/issues`
4. Applies labels: `improvement`, `domain:tokens`, `priority:should-have`
5. Assigns Troy
6. Returns the issue URL
7. Story writer updates the local file's frontmatter with `github_issue: <URL>`

### 4.4 Telegram Notification (T+1.5 minutes)

The existing Telegram notification fires with the updated format:

```
[EZRA IMPROVEMENT] Tokens: Reduce repeated system prompt via previous_response_id caching
📄 IMP-20260425-tokens.md
🔗 https://github.com/hackstert/ezra-assistant/issues/47
```

Troy sees it during the day.

### 4.5 Triage (T+4 hours, whenever Troy reviews)

Troy opens the issue on his phone or desktop. He reads the evidence, decides it's worth doing. He applies the `agent-ready` label.

**This is the first human judgment gate.** Up to this point, nothing has committed any resources toward implementation. No agent has been invoked. No runner minutes have been consumed. Ezra has simply proposed.

### 4.6 GitHub Action Fires (T+4 hours and 30 seconds)

The `issues` event with `types: [labeled]` filter matches. GitHub's scheduler allocates a runner VM. The VM boots in about 15 seconds.

### 4.7 Runner Executes Workflow (T+4 hours and 45 seconds to T+4 hours and 20 minutes)

The runner executes each step in `agent-execute.yml`:

```yaml
name: Agent Execute
on:
  issues:
    types: [labeled]

jobs:
  execute:
    if: github.event.label.name == 'agent-ready'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: write
      issues: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GH_PAT }}

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install project dependencies
        run: |
          pip install uv
          uv sync

      - name: Install Claude Code
        run: npm install -g @anthropic-ai/claude-code

      - name: Prepare task spec from issue
        id: spec
        env:
          GH_TOKEN: ${{ secrets.GH_PAT }}
        run: |
          ISSUE_NUM=${{ github.event.issue.number }}
          gh issue view $ISSUE_NUM --json title,body,labels > /tmp/issue.json
          echo "issue_num=$ISSUE_NUM" >> $GITHUB_OUTPUT

      - name: Configure git identity
        run: |
          git config user.name "ezra-agent"
          git config user.email "ezra-agent@users.noreply.github.com"

      - name: Create working branch
        run: |
          git checkout -b "improvement/${{ steps.spec.outputs.issue_num }}"

      - name: Run Claude Code on the issue
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          TITLE=$(jq -r .title /tmp/issue.json)
          BODY=$(jq -r .body /tmp/issue.json)
          cat > /tmp/task.md <<EOF
          # Task

          You are working on issue #${{ steps.spec.outputs.issue_num }} in this repository.

          ## Title
          $TITLE

          ## Details
          $BODY

          ## Instructions
          Read CLAUDE.md for project conventions. Implement the changes
          required to satisfy the Acceptance Criteria. Run the test suite
          before finishing. When done, commit your changes with a clear
          message. Do not push or create a PR — that will be handled
          after you exit.
          EOF
          claude --task-file /tmp/task.md --max-turns 50

      - name: Push branch
        run: git push -u origin HEAD

      - name: Open draft PR
        env:
          GH_TOKEN: ${{ secrets.GH_PAT }}
        run: |
          ISSUE_NUM=${{ steps.spec.outputs.issue_num }}
          TITLE=$(jq -r .title /tmp/issue.json)
          gh pr create \
            --draft \
            --title "Closes #$ISSUE_NUM: $TITLE" \
            --body "$(cat <<EOF
          ## Automated implementation of #$ISSUE_NUM

          This PR was generated by the F18 improvement loop.
          See the original issue for context and acceptance criteria.

          ### Self-review performed
          - [x] All existing tests pass
          - [x] New tests added where appropriate
          - [x] Code follows conventions in CLAUDE.md

          ### Human review required before merge

          Closes #$ISSUE_NUM
          EOF
          )"

      - name: Comment on issue on failure
        if: failure()
        env:
          GH_TOKEN: ${{ secrets.GH_PAT }}
        run: |
          gh issue comment ${{ steps.spec.outputs.issue_num }} \
            --body "Agent run failed. See logs: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
```

The agent runs for however long it needs within the 30-minute budget. For a token-caching improvement, that's typically 5-10 minutes. For a more complex change, up to 25 minutes.

During this time, Claude Code:

1. Reads `CLAUDE.md` for project conventions (Python 3.12, uv, pytest, etc.)
2. Explores the repository structure
3. Forms a plan based on the issue's task list
4. Edits files (`src/ezra/providers/xai.py`, tests, migration)
5. Runs `pytest` to verify
6. Iterates if tests fail
7. Commits with a descriptive message
8. Exits cleanly

### 4.8 PR Opens (T+4 hours and 20 minutes)

The workflow pushes the branch and creates a draft PR. GitHub sends a webhook event (`pull_request.opened`) to Ezra's webhook endpoint.

### 4.9 Ezra Webhook Handler Processes Event (T+4 hours and 20 minutes + 2 seconds)

The webhook request hits Cloudflare Tunnel, gets signature-verified, forwards to `POST /api/webhooks/github` on your Mac. The handler:

1. Parses the event payload
2. Matches: `pull_request.opened` with `closes #47` in body
3. Updates the story file frontmatter with `pull_request: <URL>`
4. Logs the event to `data/improvement-state.json`

### 4.10 Troy Reviews (T+varies, when Troy has time)

Troy gets a GitHub mobile notification for the new PR. He reviews it on his phone or desktop:

- Reads the PR description
- Scans the diff (GitHub's review UI is excellent for this)
- Optionally checks out the branch locally for deeper review
- Approves or requests changes

**This is the second human judgment gate.** The agent cannot merge its own PR. Branch protection rules on the `main` branch (configured as part of F18-S03 acceptance) require at least one approving review before merge is available.

### 4.11 Merge (T+varies, immediate after approval)

Troy clicks "Merge" (or "Squash and merge" — his preference). GitHub:

1. Merges the branch into `main`
2. Closes the branch
3. Auto-closes issue #47 because of the `Closes #47` syntax
4. Fires webhook events: `pull_request.closed` (with `merged: true`) and `issues.closed`

### 4.12 Ezra Webhook Handler Finalizes (T+varies + 2 seconds)

The webhook handler:

1. Receives `issues.closed` event
2. Locates the story file via the `github_issue` frontmatter
3. Moves `tasks/improvements/active/IMP-20260425-tokens.md` to `tasks/improvements/completed/IMP-20260425-tokens.md`
4. Updates `data/improvement-state.json` with completion timestamp
5. Fires a Telegram notification: "Improvement complete: #47 merged"

The cycle is done. The next scanner run in 9 days has a slightly better-running system to observe.

---

## 5. Operational Semantics

Understanding how the system behaves under various conditions.

### 5.1 What Requires Your Attention

Only two things in the entire loop require human action:

1. **Triage decision:** Apply `agent-ready` label (or don't) — about 30 seconds per issue
2. **Merge decision:** Review PR and approve (or reject) — about 2-5 minutes per PR

Everything else is automatic.

### 5.2 What Happens If You Ignore an Issue

Nothing. The issue sits in the `status:triage` state indefinitely. No resources are consumed. No agent fires. The backlog simply grows. You can revisit months later or close the issue manually if it's no longer relevant. Closing without merging moves the story file to a new `rejected/` folder (F18-S04 behavior), preserving it for the pattern miner.

### 5.3 What Happens If an Agent Run Fails

The workflow includes a failure handler that comments on the issue with a link to the logs. The issue remains open, the `agent-ready` label stays applied, no PR is created. You can investigate:

- Click the log link, read what went wrong
- Fix the issue body if it was ambiguous
- Remove and re-apply `agent-ready` to retry (the workflow's concurrency setting prevents duplicate runs)
- Or remove `agent-ready` entirely and work it manually

Common failure modes and their meanings:

- **Tests fail** — agent's implementation broke something. Usually the agent has already iterated; if it gave up, the tests likely needed more context than the issue provided
- **Timeout** — the task was larger than 30 minutes. Either decompose into multiple issues or extend the timeout for that specific workflow run
- **API rate limit** — rare, usually transient, retry after a few minutes
- **Permission error** — the GitHub token lacks a required scope, fix in repo settings

### 5.4 What Happens If Ezra Is Offline When Something Changes

Ezra's webhook handler will miss events. The story files in `active/` won't reflect GitHub reality. This is drift.

F18-S06 provides `/improvement sync` to reconcile drift on demand:

```
$ python -m ezra /improvement sync
Drift detected:
  - IMP-20260425-tokens.md is active, but issue #47 was closed (merged) on 2026-04-27
  - IMP-20260430-memory.md is active, but no corresponding GitHub issue exists

Run with --apply to resolve:
  --apply would:
    - Move IMP-20260425-tokens.md to completed/
    - Create missing issue for IMP-20260430-memory.md
```

The reconciliation is idempotent and always reversible. Running it twice produces the same result as running it once.

### 5.5 What Happens If You Merge Without Review

GitHub's branch protection rules make this hard by default, but if you explicitly bypass them, the merge proceeds normally. The system has no opinion about your process — it provides the judgment gate but doesn't enforce your use of it. For Selah, F18-S07 adds stricter rules (required reviewers on theology paths) that are harder to bypass.

### 5.6 What Happens When Multiple Scanners Want to Create Issues

Impossible by construction. F15's scheduler enforces one scanner per cycle. Even if two completed simultaneously, `write_improvement_story` is sequential and the GitHub API is linearizable — issues get unique numbers in the order they arrive.

### 5.7 What Happens When a PR Gets Review Comments Requesting Changes

The agent has already exited. It won't see your comments and won't respond. You have two options:

1. Make the changes yourself, push to the same branch, re-request review
2. Close the PR, delete the branch, and remove `agent-ready` + re-add it to trigger a fresh agent run

Option 1 is faster for small changes. Option 2 is better for substantial rework. A future story (not in F18) could add an `agent-continue` workflow that resumes work on an existing branch in response to review comments — but that's complexity we don't need yet.

---

## 6. Security Posture

Several things must be correct for this system to be safe.

### 6.1 Secret Scope

Three secrets matter:

| Secret | Stored in | Scope | Used by |
|---|---|---|---|
| `GITHUB_TOKEN` (for Ezra) | Your Mac's `.env` | Fine-grained PAT, limited repos, issues + PRs write | Ezra `github_issues` skill |
| `GH_PAT` (for Actions) | GitHub repo secrets | Repo-scoped, contents + PRs write | Workflow runner |
| `ANTHROPIC_API_KEY` | GitHub repo secrets | Anthropic billing | Claude Code CLI on runner |
| `GITHUB_WEBHOOK_SECRET` | Both `.env` and GitHub webhook settings | Shared secret for signature verification | Ezra webhook handler |

Each secret is scoped narrowly. None has more permission than it needs. None exists in source code. None exists in log output (workflow masks secrets automatically; Ezra should not log them).

### 6.2 Branch Protection

The `main` branch in each repo should have protection rules:

- Require pull request before merging
- Require at least one approving review
- Require status checks (tests) to pass
- Require branches to be up to date before merging
- Do not allow administrators to bypass these rules (for Selah; optional elsewhere)

This prevents any agent from merging its own PR regardless of the token scope.

### 6.3 Webhook Verification

Every webhook payload carries a `X-Hub-Signature-256` header computed as HMAC-SHA256 over the body with the shared secret. The handler verifies this before processing:

```python
import hmac
import hashlib

def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

Requests without a valid signature are rejected with 401. This prevents anyone on the internet who finds your webhook URL from injecting fake events.

### 6.4 Cloudflare Tunnel

The webhook endpoint is exposed via Cloudflare Tunnel rather than direct port forwarding. Benefits:

- No public IP exposure of your home network
- Cloudflare's edge DDoS protection
- TLS termination at the edge
- Ability to add Cloudflare Access rules (e.g., allow only GitHub's webhook IP ranges) if needed
- Can be revoked instantly if compromised

This is already part of LAN-Central-Command infrastructure and doesn't add new setup.

### 6.5 Runner Isolation

GitHub-hosted runners are ephemeral single-use VMs. A compromised runner cannot persist anything across runs. The filesystem is wiped, the VM is destroyed, the next run starts fresh. This is stronger isolation than Archon's git worktree model because it's at the VM level, not the directory level.

Self-hosted runners (not used in F18) would require additional hardening. GitHub-hosted runners require only sensible secret management.

### 6.6 Selah's Elevated Stance

The Selah repo gets stricter rules in F18-S07:

- Paths under `selah/theology/`, `selah/training/`, `selah/prompts/` are guarded
- Workflow detects changes to these paths and flags the PR with a `theological-review-required` label
- Telegram notification explicitly names these changes
- Branch protection requires two approvers for PRs touching guarded paths (configurable)
- Administrators cannot bypass these rules

The result: no theological content can reach `main` without Troy's explicit review, regardless of how confident the scanner or agent was. This is a non-negotiable property of the Selah codebase.

---

## 7. Cost Model

For personal-scale use (one scanner finding every 9 days, one merged PR every 1-2 weeks), the cost picture is:

| Resource | Monthly cost |
|---|---|
| GitHub Pro subscription | Already paid |
| GitHub Actions minutes | ~30 min/mo used of 2,000 free |
| GitHub-hosted runner compute | Included in Actions minutes |
| Anthropic API (Claude Code) | ~$5-15 based on scenario complexity |
| Cloudflare Tunnel | Free tier |
| Your Mac electricity | Unchanged |
| Grok via xAI (unchanged) | Current Ezra spend |

Net new cost: approximately $5-15 per month in Anthropic API usage. This is the cost of automating the coding step. Compared to the value of a disciplined, auditable, self-improving development loop, it's modest.

Cost scales linearly with usage. If you increased the scanner cadence to daily instead of every-9-days, costs would scale roughly 9x. The current cadence is intentional and well-matched to solo-developer rhythm.

---

## 8. Observability

You need to see what's happening. Four places to look:

### 8.1 Mission Control (Ezra's UI)

- Cron Center (`/cron`) — shows scanner runs, last execution, upcoming schedule
- Memory (`/memory`) — audit report with metrics the scanners use
- Portfolio (`/portfolio`) — project status including improvement cycle completions

### 8.2 GitHub Issues (the work queue)

- Filter by `label:improvement` to see all scanner-created issues
- Filter by `label:agent-ready` to see what's currently being worked
- Filter by `is:closed label:improvement` to see the history

### 8.3 GitHub Actions (execution logs)

- Actions tab shows every workflow run
- Click any run for full stdout/stderr of every step
- Failed runs are highlighted
- Run time, cost (minutes consumed), and artifacts all visible

### 8.4 GitHub Pull Requests (the output stream)

- Filter by `author:ezra-agent` to see all agent-generated PRs
- PR list shows merge status at a glance
- Each PR's timeline shows: creation, commits, reviews, comments, merges

### 8.5 Telegram (real-time alerts)

- Scanner finding created (with issue link)
- Agent run started
- PR opened (with review link)
- Merge completed
- Drift detected (from F18-S06 reconcile job)

For a solo operator, these five channels give complete observability. You can be on your phone and see the entire pipeline's state in under a minute.

---

## 9. Failure Recovery

Things will go wrong. Here's how to recover.

### 9.1 Agent Produces a Bad PR

Reject it. Close the PR without merging. Optionally comment on the issue with what went wrong so future scanner runs can learn from it. The issue remains open with `agent-ready` removed. Consider:

- Was the scanner's evidence accurate? If not, the scanner needs refinement (file as an improvement itself)
- Was the issue ambiguous? Improve the issue template or scanner output format
- Was the agent's tool set insufficient? Check workflow YAML, maybe add more installed deps

### 9.2 Multiple Agent Runs on Same Issue

Shouldn't happen due to workflow concurrency settings, but if it does:

- Both runners will race to push the branch
- GitHub's API will reject the second push
- Second workflow will fail and comment on the issue
- Safe but noisy — one comment to clean up

### 9.3 Webhook Handler Is Down

Drift accumulates. Run `/improvement sync --apply` when Ezra is back. Idempotent. Safe.

### 9.4 GitHub Rate Limits

For a personal account with fine-grained PATs, you're very unlikely to hit them at F18's volume. If somehow you do:

- Ezra skill should have exponential backoff on 429 responses
- Workflow should retry on rate-limited operations
- GitHub's rate limit reset is hourly; worst case is a 60-minute delay

### 9.5 Anthropic Outage

The workflow fails at the `claude` step. Issue gets a failure comment. Re-trigger later.

### 9.6 Your Mac Is Offline for Days

Scanners don't run (no new issues created), webhook handler doesn't run (drift accumulates). When you come back: scanners catch up on next schedule, `/improvement sync --apply` resolves drift. No data is lost; Ezra's state is durable across restarts.

### 9.7 Complete Rollback of the F18 Loop

If you ever want to turn it off:

1. Remove `agent-execute.yml` from `.github/workflows/`
2. Stop calling `github_issues` from `write_improvement_story` (feature flag or comment out)
3. Existing issues and PRs remain; just no new ones get created

Everything the loop produced is normal GitHub content — issues, PRs, merged commits. None of it is entangled with the automation. Turning the automation off leaves your repos in a normal state.

---

## 10. What Makes This Different From Generic CI/CD

You might wonder: is this just CI/CD with extra steps?

It isn't, and the difference matters.

**CI/CD reacts to your code changes.** You push a commit, CI runs tests. You merge a PR, CD deploys. The trigger is always you.

**The F18 loop reacts to your system's state.** Scanners observe metrics, findings emerge from data, issues get created autonomously. The trigger is not you — it's the system noticing something about itself.

**CI/CD keeps your code working.** F18 keeps your system improving. Different goals, complementary systems.

**CI/CD is synchronous with development.** F18 is asynchronous with observation. The scanner runs on its own cadence; you engage with its output on yours.

The combination is what creates the self-improvement property. CI/CD ensures the loop itself stays reliable (tests pass, deployments don't break). F18 ensures the loop produces increasingly capable systems over time. You need both.

---

## 11. Growth Paths

F18 is a foundation. Several natural extensions become available once it's stable:

**More scanners.** Any observable property of the system can become a scanner. Error rate trends, latency percentiles, memory fragmentation, skill usage patterns, theological drift in Selah (a real concern), user feedback sentiment from Telegram.

**More repos.** Once the pattern is stable in Ezra, rolling it out to Voice of Repentance, Selah, and any future personal project takes hours, not days.

**Cross-repo scanners.** A single scanner watching multiple repos could identify systemic patterns ("all three repos have the same test framework gap").

**Historical pattern mining (F18-S08).** Already in the canvas. Becomes possible once 30+ closed issues exist.

**Feedback loops into the scanners themselves.** If a scanner's proposals consistently get rejected, a meta-scanner could propose improvements to that scanner's prompt or thresholds. This is the innermost ring of the self-annealing design.

**Multi-step issues.** Currently each issue is one PR. A future extension could allow an issue to spawn multiple linked PRs if the task decomposes naturally. Requires more orchestration logic; likely not needed for F18's initial scope.

**Slack or Telegram triggers.** Beyond labels, a Telegram message to Ezra like "work on issue #47" could trigger the workflow via a GitHub API call. This is where Archon's multi-interface value might become relevant, years down the road.

---

## 12. The Bigger Picture

The pattern F18 establishes is larger than the improvement loop itself. It's a template for any long-running autonomous system that needs human-in-the-loop oversight:

- **Observer** (scanner) watches some domain
- **Proposer** (Ezra) articulates findings in a durable, structured format
- **Queue** (GitHub Issues) holds proposals awaiting review
- **Gate 1** (triage) ensures only vetted work gets automated
- **Worker** (Claude Code) implements
- **Gate 2** (PR review) ensures only approved work reaches production
- **Recorder** (GitHub + Ezra webhook) maintains audit history
- **Analyzer** (pattern miner, eventually) learns from history to improve the observer

This pattern applies directly to Selah in ways beyond the improvement loop. Imagine a theological content scanner that flags potential doctrinal issues in sermon drafts. A music-selection scanner for Voice of Repentance that proposes setlists based on congregation feedback and liturgical calendar. A clinical-guideline scanner that proposes CPG updates based on new evidence.

The mechanism is the same. The domain changes. F18 builds the mechanism once, in a low-stakes context (self-improvement), where you can tune the pattern before applying it to higher-stakes contexts.

That's why this is worth the investment even though the initial volume is low. You're not just automating improvements. You're building the template for a family of systems that share the same structural properties: observer, queue, triage, worker, judgment, record, learn.

---

## 13. Glossary

- **Action** — a GitHub feature for running workflows on event triggers
- **Agent** — a coding AI (Claude Code in F18's case) that reads an issue and produces a PR
- **Cloudflare Tunnel** — a service exposing a local HTTP endpoint to the internet without port forwarding
- **Draft PR** — a pull request flagged as not-yet-ready-for-review; still allows CI to run
- **HITL** — Human In The Loop; a pattern where automation pauses for human approval
- **Improvement cycle** — one full loop from scanner finding to merged PR
- **Label** — a string attached to an issue or PR that can trigger workflows and filter views
- **Runner** — the VM that executes a GitHub Actions workflow
- **Scanner** — a background task in Ezra that observes system state and produces findings
- **Story file** — a markdown file in `tasks/improvements/active/` representing a proposed improvement
- **Triage** — the process of reviewing a new issue and deciding whether it's ready for automation
- **Webhook** — an HTTP callback GitHub sends when events occur in a repository
- **Worktree** — Archon's isolation primitive (not used in F18); GitHub Actions uses runner VMs instead

---

## 14. Related Files

| File | Purpose |
|---|---|
| `F18-github-improvement-loop.md` | Feature canvas, stories, acceptance criteria |
| `docs/improvement-system.md` | Updated with F18 integration details |
| `docs/skill-inventory.md` | `github_issues` skill added under Tier 1 |
| `.github/workflows/agent-execute.yml` | The workflow file (F18-S03 deliverable) |
| `.github/ISSUE_TEMPLATE/*` | Structured issue templates (F18-S05 deliverable) |
| `src/ezra/skills/github_issues/tool.py` | The skill implementation (F18-S01 deliverable) |
| `src/ezra/routes/webhooks.py` | Webhook handler (F18-S04 deliverable) |

---

*Created: 2026-04-18 | Companion to F18 feature canvas*
