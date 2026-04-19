from harvester.scanners import skill_gaps
from harvester.tools import _TOOL_FACTORIES


VALID_TOOL_NAMES = set(_TOOL_FACTORIES.keys())


def test_system_prompt_non_empty() -> None:
    assert isinstance(skill_gaps.SYSTEM_PROMPT, str)
    assert len(skill_gaps.SYSTEM_PROMPT.strip()) > 50


def test_enabled_tools_is_list() -> None:
    assert isinstance(skill_gaps.ENABLED_TOOLS, list)
    assert len(skill_gaps.ENABLED_TOOLS) > 0


def test_enabled_tools_are_valid_names() -> None:
    for name in skill_gaps.ENABLED_TOOLS:
        assert name in VALID_TOOL_NAMES, f"{name!r} is not a known tool"


def test_system_prompt_mentions_report_finding() -> None:
    assert "report_finding" in skill_gaps.SYSTEM_PROMPT


def test_system_prompt_mentions_domain() -> None:
    assert "skill-gaps" in skill_gaps.SYSTEM_PROMPT or "skill_gaps" in skill_gaps.SYSTEM_PROMPT


def test_system_prompt_includes_no_finding_guidance() -> None:
    prompt = skill_gaps.SYSTEM_PROMPT.lower()
    assert "do not call" in prompt or "do not" in prompt or "if there is no" in prompt
