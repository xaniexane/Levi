"""Tests for the learning sync (distribution half of collective learning).

Covers: pack-build exclusion gates (non-consented local learnings,
facts/preferences/corrections, identifier-risk content), zero user/key
identifiers in packs, tamper rejection (hash mismatch), version ordering
(stale packs rejected), ingest dedupe against known learnings,
ingested entries never re-packing (no echo chamber), the
LEVI_GROWTH_CONTRIBUTE opt-in, LEVI_GROWTH_RECEIVE opt-out, the
min-corroboration filter, the two-instance end-to-end (A contributes,
pack built, B ingests), and the cloud endpoint
GET /v1/learning/packs/latest. All hermetic: growth dir, cloud dir,
and memory store point at tmp_path.
"""

from __future__ import annotations

import json
import re
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError

import pytest

from levi.growth import sync as S
from levi.growth.consolidate import consolidate
from levi.growth.reflect import Learning
from levi.memory.store import MemoryStore

TECHNIQUE_A = (
    "When gathering information, issue several focused 'web_search' calls "
    "in sequence before composing the final answer, rather than answering "
    "from the first result."
)
TECHNIQUE_B = (
    "Before retrying a failed 'read_file' call, re-check the path spelling "
    "and whether the file exists; do not blindly repeat the same call."
)
TECHNIQUE_C = (
    "For multi-part research tasks, chain 'web_search' then 'read_file' in "
    "a deliberate order, gathering each piece of evidence before moving on."
)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(tmp_path / "growth"))
    monkeypatch.setenv("LEVI_CLOUD_DIR", str(tmp_path / "cloud"))
    monkeypatch.setenv("LEVI_GROWTH_CONTRIBUTE", "0")
    monkeypatch.setenv("LEVI_GROWTH_RECEIVE", "1")
    store = MemoryStore(data_dir=tmp_path / "memory")
    return {"tmp": tmp_path, "store": store}


def _cloud_learning(content=TECHNIQUE_A, source_model="openai"):
    return Learning(
        kind="procedural",
        content=content,
        confidence=0.6,
        provenance={
            "mode": "rules:cloud-distill",
            "source": "cloud:alice",
            "session": "cloud_abc123_s1",
            "learned_from": source_model,
            "key_name": "alice",
        },
    )


def _local_learning(content=TECHNIQUE_B, kind="procedural"):
    return Learning(
        kind=kind,
        content=content,
        confidence=0.7,
        provenance={"mode": "rules", "source": "session:owner1"},
    )


def _seed(store, learnings):
    return consolidate(learnings, cycle_id="cyc-test", store=store)


# ---------------------------------------------------------------------------
# Pack-build gates
# ---------------------------------------------------------------------------


def test_pack_build_excludes_nonconsented_and_personal(env):
    _seed(
        env["store"],
        [
            _cloud_learning(),  # shareable
            _local_learning(),  # local, no opt-in
            _local_learning(TECHNIQUE_C, kind="fact"),  # personal fact
            _local_learning("The user prefers dark mode.", kind="preference"),
            _local_learning("User corrected Levi with: 'no'.", kind="correction"),
        ],
    )
    report = S.build_pack(store=env["store"])
    assert report["entries"] == 1
    pack = json.loads(Path(report["path"]).read_text(encoding="utf-8"))
    assert pack["entries"][0]["content"] == TECHNIQUE_A
    reasons = sorted(e["reason"] for e in report["excluded"])
    assert reasons == [
        "not-marked-shareable",
        "not-technique-kind",
        "not-technique-kind",
        "not-technique-kind",
    ]


def test_local_contribute_opt_in(env, monkeypatch):
    monkeypatch.setenv("LEVI_GROWTH_CONTRIBUTE", "1")
    _seed(env["store"], [_local_learning()])
    report = S.build_pack(store=env["store"])
    assert report["entries"] == 1
    pack = json.loads(Path(report["path"]).read_text(encoding="utf-8"))
    assert pack["entries"][0]["source_types"] == {"local": 1}


def test_pack_contains_zero_identifiers(env):
    _seed(env["store"], [_cloud_learning()])
    report = S.build_pack(store=env["store"])
    pack = json.loads(Path(report["path"]).read_text(encoding="utf-8"))
    raw = json.dumps(pack)
    # No key names, user ids, session ids, or raw provenance anywhere.
    for token in ("alice", "cloud:", "key_name", "session", "abc123"):
        assert token not in raw, f"identifier leaked: {token!r}"
    for entry in pack["entries"]:
        assert set(entry.keys()) <= {
            "kind",
            "content",
            "confidence",
            "corroborated_sources",
            "source_types",
            "learned_from",
        }
        assert entry["kind"] == "procedural"
        assert set(entry["source_types"].keys()) <= {"cloud", "local"}
    # No PII-shaped text anywhere in the pack.
    assert not re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", raw)
    assert not re.search(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)", raw)


def test_identifier_risk_content_never_packs(env):
    sneaky = _cloud_learning(
        "Technique: email the report to boss@example.com when done."
    )
    _seed(env["store"], [sneaky])
    report = S.build_pack(store=env["store"])
    assert report["entries"] == 0
    assert report["excluded"][0]["reason"] == "identifier-risk"


def test_min_corroboration_filter(env):
    # Same technique twice → second consolidate corroborates the first.
    _seed(env["store"], [_cloud_learning()])
    _seed(env["store"], [_cloud_learning()])
    report = S.build_pack(store=env["store"], min_corroboration=2)
    assert report["entries"] == 0
    report = S.build_pack(store=env["store"], min_corroboration=1)
    assert report["entries"] == 1
    pack = json.loads(Path(report["path"]).read_text(encoding="utf-8"))
    assert pack["entries"][0]["corroborated_sources"] == 2


# ---------------------------------------------------------------------------
# Verification + ingest
# ---------------------------------------------------------------------------


def test_tampered_pack_rejected(env):
    _seed(env["store"], [_cloud_learning()])
    report = S.build_pack(store=env["store"])
    path = Path(report["path"])
    raw = path.read_text(encoding="utf-8")
    tampered = raw.replace("sequence", "sequencX")
    assert tampered != raw
    path.write_text(tampered, encoding="utf-8")
    with pytest.raises(S.PackError, match="tampered"):
        S.ingest_pack_file(path, store=env["store"])


def test_older_version_rejected(env):
    _seed(env["store"], [_cloud_learning()])
    report = S.build_pack(store=env["store"])
    first = S.ingest_pack_file(report["path"], store=env["store"])
    assert first["version"] == 1
    # Same pack again: not newer → rejected.
    with pytest.raises(S.PackError, match="not newer"):
        S.ingest_pack_file(report["path"], store=env["store"])
    assert [r["version"] for r in S.installed_packs()] == [1]


def test_ingest_dedupes_known_learning(env):
    _seed(env["store"], [_local_learning(TECHNIQUE_A)])  # B already knows it
    before = len(env["store"].list(limit=10000))
    pack_env_store = MemoryStore(data_dir=env["tmp"] / "memA")
    _seed(pack_env_store, [_cloud_learning(TECHNIQUE_A)])
    report = S.build_pack(store=pack_env_store)
    out = S.ingest_pack_file(report["path"], store=env["store"])
    assert out["accepted"] == 0 and out["corroborated"] == 1
    assert len(env["store"].list(limit=10000)) == before


def test_ingested_entries_never_repack(env):
    """No echo chamber: what came from the collective stays out of packs."""
    _seed(env["store"], [_cloud_learning()])
    report = S.build_pack(store=env["store"])
    store_b = MemoryStore(data_dir=env["tmp"] / "memB")
    out = S.ingest_pack_file(report["path"], store=store_b)
    assert out["accepted"] == 1
    entry = [e for e in store_b.list(limit=10000) if "collective" in e.tags][0]
    assert entry.metadata["shareable"] is False
    assert entry.metadata["provenance"]["learned_from"] == "collective"
    assert entry.metadata["provenance"]["pack_version"] == 1
    report2 = S.build_pack(store=store_b)
    assert report2["entries"] == 0  # the collective entry did not re-pack


def test_receive_opt_out(env, monkeypatch):
    monkeypatch.setenv("LEVI_GROWTH_RECEIVE", "0")
    _seed(env["store"], [_cloud_learning()])
    report = S.build_pack(store=env["store"])
    with pytest.raises(S.PackError, match="disabled"):
        S.ingest_pack_file(report["path"], store=env["store"])


def test_end_to_end_two_instances(tmp_path, monkeypatch):
    """A contributes → pack built → B ingests → B knows the technique."""
    # Instance A
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(tmp_path / "growthA"))
    monkeypatch.setenv("LEVI_CLOUD_DIR", str(tmp_path / "cloudA"))
    store_a = MemoryStore(data_dir=tmp_path / "memA")
    _seed(store_a, [_cloud_learning()])
    report = S.build_pack(store=store_a)
    assert report["entries"] == 1

    # Instance B (fresh dirs, fresh store)
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(tmp_path / "growthB"))
    monkeypatch.setenv("LEVI_CLOUD_DIR", str(tmp_path / "cloudB"))
    store_b = MemoryStore(data_dir=tmp_path / "memB")
    out = S.ingest_pack_file(report["path"], store=store_b)
    assert out["accepted"] == 1

    entries = [e for e in store_b.list(limit=10000) if "growth" in e.tags]
    assert len(entries) == 1
    e = entries[0]
    assert e.content == TECHNIQUE_A
    assert "collective" in e.tags
    assert e.metadata["provenance"]["learned_from"] == "collective"
    assert e.metadata["status"] == "provisional"
    # And B's pack dir knows nothing about A's users.
    raw = Path(report["path"]).read_text(encoding="utf-8")
    assert "alice" not in raw


# ---------------------------------------------------------------------------
# Cloud endpoint
# ---------------------------------------------------------------------------

OWNER_TOKEN = "test-owner-token-learning-sync"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_CLOUD_DIR", str(tmp_path / "cloud"))
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(tmp_path / "growth"))
    monkeypatch.setenv("LEVI_AGENT_TOKEN", OWNER_TOKEN)
    from levi.agent.server import _AgentHandler
    from levi.cloud.ratelimit import RateLimiter

    saved = {
        "token": _AgentHandler.token,
        "owner_token": _AgentHandler.owner_token,
        "rate_limiter": _AgentHandler.rate_limiter,
        "make_registry": _AgentHandler.make_registry,
    }
    _AgentHandler.token = OWNER_TOKEN
    _AgentHandler.owner_token = OWNER_TOKEN
    _AgentHandler.rate_limiter = RateLimiter(per_minute=10_000)
    _AgentHandler.make_registry = None
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _AgentHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
        for k, v in saved.items():
            setattr(_AgentHandler, k, v)


def _get(base, path, bearer=None):
    headers = {}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urlrequest.Request(base + path, headers=headers, method="GET")
    try:
        with urlrequest.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def test_learning_endpoint_serves_verified_pack(server, tmp_path):
    store = MemoryStore(data_dir=tmp_path / "memory")
    _seed(store, [_cloud_learning()])
    built = S.build_pack(store=store)

    status, payload = _get(server, "/v1/learning/packs/latest")
    assert status == 401  # auth required
    status, payload = _get(server, "/v1/learning/packs/latest", bearer="wrong")
    assert status == 401
    status, payload = _get(server, "/v1/learning/packs/latest", bearer=OWNER_TOKEN)
    assert status == 200
    assert payload["manifest"]["version"] == built["version"]
    assert payload["pack"]["version"] == built["version"]
    # Client-side verification passes on what the server served.
    digest = S.verify_pack(payload["pack"], payload["manifest"])
    assert digest == built["manifest"]["sha256"]


def test_learning_endpoint_empty_when_no_packs(server):
    status, payload = _get(server, "/v1/learning/packs/latest", bearer=OWNER_TOKEN)
    assert status == 200
    assert payload == {"manifest": None, "pack": None}


def test_sync_from_server(tmp_path, monkeypatch, server):
    store = MemoryStore(data_dir=tmp_path / "memory")
    _seed(store, [_cloud_learning()])
    S.build_pack(store=store)

    # Receiver with a fresh memory store pulls from the server.
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(tmp_path / "growthB"))
    store_b = MemoryStore(data_dir=tmp_path / "memB")
    out = S.sync_from_server(server, OWNER_TOKEN, store=store_b)
    assert out["status"] == "ingested"
    assert out["accepted"] == 1
    entries = [e for e in store_b.list(limit=10000) if "collective" in e.tags]
    assert len(entries) == 1 and entries[0].content == TECHNIQUE_A
