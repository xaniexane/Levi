"""Tests for the GitHub connector (blueprint §5.4).

Hermetic: every transport is a fake — either an injected callable or a
monkeypatched ``urllib.request.urlopen`` that captures the real
``urllib`` Request object. No live call to api.github.com is ever made
here (no credential exists in this environment anyway).
"""

import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from levi.plugins import github as gh
from levi.plugins.github import GitHubConnector
from levi.plugins.registry import ConnectorAPIError, list_connectors

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "ghp_faketoken_for_tests_only"


class _FakeTransport:
    def __init__(self, payload=None, error=None):
        self.calls = []
        self.payload = payload if payload is not None else {}
        self.error = error

    def __call__(self, method, path, token, body):
        self.calls.append(
            {"method": method, "path": path, "token": token, "body": body}
        )
        if self.error is not None:
            raise self.error
        return self.payload


@pytest.fixture()
def conn():
    return GitHubConnector()


@pytest.fixture()
def with_token(monkeypatch):
    monkeypatch.setenv("LEVI_GITHUB_TOKEN", TOKEN)
    return TOKEN


@pytest.fixture()
def no_token(monkeypatch):
    monkeypatch.delenv("LEVI_GITHUB_TOKEN", raising=False)


# -- contract surface -------------------------------------------------------


def test_credential_env_var_name(conn):
    assert conn.credential_env_var == "LEVI_GITHUB_TOKEN"


def test_declares_read_and_write_capabilities(conn):
    names = {c.name: c.write for c in conn.capabilities}
    assert names["read.user"] is False
    assert names["read.repo"] is False
    assert names["write.issue"] is True
    assert names["write.comment"] is True


def test_requires_confirmation_is_forced(conn):
    # §1.5: write-capable connectors confirm writes, no exceptions.
    assert conn.requires_confirmation is True


def test_registered_in_plugin_registry():
    assert "github" in {c.id for c in list_connectors()}


# -- honest missing credential ----------------------------------------------


def test_whoami_without_token_is_honest(conn, no_token):
    fake = _FakeTransport()
    res = conn.execute("whoami", transport=fake)
    assert not res.ok
    assert res.status == "missing_credential"
    assert res.message.startswith("missing credential: set LEVI_GITHUB_TOKEN")
    assert not res.request_made
    assert fake.calls == [], "no network may happen without a credential"


# -- reads via fake transport ------------------------------------------------


def test_whoami_returns_authenticated_user(conn, with_token):
    fake = _FakeTransport({"login": "octocat", "name": "monalisa octocat", "id": 1})
    res = conn.execute("whoami", transport=fake)
    assert res.ok and res.status == "ok" and res.request_made
    assert res.data["login"] == "octocat"
    call = fake.calls[0]
    assert (call["method"], call["path"]) == ("GET", "/user")
    assert call["token"] == TOKEN


def test_get_repo_builds_path_from_validated_slugs(conn, with_token):
    fake = _FakeTransport(
        {
            "full_name": "octocat/hello-world",
            "description": "demo",
            "private": False,
            "stargazers_count": 42,
            "default_branch": "main",
        }
    )
    res = conn.execute(
        "get_repo", {"owner": "octocat", "repo": "hello-world"}, transport=fake
    )
    assert res.ok
    assert fake.calls[0]["path"] == "/repos/octocat/hello-world"
    assert res.data["stars"] == 42


def test_path_injection_is_rejected_before_transport(conn, with_token):
    fake = _FakeTransport()
    res = conn.execute("get_repo", {"owner": "../evil", "repo": "x"}, transport=fake)
    assert not res.ok
    assert res.status == "invalid_params"
    assert fake.calls == []


def test_missing_params_are_rejected(conn, with_token):
    fake = _FakeTransport()
    res = conn.execute("get_repo", {"owner": "octocat"}, transport=fake)
    assert not res.ok
    assert res.status == "invalid_params"
    assert "repo" in res.message
    assert fake.calls == []


# -- writes gated ------------------------------------------------------------


def test_create_issue_without_confirm_sends_nothing(conn, with_token):
    fake = _FakeTransport()
    res = conn.execute(
        "create_issue",
        {"owner": "o", "repo": "r", "title": "hello"},
        transport=fake,
    )
    assert not res.ok
    assert res.status == "confirmation_required"
    assert fake.calls == []


def test_create_issue_with_confirm_posts(conn, with_token):
    fake = _FakeTransport(
        {"number": 7, "html_url": "https://github.com/o/r/issues/7", "state": "open"}
    )
    res = conn.execute(
        "create_issue",
        {"owner": "o", "repo": "r", "title": "hello", "body": "world"},
        confirm=True,
        transport=fake,
    )
    assert res.ok and res.request_made
    call = fake.calls[0]
    assert call["method"] == "POST"
    assert call["path"] == "/repos/o/r/issues"
    assert call["body"]["title"] == "hello"
    assert res.data["number"] == 7


def test_create_comment_with_confirm_posts(conn, with_token):
    fake = _FakeTransport({"id": 99, "html_url": "https://github.com/o/r/x#c99"})
    res = conn.execute(
        "create_comment",
        {"owner": "o", "repo": "r", "issue_number": "3", "body": "nice"},
        confirm=True,
        transport=fake,
    )
    assert res.ok
    assert fake.calls[0]["path"] == "/repos/o/r/issues/3/comments"


# -- honest API errors, token never leaks ------------------------------------


def test_api_error_is_honest_and_never_contains_token(conn, with_token):
    fake = _FakeTransport(error=ConnectorAPIError("GitHub API error 404: Not Found"))
    res = conn.execute("get_repo", {"owner": "o", "repo": "r"}, transport=fake)
    assert not res.ok
    assert res.status == "api_error"
    assert "404" in res.message
    assert TOKEN not in res.message
    assert TOKEN not in json.dumps(res.data or {})


def test_token_never_appears_in_any_failure_message(conn, with_token):
    fake = _FakeTransport(
        error=ConnectorAPIError("GitHub API error 401: Bad credentials")
    )
    for kwargs in (
        {"operation": "whoami"},
        {
            "operation": "create_issue",
            "params": {"owner": "o", "repo": "r", "title": "t"},
            "confirm": True,
        },
    ):
        res = conn.execute(transport=fake, **kwargs)
        assert TOKEN not in res.message, kwargs


# -- the real stdlib transport, captured without network ---------------------


class _FakeHTTPResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_real_urllib_transport_sends_bearer_header(conn, monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return _FakeHTTPResponse(b'{"login": "octocat"}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    payload = conn._call_api("GET", "/user", TOKEN)
    assert payload == {"login": "octocat"}
    assert captured["url"] == "https://api.github.com/user"
    assert captured["method"] == "GET"
    headers = {k.lower(): v for k, v in captured["headers"].items()}
    assert headers["authorization"] == f"Bearer {TOKEN}"
    assert headers["accept"] == "application/vnd.github+json"
    assert "levi-plugin" in headers["user-agent"]
    assert captured["timeout"] == gh.TIMEOUT_SECONDS


def test_real_urllib_transport_posts_json_body(conn, monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["data"] = request.data
        captured["headers"] = dict(request.header_items())
        return _FakeHTTPResponse(b'{"number": 1}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    conn._call_api("POST", "/repos/o/r/issues", TOKEN, {"title": "t"})
    body = json.loads(captured["data"].decode("utf-8"))
    assert body == {"title": "t"}
    headers = {k.lower(): v for k, v in captured["headers"].items()}
    assert headers["content-type"] == "application/json"


def test_http_error_becomes_connector_api_error_without_token(conn, monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url,
            403,
            "Forbidden",
            {},
            io.BytesIO(b'{"message": "API rate limit exceeded"}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ConnectorAPIError) as excinfo:
        conn._call_api("GET", "/user", TOKEN)
    message = str(excinfo.value)
    assert "403" in message and "API rate limit exceeded" in message
    assert TOKEN not in message


# -- CLI end to end (subprocess; still no network) ----------------------------


def _cli(*argv):
    env = dict(os.environ)
    env.pop("LEVI_GITHUB_TOKEN", None)  # guarantee the honest path
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "core"), *sys.path])
    return subprocess.run(
        [sys.executable, "-m", "levi.cli.main", *argv],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_cli_plugin_list_shows_github():
    proc = _cli("plugin", "list")
    assert proc.returncode == 0, proc.stderr
    assert "github" in proc.stdout
    assert "LEVI_GITHUB_TOKEN" in proc.stdout


def test_cli_plugin_exec_without_token_is_honest():
    proc = _cli("plugin", "exec", "github", "whoami")
    assert proc.returncode == 2, proc.stdout
    assert "missing credential: set LEVI_GITHUB_TOKEN" in proc.stdout


def test_cli_plugin_exec_unknown_connector():
    proc = _cli("plugin", "exec", "nope", "whoami")
    assert proc.returncode == 2
    assert "Unknown connector" in proc.stdout
