from harvester.scanners import memory
from harvester.tools import _TOOL_FACTORIES


VALID_TOOL_NAMES = set(_TOOL_FACTORIES.keys())


def test_system_prompt_non_empty() -> None:
    assert isinstance(memory.SYSTEM_PROMPT, str)
    assert len(memory.SYSTEM_PROMPT.strip()) > 50


def test_enabled_tools_is_list() -> None:
    assert isinstance(memory.ENABLED_TOOLS, list)
    assert len(memory.ENABLED_TOOLS) > 0


def test_enabled_tools_are_valid_names() -> None:
    for name in memory.ENABLED_TOOLS:
        assert name in VALID_TOOL_NAMES, f"{name!r} is not a known tool"


def test_system_prompt_mentions_report_finding() -> None:
    assert "report_finding" in memory.SYSTEM_PROMPT


def test_system_prompt_mentions_domain() -> None:
    assert "memory" in memory.SYSTEM_PROMPT.lower()


def test_system_prompt_includes_no_finding_guidance() -> None:
    prompt = memory.SYSTEM_PROMPT.lower()
    assert "do not call" in prompt or "do not" in prompt or "if" in prompt
