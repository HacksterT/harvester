---
project: harvester
status: active
phase: F01 — manual testing
next_step: "Complete the F01 end-to-end cycle: trigger a real Ezra issue, apply agent-ready, confirm overnight runner produces a draft PR (HT-10)."
blockers: []
key_people:
  - "Troy (owner)"
updated: 2026-05-15
---

## Next Steps

- [ ] Local Testing: run integration test against real Ezra checkout at `~/Projects/ezra-assistant`; confirm each scanner returns a valid `Finding` *(source: F01-S04-port-scanners.md)*
- [ ] Manual Testing: run `python -m harvester scan ezra-assistant skill_gaps`; confirm real GitHub issue appears with correct labels and structured body *(source: F01-S04-port-scanners.md)*
- [ ] Test guarded-path enforcement: mock queue item with `guarded_check.required=true` touching a guarded path; confirm run aborts, item moves to `failed/`, issue comment written *(source: F01-S05-agent-runner.md)*
- [ ] Test failure path: inject a queue item for a non-existent issue; confirm graceful failure and cleanup *(source: F01-S05-agent-runner.md)*
- [ ] Local Testing: run `bash scripts/agent-runner.sh` manually with one real pending item; confirm workspace created, `claude` invoked, branch pushed, draft PR opened *(source: F01-S05-agent-runner.md)*

## Notes

F01 code complete: all six stories implemented, 112 tests passing, pushed to GitHub. Manual testing (tasks/human-test.md, HT-01 through HT-14) is the only remaining gate. F02 (web UI, Selah guardrails, cross-repo patterns) opens after 30-day F01 stability.
