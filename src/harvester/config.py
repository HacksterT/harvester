import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator


class ConfigLoadError(Exception):
    pass


class ScannerConfig(BaseModel):
    name: str
    cadence_days: int

    @field_validator("cadence_days")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be a positive integer")
        return v


class RepoConfig(BaseModel):
    name: str
    github: str
    local_path: str
    claude_md_path: str = "CLAUDE.md"
    scanners: list[ScannerConfig]
    label_prefix: str = "improvement"
    priority_labels: list[str] = Field(default_factory=lambda: ["must-have", "should-have", "nice-to-have"])
    guarded_paths: list[str] = Field(default_factory=list)
    guarded_path_policy: str = "never_execute"
    branch_prefix: str = "improvement/"
    draft_pr_default: bool = True


class GlobalSettings(BaseModel):
    queue_path: str = "data/queue"
    state_path: str = "data/harvester-state.json"
    workspaces_path: str = "~/agent-workspaces"
    findings_log_path: str = "data/findings"
    run_logs_path: str = "data/logs"
    default_max_turns: int = 50
    default_timeout_minutes: int = 30
    scheduler_tick_seconds: int = 3600
    agent_run_time: str = "02:00"
    telegram_chat_id: str
    webhook_port: int = 8500
    claude_code_auth: str = "subscription"


class HarvesterConfig(BaseModel):
    settings: GlobalSettings
    repos: list[RepoConfig]


_ENV_VAR_RE = re.compile(r"\$\{(\w+)\}")


def _expand_env_vars(obj: object) -> object:
    if isinstance(obj, str):
        return _ENV_VAR_RE.sub(lambda m: os.environ.get(m.group(1), m.group(0)), obj)
    if isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_vars(v) for v in obj]
    return obj


def load_config(path: str | Path) -> HarvesterConfig:
    p = Path(path)
    try:
        raw = p.read_text()
    except FileNotFoundError:
        raise ConfigLoadError(f"Config file not found: {path}")

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigLoadError(f"YAML parse error in {path}: {exc}")

    if not isinstance(data, dict):
        raise ConfigLoadError(f"{path} must be a YAML mapping at the top level")

    data = _expand_env_vars(data)

    global_data = data.get("global", {})
    repos_data = data.get("repos")

    if repos_data is None:
        raise ConfigLoadError("repos: section is missing from config")

    try:
        settings = GlobalSettings.model_validate(global_data)
    except ValidationError as exc:
        raise ConfigLoadError(_format_error("global", exc))

    try:
        repos = [RepoConfig.model_validate(r) for r in repos_data]
    except ValidationError as exc:
        raise ConfigLoadError(_format_error("repos", exc))

    return HarvesterConfig(settings=settings, repos=repos)


def _format_error(section: str, exc: ValidationError) -> str:
    lines = ["Configuration error:"]
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        lines.append(f"  {section}.{loc}: {err['msg']}")
    return "\n".join(lines)
