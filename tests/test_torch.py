"""Tests for levi.torch — pass-the-torch mentor bundles.

Hermetic: two fake homes (source + fresh target) under tmp_path.
Covers bundle schema, create → read round-trip into a clean HOME,
curriculum presence, provisional torch seed facts, founder's note
display, the confirm discipline, and signing.
"""

from __future__ import annotations

import json

import pytest

import levi.growth.curriculum as curriculum_mod
from levi.memory.store import MemoryStore
from levi.memory.types import MemoryType
from levi.torch import bundle as torch_bundle
from levi.torch.bundle import TorchError


LESSONS = [
    {
        "id": "torch-1",
        "topic": "Kindness",
        "kind": "fact",
        "text": "Kindness compounds: small generous acts repeated daily build trust faster than grand gestures.",
        "taught_by": "chauncey",
    },
]


@pytest.fixture()
def homes(tmp_path, monkeypatch):
    src = tmp_path / "src-home" / ".levi"
    dst = tmp_path / "dst-home" / ".levi"
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(src / "growth"))
    monkeypatch.setattr(curriculum_mod, "LESSONS", [dict(x) for x in LESSONS])
    # source home: a couple of corroborated growth learnings
    store = MemoryStore(data_dir=src / "memory")
    store.add(
        MemoryType.SEMANTIC,
        "Chauncey prefers concise answers with concrete numbers.",
        importance=0.8,
        source="levi",
        tags=["growth", "levi-learned", "preference"],
        metadata={"status": "provisional", "confidence": 0.9, "corroborated_count": 7},
    )
    store.add(
        MemoryType.SEMANTIC,
        "Backups run at 3am; never schedule heavy jobs then.",
        importance=0.6,
        source="levi",
        tags=["growth", "levi-learned", "procedural"],
        metadata={"status": "provisional", "confidence": 0.7, "corroborated_count": 2},
    )
    return {"src": src, "dst": dst, "tmp": tmp_path}


def _dst_store(homes) -> MemoryStore:
    return MemoryStore(data_dir=homes["dst"] / "memory")


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_bundle_schema(homes):
    bundle = torch_bundle.create_bundle(homes["src"])
    assert bundle["format"] == "levi-torch"
    assert bundle["version"] == 1
    sections = bundle["sections"]
    for key in (
        "lifepack",
        "curriculum",
        "journal_highlights",
        "model_card",
        "founders_note",
    ):
        assert key in sections, key
    # lifepack is the real thing, not a fork
    assert sections["lifepack"]["format"] == "levi-lifepack"
    # curriculum digest
    cur = sections["curriculum"]
    assert cur["lesson_count"] == 1
    assert cur["topics"] == ["Kindness"]
    assert cur["provenance"] == {"chauncey": 1}
    assert cur["lessons"][0]["id"] == "torch-1"
    # highlights: most corroborated first
    highlights = sections["journal_highlights"]
    assert len(highlights) == 2
    assert highlights[0]["corroborated_count"] == 7
    assert "concise answers" in highlights[0]["content"]
    # model card from the lab
    assert sections["model_card"]["current"] == "qwen3-0.6b"
    # founder's note: blank template
    note = sections["founders_note"]
    assert note["signed_by"] == "" and note["signed_at"] == ""
    assert "sign" in note["note"].lower()


def test_write_and_read_roundtrip(homes):
    bundle = torch_bundle.create_bundle(homes["src"])
    path = torch_bundle.write_bundle(homes["tmp"] / "torch.json", bundle)
    back = torch_bundle.read_bundle(path)
    assert back == bundle


def test_read_rejects_wrong_format(homes):
    bad = homes["tmp"] / "bad.json"
    bad.write_text(json.dumps({"format": "nope", "version": 1, "sections": {}}))
    with pytest.raises(TorchError):
        torch_bundle.read_bundle(bad)


def test_read_rejects_bad_version(homes):
    bundle = torch_bundle.create_bundle(homes["src"])
    bundle["version"] = 99
    with pytest.raises(TorchError):
        torch_bundle.validate_bundle(bundle)


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------


def test_ingest_requires_confirm(homes):
    bundle = torch_bundle.create_bundle(homes["src"])
    with pytest.raises(TorchError):
        torch_bundle.ingest_bundle(bundle, homes["dst"])


def test_ingest_roundtrip_into_clean_home(homes, capsys):
    bundle = torch_bundle.create_bundle(homes["src"])
    path = torch_bundle.write_bundle(homes["tmp"] / "torch.json", bundle)
    summary = torch_bundle.ingest_bundle(
        torch_bundle.read_bundle(path), homes["dst"], confirm=True
    )
    # curriculum present via the loader + torch seeds
    assert summary["curriculum"]["lessons"] == 1
    store = _dst_store(homes)
    entries = store.list(limit=5000)
    assert entries, "expected seeded entries in the new home"

    # torch seeds split into two honest kinds:
    #  * curriculum lessons → "seeded" (taught-by: torch), like the founders'
    #    curriculum but attributed to the torch;
    #  * journal highlights  → "provisional" seed facts (the learnings).
    torch_seeds = [e for e in entries if "torch-seed" in e.tags]
    assert torch_seeds, "expected taught-by: torch seed entries"
    for e in torch_seeds:
        prov = (e.metadata or {}).get("provenance") or {}
        assert prov.get("taught_by") == "torch"
        if "curriculum" in e.tags:
            assert (e.metadata or {}).get("status") == "seeded"
        else:
            assert (e.metadata or {}).get("status") == "provisional"
    assert any("curriculum" in e.tags for e in torch_seeds), "curriculum lesson missing"
    assert any("curriculum" not in e.tags for e in torch_seeds), (
        "provisional learnings missing"
    )

    # founder's note displayed on read
    rc = torch_bundle.cmd_torch(
        _ns(torch_action="read", path=str(path), yes=True), homes["dst"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "founder's note" in out.lower()
    assert "unsigned" in out.lower()


def test_ingest_idempotent_on_reimport(homes):
    bundle = torch_bundle.create_bundle(homes["src"])
    path = torch_bundle.write_bundle(homes["tmp"] / "torch.json", bundle)
    torch_bundle.ingest_bundle(
        torch_bundle.read_bundle(path), homes["dst"], confirm=True
    )
    before = len(_dst_store(homes).list(limit=5000))
    torch_bundle.ingest_bundle(
        torch_bundle.read_bundle(path), homes["dst"], confirm=True
    )
    after = len(_dst_store(homes).list(limit=5000))
    assert after == before, "re-ingest must not duplicate entries"


def test_preview_before_confirm(homes, capsys):
    bundle = torch_bundle.create_bundle(homes["src"])
    path = torch_bundle.write_bundle(homes["tmp"] / "torch.json", bundle)
    rc = torch_bundle.cmd_torch(
        _ns(torch_action="read", path=str(path), yes=False), homes["dst"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "preview" in out.lower()
    assert len(_dst_store(homes).list(limit=5000)) == 0  # nothing written


def test_torch_journal_entry(homes):
    from levi.growth import journal as growth_journal

    bundle = torch_bundle.create_bundle(homes["src"])
    path = torch_bundle.write_bundle(homes["tmp"] / "torch.json", bundle)
    torch_bundle.ingest_bundle(
        torch_bundle.read_bundle(path), homes["dst"], confirm=True
    )
    torch_reads = [
        e
        for e in growth_journal.read_entries(limit=10)
        if e.get("kind") == "torch-read"
    ]
    assert torch_reads, "expected a torch-read journal entry"
    assert torch_reads[0]["seed_facts_added"] >= 0


# ---------------------------------------------------------------------------
# sign + CLI
# ---------------------------------------------------------------------------


def test_sign_bundle(homes):
    bundle = torch_bundle.create_bundle(homes["src"])
    path = torch_bundle.write_bundle(homes["tmp"] / "torch.json", bundle)
    entry = torch_bundle.sign_bundle(path, by="Chauncey", note="Grow well, little one.")
    assert entry["signed_by"] == "Chauncey"
    assert entry["signed_at"]
    back = torch_bundle.read_bundle(path)
    assert back["sections"]["founders_note"]["signed_by"] == "Chauncey"


def test_cmd_torch_create(capsys, homes):
    out_path = homes["tmp"] / "mentor.json"
    rc = torch_bundle.cmd_torch(
        _ns(torch_action="create", path=str(out_path)), homes["src"]
    )
    assert rc == 0
    assert out_path.exists()
    assert "torch bundle created" in capsys.readouterr().out


def test_cmd_torch_sign_cli(homes):
    bundle = torch_bundle.create_bundle(homes["src"])
    path = torch_bundle.write_bundle(homes["tmp"] / "torch.json", bundle)
    rc = torch_bundle.cmd_torch(
        _ns(torch_action="sign", path=str(path), sign_by="Chauncey", sign_note="Hi."),
        homes["src"],
    )
    assert rc == 0
    assert (
        torch_bundle.read_bundle(path)["sections"]["founders_note"]["signed_by"]
        == "Chauncey"
    )


def test_cmd_torch_unknown_action(homes):
    assert torch_bundle.cmd_torch(_ns(torch_action="warp", path=""), homes["src"]) == 2


def _ns(**kwargs):
    class NS:
        pass

    ns = NS()
    defaults = {
        "torch_action": "create",
        "path": "",
        "yes": False,
        "sign_by": "",
        "sign_note": "",
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(ns, k, v)
    return ns
