---
type: testing-checklist
title: Harvester Human Testing Checkpoints
status: pending
created: 2026-04-19
---

# Harvester Human Testing Checkpoints

Manual tests that cannot be automated. Work through these in order — each story
builds on the previous one. Complete the full end-to-end cycle at least three
times before considering F01 stable.

---

## Prerequisites

Before any testing, confirm these are all true:

- [ ] `.env` file exists with `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_ID`
- [ ] `uv run python -c "from anthropic import AsyncAnthropic; print('ok')"` returns `ok`
- [ ] `gh auth status` shows authenticated as `hackstert`
- [ ] `claude --version` returns a version string
- [ ] Ezra repo exists at `~/Projects/ezra-assistant` with `CLAUDE.md` present
- [ ] Harvester server is not already running (`curl http://localhost:8500/healthz` fails)

---

## HT-01: Config Validation

**Story:** F01-S01

Run:
```bash
uv run python -m harvester validate
```

Expected: lists ezra-assistant with its scanners, no error exit.

- [ ] Command runs without error
- [ ] Output lists at least one repo and at least one scanner

---

## HT-02: Server Startup

**Story:** F01-S01

Run from the Harvester repo root:
```bash
./start.sh
```

Expected: server starts, healthz responds.

- [ ] `./start.sh` exits without error
- [ ] `curl http://localhost:8500/healthz` returns `{"status": "ok", ...}`
- [ ] `GET /api/runner/status` returns queue counts (all zeros is fine)
- [ ] Telegram message received: Harvester startup notification (if notifier is live — skip if still stub)

Cleanup: leave running for HT-03, or `./stop.sh` after this test.

---

## HT-03: GitHub Label Sync

**Story:** F01-S02

With the server running and `GITHUB_TOKEN` set:

- [ ] Open `https://github.com/hackstert/ezra-assistant/labels`
- [ ] Confirm all 21 labels from the taxonomy exist (improvement, priority:*, status:*, agent-ready, scanner:*, domain:*, theological-review-required)
- [ ] Labels not already present were created on this startup

If labels are missing, check server logs: `tail -f data/logs/harvester-server.log`

---

## HT-04: Queue CLI

**Story:** F01-S03

```bash
uv run python -m harvester queue list
```

Expected: shows `pending 0`, `completed 0`, `failed 0`, `rejected 0`.

- [ ] Command runs without error
- [ ] All four counts shown, all zero (or consistent with actual queue state)

---

## HT-05: Scanner — Skill Gaps (API call, no GitHub issue)

**Story:** F01-S04

Verify the scanner framework makes a real API call and returns a Finding.

```bash
set -a && source .env && set +a
uv run python -c "
import asyncio, types, os
from harvester.scanner_runner import run_scanner
from harvester.models import ScanContext
from unittest.mock import MagicMock

repo = MagicMock()
repo.name = 'ezra-assistant'
repo.local_path = os.path.expanduser('~/Projects/ezra-assistant')

from harvester.scanners import skill_gaps
context = ScanContext(run_id='manual-test-001')
result = asyncio.run(run_scanner(skill_gaps, repo, context))
if result:
    print('Finding:', result.title)
    print('Domain: ', result.domain)
    print('Priority:', result.priority)
else:
    print('No finding returned (scanner returned None)')
"
```

- [ ] Command completes without exception
- [ ] Either a Finding is printed, or `No finding returned` (both are valid)
- [ ] No `ANTHROPIC_API_KEY` error

---

## HT-06: Scanner — Full Scan Command

**Story:** F01-S04

```bash
uv run python -m harvester scan ezra-assistant skill_gaps
```

At this point the `scan` CLI command is stubbed (`F01-S04` note in `__main__.py`). This test confirms the stub is hit cleanly and a real implementation is the next step.

- [ ] Command exits with error message `not yet implemented`
- [ ] No crash or traceback

---

## HT-07: End-to-End Scanner → GitHub Issue

**Story:** F01-S04 (CHECKPOINT)

Run a real scanner against Ezra, produce a GitHub issue manually via the writer:

```bash
set -a && source .env && set +a
uv run python -c "
import asyncio, os
from harvester.scanner_runner import run_scanner
from harvester.writer import write_finding
from harvester.github_client import GitHubClient
from harvester.models import ScanContext
from unittest.mock import MagicMock

repo = MagicMock()
repo.name = 'ezra-assistant'
repo.local_path = os.path.expanduser('~/Projects/ezra-assistant')

from harvester.scanners import skill_gaps
context = ScanContext(run_id='manual-test-002')

async def run():
    finding = await run_scanner(skill_gaps, repo, context)
    if not finding:
        print('No finding — try again or check scanner prompt')
        return
    print('Finding:', finding.title)
    gh = GitHubClient(
        token=os.environ['GITHUB_TOKEN'],
        repo_full_name='hackstert/ezra-assistant'
    )
    url = await write_finding(finding, gh)
    print('Issue created:', url)

asyncio.run(run())
"
```

- [ ] A Finding is returned
- [ ] A GitHub issue appears at `https://github.com/hackstert/ezra-assistant/issues`
- [ ] Issue title starts with `[IMPROVEMENT]`
- [ ] Issue body has Summary, Evidence, Acceptance Criteria, Tasks sections
- [ ] Issue has labels: `improvement`, `status:triage`, a priority label, a scanner label, a domain label
- [ ] Finding logged to `data/findings/YYYY-MM-DD.jsonl`

Repeat for `memory` and `tokens` scanners by substituting the import.

---

## HT-08: Manual Enqueue

**Story:** F01-S03 / F01-S05

After HT-07 created a real issue, manually enqueue it to test the queue system:

```bash
set -a && source .env && set +a
uv run python -c "
import asyncio, os
from datetime import UTC, datetime
from pathlib import Path
from harvester.models import QueueItem
from harvester.queue import enqueue, init_queue
from unittest.mock import MagicMock

# Replace with the real issue number from HT-07
ISSUE_NUMBER = 1

repo_cfg = MagicMock()
repo_cfg.guarded_paths = ['theology/**']
repo_cfg.guarded_path_policy = 'never_execute'

item = QueueItem(
    repo_name='ezra-assistant',
    github_repo='hackstert/ezra-assistant',
    local_path=os.path.expanduser('~/Projects/ezra-assistant'),
    issue_number=ISSUE_NUMBER,
    issue_title='Test manual enqueue',
    issue_url=f'https://github.com/hackstert/ezra-assistant/issues/{ISSUE_NUMBER}',
    scanner='skill_gaps',
    priority='should-have',
    branch_prefix='improvement/',
    guarded_paths=['theology/**'],
    touches_guarded_paths=False,
    queued_at=datetime.now(UTC),
)

queue_root = Path('data/queue')
init_queue(queue_root)
path = enqueue(item, queue_root, repo_cfg)
print('Enqueued:', path)
"
```

Then confirm via CLI:
```bash
uv run python -m harvester queue list
```

- [ ] `queue list` shows `pending 1`
- [ ] File `data/queue/pending/ezra-assistant-<N>.json` exists
- [ ] JSON file contains correct `github_repo`, `issue_number`, `scanner` fields

---

## HT-09: Agent Runner — Dry Run Preflight

**Story:** F01-S05

Before running overnight, verify the preflight checks pass:

```bash
set -a && source .env && set +a
HARVESTER_ROOT=$(pwd) bash scripts/agent-runner.sh
```

With an empty queue, this should pass all preflights and exit cleanly with "queue is empty."

- [ ] All preflight tools found: `jq`, `yq`, `gh`, `git`, `claude`, `curl`
- [ ] `gh` shows authenticated
- [ ] Claude Code probe returns `READY` (confirms subscription session is live)
- [ ] Script exits 0 with "Queue is empty. Nothing to do."
- [ ] Log file written to `data/logs/run-YYYYMMDD-HHMMSS.log`

If the Claude auth probe fails, run `claude` interactively, authenticate, and retry.

---

## HT-10: Agent Runner — Full Cycle

**Story:** F01-S05 (CHECKPOINT)

With a real item in `data/queue/pending/` (from HT-08):

```bash
set -a && source .env && set +a
HARVESTER_ROOT=$(pwd) bash scripts/agent-runner.sh
```

- [ ] Script clones or resets workspace at `~/agent-workspaces/ezra-assistant-<N>/`
- [ ] GitHub issue body fetched from API
- [ ] `claude -p` invoked; terminal shows Claude Code working
- [ ] No guarded-path violations
- [ ] Branch `improvement/<N>` pushed to `hackstert/ezra-assistant`
- [ ] Draft PR opened — confirm URL printed in script output
- [ ] Queue item moved from `pending/` to `completed/`
- [ ] Telegram message received: per-item success notification
- [ ] Telegram message received: post-run summary `N succeeded, 0 failed`
- [ ] `uv run python -m harvester queue list` shows `pending 0`, `completed 1`

---

## HT-11: Guarded-Path Enforcement

**Story:** F01-S05

Manually create a queue item that `touches_guarded_paths=True` for a repo with `never_execute` policy, then run the agent runner. This tests the second-layer enforcement (diff check after agent finishes).

For a simpler smoke test without a full agent run: enqueue an item, manually create a branch in the workspace that touches `theology/test.md`, then invoke the runner.

- [ ] Run aborts before push
- [ ] Queue item moves to `failed/`
- [ ] GitHub issue receives a guarded-path violation comment
- [ ] Telegram alert fires with `GUARDED PATH VIOLATION` text
- [ ] No branch pushed to GitHub

---

## HT-12: launchd Installation

**Story:** F01-S05

```bash
bash scripts/install-launchd.sh
```

- [ ] Script completes without error
- [ ] `launchctl list | grep harvester` shows both `com.hackstert.harvester` and `com.hackstert.harvester.runner`
- [ ] `curl http://localhost:8500/healthz` returns ok (server loaded and running)
- [ ] Runner plist shows `StartCalendarInterval` at 02:00 in `~/Library/LaunchAgents/com.hackstert.harvester.runner.plist`

---

## HT-13: Webhook Receipt

**Story:** F01-S06

Confirm the webhook endpoint is reachable and validates signatures correctly.

From another terminal (or use the Cloudflare Tunnel URL):
```bash
# Correct signature (replace SECRET with your GITHUB_WEBHOOK_SECRET)
SECRET="your-webhook-secret"
PAYLOAD='{"action":"labeled","issue":{"number":1},"label":{"name":"agent-ready"}}'
SIG="sha256=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')"
curl -X POST http://localhost:8500/webhook \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$PAYLOAD"
```

- [ ] Returns `200 {"ok": true}`
- [ ] Bad signature returns `401`
- [ ] Missing signature returns `401`

---

## HT-14: Full Autonomous Loop × 3

**Story:** F01 Success Criteria

The loop is done when a finding travels from scanner to merged PR at least three times without manual intervention beyond triage and review.

For each cycle:
1. Scanner runs (via scheduler or manual invocation)
2. Finding written to GitHub issue automatically
3. Troy applies `agent-ready` label (triage step — this is intentional manual gate)
4. Item enters queue
5. Overnight runner processes it
6. Draft PR opened
7. Troy reviews and merges or closes

Cycle tracking:

| # | Issue | Scanner | PR | Outcome | Date |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

- [ ] 3 cycles completed
- [ ] Merge rate ≥ 50%
- [ ] No guarded-path violations
- [ ] Harvester ran without unplanned downtime exceeding 24h

---

## Notes

**Tools required for HT-09+:**
- `jq` — `brew install jq`
- `yq` — `brew install yq`

**If the Claude auth probe hangs:** the subscription session may be stale. Run `claude` interactively, re-authenticate via browser, then retry.

**If a scanner returns None repeatedly:** check that `~/Projects/ezra-assistant` has the expected database files. The scanners read `data/state/ezra.db` and `data/memory/boluses.db` directly. If those don't exist, the scanner will explore, find nothing, and return None.

**Queue cleanup between test runs:**
```bash
rm -f data/queue/pending/*.json
rm -f data/queue/failed/*.json
```
