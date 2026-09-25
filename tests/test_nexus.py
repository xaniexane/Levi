"""NEXUS tests — hermetic, no network.

Covers the routing law: every envelope gets a receipt, no silent
drops, unknown organs dead-letter (never raise), TTL expiry
dead-letters, poison payloads rejected pre-route, journal round-trips
under a hermetic home, SI/ai separation, and bridge labeling.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from levi.nexus import Envelope, Nexus, Receipt
from levi.nexus.ai import BRIDGE_LABEL, adapt_chat_request, adapt_chat_response
from levi.nexus.ai.bridge import execute_tool, tool_schemas
from levi.nexus.envelope import MAX_PAYLOAD_BYTES, validate


@pytest.fixture()
def nexus(tmp_path):
    """Hermetic nexus: isolated home, journaling on."""
    return Nexus(home=tmp_path / "levi-home", journal=True)


def test_send_routed_receipt(nexus):
    nexus.register_organ("alpha")
    nexus.register_organ("beta")
    receipt = nexus.send("alpha", "beta", "ping", {"n": 1})
    assert isinstance(receipt, Receipt)
    assert receipt.status == "routed"
    assert receipt.organ == "beta"
    assert receipt.reason, "routed receipts still carry a reason"
    assert receipt.trace_id
    inbox = nexus.inbox("beta")
    assert len(inbox) == 1
    assert inbox[0].payload == {"n": 1}


def test_broadcast_one_receipt_per_organ(nexus):
    for organ in ("alpha", "beta", "gamma"):
        nexus.register_organ(organ)
    env = Envelope(
        from_organ="alpha", to_organ=None, kind="announce", payload={"msg": "hi"}
    )
    receipts = nexus.broadcast(env, exclude="alpha")
    assert {r.organ for r in receipts} == {"beta", "gamma"}
    assert all(r.status == "routed" for r in receipts)
    assert all(r.trace_id == env.trace_id for r in receipts)
    # distinct envelope ids per delivery
    assert len({r.envelope_id for r in receipts}) == 2


def test_unknown_organ_dead_letters_never_raises(nexus):
    nexus.register_organ("alpha")
    receipt = nexus.send("alpha", "no-such-organ", "ping", {})
    assert receipt.status == "dead-lettered"
    assert "unknown organ" in receipt.reason
    dead = nexus.dead_letters()
    assert len(dead) == 1
    assert "unknown organ" in dead[0]["reason"]


def test_ttl_expiry_dead_letters(nexus):
    nexus.register_organ("alpha")
    nexus.register_organ("beta")
    env = Envelope(
        from_organ="alpha",
        to_organ="beta",
        kind="stale",
        payload={},
        ttl=10.0,
        created_at=time.time() - 100.0,
    )
    assert env.expired()
    receipt = nexus.route(env)
    assert receipt.status == "dead-lettered"
    assert "TTL expired" in receipt.reason


def test_zero_ttl_expires_immediately(nexus):
    nexus.register_organ("alpha")
    nexus.register_organ("beta")
    receipt = nexus.send("alpha", "beta", "ping", {}, ttl=0.0)
    assert receipt.status == "dead-lettered"
    assert "TTL expired" in receipt.reason


def test_poison_non_dict_payload_rejected(nexus):
    nexus.register_organ("alpha")
    nexus.register_organ("beta")
    env = Envelope(from_organ="alpha", to_organ="beta", kind="x")
    env.payload = ["not", "a", "dict"]  # bypass dataclass typing on purpose
    receipt = nexus.route(env)
    assert receipt.status == "rejected"
    assert "poison payload" in receipt.reason
    assert nexus.inbox("beta") == []


def test_poison_absurd_size_rejected(nexus):
    nexus.register_organ("alpha")
    nexus.register_organ("beta")
    env = Envelope(
        from_organ="alpha",
        to_organ="beta",
        kind="x",
        payload={"blob": "x" * (MAX_PAYLOAD_BYTES + 1)},
    )
    assert validate(env) is not None
    receipt = nexus.route(env)
    assert receipt.status == "rejected"
    assert "exceeds" in receipt.reason


def test_no_silent_drop_invariant(nexus):
    """Every route/broadcast returns a Receipt with a status and a
    reason for anything that is not routed. Never an exception, never
    None, never silent."""
    nexus.register_organ("alpha")
    cases = [
        Envelope("alpha", "beta", "k", {}),  # unknown organ
        Envelope("alpha", "alpha", "k", {}),  # self-route ok
        Envelope("", "alpha", "k", {}),  # bad from
        Envelope("alpha", "alpha", "", {}),  # bad kind
        Envelope("alpha", "alpha", "k", {}, ttl=0.0),  # expired ttl
        Envelope("alpha", None, "k", {}),  # broadcast intent
    ]
    for env in cases:
        receipt = nexus.route(env)
        assert isinstance(receipt, Receipt)
        assert receipt.status in ("accepted", "routed", "rejected", "dead-lettered")
        if receipt.status in ("rejected", "dead-lettered"):
            assert receipt.reason, "non-delivery must carry a reason"
        assert receipt.envelope_id == env.id
        assert receipt.trace_id == env.trace_id
    # broadcast to an empty registry also returns receipts, not silence
    empty = Nexus(home=nexus.engine.home / "empty", journal=False)
    receipts = empty.broadcast(Envelope("x", None, "k", {}))
    assert len(receipts) == 1
    assert receipts[0].status == "dead-lettered"


def test_journal_round_trip_hermetic_home(tmp_path):
    home = tmp_path / "hermetic"
    nexus = Nexus(home=home, journal=True)
    nexus.register_organ("alpha")
    nexus.register_organ("beta")
    receipt = nexus.send("alpha", "beta", "ping", {"n": 7})
    journal_path = home / "nexus" / "journal.jsonl"
    assert journal_path.exists()
    entries = nexus.engine.read_journal()
    assert entries, "journal must record receipts"
    match = [
        e
        for e in entries
        if e.get("receipt", {}).get("envelope_id") == receipt.envelope_id
    ]
    assert match, "the routed receipt must be in the journal"
    assert match[0]["receipt"]["status"] == "routed"
    assert match[0]["envelope_kind"] == "ping"


def test_journal_disabled_writes_nothing(tmp_path):
    nexus = Nexus(home=tmp_path / "nohome", journal=False)
    nexus.register_organ("alpha")
    receipt = nexus.send("alpha", "alpha", "ping", {})
    assert receipt.status == "routed"
    assert not (tmp_path / "nohome" / "nexus").exists()


def test_levi_home_env_overrides_default(tmp_path, monkeypatch):
    from levi.nexus.si.engine import resolve_home

    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "envhome"))
    assert resolve_home() == tmp_path / "envhome"


def test_handler_failure_recorded_not_silent(nexus):
    def bad_handler(env):
        raise RuntimeError("organ blew up")

    nexus.register_organ("alpha")
    nexus.register_organ("beta", handler=bad_handler)
    receipt = nexus.send("alpha", "beta", "ping", {})
    assert receipt.status == "routed"  # delivery happened
    assert "RuntimeError" in receipt.detail  # failure recorded, not silent
    assert nexus.inbox("beta"), "envelope stays in the inbox"


def test_si_never_imports_ai():
    """The authoritative SI core must stand alone: importing it must
    not pull the ai bridge into sys.modules."""
    code = (
        "import sys; "
        "import levi.nexus.si; import levi.nexus.si.engine; "
        "import levi.nexus.envelope; import levi.nexus.bus; "
        "bad = [m for m in sys.modules if m.startswith('levi.nexus.ai')]; "
        "assert not bad, bad; print('si-clean')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "core"),
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert "si-clean" in proc.stdout


def test_bridge_labels():
    assert "AI counterpart bridge for nexus" in BRIDGE_LABEL
    assert "the SI core is authoritative" in BRIDGE_LABEL
    assert "this bridge claims nothing" in BRIDGE_LABEL
    import levi.nexus.ai.bridge as bridge_mod

    assert "AI counterpart bridge for nexus" in bridge_mod.__doc__


def test_tool_schemas_mcp_shaped():
    schemas = tool_schemas()
    names = {s["name"] for s in schemas}
    assert {
        "nexus_send",
        "nexus_broadcast",
        "nexus_organs",
        "nexus_dead_letters",
    } <= names
    for schema in schemas:
        assert schema["description"]
        assert isinstance(schema["inputSchema"], dict)
        assert schema["inputSchema"].get("type") == "object"
    send_schema = next(s for s in schemas if s["name"] == "nexus_send")
    assert "AI counterpart bridge" in send_schema["description"]


def test_execute_tool_delegates_to_si_core(nexus):
    nexus.register_organ("alpha")
    nexus.register_organ("beta")
    result = execute_tool(
        "nexus_send",
        {
            "from_organ": "alpha",
            "to_organ": "beta",
            "kind": "ping",
            "payload": {"n": 1},
        },
        nexus,
    )
    assert result["receipt"]["status"] == "routed"
    assert "bridge" in result
    assert execute_tool("nexus_organs", {}, nexus)["organs"] == ["alpha", "beta"]
    with pytest.raises(ValueError):
        execute_tool("nope", {}, nexus)


def test_adapt_chat_request_and_response(nexus):
    nexus.register_organ("beta")
    env = adapt_chat_request(
        {
            "model": "whatever-claims-nothing",
            "messages": [{"role": "user", "content": "hello"}],
            "to_organ": "beta",
            "kind": "chat.request",
        }
    )
    assert isinstance(env, Envelope)
    assert env.to_organ == "beta"
    assert env.payload["messages"][0]["content"] == "hello"
    receipt = nexus.route(env)
    shaped = adapt_chat_response(receipt, env)
    assert shaped["object"] == "chat.completion"
    content = shaped["choices"][0]["message"]["content"]
    assert "routed" in content
    assert "bridge" in shaped


def test_adapt_chat_response_dead_letter_honest(nexus):
    nexus.register_organ("alpha")
    env = adapt_chat_request({"messages": [], "to_organ": "ghost"})
    receipt = nexus.route(env)
    assert receipt.status == "dead-lettered"
    shaped = adapt_chat_response(receipt, env)
    content = shaped["choices"][0]["message"]["content"]
    assert "dead-lettered" in content
    assert "unknown organ" in content


def test_envelope_round_trip():
    env = Envelope(from_organ="a", to_organ="b", kind="k", payload={"x": 1})
    env2 = Envelope.from_dict(env.to_dict())
    assert env2.from_organ == "a" and env2.payload == {"x": 1}
    assert env2.id == env.id and env2.trace_id == env.trace_id
    r = Receipt(
        status="routed",
        envelope_id=env.id,
        trace_id=env.trace_id,
        organ="b",
        reason="ok",
    )
    r2 = Receipt.from_dict(json.loads(json.dumps(r.to_dict())))
    assert r2.status == "routed" and r2.ok()
