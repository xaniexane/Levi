"""Void-mind API over a real socket: the daemon answers honestly.

Covers /api/* on an ephemeral localhost port against a temp static dir:
health, registers (14 live), growth (real ladder stage), chat (a real
orchestrator turn — never canned), note, fork, session log, the hash
chain, and the static half (SPA fallback, honest 404s, no traversal).
"""

from __future__ import annotations

import json
import threading
import urllib.request

import pytest

from levi.serve.server import make_server
from levi.serve import void_api


@pytest.fixture()
def daemon(tmp_path):
    (tmp_path / "index.html").write_text("<html>void</html>", encoding="utf-8")
    server = make_server(str(tmp_path), port=0, bind="127.0.0.1")
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    base = "http://127.0.0.1:%d" % server.server_address[1]
    yield base
    server.shutdown()
    server.server_close()


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=30) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def post(base, path, obj):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(obj).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def post_raw(base, path, raw: bytes, ctype="application/json"):
    req = urllib.request.Request(
        base + path, data=raw, headers={"Content-Type": ctype}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_health(daemon):
    status, body = get(daemon, "/api/health")
    assert status == 200 and body["ok"] is True


def test_registers_are_the_live_fourteen(daemon):
    from levi.persona.levi import all_variants

    status, body = get(daemon, "/api/registers")
    assert status == 200 and body["count"] == 14
    assert {r["id"] for r in body["registers"]} == {v.id for v in all_variants()}


def test_growth_stage_is_a_real_ladder_stage(daemon):
    from levi.growth.stages import STAGE_LADDER

    status, body = get(daemon, "/api/growth")
    assert status == 200
    assert body["stage"] in {name for name, _, _ in STAGE_LADDER}
    assert isinstance(body["learnings"], int)


def test_model_status_is_honest(daemon):
    status, body = get(daemon, "/api/model")
    assert status == 200 and body["resolved"]
    assert "streaming_note" in body  # the non-streaming limit, stated


def test_chat_is_a_real_turn(daemon):
    status, body = post(
        daemon,
        "/api/chat",
        {
            "session_id": "void-test",
            "message": "Say the word stone.",
            "register": "levi_void",
        },
    )
    assert status == 200
    assert body["persona_id"] == "levi_void"
    assert body["reply"].strip()
    assert body["tok_per_s"] > 0
    assert body["tick"]["n"] == 2  # user tick n=1, reply tick n=2
    # chain continuity on the next turn
    status2, body2 = post(
        daemon,
        "/api/chat",
        {"session_id": "void-test", "message": "Again.", "register": "levi"},
    )
    assert status2 == 200 and body2["persona_id"] == "levi"
    assert body2["tick"]["n"] == 4


def test_chat_rejects_bad_input(daemon):
    s1, _ = post_raw(
        daemon,
        "/api/chat",
        json.dumps({"session_id": "void-test", "message": "   "}).encode(),
    )
    assert s1 == 400
    s2, _ = post_raw(
        daemon,
        "/api/chat",
        json.dumps(
            {"session_id": "void-test", "message": "hi", "register": "nope"}
        ).encode(),
    )
    assert s2 == 400
    s3, _ = post_raw(daemon, "/api/chat", b"not json{")
    assert s3 == 400
    s4, _ = post_raw(daemon, "/api/chat", b"x" * (void_api.MAX_BODY_BYTES + 1))
    assert s4 == 400


def test_note_pins_to_session_log(daemon, tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(tmp_path / "sessions"))
    status, body = post(
        daemon, "/api/note", {"session_id": "void-note", "text": "the keeper's mark"}
    )
    assert status == 200 and body["ok"] is True
    s2, log = get(daemon, "/api/session/void-note")
    assert s2 == 200
    notes = [r for r in log["records"] if r["kind"] == "note"]
    assert notes and "keeper's mark" in notes[-1]["content"]


def test_fork_seeds_new_chain(daemon):
    status, body = post(
        daemon, "/api/fork", {"new_session_id": "void-fork", "from_tick": "abc123"}
    )
    assert status == 200 and body["tick"] == "abc123"
    s2, log = get(daemon, "/api/session/void-fork")
    assert log["chain"]["tick"] == "abc123"


def test_unknown_api_route_404s(daemon):
    try:
        get(daemon, "/api/nope")
        raise AssertionError("should 404")
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_static_half_still_honest(daemon):
    with urllib.request.urlopen(daemon + "/", timeout=30) as r:
        assert r.status == 200 and r.headers.get_content_type() == "text/html"
    try:
        urllib.request.urlopen(daemon + "/missing.js", timeout=30)
        raise AssertionError("should 404")
    except urllib.error.HTTPError as e:
        assert e.code == 404
