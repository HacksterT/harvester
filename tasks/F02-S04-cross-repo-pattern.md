---
type: story
feature: F02
story: F02-S04
title: Cross-Repo Pattern Scanner
status: backlog
created: 2026-04-18
priority: nice-to-have
---

# F02-S04: Cross-Repo Pattern Scanner

**Feature:** F02 — Harvester Completion — Expansion and Steady State
**Priority:** Nice-to-Have

## Summary

The self-annealing mechanism: a scanner that mines the historical corpus of closed issues across all repos to identify patterns in what gets merged, what gets rejected, and what keeps recurring. This is the autoresearch loop's `results.tsv` equivalent — the record of what worked and what didn't, fed back into the system to improve future experiments. It runs monthly and produces at most one finding: the single most actionable signal from the history. Hard-gated at 30 closed issues; activates automatically once the corpus is large enough.

## Acceptance Criteria

- [ ] Scanner is corpus-gated: queries GitHub for closed issues labeled `improvement` across all repos; returns `None` if fewer than 30 found
- [ ] Produces at most one finding per monthly run
- [ ] Finding is categorized as one of: over-triggering scanner (propose retiring/retuning), low-merge-rate repo (propose cadence review), or stale domain (propose new scanner or topic shift)
- [ ] First real pattern finding produced and either actioned or consciously deferred
- [ ] Corpus gate and last-run state tracked in `harvester-state.json` like other scanners

## Tasks

### Backend
- [ ] Implement `scanners/cross_repo_patterns.py`: `SYSTEM_PROMPT` instructs Claude to analyze the provided issue corpus (merge rate per scanner, rejection patterns, recurring domains) and call `report_finding` with one actionable signal; `ENABLED_TOOLS = []` (no filesystem access needed — GitHub data is injected into the prompt as structured context by the runner); the runner passes a pre-built JSON summary of closed issues as the user message
- [ ] Add corpus gate check: count total closed issues; return `None` immediately if below threshold (log at DEBUG)
- [ ] Register `cross_repo_patterns` scanner in `scanners/__init__.py`; add to Ezra's config entry in `harvester-config.yaml` with `cadence_days: 30`
- [ ] Update `harvester-state.json` schema docs to include the cross-repo scanner entry

### Testing & Verification
- [ ] Write `tests/scanners/test_cross_repo_patterns.py`: mock GitHub responses with 10 issues (below gate); assert `None` returned; mock with 35 issues; assert finding returned with expected structure
- [ ] Local Testing: `uv run pytest tests/scanners/test_cross_repo_patterns.py -x`; if corpus exists, run `python -m harvester scan ezra-assistant cross_repo_patterns` and review output
- [ ] Manual Testing: CHECKPOINT — Review first real pattern finding; decide whether to action it (tune a scanner), defer it, or dismiss it; document the decision in the issue before closing

### Git
- [ ] Commit, fetch/rebase, push

## Technical Notes

This scanner runs monthly and touches the GitHub API heavily (listing all closed issues across all repos plus their linked PRs). Rate limit awareness is important here more than anywhere else — build in deliberate `asyncio.sleep(1)` delays between paginated requests.

Pattern detection approach: keep it simple. Three signal categories:
1. Scanner over-triggering: scanner X has produced N issues, merge rate < 30%
2. Low-activity repo: repo Y has had 0 merges in 60 days despite issues being labeled `agent-ready`
3. Recurring domain: same domain appears in 3+ consecutive issues across any repo

Claude's job is to take these signals and write a readable finding summary with one specific recommendation. The scanner should not try to do NLP or ML — it is a metric aggregator. Claude is the analyst, invoked via `scanner_runner.py` + `client.beta.messages.tool_runner()` with only `report_finding` in the tool list.

This scanner is the only one that does not read local filesystem state. It reads GitHub exclusively via `GitHubClient`. This means it runs correctly even if local Ezra/Selah repos are not present.

## Blockers

F01 complete; F02-S03 (code health scanner) adds to the corpus; corpus gate (30+ closed issues) must be met before producing real findings. Do not start this story until F01 has been running for at least 60 days.
