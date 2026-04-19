# F18 Addendum: Subscription-Based Overnight Runs

**Status:** Alternative architecture to F18-S03 (GitHub Actions agent executor)
**Created:** 2026-04-18
**Relationship:** Either this OR F18-S03 is chosen; they solve the same problem differently

---

## Context

The F18 canvas and technical guide describe agent execution via GitHub Actions, which requires `ANTHROPIC_API_KEY` and bills usage against the Anthropic API account. This addendum describes an alternative: **executing the coding agent locally on your Mac overnight, using the Claude Code subscription login rather than API billing.**

The choice between the two is a real tradeoff. This document exists so the decision is informed.

---

## The Core Difference

Claude Code CLI supports two authentication modes:

**Subscription login** (`claude login`)
- Interactive OAuth flow in a browser
- Usage counts against your Anthropic Pro/Max subscription
- Generous monthly limits included in subscription price
- Cannot be automated in a headless environment

**API key** (`ANTHROPIC_API_KEY`)
- Non-interactive, works headlessly
- Usage is pay-per-token to the API billing account
- No predefined cap; you pay for what you use
- Required for cloud automation like GitHub Actions

GitHub Actions runs on ephemeral VMs with no browser. It cannot complete the OAuth flow. Therefore Actions must use API keys. Your subscription cannot be used for Actions-based automation.

However, your **Mac** has a browser and is logged in. Claude Code CLI running on your Mac can use the subscription. The question becomes: can we structure the workflow to run the agent on your Mac instead of in GitHub's cloud?

Yes. Here's how.

---

## The Subscription Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Ezra Server (your Mac, always on)                          │
│                                                             │
│  Scanner fires → finding dict                               │
│    │                                                        │
│    ├─→ local story file (tasks/improvements/active/*.md)   │
│    └─→ GitHub Issue (via github_issues skill)               │
│                                                             │
│  Telegram notification sent                                 │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
          Troy applies agent-ready label
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  GitHub Webhook fires: issues.labeled                       │
│  Payload forwarded via Cloudflare Tunnel to Ezra            │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Ezra Webhook Handler (your Mac)                            │
│                                                             │
│  Does NOT immediately run the agent.                        │
│  Instead: writes work item to queue                         │
│    data/agent-queue/pending/ISSUE-47.json                   │
│                                                             │
│  Queue item contains:                                       │
│    - issue number                                           │
│    - repo (hackstert/ezra-assistant)                        │
│    - target branch (improvement/47)                         │
│    - timestamp                                              │
│    - agent config (model, max_turns, etc)                   │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
      (Mac idle, Troy asleep, hours pass)
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  launchd schedules agent-runner at 02:00 local time         │
│  ~/Library/LaunchAgents/com.hackstert.ezra-agent.plist      │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  agent-runner.sh (your Mac, subscription-authenticated)     │
│                                                             │
│  For each item in data/agent-queue/pending/:                │
│    1. Clone repo to ~/agent-workspaces/ISSUE-47/            │
│    2. cd into workspace                                     │
│    3. Create branch improvement/47                          │
│    4. Fetch issue body via gh CLI                           │
│    5. Write task spec to /tmp/task.md                       │
│    6. Run: claude --task-file /tmp/task.md --max-turns 50  │
│       (uses subscription login, no API key)                 │
│    7. Commit changes                                        │
│    8. Push branch                                           │
│    9. Open draft PR via gh CLI                              │
│   10. Move queue item to data/agent-queue/completed/        │
│                                                             │
│  On failure: move to data/agent-queue/failed/ + comment     │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  GitHub now has a draft PR linked to the issue              │
│  Troy wakes up, reviews, merges                             │
└─────────────────────────────────────────────────────────────┘
```

**Key architectural change:** The webhook handler enqueues work instead of executing it. A separate scheduled process drains the queue overnight. Ezra's main FastAPI loop remains responsive and never blocks on a 20-minute agent run.

---

## What Changes Compared to F18-S03

| Aspect | F18-S03 (GitHub Actions, API) | F18-S03-ALT (Local overnight, subscription) |
|---|---|---|
| Execution location | GitHub-hosted runner (Azure) | Your Mac |
| Authentication | `ANTHROPIC_API_KEY` | `claude login` session |
| Billing | Pay-per-token (~$1-6/run with Sonnet) | Included in Pro/Max subscription |
| Triggering | `issues.labeled` event → immediate | `issues.labeled` → queue → 02:00 drain |
| Latency | ~5-20 minutes from label to PR | Hours (up to next 02:00) |
| Requires Mac always-on | No | Yes (your setup already is) |
| Parallel execution | Free (multiple runners) | Serial (queue drained one at a time) |
| Runner isolation | VM-level (stronger) | Directory-level (weaker but adequate) |
| Internet outage resilience | Can't run | Can't run (both need GitHub access) |
| Cost at F18 cadence | $1-6/month API | $0 marginal |
| Cost at 10x volume | $10-60/month API | Still $0 marginal until subscription cap |
| Setup complexity | Moderate | Moderate (different skillset: launchd + scripts) |

---

## When to Choose Each

**Choose F18-S03 (GitHub Actions, API) if:**

- You want low latency from label to PR (minutes, not hours)
- You want zero Mac dependency (works even if your Mac is off)
- You want parallel execution of multiple issues
- You're willing to pay $1-6/run for convenience and separation
- You want the coding agent's compute completely isolated from your personal machine

**Choose F18-S03-ALT (Local overnight, subscription) if:**

- Your Mac is reliably on (Atlas running 24/7 as noted in your setup)
- You're comfortable with overnight latency — the PR is waiting when you wake up
- You want to maximize the value of your Pro/Max subscription
- You want zero marginal cost regardless of volume
- You want the subscription's higher rate limits (Opus access, larger context windows) without per-token anxiety
- You value the aesthetic of "all this happens while I sleep" (it's genuinely nice)

**Both share:**

- Same human triage gate (label application)
- Same human judgment gate (PR review)
- Same issue and PR contract format
- Same webhook-driven state synchronization
- Same rollback behavior (remove automation, existing issues/PRs stay normal)

The choice doesn't affect the overall F18 architecture. It only changes where the coding step physically happens.

---

## Implementation Details for F18-S03-ALT

If you choose the local-overnight path, here's what gets built.

### The Queue

A directory-based queue in `data/agent-queue/` with three subfolders:

```
data/agent-queue/
├── pending/      # Enqueued by webhook, awaiting execution
├── completed/    # Successfully processed
└── failed/       # Errored out; kept for review
```

Each queue item is a JSON file named `ISSUE-{number}.json`:

```json
{
  "issue_number": 47,
  "repo": "hackstert/ezra-assistant",
  "issue_title": "Reduce repeated system prompt via previous_response_id caching",
  "issue_url": "https://github.com/hackstert/ezra-assistant/issues/47",
  "enqueued_at": "2026-04-25T14:32:11Z",
  "agent_config": {
    "model": "sonnet",
    "max_turns": 50,
    "timeout_minutes": 30
  }
}
```

Directory-based queues are intentional — they're trivially inspectable (just `ls`), safe across process restarts, and don't need a separate database.

### The Webhook Handler Modification

F18-S04 specified that the webhook handler moves story files on issue closure. For the local-overnight variant, it also enqueues work on label events:

```python
@router.post("/api/webhooks/github")
async def github_webhook(request: Request):
    body = await request.body()
    verify_signature(body, request.headers["X-Hub-Signature-256"])
    event = await request.json()
    event_type = request.headers["X-GitHub-Event"]

    match event_type:
        case "issues" if event["action"] == "labeled":
            if event["label"]["name"] == "agent-ready":
                await enqueue_agent_work(event["issue"])

        case "issues" if event["action"] == "closed":
            await handle_issue_closed(event["issue"])

        case "pull_request" if event["action"] == "opened":
            await handle_pr_opened(event["pull_request"])

    return {"status": "ok"}


async def enqueue_agent_work(issue: dict) -> None:
    queue_dir = Path("data/agent-queue/pending")
    queue_dir.mkdir(parents=True, exist_ok=True)
    item = {
        "issue_number": issue["number"],
        "repo": issue["repository_url"].split("github.com/")[1],
        "issue_title": issue["title"],
        "issue_url": issue["html_url"],
        "enqueued_at": datetime.now(UTC).isoformat(),
        "agent_config": {
            "model": "sonnet",
            "max_turns": 50,
            "timeout_minutes": 30,
        },
    }
    path = queue_dir / f"ISSUE-{issue['number']}.json"
    path.write_text(json.dumps(item, indent=2))
    logger.info("Enqueued agent work for issue #%d", issue["number"])
```

### The Agent Runner Script

`scripts/agent-runner.sh` drains the queue. Designed to be run by launchd at 02:00 local time.

```bash
#!/usr/bin/env bash
set -euo pipefail

QUEUE_DIR="$HOME/Projects/ezra-assistant/data/agent-queue"
WORKSPACES="$HOME/agent-workspaces"
LOG_DIR="$HOME/Projects/ezra-assistant/logs/agent-runner"

mkdir -p "$WORKSPACES" "$LOG_DIR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOGFILE="$LOG_DIR/run-$TIMESTAMP.log"

{
    echo "=== Agent runner started at $(date) ==="

    shopt -s nullglob
    for item in "$QUEUE_DIR/pending"/*.json; do
        ITEM_NAME=$(basename "$item")
        ISSUE_NUM=$(jq -r '.issue_number' "$item")
        REPO=$(jq -r '.repo' "$item")
        TITLE=$(jq -r '.issue_title' "$item")
        MAX_TURNS=$(jq -r '.agent_config.max_turns' "$item")

        echo ""
        echo "--- Processing $ITEM_NAME (issue #$ISSUE_NUM) ---"

        WORKSPACE="$WORKSPACES/issue-$ISSUE_NUM"
        rm -rf "$WORKSPACE"

        if ! gh repo clone "$REPO" "$WORKSPACE"; then
            echo "Clone failed, moving to failed/"
            mv "$item" "$QUEUE_DIR/failed/"
            gh issue comment "$ISSUE_NUM" --repo "$REPO" \
                --body "Agent run failed: clone error. Check logs on Ezra host."
            continue
        fi

        cd "$WORKSPACE"
        git config user.name "ezra-agent"
        git config user.email "ezra-agent@local"

        BRANCH="improvement/$ISSUE_NUM"
        git checkout -b "$BRANCH"

        # Fetch the issue body
        gh issue view "$ISSUE_NUM" --repo "$REPO" --json body -q .body > /tmp/issue-body.md

        # Build the task spec
        cat > /tmp/task.md <<EOF
# Task

You are working on issue #$ISSUE_NUM in this repository.

## Title
$TITLE

## Details
$(cat /tmp/issue-body.md)

## Instructions
Read CLAUDE.md for project conventions. Implement the changes required
to satisfy the Acceptance Criteria. Run the test suite before finishing.
When done, commit your changes with a clear message. Do not push or
create a PR — that will be handled after you exit.
EOF

        # Run Claude Code with subscription authentication
        # (no ANTHROPIC_API_KEY in this shell — CLI uses the login session)
        if ! claude --task-file /tmp/task.md --max-turns "$MAX_TURNS"; then
            echo "Claude Code execution failed"
            mv "$item" "$QUEUE_DIR/failed/"
            gh issue comment "$ISSUE_NUM" --repo "$REPO" \
                --body "Agent run failed during Claude Code execution. See host logs."
            continue
        fi

        # Push the branch
        if ! git push -u origin "$BRANCH"; then
            echo "Push failed"
            mv "$item" "$QUEUE_DIR/failed/"
            continue
        fi

        # Open the PR
        gh pr create --draft \
            --title "Closes #$ISSUE_NUM: $TITLE" \
            --body "Automated implementation via overnight agent run. Closes #$ISSUE_NUM" \
            --repo "$REPO"

        # Move queue item to completed
        mv "$item" "$QUEUE_DIR/completed/"
        echo "Completed issue #$ISSUE_NUM"
    done

    echo ""
    echo "=== Agent runner finished at $(date) ==="
} 2>&1 | tee "$LOGFILE"
```

### The launchd Schedule

macOS uses launchd (not cron) for scheduled tasks. File: `~/Library/LaunchAgents/com.hackstert.ezra-agent.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hackstert.ezra-agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/hackstert/Projects/ezra-assistant/scripts/agent-runner.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/hackstert/Projects/ezra-assistant/logs/agent-runner/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/hackstert/Projects/ezra-assistant/logs/agent-runner/stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

Load with `launchctl load ~/Library/LaunchAgents/com.hackstert.ezra-agent.plist`. Runs every day at 02:00.

If the queue is empty, the script exits quickly (the for-loop has nothing to iterate). No wasted work.

### Mission Control Integration

The Cron Center (F16) can show the agent runner as a registered cron job, including:
- Last run timestamp
- Queue depth (pending/completed/failed counts)
- Success rate

This is a small extension to the existing cron registry.

---

## Tradeoffs Beyond Cost

**Resource usage on your Mac.** A Claude Code run can consume meaningful CPU and memory for 5-20 minutes. Running overnight avoids any impact on your daytime work. Running multiple queue items in sequence means your Mac might be busy for 30-60 minutes at 2am if several issues accumulated. Not a problem while you sleep.

**Subscription fairness.** Anthropic's subscription ToS permits personal use. Running 4-5 automated agent tasks per week on your own codebases is well within personal use. Running hundreds of tasks per day against client codebases would cross the line into usage that should be API-billed. The F18 cadence (one run every 1-2 weeks, plus maybe occasional backlog burndown) is clearly personal use.

**Context about authentication state.** If Claude Code's subscription session expires (which can happen after long inactivity), the overnight run fails. Easy fix: run `claude` interactively once, the session refreshes, next overnight run works. Put a reminder in your monthly review to manually invoke `claude` once to keep the session warm.

**Debugging.** When things fail on GitHub Actions, the logs are in GitHub's UI. When things fail in launchd, the logs are in `~/Projects/ezra-assistant/logs/agent-runner/`. Different debugging context, neither harder than the other.

**Separation of concerns.** GitHub Actions keeps agent compute completely separate from your personal Mac. If you ever get a compromised dependency or an agent goes rogue, it runs in an ephemeral VM, not on your machine. The local variant is less isolated. For low-trust dependencies this matters; for your own repos working on your own code, the risk is low.

---

## A Practical Recommendation

Given your context:

- Your Mac is always on (Atlas setup)
- Cost sensitivity is real (you mentioned the Grok-vs-Claude tradeoff)
- You have a Pro subscription already
- The F18 cadence is low (weeks between runs)
- Overnight latency is completely acceptable for self-improvement work

**F18-S03-ALT (local overnight, subscription) is probably the right choice for you.**

The aesthetic is also genuinely appealing: your system observes itself during the day, proposes improvements, you triage on your phone during breaks, and then overnight — while you sleep — the work gets done. You wake up, review PRs with morning coffee, merge what looks good. That rhythm matches how self-improvement should feel: something the system handles in its quiet hours, presented for judgment in yours.

Once you've proven the pattern works locally, you can always migrate individual high-priority or urgent-response repos to the Actions path later. The migration is trivial — same contract, different executor.

---

## Migration Path Between the Two

If you start with F18-S03-ALT and later want to migrate to F18-S03 (or vice versa):

**Local → Actions:**
1. Add `.github/workflows/agent-execute.yml`
2. Add `ANTHROPIC_API_KEY` to repo secrets
3. Unload the launchd plist (`launchctl unload ...`)
4. Remove the webhook's enqueue behavior; keep only state-sync behavior

**Actions → Local:**
1. Remove or disable the workflow file
2. Add the enqueue logic to the webhook handler
3. Add `scripts/agent-runner.sh`
4. Load the launchd plist
5. Ensure `claude login` is current

The queue directory, issue templates, PR conventions, and human gates are identical between both paths. Only the executor changes.

---

## Acceptance Criteria for F18-S03-ALT

If you adopt this variant, the story F18-S03 acceptance criteria change as follows:

- [ ] `data/agent-queue/{pending,completed,failed}/` directories exist
- [ ] Webhook handler enqueues on `agent-ready` label event
- [ ] `scripts/agent-runner.sh` is executable and drains the queue
- [ ] launchd plist is installed and loaded
- [ ] Claude Code is authenticated with `claude login`
- [ ] One full cycle tested end-to-end: label applied, enqueued, run overnight, PR appears in morning
- [ ] Failure mode tested: queue item moves to `failed/`, issue gets comment
- [ ] Mission Control Cron Center shows the agent-runner job
- [ ] Documented in `docs/improvement-system.md` under "Local Overnight Execution"

---

*Created: 2026-04-18 | Companion to F18 canvas*
