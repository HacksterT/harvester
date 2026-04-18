from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from github import GithubException

from harvester.github_client import GitHubClient, LABEL_TAXONOMY


def _make_client() -> GitHubClient:
    client = GitHubClient(token="fake-token", repo_full_name="owner/repo")
    return client


def _mock_repo(client: GitHubClient) -> MagicMock:
    repo = MagicMock()
    client._gh_repo = repo
    return repo


# ---------------------------------------------------------------------------
# create_issue
# ---------------------------------------------------------------------------

async def test_create_issue_returns_url() -> None:
    client = _make_client()
    repo = _mock_repo(client)
    issue = MagicMock()
    issue.number = 42
    issue.html_url = "https://github.com/owner/repo/issues/42"
    repo.create_issue.return_value = issue

    url = await client.create_issue("Test title", "Test body", ["improvement"])

    assert url == "https://github.com/owner/repo/issues/42"
    repo.create_issue.assert_called_once_with(
        title="Test title", body="Test body", labels=["improvement"]
    )


# ---------------------------------------------------------------------------
# get_issue / close_issue / comment / apply_labels
# ---------------------------------------------------------------------------

async def test_close_issue_calls_edit() -> None:
    client = _make_client()
    repo = _mock_repo(client)
    issue = MagicMock()
    repo.get_issue.return_value = issue

    await client.close_issue(7)

    repo.get_issue.assert_called_once_with(7)
    issue.edit.assert_called_once_with(state="closed")


async def test_comment_on_issue() -> None:
    client = _make_client()
    repo = _mock_repo(client)
    issue = MagicMock()
    repo.get_issue.return_value = issue

    await client.comment_on_issue(3, "hello")

    issue.create_comment.assert_called_once_with("hello")


async def test_apply_labels() -> None:
    client = _make_client()
    repo = _mock_repo(client)
    issue = MagicMock()
    repo.get_issue.return_value = issue

    await client.apply_labels(5, ["agent-ready", "improvement"])

    issue.set_labels.assert_called_once_with("agent-ready", "improvement")


# ---------------------------------------------------------------------------
# Rate limit backoff
# ---------------------------------------------------------------------------

async def test_rate_limit_retries_then_succeeds() -> None:
    client = _make_client()
    repo = _mock_repo(client)
    issue = MagicMock()
    issue.number = 1
    issue.html_url = "https://github.com/owner/repo/issues/1"

    call_count = 0

    def create_issue_side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise GithubException(429, {"message": "rate limit"}, {})
        return issue

    repo.create_issue.side_effect = create_issue_side_effect

    with patch("harvester.github_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        url = await client.create_issue("T", "B", [])

    assert url == "https://github.com/owner/repo/issues/1"
    assert mock_sleep.call_count == 2


async def test_rate_limit_exhausted_raises() -> None:
    client = _make_client()
    repo = _mock_repo(client)
    repo.create_issue.side_effect = GithubException(429, {"message": "rate limit"}, {})

    with patch("harvester.github_client.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(RuntimeError, match="rate limit exceeded"):
            await client.create_issue("T", "B", [])


async def test_non_429_exception_propagates() -> None:
    client = _make_client()
    repo = _mock_repo(client)
    repo.create_issue.side_effect = GithubException(404, {"message": "not found"}, {})

    with pytest.raises(GithubException) as exc_info:
        await client.create_issue("T", "B", [])
    assert exc_info.value.status == 404


# ---------------------------------------------------------------------------
# ensure_labels_exist
# ---------------------------------------------------------------------------

async def test_ensure_labels_creates_missing() -> None:
    client = _make_client()
    repo = _mock_repo(client)

    existing_label = MagicMock()
    existing_label.name = "improvement"
    repo.get_labels.return_value = [existing_label]

    await client.ensure_labels_exist()

    created_names = {call.kwargs["name"] for call in repo.create_label.call_args_list}
    assert "improvement" not in created_names
    assert len(created_names) == len(LABEL_TAXONOMY) - 1


async def test_ensure_labels_idempotent_on_422() -> None:
    client = _make_client()
    repo = _mock_repo(client)
    repo.get_labels.return_value = []
    repo.create_label.side_effect = GithubException(422, {"message": "already exists"}, {})

    # Should not raise — 422 treated as success
    await client.ensure_labels_exist()


async def test_ensure_labels_raises_on_non_422() -> None:
    client = _make_client()
    repo = _mock_repo(client)
    repo.get_labels.return_value = []
    repo.create_label.side_effect = GithubException(500, {"message": "server error"}, {})

    with pytest.raises(GithubException) as exc_info:
        await client.ensure_labels_exist()
    assert exc_info.value.status == 500
