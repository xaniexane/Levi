"""Hermetic tests for levi.agent.server (the HTTP front door).

Starts the real stdlib ``ThreadingHTTPServer`` machinery on an ephemeral
port in a thread; traffic stays on loopback. ``LEVI_AGENT_TOKEN`` is a
monkeypatched dummy, never a real secret.
"""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from levi.agent import server as agent_server
from levi.agent.loop import AgentTranscript

TOKEN = "test-token-not-a-real-secret"


@pytest.fixture()
def srv(monkeypatch):
    monkeypatch.setenv("LEVI_AGENT_TOKEN", TOKEN)
    monkeypatch.setattr(agent_server._AgentHandler, "token", TOKEN)
    http_srv = ThreadingHTTPServer(("127.0.0.1", 0), agent_server._AgentHandler)
    thread = threading.Thread(target=http_srv.serve_forever, daemon=True)
    thread.start()
    yield http_srv
    http_srv.shutdown()
    http_srv.server_close()


def _base(srv):
    return "http://127.0.0.1:%d" % srv.server_address[1]


def _request(srv, path, method="GET", body=None, token=None):
    req = urllib.request.Request(_base(srv) + path, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if token is not None:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _json_body(obj):
    return json.dumps(obj).encode("utf-8")


# -- /healthz ----------------------------------------------------------------


def test_healthz_open_without_token(srv):
    status, payload = _request(srv, "/healthz")
    assert status == 200
    assert payload["status"] == "ok"


# -- /v1/tools auth ------------------------------------------------------------


def test_tools_401_without_token(srv):
    status, payload = _request(srv, "/v1/tools")
    assert status == 401
    assert payload["error"] == "unauthorized"


def test_tools_401_with_wrong_token(srv):
    status, _ = _request(srv, "/v1/tools", token="wrong-token")
    assert status == 401


def test_tools_200_with_correct_token(srv):
    status, payload = _request(srv, "/v1/tools", token=TOKEN)
    assert status == 200
    tools = payload["tools"]
    assert len(tools) > 0
    names = {t["name"] for t in tools}
    assert "file_write" in names and "shell_exec" in names
    # every tool descriptor carries its confirmation flag
    for t in tools:
        assert "requires_confirmation" in t
    gated = {t["name"] for t in tools if t["requires_confirmation"]}
    assert "file_write" in gated and "file_read" not in gated


# -- /v1/agent/run -------------------------------------------------------------


def _patch_run(monkeypatch):
    """Swap the loop entry point the server module imports at request time."""
    import levi.agent.loop as agent_loop

    seen = {}

    def _fake_run(task, **kwargs):
        seen.update(task=task, kwargs=kwargs)
        return AgentTranscript(
            task=task, provider_name="fake", steps=[],
            final="fake run complete", ok=True,
        )

    monkeypatch.setattr(agent_loop, "run_subtask", _fake_run)
    return seen


def test_agent_run_drives_the_loop(srv, monkeypatch):
    seen = _patch_run(monkeypatch)
    status, payload = _request(
        srv, "/v1/agent/run", method="POST",
        body=_json_body({"task": "do the thing", "max_steps": 5}),
        token=TOKEN,
    )
    assert status == 200
    transcript = payload["transcript"]
    assert transcript["final"] == "fake run complete"
    assert transcript["ok"] is True
    # non-interactive by construction: confirm is None
    assert seen["task"] == "do the thing"
    assert seen["kwargs"]["max_steps"] == 5
    assert seen["kwargs"]["consent"] is False
    assert seen["kwargs"]["confirm"] is None


def test_agent_run_401_without_token(srv, monkeypatch):
    _patch_run(monkeypatch)
    status, _ = _request(
        srv, "/v1/agent/run", method="POST",
        body=_json_body({"task": "do the thing"}),
    )
    assert status == 401


def test_agent_run_missing_task_400(srv, monkeypatch):
    _patch_run(monkeypatch)
    status, payload = _request(
        srv, "/v1/agent/run", method="POST",
        body=_json_body({}), token=TOKEN,
    )
    assert status == 400
    assert "task" in payload["error"]


def test_agent_run_body_too_large_413(srv, monkeypatch):
    _patch_run(monkeypatch)
    status, payload = _request(
        srv, "/v1/agent/run", method="POST",
        body=b"x" * (agent_server.MAX_BODY_BYTES + 1), token=TOKEN,
    )
    assert status == 413
    assert "too large" in payload["error"]


def test_agent_run_max_steps_capped(srv, monkeypatch):
    seen = _patch_run(monkeypatch)
    status, _ = _request(
        srv, "/v1/agent/run", method="POST",
        body=_json_body({"task": "x", "max_steps": 9999}), token=TOKEN,
    )
    assert status == 200
    assert seen["kwargs"]["max_steps"] == agent_server.MAX_STEPS_CAP


# -- routing -------------------------------------------------------------------


def test_unknown_paths_404(srv):
    status, _ = _request(srv, "/nope", token=TOKEN)
    assert status == 404
    status, _ = _request(srv, "/nope", method="POST", token=TOKEN)
    assert status == 404


# -- serve() gate ----------------------------------------------------------------


def test_serve_refuses_without_token(monkeypatch, capsys):
    monkeypatch.delenv("LEVI_AGENT_TOKEN", raising=False)
    with pytest.raises(SystemExit) as exc:
        agent_server.serve(host="127.0.0.1", port=0)
    assert exc.value.code == 2
    assert "LEVI_AGENT_TOKEN" in capsys.readouterr().err


# -- /v1/agent/chat ------------------------------------------------------------


def _patch_chat(monkeypatch):
    """Swap ConversationManager for a fake that records the call."""
    import levi.agent.chat as agent_chat

    seen = {}

    class _FakeManager:
        def __init__(self, session_name, **kwargs):
            seen.update(session_name=session_name, kwargs=kwargs)

        def turn(self, message, **kwargs):
            seen.update(message=message, turn_kwargs=kwargs)
            return agent_chat.TurnResult(
                transcript=AgentTranscript(
                    task=message, provider_name="fake", steps=[],
                    final="fake chat reply", ok=True,
                ),
                context_pct=0.12,
                compressed=False,
                summary=None,
            )

    monkeypatch.setattr(agent_chat, "ConversationManager", _FakeManager)
    return seen


def test_agent_chat_drives_a_turn(srv, monkeypatch):
    seen = _patch_chat(monkeypatch)
    status, payload = _request(
        srv, "/v1/agent/chat", method="POST",
        body=_json_body({"session_id": "s1", "message": "hello there",
                         "max_steps": 4}),
        token=TOKEN,
    )
    assert status == 200
    assert payload["session_id"] == "s1"
    assert payload["transcript"]["final"] == "fake chat reply"
    assert payload["context_pct"] == 0.12
    assert payload["compressed"] is False
    assert seen["session_name"] == "s1"
    assert seen["message"] == "hello there"
    # same non-interactive discipline as /v1/agent/run
    assert seen["kwargs"]["confirm"] is None
    assert seen["kwargs"]["consent"] is False
    assert seen["kwargs"]["max_steps"] == 4


def test_agent_chat_401_without_token(srv, monkeypatch):
    _patch_chat(monkeypatch)
    status, _ = _request(
        srv, "/v1/agent/chat", method="POST",
        body=_json_body({"session_id": "s1", "message": "hi"}),
    )
    assert status == 401


def test_agent_chat_401_with_wrong_token(srv, monkeypatch):
    _patch_chat(monkeypatch)
    status, _ = _request(
        srv, "/v1/agent/chat", method="POST",
        body=_json_body({"session_id": "s1", "message": "hi"}),
        token="wrong-token",
    )
    assert status == 401


def test_agent_chat_missing_fields_400(srv, monkeypatch):
    _patch_chat(monkeypatch)
    status, payload = _request(
        srv, "/v1/agent/chat", method="POST",
        body=_json_body({"message": "hi"}), token=TOKEN,
    )
    assert status == 400
    assert "session_id" in payload["error"]
    status, payload = _request(
        srv, "/v1/agent/chat", method="POST",
        body=_json_body({"session_id": "s1"}), token=TOKEN,
    )
    assert status == 400
    assert "message" in payload["error"]


def test_agent_chat_bad_session_id_400(srv, monkeypatch):
    _patch_chat(monkeypatch)
    status, payload = _request(
        srv, "/v1/agent/chat", method="POST",
        body=_json_body({"session_id": "../../etc", "message": "hi"}),
        token=TOKEN,
    )
    assert status == 400
    assert "invalid session id" in payload["error"]


def test_agent_chat_turns_accumulate_in_one_session(srv, monkeypatch, tmp_path):
    """End-to-end through the real ConversationManager with LEVI_PROVIDER=local."""
    monkeypatch.setenv("LEVI_PROVIDER", "local")
    monkeypatch.setenv("LEVI_MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(tmp_path / "sessions"))
    status, payload = _request(
        srv, "/v1/agent/chat", method="POST",
        body=_json_body({"session_id": "e2e", "message": "remember the sky is green"}),
        token=TOKEN,
    )
    assert status == 200
    assert payload["transcript"]["ok"] is True
    session_file = tmp_path / "sessions" / "e2e.jsonl"
    assert session_file.exists()
    assert "remember the sky is green" in session_file.read_text()
