---
type: story
feature: F02
story: F02-S03
title: Generic Code Health Scanner
status: backlog
created: 2026-04-18
priority: should-have
---

# F02-S03: Generic Code Health Scanner

**Feature:** F02 — Harvester Completion — Expansion and Steady State
**Priority:** Should-Have

## Summary

A scanner applicable to any Python repo that uses off-the-shelf static analysis tools (`ruff`, `mypy`, `radon`, `coverage.py`) to identify concrete, actionable code health issues. Unlike the Ezra-specific scanners ported in F01-S04, this one is domain-agnostic and ships with sensible thresholds overridable per repo in `harvester-config.yaml`. It produces one focused finding per run — the highest-priority issue, not a comprehensive report — keeping the issue backlog from flooding.

## Acceptance Criteria

- [ ] Scanner runs against Ezra and Selah repos without errors
- [ ] Produces a `Finding` matching the scanner contract (one per run, structured evidence)
- [ ] Detects at least four health dimensions: oversized files, high-complexity functions, missing type hints in public APIs, stale TODO/FIXME comments
- [ ] Thresholds configurable per repo in `harvester-config.yaml` under the scanner entry
- [ ] Three real findings produced across repos during development and reviewed by Troy
- [ ] `docs/scanner-contract.md` updated with a code_health example section

## Tasks

### Backend
- [ ] Implement `scanners/code_health.py`: subprocess calls to `ruff check`, `mypy`, `radon cc` (cyclomatic complexity); `grep` for TODO/FIXME with git-blame date check; parse output; rank issues by impact; return the single highest-priority `Finding`
- [ ] Add default thresholds to `ScanContext` or scanner config: `max_file_lines: 400`, `max_function_complexity: 10`, `min_coverage_pct: 80`, `todo_staleness_days: 30`
- [ ] Support per-repo threshold overrides via `harvester-config.yaml` scanner entry `thresholds:` key; validated by pydantic in `config.py`
- [ ] Update `docs/scanner-contract.md` with a `code_health` worked example

### Dependencies
- [ ] `ruff`, `mypy`, `radon` are dev tools — invoke via `subprocess`, no need to add as runtime dependencies
- [ ] Confirm these tools are available in the Mac environment; add install note to `docs/operational-runbook.md`

### Testing & Verification
- [ ] Write `tests/scanners/test_code_health.py`: mock subprocess outputs for each tool; assert Finding fields populated correctly; assert threshold override respected
- [ ] Local Testing: `uv run pytest tests/scanners/test_code_health.py -x`; run `python -m harvester scan ezra-assistant code_health` against real Ezra checkout; confirm a real finding is returned
- [ ] Manual Testing: CHECKPOINT — Review three real code health findings in GitHub issues; confirm evidence is accurate and tasks are actionable; apply `agent-ready` to at least one and confirm it runs successfully

### Git
- [ ] Commit, fetch/rebase, push

## Technical Notes

The scanner invokes tools as subprocesses rather than importing them as libraries. This keeps Harvester's dependency list clean — ruff, mypy, and radon are installed in the target repo's environment, not Harvester's. Use `subprocess.run([tool, ...], cwd=repo_config.local_path, capture_output=True, text=True)`.

The scanner's LLM call is minimal: the tool outputs contain the raw facts; Grok's job is to select the single highest-value finding from them and generate the `Finding.title`, `Finding.summary`, and `Finding.criteria` fields in structured format. Evidence is the raw tool output excerpt.

`radon cc` output format: `src/ezra/memory/store.py - F:42 run_decay_sweep - B (6)`. Parse with simple regex to extract file, function, score.

## Blockers

F01 complete; independent of F02-S01 and F02-S02.
