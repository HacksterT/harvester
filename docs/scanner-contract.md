# Scanner Contract

A scanner is a Python module that tells Harvester what to look for in a repository and which tools to use. The framework handles all API calls, tool execution, issue creation, and queue management. Scanners contain only configuration.

---

## Module Structure

Every scanner module must define two module-level constants:

```python
# src/harvester/scanners/my_scanner.py

SYSTEM_PROMPT: str = """
You are auditing ... (detailed instructions for Claude)

Call report_finding with: ...
If no finding this cycle, do NOT call report_finding. End naturally.
"""

ENABLED_TOOLS: list[str] = ["read_file", "query_sqlite"]
```

That is the entire contract. No classes, no functions, no imports required.

---

## How the Framework Runs a Scanner

`scanner_runner.run_scanner(scanner_module, repo_config, context)`:

1. Instantiates `AsyncAnthropic()` (reads `ANTHROPIC_API_KEY` from environment)
2. Calls `build_tools(scanner_module.ENABLED_TOOLS, repo_config.local_path)` to get the enabled tool set, scoped to the repo's local checkout
3. Creates the `report_finding` tool as a closure that captures the result
4. Passes the system prompt with `cache_control: {"type": "ephemeral"}` for prompt caching
5. Calls `client.beta.messages.tool_runner()` with model `claude-sonnet-4-6`, max_tokens 4096
6. Awaits `runner.until_done()` — Claude iterates through tools autonomously
7. Returns the `Finding` if `report_finding` was called, or `None` if Claude reached `end_turn` without reporting

---

## Tool Library Reference

Tools available to scanners via `ENABLED_TOOLS`. All filesystem paths are relative to the repo's `local_path` and are sandboxed — paths that escape the repo root are rejected.

| Tool | Description | Notes |
|---|---|---|
| `read_file` | Read a file. Returns text, capped at 10,000 chars. | path relative to repo root |
| `query_sqlite` | Run a SELECT query against a SQLite database. Returns JSON rows (max 200). | SELECT-only enforced |
| `run_command` | Run a static analysis command. | Allowlist: `ruff`, `mypy`, `radon`, `coverage`, `git` |
| `list_directory` | List files and directories at path. | path relative to repo root |
| `read_git_log` | Read the N most recent git log entries. | default 20, max 100 |

`report_finding` is always included — it is not listed in `ENABLED_TOOLS`.

---

## The `report_finding` Tool

`report_finding` is the only structured output path. Claude must call it to produce a finding. Its parameters map exactly to the `Finding` dataclass:

| Parameter | Type | Description |
|---|---|---|
| `title` | str | Concise name for the finding (used as GitHub issue title suffix) |
| `summary` | str | What the problem is and why it matters |
| `evidence` | str | Specific data, file paths, query results, or patterns |
| `criteria` | list[str] | 2-4 measurable acceptance criteria for a PR |
| `domain` | str | One of: `skill-gaps`, `memory`, `tokens`, `code-health`, `theology`, `patterns` |
| `priority` | str | One of: `must-have`, `should-have`, `nice-to-have` |
| `scanner` | str | The scanner module name (e.g. `skill_gaps`) |
| `repo` | str | The repo name as passed at scan start |
| `touches_guarded_paths` | bool | True if the fix would touch a guarded path (triggers theological review label) |

When Claude calls `report_finding`, the framework records the finding and returns `"Finding recorded. Scan complete."` — Claude naturally stops.

---

## Writing a Scanner

### 1. Create the module

```python
# src/harvester/scanners/my_scanner.py

SYSTEM_PROMPT = """
You are auditing the Ezra assistant for <what you're looking for>.

Steps:
1. <specific exploration steps using the tools>
2. <what to look for>
3. <how to decide if it's worth reporting>

Call report_finding with:
- title: ...
- summary: ...
- evidence: specific data from your queries
- criteria: 2-4 measurable acceptance criteria
- domain: "<domain>"
- priority: <based on impact>
- scanner: "my_scanner"
- repo: the repo name passed at scan start
- touches_guarded_paths: <true/false>

If no clear finding exists this cycle, do NOT call report_finding. End naturally.
"""

ENABLED_TOOLS = ["query_sqlite", "read_file"]
```

### 2. Add tests

```python
# tests/scanners/test_my_scanner.py

from harvester.scanners import my_scanner
from harvester.tools import _TOOL_FACTORIES

VALID_TOOL_NAMES = set(_TOOL_FACTORIES.keys())

def test_system_prompt_non_empty():
    assert len(my_scanner.SYSTEM_PROMPT.strip()) > 50

def test_enabled_tools_valid():
    for name in my_scanner.ENABLED_TOOLS:
        assert name in VALID_TOOL_NAMES

def test_system_prompt_mentions_report_finding():
    assert "report_finding" in my_scanner.SYSTEM_PROMPT
```

### 3. Register in config

Add the scanner to `harvester-config.yaml` under the appropriate repo:

```yaml
repos:
  - name: ezra-assistant
    github: HacksterT/ezra-assistant
    local_path: ~/Projects/ezra-assistant
    scanners:
      - name: my_scanner
        cadence_days: 7
```

The `name` must match the Python module name (`src/harvester/scanners/<name>.py`).

---

## Writing Effective System Prompts

**Be specific about what to read.** Claude cannot guess database schemas or file structures — tell it exactly where to look and what queries to run.

**One finding per scan.** Instruct Claude to identify the single most actionable improvement. Multiple findings in one call dilute quality.

**Include the no-finding case.** Always tell Claude when NOT to call `report_finding`. Scanners that always report something produce noise.

**Match domain to label.** The `domain` field determines which GitHub label is applied. Use exact domain names from the label taxonomy.

**Include the `repo` field.** Remind Claude to use the repo name from the scan invocation, not a hardcoded string. The prompt template passes it in the user message.

---

## Guarded Paths

If a finding's fix would touch paths in the repo's `guarded_paths` list (configured in `harvester-config.yaml`), set `touches_guarded_paths: True`. The framework will:

- Apply the `theological-review-required` label to the GitHub issue
- Refuse to enqueue the issue for overnight execution if the repo policy is `never_execute`

For Ezra, `theology/**` is a guarded path. Selah adds additional guarded paths. When in doubt, set `touches_guarded_paths: True` — a false positive causes a label; a false negative could trigger an unauthorized agent run on sensitive content.

---

## Auth and Cost

Scanners use the Anthropic REST API via `ANTHROPIC_API_KEY` and consume API credits. The overnight agent runner uses the Claude Code CLI subscription — these are separate auth mechanisms with separate billing.

Each scanner invocation is one conversation with Claude. Prompt caching is enabled on the system prompt (the longest, most stable part of the context). A typical scan costs $0.01-$0.10 depending on how many tools Claude calls.
