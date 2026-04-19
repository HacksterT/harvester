import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from harvester.models import Finding
from harvester.writer import _build_labels, _format_issue_body, write_finding


def _finding(**kwargs) -> Finding:
    defaults = dict(
        title="Cache hit rate below threshold",
        summary="The cache hit rate is 18%, well below the 40% target.",
        evidence="7-day query returned: cache_read=1200, cache_creation=5500",
        criteria=["Cache hit rate > 40% after fix", "No regression in response quality"],
        domain="tokens",
        priority="should-have",
        scanner="tokens",
        repo="ezra-assistant",
        touches_guarded_paths=False,
        generated_at=datetime(2026, 4, 18, 2, 0, 0, tzinfo=UTC),
    )
    defaults.update(kwargs)
    return Finding(**defaults)


# ---------------------------------------------------------------------------
# _format_issue_body
# ---------------------------------------------------------------------------

def test_issue_body_contains_summary() -> None:
    f = _finding()
    body = _format_issue_body(f)
    assert f.summary in body


def test_issue_body_contains_evidence() -> None:
    f = _finding()
    body = _format_issue_body(f)
    assert f.evidence in body


def test_issue_body_contains_criteria_checkboxes() -> None:
    f = _finding()
    body = _format_issue_body(f)
    for criterion in f.criteria:
        assert f"- [ ] {criterion}" in body


def test_issue_body_contains_metadata_table() -> None:
    f = _finding()
    body = _format_issue_body(f)
    assert "ezra-assistant" in body
    assert "tokens" in body
    assert "should-have" in body


def test_issue_body_contains_generated_date() -> None:
    f = _finding()
    body = _format_issue_body(f)
    assert "2026-04-18" in body


# ---------------------------------------------------------------------------
# _build_labels
# ---------------------------------------------------------------------------

def test_labels_include_improvement_and_triage() -> None:
    labels = _build_labels(_finding())
    assert "improvement" in labels
    assert "status:triage" in labels


def test_labels_include_priority() -> None:
    labels = _build_labels(_finding(priority="must-have"))
    assert "priority:must-have" in labels


def test_labels_include_domain() -> None:
    labels = _build_labels(_finding(domain="memory"))
    assert "domain:memory" in labels


def test_labels_include_scanner() -> None:
    labels = _build_labels(_finding(scanner="skill_gaps"))
    assert "scanner:skill_gaps" in labels


def test_labels_include_theological_review_when_guarded() -> None:
    labels = _build_labels(_finding(touches_guarded_paths=True))
    assert "theological-review-required" in labels


def test_labels_no_theological_review_when_not_guarded() -> None:
    labels = _build_labels(_finding(touches_guarded_paths=False))
    assert "theological-review-required" not in labels


# ---------------------------------------------------------------------------
# write_finding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_finding_calls_create_issue() -> None:
    mock_gh = AsyncMock()
    mock_gh.create_issue.return_value = "https://github.com/HacksterT/ezra-assistant/issues/42"

    with tempfile.TemporaryDirectory() as d:
        url = await write_finding(_finding(), mock_gh, findings_dir=d)

    mock_gh.create_issue.assert_awaited_once()
    call_kwargs = mock_gh.create_issue.call_args.kwargs
    assert "[IMPROVEMENT]" in call_kwargs["title"]
    assert "Cache hit rate" in call_kwargs["title"]
    assert url == "https://github.com/HacksterT/ezra-assistant/issues/42"


@pytest.mark.asyncio
async def test_write_finding_logs_to_jsonl() -> None:
    mock_gh = AsyncMock()
    mock_gh.create_issue.return_value = "https://github.com/HacksterT/ezra-assistant/issues/7"

    with tempfile.TemporaryDirectory() as d:
        await write_finding(_finding(), mock_gh, findings_dir=d)
        jsonl_files = list(Path(d).glob("*.jsonl"))
        assert len(jsonl_files) == 1
        records = [json.loads(line) for line in jsonl_files[0].read_text().splitlines()]

    assert len(records) == 1
    assert records[0]["title"] == "Cache hit rate below threshold"
    assert records[0]["issue_url"] == "https://github.com/HacksterT/ezra-assistant/issues/7"


@pytest.mark.asyncio
async def test_write_finding_returns_issue_url() -> None:
    mock_gh = AsyncMock()
    expected_url = "https://github.com/HacksterT/ezra-assistant/issues/99"
    mock_gh.create_issue.return_value = expected_url

    with tempfile.TemporaryDirectory() as d:
        url = await write_finding(_finding(), mock_gh, findings_dir=d)

    assert url == expected_url


@pytest.mark.asyncio
async def test_write_finding_creates_findings_dir_if_missing() -> None:
    mock_gh = AsyncMock()
    mock_gh.create_issue.return_value = "https://github.com/x/y/issues/1"

    with tempfile.TemporaryDirectory() as d:
        nested = Path(d) / "data" / "findings"
        await write_finding(_finding(), mock_gh, findings_dir=nested)
        assert nested.exists()
