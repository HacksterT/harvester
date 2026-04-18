---
type: story
feature: F01
story: F01-S05
title: Agent Runner with Subscription Auth
status: backlog
created: 2026-04-18
priority: must-have
---

# F01-S05: Agent Runner with Subscription Auth

**Feature:** F01 — Harvester Core — Autonomous Improvement Loop
**Priority:** Must-Have

## Summary

The overnight agent runner is the execution heart of Harvester. It drains the pending queue, invokes Claude Code once per item within a fresh workspace, pushes the result as a branch, and opens a draft PR. It runs as a bash script invoked by launchd at 02:00 local time. Subscription authentication (not API key) is used — Claude Code on Troy's Mac is authenticated via his Claude.ai subscription. The runner's security model has two guarded-path enforcement layers: the enqueue gate (S03) and a diff check before any push.

## Acceptance Criteria

- [ ] `scripts/agent-runner.sh` drains `data/queue/pending/` correctly, oldest-first
- [ ] Each run uses a fresh workspace: hard reset to `origin/main` if exists, fresh clone if new
- [ ] Subscription auth preflight: `claude --version` returns cleanly; runner exits with Telegram alert if stale
- [ ] `gh` CLI authenticated preflight check
- [ ] Guarded-path second-layer enforcement: diff checked before push; violation aborts run, moves to `failed/`, comments on issue, fires Telegram alert
- [ ] PR opened in draft state: `gh pr create --draft`; title format `Closes #N: <issue title>`
- [ ] Failed run path: issue receives comment with failure reason; queue item moves to `failed/`; Telegram summary includes failure count
- [ ] Telegram post-run summary fires: "Harvester run complete: N succeeded, M failed"
- [ ] `scripts/install-launchd.sh` correctly installs and loads the launchd plist for 02:00 local time
- [ ] One full end-to-end cycle completed: real Ezra issue → label → enqueue → overnight run → draft PR

## Tasks

### Infrastructure
- [ ] Write `scripts/agent-runner.sh`: preflight checks (claude, gh, subscription session); iterate `pending/*.json` oldest-first; per-item workspace prep (clone or hard reset); `gh issue view` to fetch issue body; build `/tmp/task.md` combining issue body and repo's `CLAUDE.md`; invoke `claude --task-file /tmp/task.md --max-turns 50 --timeout-minutes 30`; diff check for guarded paths; push branch; `gh pr create --draft`; move queue item; Telegram notification per item; post-run summary
- [ ] Write `scripts/install-launchd.sh`: writes `~/Library/LaunchAgents/com.hackstert.harvester.plist` with `StartCalendarInterval` (02:00), `ProgramArguments`, stdout/stderr to `data/logs/`, `EnvironmentVariables` including PATH with Homebrew + gh + claude
- [ ] Write `runner.py` in `src/harvester/`: Python module for queue inspection used by launchd plist health check; also exposes `GET /api/runner/status` showing last run time and outcome from logs

### Testing & Verification
- [ ] Test guarded-path enforcement: create a mock queue item with `guarded_check.required=true` and a diff touching a guarded path; confirm run aborts, item moves to `failed/`, issue comment written (use `--dry-run` flag in test mode)
- [ ] Test failure path: inject a queue item for a non-existent issue; confirm graceful failure and cleanup
- [ ] Local Testing: run `bash scripts/agent-runner.sh` manually with one real pending item; confirm workspace created, `claude` invoked, branch pushed, draft PR opened
- [ ] Manual Testing: CHECKPOINT — After full cycle, confirm draft PR in `hackstert/ezra-assistant` with `Closes #N` in body; review and merge or close; confirm queue item moves to `completed/` on the issues.closed webhook (F01-S06)

### Git
- [ ] Commit, fetch/rebase, push

## Technical Notes

Claude Code invocation: `claude --task-file /tmp/task.md --max-turns 50`. The `--max-turns` cap is a cost and time control. The 30-minute wall-clock timeout is enforced by the bash `timeout` command wrapping the invocation: `timeout 1800 claude --task-file /tmp/task.md --max-turns 50`.

Workspace path: `~/agent-workspaces/<repo-name>-<issue-num>/`. Each issue gets its own workspace and the directory persists across runs (hard-reset rather than re-clone for speed). The directory is gitignored from the Harvester repo.

Guarded-path diff check: `git diff --name-only origin/main...HEAD` after the agent finishes. Compare each path against the repo config's `guarded_paths` using `fnmatch`. If any match and the policy is `never_execute`, abort.

The task file `/tmp/task.md` structure:
```
# Task — Issue #N: <title>

## Issue Body
<full GitHub issue body including Summary, Evidence, Acceptance Criteria, Tasks>

## Repository Context
<contents of repo's CLAUDE.md>

## Instructions
Implement the changes required to satisfy the Acceptance Criteria above.
Run tests before finishing. Commit with a descriptive message. Do not push.
```

## Blockers

F01-S03 (queue read operations), F01-S02 (GitHub client for issue comments), F01-S04 (scanners producing real issues to test against).
