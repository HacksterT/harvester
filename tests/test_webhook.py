import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from harvester.main import app

client = TestClient(app, raise_server_exceptions=False)


def _sign(body: bytes, secret: str = "test-secret") -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _post(payload: dict, secret: str = "test-secret", signature: str | None = None) -> any:
    body = json.dumps(payload).encode()
    sig = signature if signature is not None else _sign(body, secret)
    return client.post(
        "/webhook",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "test-delivery-id",
            "Content-Type": "application/json",
        },
    )


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def test_valid_signature_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    resp = _post({"action": "opened"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_invalid_signature_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    resp = _post({"action": "opened"}, signature="sha256=deadbeef")
    assert resp.status_code == 401


def test_missing_signature_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    body = json.dumps({"action": "opened"}).encode()
    resp = client.post(
        "/webhook",
        content=body,
        headers={"X-GitHub-Event": "issues", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


def test_wrong_secret_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "real-secret")
    resp = _post({"action": "opened"}, secret="wrong-secret")
    assert resp.status_code == 401


def test_missing_env_secret_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    resp = _post({"action": "opened"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Payload handling
# ---------------------------------------------------------------------------

def test_malformed_json_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    body = b"{not valid json"
    sig = _sign(body)
    resp = client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": sig, "X-GitHub-Event": "issues", "Content-Type": "application/json"},
    )
    assert resp.status_code == 400


def test_known_event_dispatched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    payload = {
        "action": "labeled",
        "issue": {"number": 99},
        "label": {"name": "agent-ready"},
        "repository": {"full_name": "owner/repo"},
    }
    resp = _post(payload)
    assert resp.status_code == 200


def test_unknown_event_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    resp = _post({"action": "ping"})
    assert resp.status_code == 200
