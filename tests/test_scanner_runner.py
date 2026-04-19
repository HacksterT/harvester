"""
Tests for scanner_runner.run_scanner.

Strategy: mock AsyncAnthropic and the tool_runner it returns. Capture the tools
list passed to tool_runner, then invoke the report_finding closure directly to
simulate Claude calling it — confirming the Finding is constructed and returned.
"""
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harvester.models import Finding, ScanContext
from harvester.scanner_runner import run_scanner


def _make_repo_config(name="ezra-assistant", local_path="/tmp/ezra"):
    cfg = MagicMock()
    cfg.name = name
    cfg.local_path = local_path
    return cfg


def _make_scanner_module(enabled_tools=None):
    mod = types.SimpleNamespace(
        SYSTEM_PROMPT="You are a test scanner.",
        ENABLED_TOOLS=enabled_tools or [],
        __name__="test_scanner",
    )
    return mod


def _make_context():
    return ScanContext(run_id="test-run-001")


# ---------------------------------------------------------------------------
# Helper to extract the report_finding tool from the captured tools list
# ---------------------------------------------------------------------------

def _get_report_finding_tool(tools: list):
    for t in tools:
        if hasattr(t, "name") and t.name == "report_finding":
            return t
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returns_none_when_no_finding_reported() -> None:
    """When Claude calls no tools (end_turn), run_scanner returns None."""
    mock_runner = AsyncMock()
    mock_runner.until_done = AsyncMock(return_value=None)

    mock_client = MagicMock()
    mock_client.beta.messages.tool_runner.return_value = mock_runner

    with patch("harvester.scanner_runner.AsyncAnthropic", return_value=mock_client):
        result = await run_scanner(
            _make_scanner_module(), _make_repo_config(), _make_context()
        )

    assert result is None


@pytest.mark.asyncio
async def test_returns_finding_when_report_finding_called() -> None:
    """When report_finding is called during the loop, its Finding is returned."""
    captured_tools: list = []

    async def fake_until_done():
        rf = _get_report_finding_tool(captured_tools)
        assert rf is not None, "report_finding tool not in tools list"
        await rf.func(
            title="Test gap",
            summary="Ezra cannot answer medication questions",
            evidence="5 conversations with no useful response",
            criteria=["Add medication module", "Test with 10 sample queries"],
            domain="skill-gaps",
            priority="should-have",
            scanner="skill_gaps",
            repo="ezra-assistant",
        )

    mock_runner = MagicMock()
    mock_runner.until_done = fake_until_done

    def fake_tool_runner(**kwargs):
        captured_tools.extend(kwargs["tools"])
        return mock_runner

    mock_client = MagicMock()
    mock_client.beta.messages.tool_runner = fake_tool_runner

    with patch("harvester.scanner_runner.AsyncAnthropic", return_value=mock_client):
        result = await run_scanner(
            _make_scanner_module(), _make_repo_config(), _make_context()
        )

    assert isinstance(result, Finding)
    assert result.title == "Test gap"
    assert result.scanner == "skill_gaps"
    assert result.repo == "ezra-assistant"
    assert result.domain == "skill-gaps"
    assert result.priority == "should-have"
    assert result.touches_guarded_paths is False


@pytest.mark.asyncio
async def test_finding_touches_guarded_paths_flag() -> None:
    captured_tools: list = []

    async def fake_until_done():
        rf = _get_report_finding_tool(captured_tools)
        await rf.func(
            title="Theology gap",
            summary="Needs update",
            evidence="Evidence",
            criteria=["Fix it"],
            domain="theology",
            priority="must-have",
            scanner="skill_gaps",
            repo="ezra-assistant",
            touches_guarded_paths=True,
        )

    mock_runner = MagicMock()
    mock_runner.until_done = fake_until_done

    def fake_tool_runner(**kwargs):
        captured_tools.extend(kwargs["tools"])
        return mock_runner

    mock_client = MagicMock()
    mock_client.beta.messages.tool_runner = fake_tool_runner

    with patch("harvester.scanner_runner.AsyncAnthropic", return_value=mock_client):
        result = await run_scanner(
            _make_scanner_module(), _make_repo_config(), _make_context()
        )

    assert result is not None
    assert result.touches_guarded_paths is True


@pytest.mark.asyncio
async def test_tool_runner_receives_system_prompt_with_cache_control() -> None:
    """System prompt is passed as a list with cache_control ephemeral block."""
    call_kwargs: dict = {}

    async def fake_until_done():
        pass

    mock_runner = MagicMock()
    mock_runner.until_done = fake_until_done

    def fake_tool_runner(**kwargs):
        call_kwargs.update(kwargs)
        return mock_runner

    mock_client = MagicMock()
    mock_client.beta.messages.tool_runner = fake_tool_runner

    scanner = _make_scanner_module()

    with patch("harvester.scanner_runner.AsyncAnthropic", return_value=mock_client):
        await run_scanner(scanner, _make_repo_config(), _make_context())

    system = call_kwargs["system"]
    assert isinstance(system, list)
    assert len(system) == 1
    assert system[0]["type"] == "text"
    assert system[0]["text"] == scanner.SYSTEM_PROMPT
    assert system[0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_tool_runner_receives_correct_model() -> None:
    call_kwargs: dict = {}

    async def fake_until_done():
        pass

    mock_runner = MagicMock()
    mock_runner.until_done = fake_until_done

    def fake_tool_runner(**kwargs):
        call_kwargs.update(kwargs)
        return mock_runner

    mock_client = MagicMock()
    mock_client.beta.messages.tool_runner = fake_tool_runner

    with patch("harvester.scanner_runner.AsyncAnthropic", return_value=mock_client):
        await run_scanner(
            _make_scanner_module(), _make_repo_config(), _make_context()
        )

    assert call_kwargs["model"] == "claude-sonnet-4-6"
    assert call_kwargs["max_tokens"] == 4096


@pytest.mark.asyncio
async def test_report_finding_tool_always_included() -> None:
    """report_finding must be in tools even if ENABLED_TOOLS is empty."""
    captured_tools: list = []

    async def fake_until_done():
        pass

    mock_runner = MagicMock()
    mock_runner.until_done = fake_until_done

    def fake_tool_runner(**kwargs):
        captured_tools.extend(kwargs["tools"])
        return mock_runner

    mock_client = MagicMock()
    mock_client.beta.messages.tool_runner = fake_tool_runner

    with patch("harvester.scanner_runner.AsyncAnthropic", return_value=mock_client):
        await run_scanner(
            _make_scanner_module(enabled_tools=[]),
            _make_repo_config(),
            _make_context(),
        )

    tool_names = [t.name for t in captured_tools if hasattr(t, "name")]
    assert "report_finding" in tool_names


@pytest.mark.asyncio
async def test_enabled_tools_subset_included() -> None:
    """Only tools named in ENABLED_TOOLS (plus report_finding) are passed."""
    captured_tools: list = []

    async def fake_until_done():
        pass

    mock_runner = MagicMock()
    mock_runner.until_done = fake_until_done

    def fake_tool_runner(**kwargs):
        captured_tools.extend(kwargs["tools"])
        return mock_runner

    mock_client = MagicMock()
    mock_client.beta.messages.tool_runner = fake_tool_runner

    with patch("harvester.scanner_runner.AsyncAnthropic", return_value=mock_client):
        await run_scanner(
            _make_scanner_module(enabled_tools=["read_file", "list_directory"]),
            _make_repo_config(),
            _make_context(),
        )

    tool_names = {t.name for t in captured_tools if hasattr(t, "name")}
    assert "read_file" in tool_names
    assert "list_directory" in tool_names
    assert "report_finding" in tool_names
    assert "query_sqlite" not in tool_names
    assert "run_command" not in tool_names
