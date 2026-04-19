import json
import shlex
import sqlite3
import subprocess
from pathlib import Path

from anthropic import beta_async_tool

ALLOWED_COMMANDS = {"ruff", "mypy", "radon", "coverage", "git"}
_MAX_FILE_BYTES = 10_000


def _safe_path(root: Path, rel: str) -> Path | None:
    """Return absolute path if it is inside root, else None."""
    full = (root / rel).resolve()
    if str(full).startswith(str(root)):
        return full
    return None


# ---------------------------------------------------------------------------
# Per-scan tool factories — each returns a beta_async_tool-decorated function
# scoped to `root`.
# ---------------------------------------------------------------------------

def _make_read_file(root: Path):
    async def read_file(path: str) -> str:
        """Read a file from the target repository. path is relative to repo root."""
        full = _safe_path(root, path)
        if full is None:
            return f"Error: path {path!r} escapes repository root"
        if not full.exists():
            return f"Error: file not found: {path}"
        try:
            text = full.read_text(errors="replace")
            if len(text) > _MAX_FILE_BYTES:
                text = text[:_MAX_FILE_BYTES] + f"\n... (truncated at {_MAX_FILE_BYTES} chars)"
            return text
        except Exception as exc:
            return f"Error reading {path}: {exc}"

    return beta_async_tool(read_file)


def _make_query_sqlite(root: Path):
    async def query_sqlite(db_path: str, sql: str) -> str:
        """Run a read-only SELECT query against a SQLite database. db_path is relative to repo root."""
        if not sql.strip().upper().startswith("SELECT"):
            return "Error: only SELECT queries are permitted"
        full = _safe_path(root, db_path)
        if full is None:
            return f"Error: db_path {db_path!r} escapes repository root"
        if not full.exists():
            return f"Error: database not found: {db_path}"
        try:
            with sqlite3.connect(f"file:{full}?mode=ro", uri=True) as conn:
                conn.row_factory = sqlite3.Row
                rows = [dict(row) for row in conn.execute(sql).fetchmany(200)]
            return json.dumps(rows, default=str)
        except sqlite3.Error as exc:
            return f"Error: {exc}"

    return beta_async_tool(query_sqlite)


def _make_run_command(root: Path):
    async def run_command(command: str) -> str:
        """Run a static analysis command. Allowed executables: ruff, mypy, radon, coverage, git."""
        try:
            parts = shlex.split(command)
        except ValueError as exc:
            return f"Error parsing command: {exc}"
        if not parts:
            return "Error: empty command"
        exe = Path(parts[0]).name
        if exe not in ALLOWED_COMMANDS:
            return f"Error: {exe!r} is not in the allowed command list: {sorted(ALLOWED_COMMANDS)}"
        try:
            result = subprocess.run(
                parts,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = result.stdout + result.stderr
            if len(output) > _MAX_FILE_BYTES:
                output = output[:_MAX_FILE_BYTES] + "\n... (truncated)"
            return output or "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: command timed out after 60 seconds"
        except Exception as exc:
            return f"Error: {exc}"

    return beta_async_tool(run_command)


def _make_list_directory(root: Path):
    async def list_directory(path: str = ".") -> str:
        """List files and directories at path. path is relative to repo root."""
        full = _safe_path(root, path)
        if full is None:
            return f"Error: path {path!r} escapes repository root"
        if not full.exists():
            return f"Error: path not found: {path}"
        if not full.is_dir():
            return f"Error: {path!r} is not a directory"
        entries = sorted(full.iterdir(), key=lambda p: (p.is_file(), p.name))
        lines = []
        for entry in entries[:200]:
            indicator = "/" if entry.is_dir() else ""
            lines.append(f"{entry.name}{indicator}")
        return "\n".join(lines) or "(empty directory)"

    return beta_async_tool(list_directory)


def _make_read_git_log(root: Path):
    async def read_git_log(n: int = 20) -> str:
        """Read the n most recent git log entries from the repository. Defaults to 20."""
        n = min(max(1, n), 100)
        try:
            result = subprocess.run(
                ["git", "log", f"-{n}", "--oneline", "--no-decorate"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=15,
            )
            return result.stdout.strip() or "(no commits)"
        except Exception as exc:
            return f"Error: {exc}"

    return beta_async_tool(read_git_log)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_TOOL_FACTORIES = {
    "read_file": _make_read_file,
    "query_sqlite": _make_query_sqlite,
    "run_command": _make_run_command,
    "list_directory": _make_list_directory,
    "read_git_log": _make_read_git_log,
}


def build_tools(enabled: list[str], local_path: str | Path) -> list:
    """Return beta_async_tool instances for the named tools, scoped to local_path."""
    root = Path(local_path).expanduser().resolve()
    return [_TOOL_FACTORIES[name](root) for name in enabled if name in _TOOL_FACTORIES]
