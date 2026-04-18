import tempfile
from pathlib import Path

import pytest

from harvester.config import ConfigLoadError, HarvesterConfig, load_config

VALID_YAML = """
global:
  queue_path: data/queue
  state_path: data/harvester-state.json
  workspaces_path: ~/agent-workspaces
  findings_log_path: data/findings
  run_logs_path: data/logs
  telegram_chat_id: "12345"
  webhook_port: 8500

repos:
  - name: test-repo
    github: HacksterT/test-repo
    local_path: ~/Projects/test-repo
    scanners:
      - name: skill_gaps
        cadence_days: 9
      - name: code_health
        cadence_days: 14
"""


def _write(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


def test_valid_config_loads() -> None:
    cfg = load_config(_write(VALID_YAML))
    assert isinstance(cfg, HarvesterConfig)
    assert len(cfg.repos) == 1
    assert cfg.repos[0].name == "test-repo"
    assert cfg.repos[0].github == "HacksterT/test-repo"
    assert len(cfg.repos[0].scanners) == 2
    assert cfg.settings.webhook_port == 8500


def test_scanner_cadence_values() -> None:
    cfg = load_config(_write(VALID_YAML))
    assert cfg.repos[0].scanners[0].cadence_days == 9
    assert cfg.repos[0].scanners[1].cadence_days == 14


def test_missing_github_field_raises() -> None:
    bad = VALID_YAML.replace("    github: HacksterT/test-repo\n", "")
    with pytest.raises(ConfigLoadError) as exc_info:
        load_config(_write(bad))
    assert "github" in str(exc_info.value)


def test_negative_cadence_rejected() -> None:
    bad = VALID_YAML.replace("cadence_days: 9", "cadence_days: -1")
    with pytest.raises(ConfigLoadError) as exc_info:
        load_config(_write(bad))
    assert "cadence_days" in str(exc_info.value)


def test_zero_cadence_rejected() -> None:
    bad = VALID_YAML.replace("cadence_days: 9", "cadence_days: 0")
    with pytest.raises(ConfigLoadError) as exc_info:
        load_config(_write(bad))
    assert "cadence_days" in str(exc_info.value)


def test_missing_repos_section_raises() -> None:
    yaml = "global:\n  queue_path: data/queue\n  telegram_chat_id: '123'\n"
    with pytest.raises(ConfigLoadError) as exc_info:
        load_config(_write(yaml))
    assert "repos" in str(exc_info.value)


def test_malformed_yaml_raises() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_config(_write("global:\n  queue_path: [unclosed"))
    assert "YAML" in str(exc_info.value)


def test_file_not_found_raises() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_config("/nonexistent/path/config.yaml")
    assert "not found" in str(exc_info.value)


def test_env_var_expansion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_CHAT_ID", "99999")
    yaml = VALID_YAML.replace('telegram_chat_id: "12345"', "telegram_chat_id: ${TEST_CHAT_ID}")
    cfg = load_config(_write(yaml))
    assert cfg.settings.telegram_chat_id == "99999"


def test_error_message_is_human_readable() -> None:
    bad = VALID_YAML.replace("cadence_days: 9", "cadence_days: -5")
    try:
        load_config(_write(bad))
        pytest.fail("Expected ConfigLoadError")
    except ConfigLoadError as exc:
        msg = str(exc)
        assert "Configuration error" in msg
        assert "cadence_days" in msg
        assert "ValidationError" not in msg
