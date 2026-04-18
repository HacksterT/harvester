# Harvester

A self-improving code maintenance service for personal repositories. Harvester runs on your Mac, watches your repos on a schedule, surfaces improvement opportunities as GitHub issues, and executes approved changes overnight via Claude Code — producing draft PRs for morning review.

The loop is the [Karpathy autoresearch](https://github.com/karpathy/autoresearch) pattern applied to code improvement: a scanner identifies a change worth trying, a GitHub issue records the hypothesis, applying the `agent-ready` label dispatches the overnight agent, and you merge or close the PR the next morning. Repeat indefinitely.

---

## How It Works

```
scanner runs → finding → GitHub issue created → you triage (30 seconds)
  → apply agent-ready label → overnight agent implements → draft PR
  → you review (2-5 minutes) → merge or close → repeat
```

Two human decisions. Everything else is automatic.

---

## Design Principles

- **Cron daemon, not a platform.** One FastAPI server, one asyncio scheduler, one bash script. No agent framework, no vector store, no graph execution engine.
- **Configuration is a file.** All behavior is defined in `harvester-config.yaml`. Editing the YAML is how you change behavior.
- **Scanners are importable modules.** Each scanner is a Python module implementing one async function. Testable in isolation, no plugin discovery.
- **Human gates are sacred.** Triage (apply `agent-ready`) and PR review are the only mandatory human steps and cannot be configured away.
- **Reversibility over speed.** Every automated action is undoable. Issues can be closed. PRs can be rejected. Merges can be reverted.

---

## Architecture

```
Harvester Service (your Mac)
├── Config loader          harvester-config.yaml → RepoConfig[]
├── Scanner scheduler      asyncio loop, per-(repo, scanner) cadence
├── Scanners               importable modules, pure async functions
├── GitHub client          PyGithub wrapper, issue + label + PR management
├── Webhook handler        receives signed GitHub events, drives queue
├── Directory queue        JSON files in data/queue/{pending,completed,failed,rejected}/
├── Agent runner           bash script, invoked by launchd at 02:00
└── Web UI                 Jinja templates at localhost:8500
```

The agent runner invokes Claude Code with subscription authentication (no API key required). Each overnight run gets a fresh git workspace, a 30-minute budget, and a task file combining the GitHub issue body with the repo's `CLAUDE.md`.

---

## Requirements

- macOS (launchd for scheduling)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Claude Code CLI with active Claude.ai subscription
- GitHub CLI (`gh`) authenticated
- Cloudflare Tunnel (for webhook delivery — existing infrastructure or set up via [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/))
- xAI API key (Grok, for scanner LLM calls)
- Telegram bot token (for notifications)

---

## Quick Start

```bash
# Install dependencies
uv sync

# Validate your config
python -m harvester validate

# Start the service
python -m harvester serve

# Run a scanner on demand
python -m harvester scan <repo-name> <scanner-name>

# Check queue state
python -m harvester queue list
```

---

## Configuration

Edit `harvester-config.yaml` to define which repos to watch and which scanners to run:

```yaml
global:
  webhook_port: 8500
  agent_run_time: "02:00"
  claude_code_auth: subscription

repos:
  - name: my-repo
    github: username/my-repo
    local_path: ~/Projects/my-repo
    claude_md_path: CLAUDE.md
    scanners:
      - name: code_health
        cadence_days: 7
      - name: dependency_freshness
        cadence_days: 30
```

Adding a new repo: append an entry and restart Harvester. Config validation runs on startup.

---

## Available Scanners

| Scanner | What it finds | Applies to |
|---|---|---|
| `code_health` | Oversized files, high complexity, stale TODOs, type hint gaps | Any Python repo |
| `dependency_freshness` | Unpinned or stale dependencies | Any repo with a lock file |
| `test_coverage` | Coverage gaps by module | Any repo with a test suite |
| `skill_gaps` | Conversation vs. skill inventory gaps | LLM agent repos |
| `memory` | Memory system metrics and coverage | Ezra-compatible memory systems |
| `tokens` | LLM spend and cache hit rate | Any repo with LLM API usage |
| `theology_review` | Theological content consistency | Selah and ministry repos |
| `cross_repo_patterns` | Patterns across all repos (self-annealing) | Meta — runs monthly |

---

## Onboarding a New Repo

See [`docs/onboarding-guide.md`](docs/onboarding-guide.md) for the full assessment and configuration process. Adding a repo to Harvester requires a structured assessment, a `CLAUDE.md` in the target repo, a `harvester-config.yaml` entry, and one-time GitHub setup (webhook, branch protection, labels).

---

## Documentation

| Document | Purpose |
|---|---|
| [`docs/onboarding-guide.md`](docs/onboarding-guide.md) | How to onboard a new repo |
| [`docs/scanner-contract.md`](docs/scanner-contract.md) | How to write a new scanner |
| [`docs/selah-guardrails.md`](docs/selah-guardrails.md) | Theological content safety design |
| [`docs/operational-runbook.md`](docs/operational-runbook.md) | Common operations and failure recovery |
| [`docs/ezra-technical-guide.md`](docs/ezra-technical-guide.md) | Architecture reference for Ezra-dispatched agents |
| [`tasks/F01-harvester-core.md`](tasks/F01-harvester-core.md) | Core feature canvas |
| [`tasks/F02-harvester-completion.md`](tasks/F02-harvester-completion.md) | Expansion feature canvas |

---

## License

MIT — see [LICENSE](LICENSE).

---

*Built by [HacksterT](https://github.com/hackstert). Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch).*
