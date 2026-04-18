---
type: story
feature: F02
story: F02-S06
title: Telegram Notifications
status: backlog
created: 2026-04-18
priority: must-have
---

# F02-S06: Telegram Notifications

**Feature:** F02 — Harvester Completion — Expansion and Steady State
**Priority:** Must-Have

## Summary

Wire Harvester's operational events to Telegram so Troy can communicate with and monitor Harvester without checking log files. Notifications cover the full loop: new findings, agent run outcomes (success with PR link, failure with reason), and guarded-path violations. The `python-telegram-bot` package is already a dependency. This is a one-way notification channel — Harvester sends to Telegram, no command handling in this story.

## Acceptance Criteria

- [ ] Telegram bot sends a message when a scanner produces a finding (repo, scanner, title, priority, issue link)
- [ ] Telegram bot sends a message when an agent run completes successfully (repo, issue, PR link)
- [ ] Telegram bot sends a message when an agent run fails (repo, issue, failure reason)
- [ ] Telegram bot sends a message when a guarded-path violation is detected and the run is aborted
- [ ] Telegram bot sends a message when Harvester starts up successfully (port, repos configured)
- [ ] All notifications go to `TELEGRAM_ALLOWED_CHAT_ID` from env
- [ ] If `TELEGRAM_BOT_TOKEN` is not set, notifications are silently skipped — no crash
- [ ] Message format is clean and readable on mobile: emoji-prefixed, key facts only, no walls of text

## Tasks

### Backend

- [ ] Implement `src/harvester/notifier.py`: async `send(message: str) -> None` using `python-telegram-bot`'s `Bot.send_message()`; reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_CHAT_ID` from env; no-ops gracefully if either is missing
- [ ] Define notification message templates as module-level constants: `MSG_FINDING`, `MSG_RUN_SUCCESS`, `MSG_RUN_FAILED`, `MSG_GUARDED_PATH`, `MSG_STARTUP`
- [ ] Wire startup notification into `main.py` lifespan
- [ ] Wire finding notification into `writer.py` after issue creation
- [ ] Wire run outcome notifications into `agent-runner.sh` via `python -m harvester notify` CLI command (so bash can trigger them without importing Python)
- [ ] Add `notify` command to `__main__.py`: `python -m harvester notify <event> [--data key=value ...]`

### Testing & Verification

- [ ] Write `tests/test_notifier.py`: mock `Bot.send_message`; assert correct message sent for each event type; assert no-op when token missing
- [ ] Manual Testing: CHECKPOINT — Trigger a test notification via `python -m harvester notify startup`; confirm message appears in Telegram

### Git

- [ ] Commit, fetch/rebase, push

## Technical Notes

Message format examples:

```
🌱 New finding — ezra-assistant
Scanner: skill_gaps | Priority: should-have
"Missing coverage for async tool calls"
→ https://github.com/HacksterT/ezra-assistant/issues/42

✅ Agent run complete — ezra-assistant #42
PR ready for review: https://github.com/HacksterT/ezra-assistant/pull/7

❌ Agent run failed — ezra-assistant #42
Reason: max turns exceeded
Check: data/logs/2026-04-18-ezra-42.log

🚨 Guarded path violation — selah #15
Agent diff touched theology/creeds.md — run aborted

🟢 Harvester started on port 8500
Watching: ezra-assistant, selah
```

The `notify` CLI command exists so `agent-runner.sh` can fire Telegram messages without needing to embed Python logic in bash. Example: `python -m harvester notify run_success --repo ezra-assistant --issue 42 --pr-url https://...`

## Blockers

F01-S01 (CLI structure) complete. No other blockers — can be implemented in parallel with other F02 stories.
