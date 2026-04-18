---
type: story
feature: F02
story: F02-S02
title: Selah Theology Review Scanner and Guardrails
status: backlog
created: 2026-04-18
priority: should-have
---

# F02-S02: Selah Theology Review Scanner and Guardrails

**Feature:** F02 — Harvester Completion — Expansion and Steady State
**Priority:** Should-Have

## Summary

Add Selah to Harvester's watch list with a theology-review scanner and four-layer guarded-path protection. The theology review scanner is explicitly non-actionable — it produces findings framed as human review requests, not change proposals. The four-layer defense (scanner construction, enqueue policy, runner diff check, GitHub branch protection) makes automated changes to theological content virtually impossible. This story delivers the scanner, the guardrail layers already built in F01 configured for Selah, and a documentation page describing the defense-in-depth design.

## Acceptance Criteria

- [ ] Selah added to `harvester-config.yaml` with `guarded_paths` and `guarded_path_policy: never_execute`
- [ ] `scanners/theology_review.py` produces findings framed as review requests, never as change proposals
- [ ] `touches_guarded_paths=True` is set on any finding that references theological content
- [ ] Layer 1: scanner cannot produce change-oriented findings for guarded paths (verified by reading the implementation)
- [ ] Layer 2: enqueue refusal tested — a mock finding with `touches_guarded_paths=True` on Selah is refused with a GitHub comment
- [ ] Layer 3: runner diff check tested — a mock diff touching `theology/**` triggers abort with issue comment and Telegram alert
- [ ] Layer 4: documented in `docs/selah-guardrails.md` with instructions for configuring GitHub branch protection
- [ ] First real theology finding produced, reviewed manually by Troy, and marked handled

## Tasks

### Backend
- [ ] Add Selah entry to `harvester-config.yaml` with confirmed guarded paths: `theology/**`, `training/**`, `prompts/**`, `doctrine/**`; policy: `never_execute`; scanner: `theology_review` on 30-day cadence
- [ ] Implement `scanners/theology_review.py`: `SYSTEM_PROMPT` instructs Claude to read `prompts/`, `doctrine/`, and `theology/` files from the Selah repo, examine Nicene Creed alignment and denominational consistency, and call `report_finding` with `touches_guarded_paths=True` and summary framed as "flag for review"; `ENABLED_TOOLS = ["read_file", "list_directory"]`; `scanner_runner.py` drives the tool-calling loop
- [ ] Write issue body template for theology findings: prefix with explicit disclaimer that this is a review request, not an automation target; add `theological-review-required` label automatically
- [ ] Write `docs/selah-guardrails.md`: describe all four layers, their independence, and what to do if a violation somehow occurs

### Testing & Verification
- [ ] Write `tests/scanners/test_theology_review.py`: mock Selah repo files; assert finding has `touches_guarded_paths=True`; assert no change-oriented language in summary or tasks
- [ ] Test layer 2 (enqueue refusal): call `queue.enqueue(item)` with a finding from Selah touching guarded paths; assert `QueueRefusedError` raised and GitHub comment written
- [ ] Test layer 3 (runner diff check): inject a mock diff touching `theology/` in the runner test harness; assert run aborts with correct failure reason
- [ ] Local Testing: `uv run pytest tests/scanners/test_theology_review.py -x`; run `python -m harvester scan selah theology_review` against real Selah checkout
- [ ] Manual Testing: CHECKPOINT — Review the first real theology finding issue on GitHub; verify it is framed as a review request with correct labels; manually implement or dismiss; confirm Harvester records the outcome

### Git
- [ ] Commit, fetch/rebase, push

## Technical Notes

Selah's `CLAUDE.md` must exist before this story can complete. If it does not exist, write a minimal one as a prerequisite (not part of this story's scope — flag and wait for Troy to author it).

The theology scanner reads file content, not Git history. It does not require a running Selah service. It accesses the files at `repo_config.local_path` via `Path.read_text()`.

The scanner's issue body must include:
> "This finding is a request for theological review, not a proposal for automated change. The agent runner will not execute changes to guarded paths in this repo. Troy's manual review and implementation are required."

This explicit statement is layer 1 in human-readable form. Even if all automated layers failed, a human reviewer would see this and understand not to merge an agent-generated PR touching theology.

## Blockers

F01 complete; Selah repo with initial `CLAUDE.md` and guarded directory structure; F02-S03 is independent and can proceed in parallel.
