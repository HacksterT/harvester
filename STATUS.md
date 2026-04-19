---
project: harvester
status: active
phase: F01 — manual testing
next_step: "Complete the F01 end-to-end cycle: trigger a real Ezra issue, apply agent-ready, confirm overnight runner produces a draft PR (HT-10)."
blockers: []
key_people:
  - "Troy (owner)"
updated: 2026-04-18
---

## Next Steps

- [ ] Run `bash scripts/agent-runner.sh` manually with one real pending item; confirm workspace created, claude invoked, branch pushed, draft PR opened *(source: F01-S05-agent-runner.md)*
- [ ] One full end-to-end cycle completed: real Ezra issue → label → enqueue → overnight run → draft PR *(source: F01-S05-agent-runner.md)*
- [ ] Manual Testing: confirm draft PR in `hackstert/ezra-assistant` with `Closes #N`; merge or close; confirm queue item moves to `completed/` on issues.closed webhook *(source: F01-S05-agent-runner.md)*
- [ ] Integration test: run each scanner against real Ezra checkout at `~/Projects/ezra-assistant`; confirm valid Finding returned *(source: F01-S04-port-scanners.md)*
- [ ] Test guarded-path enforcement: mock queue item with `guarded_check.required=true` touching a guarded path; confirm run aborts, item moves to `failed/` *(source: F01-S05-agent-runner.md)*

## Notes

F01 code complete: all six stories implemented, 112 tests passing, pushed to GitHub. Manual testing (tasks/human-test.md, HT-01 through HT-14) is the only remaining gate. F02 (web UI, Selah guardrails, cross-repo patterns) opens after 30-day F01 stability.
