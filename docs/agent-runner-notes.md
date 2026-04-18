# `agent-runner.sh` — Design Notes and Operational Guide

**Purpose:** Reference for operating, modifying, and debugging the Harvester overnight agent runner.
**Companion to:** `scripts/agent-runner.sh`
**Audience:** Troy (primary operator), future Claude Code instances working on Harvester

---

## What This Script Does, in One Paragraph

Every night at 02:00, launchd wakes the Mac, runs this script, and the script drains the Harvester work queue. For each pending work item, it creates an ephemeral workspace, clones the target repo fresh, checks out a new branch named for the issue, fetches the issue body from GitHub, assembles a task specification combining the issue and the repo's `CLAUDE.md`, invokes Claude Code with subscription authentication, verifies the agent produced commits and didn't touch guarded paths, pushes the branch, and opens a draft PR linked to the issue. On any failure, the item moves to `failed/` with a diagnostic annotation; on success, it moves to `completed/` with the PR URL recorded. A Telegram summary fires at the end of the run.

---

## Design Principles Baked Into This Script

**Every failure is recoverable.** No destructive operations. Branches are only pushed after local verification succeeds. Queue items are moved (not deleted) with their failure reason attached. If something breaks at 3am, the system stops but nothing is damaged.

**Preflight is aggressive.** Before processing any items, the script verifies every external dependency is present and working. A failed preflight fails loudly via Telegram and exits without touching the queue. This catches stale subscription auth, missing tools, and config problems before they corrupt work items.

**Per-item isolation.** Each queue item runs in a completely fresh workspace. If the previous item left garbage behind, the current item's hard reset cleans it up. No state leaks between items.

**`set -e` is deliberately not used.** The conventional bash practice is to set `-e` so any failing command aborts the script. For this script, that would be wrong — if one queue item fails, we want to continue processing the rest. Each failure is handled explicitly and the main loop continues.

**Telegram is best-effort.** Notifications never fail the script. If Telegram is down or credentials are wrong, the script continues normally; you just don't get the ping. The work is what matters; notifications are convenience.

**Logs over silence.** Everything is logged with UTC timestamps. The log file for each run is referenced in every error annotation, so when you investigate a failure you have one place to look.

---

## The Preflight Sequence

Preflight runs before any work item is touched. It validates seven things:

**1. Required tools on PATH.** The script uses `jq`, `yq`, `gh`, `git`, `claude`, and `curl`. If any is missing, it fails fast with a clear message and the current `PATH` value. This is the most common cause of mysterious 2am failures — launchd runs with a limited `PATH` by default, and tools installed via Homebrew may not be found. The launchd plist sets `PATH` explicitly to include `/opt/homebrew/bin`, but this check catches cases where that's wrong.

**2. Config file exists and parses.** `harvester-config.yaml` must be present and valid YAML. If it's broken, the script can't know what to do.

**3. Queue directory structure.** The `pending/`, `completed/`, and `failed/` folders must exist. The script creates them on first run, but this check catches cases where someone deleted them.

**4. GitHub CLI authentication.** `gh auth status` verifies you're logged in. If you're not, no PR can be created and no issue can be updated. Fails early.

**5. Claude Code binary works.** `claude --version` succeeds. This catches cases where Claude Code was uninstalled or broken.

**6. Claude Code subscription session is live.** This is the subtle one. Claude Code's subscription session can expire after weeks of inactivity. A `--version` call succeeds even with stale auth; it only fails when you try to actually make a request. So preflight makes a minimal real request ("Reply with just the word READY.") and verifies it returns "READY". This costs one small subscription request per run but catches stale auth before you waste 15 minutes of compute on doomed work.

The probe text is deliberately dull — no jargon, no theatrics. If Anthropic ever analyzes subscription usage patterns, this probe should look like normal use, not like automation trying to evade detection. It also succeeds with any of Claude's models, so if Anthropic changes the default model, the probe still works.

**7. Recovery guidance on failure.** If the session probe fails, the error message tells you exactly what to do: run `claude` interactively, authenticate in the browser, exit, re-run. This is the one thing you'll occasionally have to do manually — the calendar reminder in your workflow is meant to prevent this from happening in the middle of a run.

---

## The Item Processing Sequence

For each item, the script follows a strict sequence where each step must succeed before the next starts. If any step fails, the item is annotated and moved to `failed/`, and the loop continues with the next item.

**Step 1 — Parse the queue item.** Extract issue number, repo, local path, title, and agent config from the JSON. Missing required fields = malformed item = immediate fail.

**Step 2 — Workspace setup.** Either hard-reset an existing workspace (faster, preserves git history cache) or fresh-clone if none exists. The choice is automatic based on whether `.git` already exists in the target directory.

The choice between reset-existing and fresh-clone is a deliberate trade-off. Fresh clones are cleaner but slower (especially for large repos). Hard resets are faster but could theoretically leak state if git's reset logic fails. In practice, `git reset --hard` plus `git clean -fd` produces a workspace indistinguishable from a fresh clone 99.9% of the time, and the 0.1% case is caught by subsequent test failures. Fast iteration wins.

**Step 3 — Git identity.** Set the committer name and email explicitly. This is important so PR commits are clearly attributed to `harvester-agent` rather than whoever's git global config happens to be active on your Mac. When you review PRs, you want to see immediately which commits came from the agent.

**Step 4 — Branch creation.** Create a branch named by convention: `improvement/<issue-num>`. The prefix is repo-configurable. If a branch with that name already exists locally from a previous failed run, it's deleted first — we never want to accidentally continue from a previous attempt.

**Step 5 — Fetch issue body.** Pull the current issue body from GitHub. This deliberately uses GitHub as the source of truth rather than caching anything locally — the issue may have been edited since enqueue.

**Step 6 — Build task spec.** Assemble a markdown file containing the issue body plus standard instructions to Claude Code. The instructions emphasize:
- Read the repo's `CLAUDE.md` first
- Stay within scope defined by acceptance criteria
- Test before committing
- Commit but don't push (the script handles push)
- Fail gracefully if the task can't be completed — commit partial work with explanation rather than forcing a bad solution
- Don't touch guarded paths

The task spec is short and direct. Claude Code reads the repo's `CLAUDE.md` for the deep context; the task spec just delivers the work.

**Step 7 — Invoke Claude Code.** The actual agent run. Wrapped in `timeout` as a hard ceiling — even if Claude Code's own `max_turns` doesn't fire, the shell-level timeout does. 30 minutes is the default; long enough for substantive work, short enough to catch stuck runs.

The exit code handling distinguishes three cases:
- `0` — normal exit (may or may not have produced commits; checked next)
- `124` — timeout fired
- anything else — Claude Code error

Each is handled with its own error message on the issue.

**Step 8 — Verify commits were made.** It's possible for Claude Code to exit cleanly without producing any commits — maybe the task was ambiguous, maybe it decided the work couldn't be done safely. If zero commits, the run is treated as a failure with a clear comment: the task needs human attention, not another agent attempt.

**Step 9 — Guarded-path enforcement.** This is the Selah-critical step. Before any push happens, compute the diff of changed files and check each against the repo's guarded paths. If any guarded path is touched and the repo's policy is `never_execute`, abort immediately:
- Don't push the branch
- Delete the branch locally so nothing lingers
- Loud Telegram alert (this shouldn't happen in normal operation)
- Comment on the issue explaining why
- Move item to `failed/`

The guarded-path check uses bash globstar matching (`shopt -s globstar`), which handles `**` recursive globs correctly. A guarded path of `selah/theology/**` matches any file under `selah/theology/` at any depth.

**Step 10 — Push branch.** `git push -u origin <branch>`. If this fails, the work is done but not visible to GitHub; treat as failure.

**Step 11 — Open draft PR.** Use `gh pr create --draft` to open a pull request. The `--draft` flag is important — Troy decides when a PR is ready for review, not the agent. The PR body includes:
- Reference to the originating issue
- A summary of what Claude Code did (from the last commit message)
- A review checklist
- Run metadata (timestamp, duration, commit count, workspace path, log file)
- `Closes #<issue>` on its own line so merge auto-closes the issue

**Step 12 — Move to completed.** Annotate the queue item with the PR URL and move to `completed/`. Fire per-item Telegram notification so Troy knows there's a PR waiting.

---

## Guarded Paths: The Defense In Depth

The script's guarded-path check is one of four independent defense layers, per F19-S08. This script implements layer three. The layers are:

**Layer 1 — Scanner output.** The `theology_review` scanner is designed so it *cannot* produce change-oriented findings for guarded paths. Its output schema constrains it to review-request findings only.

**Layer 2 — Enqueue time.** Harvester's webhook handler checks if a finding touches guarded paths and refuses to enqueue if the repo's policy is `never_execute`. No queue item should ever exist for a guarded-path change.

**Layer 3 — Runner time (this script).** Even if something slipped through layers 1 and 2, this script examines the actual diff and aborts before pushing. This is the last line of defense before the change becomes visible on GitHub.

**Layer 4 — Branch protection.** GitHub branch protection rules on the Selah repo require human review for PRs that touch guarded paths. Even if all three earlier layers failed, the change still cannot merge without explicit approval.

The four layers are independent — each one catches different failure modes. Scanner layer catches design errors in the scanner itself. Enqueue layer catches mismatches between scanner output and the repo's policy. Runner layer catches cases where the agent took unexpected liberties during execution. Branch protection catches everything else.

If this script's layer ever triggers (Telegram alert fires), it's a notable event. It means something upstream failed and you should investigate the full chain before the next run. The alert copy is intentionally blunt ("GUARDED PATH VIOLATION") to make sure it gets attention.

---

## Failure Annotation Convention

When an item fails, the script appends a `failure` field to the JSON before moving it to `failed/`. Example:

```json
{
  "issue_number": 47,
  "repo": "hackstert/ezra-assistant",
  "repo_name": "ezra-assistant",
  ...
  "failure": {
    "reason": "claude_timeout",
    "detail": "Exceeded 30-minute timeout",
    "timestamp": "2026-04-26T02:34:11Z",
    "log_file": "/Users/hackstert/Projects/harvester/data/logs/run-20260426-020000.log"
  }
}
```

The `reason` field is a machine-readable enum used by the web UI for grouping. The `detail` is human-readable context. The `log_file` points to the full run log for investigation.

Defined reasons:

| Reason | Meaning |
|---|---|
| `malformed_queue_item` | JSON missing required fields |
| `clone_failed` | Initial git clone failed |
| `workspace_reset_failed` | Hard reset of existing workspace failed |
| `workspace_cd_failed` | Couldn't `cd` into workspace (permissions, missing) |
| `branch_creation_failed` | `git checkout -b` failed |
| `issue_fetch_failed` | Couldn't fetch issue body from GitHub |
| `claude_timeout` | Claude Code hit the 30-minute hard ceiling |
| `claude_error` | Claude Code exited non-zero |
| `no_commits` | Claude Code exited cleanly but produced no commits |
| `guarded_path_violation` | Agent touched guarded paths; run aborted |
| `push_failed` | Branch push to origin failed |
| `pr_creation_failed` | `gh pr create` failed |

Adding a new reason is free — just use it consistently and update this table.

---

## launchd Configuration

macOS uses launchd, not cron. The plist file lives at `~/Library/LaunchAgents/com.hackstert.harvester.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hackstert.harvester</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/hackstert/Projects/harvester/scripts/agent-runner.sh</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/hackstert/Projects/harvester/data/logs/launchd-stdout.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/hackstert/Projects/harvester/data/logs/launchd-stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>HOME</key>
        <string>/Users/hackstert</string>
    </dict>

    <key>RunAtLoad</key>
    <false/>

    <key>WorkingDirectory</key>
    <string>/Users/hackstert/Projects/harvester</string>
</dict>
</plist>
```

**The `PATH` key is critical.** launchd runs with an extremely minimal default `PATH`. Homebrew-installed tools won't be found unless `PATH` is set explicitly. This is the #1 cause of mysterious launchd failures.

**`RunAtLoad` is false** so loading the plist doesn't kick off an immediate run. You only want runs at 02:00, not every time you reboot.

**Install with:**

```bash
launchctl load ~/Library/LaunchAgents/com.hackstert.harvester.plist
```

**Verify it's scheduled:**

```bash
launchctl list | grep harvester
```

**Trigger manually for testing:**

```bash
launchctl kickstart -k gui/$(id -u)/com.hackstert.harvester
```

**Remove:**

```bash
launchctl unload ~/Library/LaunchAgents/com.hackstert.harvester.plist
```

An install script `scripts/install-launchd.sh` should handle the path substitution and loading automatically.

---

## Environment Variables the Script Reads

| Variable | Purpose | Default |
|---|---|---|
| `HARVESTER_ROOT` | Base path for Harvester files | `$HOME/Projects/harvester` |
| `WORKSPACES_DIR` | Where per-issue workspaces live | `$HOME/agent-workspaces` |
| `HARVESTER_DEFAULT_TIMEOUT` | Timeout per item in minutes | 30 |
| `HARVESTER_DEFAULT_MAX_TURNS` | Claude Code max turns | 50 |
| `TELEGRAM_BOT_TOKEN` | Bot token for notifications | (none, notifications off) |
| `TELEGRAM_ALLOWED_CHAT_ID` | Your chat ID | (none) |

These should be set in a `.env` file that the launchd wrapper sources, or explicitly set in the launchd plist. The script itself does not source `.env` files — that's the wrapper's job.

---

## What This Script Intentionally Does Not Do

**It does not merge PRs.** Ever. Branch protection would prevent this, but the script also doesn't try. Merge is Troy's judgment.

**It does not handle PR review comments.** If Troy requests changes on a PR, the script doesn't respond. To iterate on an existing PR, Troy either (a) makes changes manually, or (b) closes the PR, removes `agent-ready`, re-applies it to trigger a fresh run.

**It does not retry failed items automatically.** A failed item stays in `failed/` until Troy manually decides to retry it via the web UI's "Retry" button (which moves it back to `pending/`). Automatic retry would risk wasting subscription requests on tasks that will never succeed.

**It does not update Ezra's state.** Queue state lives in the Harvester filesystem. Ezra's webhook-based state sync (F19-S06) handles the Ezra side independently. This script is agnostic about what's monitoring the queue.

**It does not prune old workspaces.** Workspaces in `~/agent-workspaces/` accumulate over time. A separate maintenance script should handle pruning (monthly, delete workspaces older than 30 days). Keeping them around for a while is useful for post-mortem of interesting runs.

**It does not aggregate across repos.** Each queue item is independent. If three items for three repos are pending, they run sequentially, each in its own workspace, each with its own clone. There is no cross-repo batching or context sharing.

---

## Operational Playbook

### "The script ran but produced no PRs"

Check `data/queue/failed/` for items with recent failure annotations. Look at the `reason` field. If `claude_timeout` dominates, tasks may be too large or agent is getting stuck. If `no_commits` dominates, scanner outputs may be too vague for agent to act on. If `guarded_path_violation` appears, investigate immediately.

### "The script didn't run at all overnight"

Check launchd status:

```bash
launchctl list | grep harvester
```

If it's not listed, the plist isn't loaded. Reload.

If it is listed, check `data/logs/launchd-stderr.log` for preflight failures. Most common:
- Stale Claude Code subscription session → run `claude` interactively to refresh
- `gh` token expired → run `gh auth refresh`
- Network issue at 02:00 → one-off, will retry tomorrow

### "Claude Code subscription expired"

Run `claude` interactively on your Mac. Authenticate in the browser. Exit when prompted. Next run will work.

Set a calendar reminder for every 3 weeks to run `claude` once — this keeps the session warm indefinitely. The session typically lasts months if used regularly, but automation's "use" pattern doesn't always count.

### "An item has been in `pending/` but never ran"

Check if launchd actually fired at 02:00. Check log files for the expected timestamp. If launchd did fire but the item was skipped, it may be malformed — check the `reason` field if it moved to `failed/`.

If it's still in `pending/` with no log trace, launchd may not have run. Check macOS sleep settings — if your Mac slept at 2am and didn't wake, the job missed. Mac should be set to either stay awake or wake on schedule.

### "A guarded-path violation fired"

Do not proceed with normal operation until you understand what happened. Review:

1. Which file(s) were touched
2. Which scanner produced the finding
3. What the issue body actually said
4. Whether the scanner's output schema was followed

If the scanner produced a malformed finding, fix the scanner. If the agent went rogue within scope, tighten the issue template. If a legitimate path needed change and was incorrectly guarded, adjust `harvester-config.yaml` (carefully, with review).

### "The Mac was offline for a few days"

Items pending from before the outage will run on the next 02:00 after the Mac comes back online. Items created while offline are queued at GitHub — Harvester's webhook reconciliation on restart will enqueue them locally.

### "I want to test a change to the script"

Use `launchctl kickstart -k gui/$(id -u)/com.hackstert.harvester` to trigger an immediate run. If there's nothing in `pending/`, the script will log "Queue is empty" and exit quickly. Use this after any script edit to verify preflight still passes.

For testing with real items, manually create a test issue in a throwaway repo with the `agent-ready` label, confirm it enqueues, then trigger the runner.

---

## Security Notes

**Subscription auth lives in your user account's Claude Code state.** The script doesn't handle auth directly. This is safer than API keys because the auth cannot leak via log files or script environment.

**GitHub tokens are only referenced by the `gh` CLI.** The script never directly handles `GITHUB_TOKEN`. This means the script cannot accidentally leak tokens to logs.

**Telegram credentials are optional.** If unset, notifications silently skip. No leakage risk.

**Logs may contain snippets of issue bodies.** These are already public within your GitHub repos; no new exposure. Logs should not be shared outside your machine without review.

**Workspaces may contain cloned repo content.** These are on your local machine; the security posture is the same as having the repo checked out normally. No net-new exposure.

**The `timeout` command is load-bearing.** Without it, a runaway Claude Code invocation could consume unbounded time. With it, the worst case is 30 minutes wasted. The timeout is non-negotiable.

---

## Dependencies and Versions

The script requires these tools at these minimum versions (tested against):

| Tool | Minimum | Installation |
|---|---|---|
| `bash` | 4.0 | macOS ships with 3.x; `brew install bash` and use `/opt/homebrew/bin/bash` |
| `jq` | 1.6 | `brew install jq` |
| `yq` | 4.0 | `brew install yq` — note this is Mike Farah's yq, not the Python one |
| `gh` | 2.0 | `brew install gh` |
| `git` | 2.30 | comes with Xcode CLI tools |
| `claude` | latest | `npm install -g @anthropic-ai/claude-code` |
| `curl` | any | macOS default |

**About bash 4+:** macOS ships bash 3.2 (frozen at that version for licensing reasons). This script uses features that require bash 4+ (associative arrays, globstar, `set -o pipefail` with proper behavior). Install bash via Homebrew and make sure the shebang `#!/usr/bin/env bash` resolves to the Homebrew one by having `/opt/homebrew/bin` early in `PATH`.

**About yq:** There are two tools called `yq`. The script uses Mike Farah's yq (the Go implementation), which is what `brew install yq` provides. The Python yq uses different syntax and will not work as a drop-in.

---

## What Changes Might You Make

Some edits you might want to make later, with notes:

**Changing the run time.** Edit the launchd plist `StartCalendarInterval`. Reload: `launchctl unload` then `launchctl load`.

**Running multiple times per day.** Replace `StartCalendarInterval` with a `StartInterval` of seconds (e.g., 43200 = every 12 hours). Or use multiple calendar entries.

**Parallelizing item processing.** Don't. The script runs items sequentially by design — this respects rate limits, keeps behavior predictable, and makes logs linear. Parallelism would require coordinating workspaces and would not meaningfully speed up the overall workflow at Harvester's cadence.

**Adding a dry-run mode.** Add a `--dry-run` flag that performs everything through branch creation but skips the Claude Code invocation and push. Useful for testing config changes.

**Swapping to API-based Claude.** Change the `claude --task-file` invocation to use the Anthropic API directly via a Python wrapper. Remove the subscription preflight probe. Add `ANTHROPIC_API_KEY` env handling. The rest of the script is unchanged — the pattern is agent-agnostic at the protocol level.

**Auto-retry for specific failure reasons.** Add logic before final `move_queue_item "failed"` that checks the failure reason and, for transient reasons (network errors, rate limits), moves back to `pending/` with an incremented retry count. Cap at 2-3 retries to avoid loops.

Each of these is a small edit to a specific section. The script's structure makes them localized changes, not rewrites.

---

## One Last Note

This script is deliberately longer and more verbose than it needs to be. Every comment, every log line, every explicit error message exists because at some point in the future, you (or Claude Code working on Harvester itself) will be reading it at 3am trying to figure out why something went wrong.

Terseness is a false economy in operational code. The script you can read when tired beats the elegant script you can read when fresh.

---

*Created: 2026-04-18 | Companion to `scripts/agent-runner.sh`*
