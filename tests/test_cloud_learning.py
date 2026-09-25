"""Tests for cross-user growth learning (cloud sessions → distillation).

Covers: cloud harvest with consent gating (per-key opt-out, kill
switch, unknown tails), the redaction gate (secrets/PII never reach
memory or the journal), technique distillation heuristics
(good-outcome distills, bad-outcome/LEVI-source distills nothing),
exclusion of cloud content from the model reflector, and the
turn-meta provenance records. All hermetic: sessions, cloud dir,
growth dir, and memory store are pointed at tmp_path.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from levi.cloud import apikeys
from levi.growth import cycle as growth_cycle
from levi.growth import journal as growth_journal
from levi.growth.experience import Experience
from levi.growth import harvest_cloud as hc
from levi.growth.redact import redact_cloud_experiences, redact_text
from levi.growth.reflect import reflect, reflect_cloud
from levi.memory.store import MemoryStore

# NOTE: `levi.growth.__init__` re-exports the *function* `reflect`, so a
# plain `from levi.growth import reflect` would not give the module.
# import_module() returns the real submodule from sys.modules.
reflect_mod = importlib.import_module("levi.growth.reflect")


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def env(tmp_path, monkeypatch):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    cloud = tmp_path / "cloud"
    growth = tmp_path / "growth"
    mem = tmp_path / "memory"
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(sessions))
    monkeypatch.setenv("LEVI_CLOUD_DIR", str(cloud))
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(growth))
    monkeypatch.setenv("LEVI_GROWTH_CLOUD_LEARN", "1")
    return {
        "sessions": sessions,
        "cloud": cloud,
        "growth": growth,
        "mem": mem,
        "store": MemoryStore(data_dir=mem),
    }


def _tail_for(rec: dict) -> str:
    prefix = str(rec.get("prefix", ""))
    return "".join(c for c in prefix if c.isalnum())[-8:]


def _make_key(name="alice", **kw):
    raw, rec = apikeys.create_key(name, **kw)
    return raw, rec


def _write_cloud_session(
    sessions: Path, tail: str, name: str, records: list[dict]
) -> Path:
    p = sessions / f"cloud_{tail}_{name}.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return p


def _good_session(provider="openai") -> list[dict]:
    return [
        {
            "kind": "message",
            "role": "user",
            "ts": "2026-09-15T10:00:00Z",
            "content": "Research the best lightweight stargazing telescopes.",
        },
        {
            "kind": "turn-meta",
            "ts": "2026-09-15T10:00:10Z",
            "provider": provider,
            "ok": True,
            "steps": 3,
        },
        {
            "kind": "message",
            "role": "assistant",
            "ts": "2026-09-15T10:00:11Z",
            "content": "ZEBRA-UNIQUE-PHRASE-77 searching now.",
        },
        {
            "kind": "message",
            "role": "tool",
            "name": "web_search",
            "ts": "2026-09-15T10:00:12Z",
            "content": "results: 3 telescopes",
        },
        {
            "kind": "message",
            "role": "tool",
            "name": "web_search",
            "ts": "2026-09-15T10:00:13Z",
            "content": "results: prices compared",
        },
        {
            "kind": "message",
            "role": "assistant",
            "ts": "2026-09-15T10:00:14Z",
            "content": "Here is the comparison table you asked for.",
        },
        {
            "kind": "message",
            "role": "user",
            "ts": "2026-09-15T10:01:00Z",
            "content": "Perfect, thanks — exactly what I needed!",
        },
    ]


# ---------------------------------------------------------------------------
# harvest + consent
# ---------------------------------------------------------------------------


def test_cloud_harvest_tags_key_and_provider(env):
    _, rec = _make_key("alice")
    tail = _tail_for(rec)
    _write_cloud_session(env["sessions"], tail, "demo", _good_session())
    exps, marks = hc.harvest_cloud_sessions()
    assert exps, "expected cloud experiences"
    assert all(e.meta.get("origin") == "cloud" for e in exps)
    assert all(e.meta.get("key_name") == "alice" for e in exps)
    assert any(e.meta.get("provider") == "openai" for e in exps)
    assert any(k.startswith("cloud:cloud_") for k in marks)
    # idempotent via watermark
    exps2, _ = hc.harvest_cloud_sessions(since=marks)
    assert exps2 == []


def test_opted_out_key_is_skipped_entirely(env):
    _, rec = _make_key("bob", learn=False)
    tail = _tail_for(rec)
    _write_cloud_session(env["sessions"], tail, "demo", _good_session())
    exps, _ = hc.harvest_cloud_sessions()
    assert exps == []


def test_kill_switch_disables_cloud_harvest(env, monkeypatch):
    _, rec = _make_key("alice")
    tail = _tail_for(rec)
    _write_cloud_session(env["sessions"], tail, "demo", _good_session())
    monkeypatch.setenv("LEVI_GROWTH_CLOUD_LEARN", "0")
    assert not hc.cloud_learn_enabled()
    exps, _ = hc.harvest_cloud_sessions()
    assert exps == []


def test_unknown_tail_is_skipped(env):
    _write_cloud_session(env["sessions"], "deadbeef", "demo", _good_session())
    exps, _ = hc.harvest_cloud_sessions()
    assert exps == []


def test_apikey_learn_toggle(env):
    _, rec = _make_key("carol")
    assert rec.get("learn", True) is True
    out = apikeys.set_learn("carol", False)
    assert out["learn"] is False
    out = apikeys.set_learn("carol", True)
    assert out["learn"] is True
    names = {k["name"]: k.get("learn", True) for k in apikeys.list_keys()}
    assert names["carol"] is True


# ---------------------------------------------------------------------------
# redaction gate
# ---------------------------------------------------------------------------


def test_redaction_scrubs_secrets_and_pii():
    dirty = (
        "contact me at jane@example.com or 555-123-4567, "
        "key levi_sk_abcDEF123456, password=hunter2, "
        "card 4111111111111111"
    )
    clean = redact_text(dirty)
    for secret in (
        "jane@example.com",
        "555-123-4567",
        "levi_sk_abcDEF123456",
        "hunter2",
        "4111111111111111",
    ):
        assert secret not in clean, secret


def test_redact_cloud_experiences_generalizes_user_speech(env):
    exps = [
        Experience(
            id="1",
            kind="user-said",
            source="cloud:alice",
            ts="2026-09-15T10:00:00Z",
            content="My email is jane@example.com and password=hunter2 please help",
            meta={"origin": "cloud"},
        ),
        Experience(
            id="2",
            kind="levi-did",
            source="cloud:alice",
            ts="2026-09-15T10:00:01Z",
            content="[tool web_search] results ok",
            meta={"origin": "cloud"},
        ),
    ]
    out = redact_cloud_experiences(exps)
    assert all(e.meta.get("redacted") is True for e in out)
    joined = " ".join(e.content for e in out)
    assert "jane@example.com" not in joined
    assert "hunter2" not in joined
    # structure survives: tool marker still present
    assert "[tool web_search]" in joined


# ---------------------------------------------------------------------------
# distillation heuristics
# ---------------------------------------------------------------------------


def test_good_outcome_distills_technique_tagged_with_source(env):
    _, rec = _make_key("alice")
    tail = _tail_for(rec)
    _write_cloud_session(env["sessions"], tail, "demo", _good_session("openai"))
    exps, _ = hc.harvest_cloud_sessions()
    redacted = redact_cloud_experiences(exps)
    learnings = reflect_cloud(redacted)
    assert len(learnings) == 1
    learning = learnings[0]
    assert learning.kind == "procedural"
    assert learning.provenance.get("learned_from") == "openai"
    assert learning.provenance.get("source") == "cloud:alice"
    # technique only — the source model's verbatim output must not be stored
    assert "ZEBRA-UNIQUE-PHRASE-77" not in learning.content
    assert "web_search" in learning.content


def test_bad_outcome_distills_nothing(env):
    _, rec = _make_key("alice")
    tail = _tail_for(rec)
    records = _good_session("openai")
    records[-1] = {
        "kind": "message",
        "role": "user",
        "ts": "2026-09-15T10:01:00Z",
        "content": "No, that's wrong — I meant something else entirely.",
    }
    _write_cloud_session(env["sessions"], tail, "demo", records)
    exps, _ = hc.harvest_cloud_sessions()
    assert reflect_cloud(redact_cloud_experiences(exps)) == []


def test_levi_own_source_distills_nothing(env):
    _, rec = _make_key("alice")
    tail = _tail_for(rec)
    _write_cloud_session(env["sessions"], tail, "demo", _good_session("levi-brain"))
    exps, _ = hc.harvest_cloud_sessions()
    assert reflect_cloud(redact_cloud_experiences(exps)) == []


def test_cloud_never_reaches_model_reflector(env, monkeypatch):
    seen: list = []

    def _stub(experiences):
        seen.append(list(experiences))
        raise RuntimeError("no provider in test")

    monkeypatch.setattr(reflect_mod, "_reflect_model", _stub)
    cloud_exp = Experience(
        id="c1",
        kind="levi-did",
        source="cloud:alice",
        ts="2026-09-15T10:00:00Z",
        content="did a thing",
        meta={"origin": "cloud"},
    )
    local_exp = Experience(
        id="l1",
        kind="user-said",
        source="default",
        ts="2026-09-15T10:00:00Z",
        content="Please remember that I prefer dark mode.",
        meta={"origin": "local"},
    )
    learnings, mode = reflect([cloud_exp, local_exp], use_model=True)
    assert mode == "rules"  # stub raised → honest fallback
    assert seen and all(
        e.meta.get("origin") != "cloud" for batch in seen for e in batch
    ), "cloud content must never be passed to the model reflector"


# ---------------------------------------------------------------------------
# end-to-end: secrets never reach memory or journal
# ---------------------------------------------------------------------------


def test_full_cycle_secret_never_reaches_memory_or_journal(env):
    _, rec = _make_key("alice")
    tail = _tail_for(rec)
    records = _good_session("openai")
    records[0] = {
        "kind": "message",
        "role": "user",
        "ts": "2026-09-15T10:00:00Z",
        "content": (
            "Research telescopes. My email is jane@example.com, "
            "password=hunter2, key levi_sk_SECRETSEED999."
        ),
    }
    _write_cloud_session(env["sessions"], tail, "demo", records)
    report = growth_cycle.run_cycle(use_model=False, dry_run=False, store=env["store"])
    assert report["experiences"] > 0
    assert report["sources"]["by_origin"].get("cloud", 0) > 0

    secrets = ("jane@example.com", "hunter2", "levi_sk_SECRETSEED999")
    entries = [e for e in env["store"].list(limit=5000) if "growth" in e.tags]
    blob = " ".join((e.content or "") for e in entries)
    for secret in secrets:
        assert secret not in blob, secret

    journal_text = growth_journal.journal_path().read_text(encoding="utf-8")
    for secret in secrets:
        assert secret not in journal_text, secret

    # …but the technique learning did land, tagged with its source
    procedural = [e for e in entries if "procedural" in e.tags]
    assert procedural
    assert any("openai" in (e.content or "") for e in procedural)


def test_status_reports_source_breakdown(env):
    _, rec = _make_key("alice")
    tail = _tail_for(rec)
    _write_cloud_session(env["sessions"], tail, "demo", _good_session("openai"))
    s = growth_cycle.status(store=env["store"])
    pending = s.get("pending_by_source") or {}
    assert pending.get("by_origin", {}).get("cloud", 0) > 0
    assert pending.get("cloud_providers", {}).get("openai", 0) > 0


def test_turn_meta_record_roundtrip(env):
    from levi.agent.chat import ChatSession

    sess = ChatSession(name="cloud_deadbeef_probe")
    sess.append_message("user", "hi")
    sess.append_turn_meta(provider="openai", ok=True, steps=2)
    metas = [r for r in sess.records if r.get("kind") == "turn-meta"]
    assert metas and metas[0]["provider"] == "openai"
    # dialogue readers ignore it
    assert all(m.role in ("user", "assistant", "tool") for m in sess.messages())
