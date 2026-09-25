"""Proof tests for the Meta DYI graph export.

Laws: read-only source, no silent drops (unresolved endpoints become
placeholder nodes and are reported), deterministic output, manifest
checksums, referential integrity on verify.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from levi.liberation.dyi_graph import (  # noqa: E402
    DYIError,
    extract_graph,
    verify_export,
    write_export,
)


def _fake_dyi(root: Path) -> Path:
    d = root / "dyi"
    (d / "profile_information").mkdir(parents=True)
    (d / "profile_information" / "profile_information.json").write_text(json.dumps({
        "profile_v2": {"name": {"full_name": "Test User"}}
    }))
    (d / "friends_and_followers").mkdir(parents=True)
    (d / "friends_and_followers" / "friends.json").write_text(json.dumps({
        "friends_v2": [
            {"name": "Sam Rivera", "timestamp": 1700000000},
            {"name": "Alex Kim", "timestamp": 1700000100},
        ]
    }))
    (d / "groups").mkdir(parents=True)
    (d / "groups" / "your_groups.json").write_text(json.dumps([
        {"name": "Retro Computing", "timestamp": 1700000200}
    ]))
    return d


def test_extracts_full_graph(tmp_path):
    g = extract_graph(_fake_dyi(tmp_path))
    kinds = {n["kind"] for n in g.nodes.values()}
    assert {"profile", "person", "group"} <= kinds
    rels = {e["rel"] for e in g.edges}
    assert {"friend", "member_of"} <= rels
    assert len([e for e in g.edges if e["rel"] == "friend"]) == 2


def test_write_and_verify_round_trip(tmp_path):
    g = extract_graph(_fake_dyi(tmp_path))
    out = tmp_path / "export"
    manifest = write_export(g, out, tmp_path / "dyi")
    assert manifest["node_count"] >= 4
    assert manifest["edge_count"] == 3
    ok, findings = verify_export(out)
    assert ok, findings


def test_deterministic_bytes(tmp_path):
    d1 = _fake_dyi(tmp_path / "a")
    g1 = extract_graph(d1)
    write_export(g1, tmp_path / "e1", d1)
    d2 = _fake_dyi(tmp_path / "b")
    g2 = extract_graph(d2)
    write_export(g2, tmp_path / "e2", d2)
    assert (tmp_path / "e1" / "graph.json").read_bytes() == \
           (tmp_path / "e2" / "graph.json").read_bytes()


def test_tampered_graph_fails_verify(tmp_path):
    g = extract_graph(_fake_dyi(tmp_path))
    out = tmp_path / "export"
    write_export(g, out, tmp_path / "dyi")
    data = json.loads((out / "graph.json").read_text())
    data["nodes"].append({"id": "person:evil", "kind": "person", "key": "Evil"})
    (out / "graph.json").write_text(json.dumps(data))
    ok, findings = verify_export(out)
    assert not ok
    assert "checksum mismatch" in findings[0]


def test_dangling_edge_fails_referential_integrity(tmp_path):
    g = extract_graph(_fake_dyi(tmp_path))
    out = tmp_path / "export"
    write_export(g, out, tmp_path / "dyi")
    # Surgical edit that KEEPS the checksum valid: re-sign via write path
    # is not available, so instead rebuild the manifest to match a graph
    # with a dangling edge, proving verify catches it.
    data = json.loads((out / "graph.json").read_text())
    data["edges"].append({"src": data["nodes"][0]["id"],
                         "dst": "person:nowhere", "rel": "friend"})
    import hashlib

    raw = json.dumps(data, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode() + b"\n"
    (out / "graph.json").write_bytes(raw)
    manifest = json.loads((out / "manifest.json").read_text())
    manifest["graph_sha256"] = hashlib.sha256(raw).hexdigest()
    (out / "manifest.json").write_text(json.dumps(manifest))
    ok, findings = verify_export(out)
    assert not ok
    assert any("dangling edge" in f for f in findings)


def test_source_dir_never_modified(tmp_path):
    d = _fake_dyi(tmp_path)
    before = {str(p) for p in d.rglob("*")}
    g = extract_graph(d)
    write_export(g, tmp_path / "export", d)
    assert {str(p) for p in d.rglob("*")} == before


def test_missing_dir_is_refused(tmp_path):
    with pytest.raises(DYIError):
        extract_graph(tmp_path / "nope")
