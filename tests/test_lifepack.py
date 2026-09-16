"""Tests for LEVI life-pack export/import (core/levi/lifepack/pack.py).

Hermetic: every function takes an explicit ``home`` path, so the tests run
against fresh tmp_path homes and never touch the real ``~/.levi``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

from levi.identity.profile import ProfileStore, UserProfile
from levi.lifepack.pack import (
    FORMAT,
    PACK_VERSION,
    LifepackError,
    cmd_lifepack,
    export_pack,
    import_pack,
    looks_secret,
    preview_import,
    validate_pack,
)
from levi.memory.store import MemoryStore
from levi.memory.types import MemoryType


# ── helpers ────────────────────────────────────────────────────────


def seed_home(home: Path) -> None:
    """Seed a fake LEVI home with identity, settings, and memory."""
    home.mkdir(parents=True, exist_ok=True)
    profile = UserProfile(
        name="Chauncey", goal_this_week="Ship life packs", onboarded=True
    )
    ProfileStore(path=home / "profile.json").save(profile)
    (home / "charter.json").write_text(
        json.dumps({"principle": "local-first"}), encoding="utf-8"
    )

    store = MemoryStore(data_dir=home / "memory")
    store.add(MemoryType.SEMANTIC, "Chauncey prefers dark mode", source="user")
    store.add(MemoryType.PREFERENCE, "coffee: black", source="user")
    store.add(MemoryType.PROCEDURAL, "deploy with ./deploy.sh", source="user")
    store.add(
        MemoryType.WORKING, "ephemeral scratch note", source="user"
    )  # must NOT travel
    store.add(
        MemoryType.DEVICE, "phone battery 80%", source="device"
    )  # must NOT travel


def snapshot_files(home: Path) -> dict:
    out = {}
    for p in sorted(home.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(home))] = p.read_bytes()
    return out


# ── format / validation ────────────────────────────────────────────


def test_export_pack_shape(tmp_path):
    seed_home(tmp_path)
    pack = export_pack(tmp_path)
    assert pack["format"] == FORMAT
    assert pack["version"] == PACK_VERSION
    assert pack["exported_at"]
    assert pack["levi_version"]
    secs = pack["sections"]
    assert secs["identity"]["name"] == "Chauncey"
    assert secs["settings"]["charter.json"] == {"principle": "local-first"}
    contents = [e["content"] for e in secs["memory"]]
    assert "Chauncey prefers dark mode" in contents
    assert "coffee: black" in contents
    assert "deploy with ./deploy.sh" in contents
    # ephemeral + device state stay home
    assert "ephemeral scratch note" not in contents
    assert "phone battery 80%" not in contents
    # skills: manifest only, no playbook bodies
    manifest = secs["skills"]["manifest"]
    assert len(manifest) > 100
    ids = [s["id"] for s in manifest]
    assert "status" in ids
    assert all(
        set(s) == {"id", "name", "category", "version", "risk_level"} for s in manifest
    )


def test_export_tolerates_empty_home(tmp_path):
    pack = export_pack(tmp_path / "missing")
    assert pack["sections"]["identity"]["name"] == ""
    assert pack["sections"]["settings"] == {}
    assert pack["sections"]["memory"] == []


def test_validate_pack_rejects_garbage(tmp_path):
    with pytest.raises(LifepackError):
        validate_pack({"format": "zip", "version": 1, "sections": {}})
    with pytest.raises(LifepackError):
        validate_pack({"format": FORMAT, "version": 999, "sections": {}})
    seed_home(tmp_path)
    pack = export_pack(tmp_path)
    del pack["sections"]["memory"]
    with pytest.raises(LifepackError):
        validate_pack(pack)


# ── round trip ─────────────────────────────────────────────────────


def test_export_import_round_trip(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    seed_home(src)
    pack = export_pack(src)

    summary = import_pack(pack, dst, confirm=True)
    assert summary["identity"]["changed"] is True
    assert summary["memory"]["added"] == 3  # only the 3 durable entries
    assert summary["skills"]["changed"] is False

    # identity landed
    assert ProfileStore(path=dst / "profile.json").load().name == "Chauncey"
    # memory landed (durable only)
    store = MemoryStore(data_dir=dst / "memory")
    assert len(store.list(limit=10_000)) == 3
    # settings landed
    assert json.loads((dst / "charter.json").read_text()) == {
        "principle": "local-first"
    }
    # skills manifest verifiable
    assert summary["skills"]["local_count"] == summary["skills"]["pack_count"]


def test_reimport_is_noop(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    seed_home(src)
    pack = export_pack(src)
    import_pack(pack, dst, confirm=True)
    before = snapshot_files(dst)
    summary = import_pack(pack, dst, confirm=True)
    assert summary["identity"]["changed"] is False
    assert summary["memory"]["added"] == 0
    assert summary["memory"]["changed_entries"] == 0
    assert summary["settings"]["files"] == []
    assert snapshot_files(dst) == before


def test_changed_memory_entry_updates(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    seed_home(src)
    pack = export_pack(src)
    import_pack(pack, dst, confirm=True)
    # mutate one entry in the pack
    for e in pack["sections"]["memory"]:
        if e["content"] == "coffee: black":
            e["content"] = "coffee: oat latte"
    summary = import_pack(pack, dst, confirm=True)
    assert summary["memory"]["changed_entries"] == 1
    store = MemoryStore(data_dir=dst / "memory")
    assert any(e.content == "coffee: oat latte" for e in store.list(limit=10_000))


# ── preview ────────────────────────────────────────────────────────


def test_preview_diff(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    seed_home(src)
    pack = export_pack(src)
    import_pack(pack, dst, confirm=True)

    # diverge the target home: change a profile field, add a new setting file
    profile = ProfileStore(path=dst / "profile.json").load()
    profile.name = "Someone Else"
    ProfileStore(path=dst / "profile.json").save(profile)
    # diverge a settings file the pack also carries
    (dst / "charter.json").write_text(
        json.dumps({"principle": "cloud-first"}), encoding="utf-8"
    )

    lines = preview_import(pack, dst)
    text = "\n".join(lines)
    assert "'Someone Else'" in text and "'Chauncey'" in text, text
    assert any(
        "settings" in line and "charter.json" in line and "differs" in line
        for line in lines
    ), text
    assert any(
        line.startswith("memory:") and "+0 new" in line and "0 changed" in line
        for line in lines
    ), text
    assert any(line.startswith("skills:") for line in lines), text

    # preview is read-only
    assert ProfileStore(path=dst / "profile.json").load().name == "Someone Else"


def test_preview_no_changes(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    seed_home(src)
    pack = export_pack(src)
    import_pack(pack, dst, confirm=True)
    lines = preview_import(pack, dst)
    assert any("identity: no changes" in line for line in lines)


# ── permission discipline ──────────────────────────────────────────


def test_import_without_confirm_writes_nothing(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    seed_home(src)
    pack = export_pack(src)
    with pytest.raises(LifepackError, match="preview"):
        import_pack(pack, dst)
    assert not (dst / "profile.json").exists()
    assert not (dst / "memory").exists()


def test_cmd_import_preview_writes_nothing(tmp_path, capsys):
    src = tmp_path / "src"
    seed_home(src)
    pack = export_pack(src)
    pack_file = tmp_path / "pack.json"
    pack_file.write_text(json.dumps(pack), encoding="utf-8")

    dst = tmp_path / "dst"
    args = argparse.Namespace(
        lifepack_action="import", file=str(pack_file), preview=True, yes=False
    )
    rc = cmd_lifepack(args, home=dst)
    assert rc == 0
    assert not (dst / "profile.json").exists()
    out = capsys.readouterr().out
    assert "preview only" in out


def test_cmd_import_refuses_without_tty_or_yes(tmp_path, monkeypatch, capsys):
    src = tmp_path / "src"
    seed_home(src)
    pack = export_pack(src)
    pack_file = tmp_path / "pack.json"
    pack_file.write_text(json.dumps(pack), encoding="utf-8")

    dst = tmp_path / "dst"
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    args = argparse.Namespace(
        lifepack_action="import", file=str(pack_file), preview=False, yes=False
    )
    rc = cmd_lifepack(args, home=dst)
    assert rc == 1
    assert not (dst / "profile.json").exists()
    assert "confirmation" in capsys.readouterr().err


def test_cmd_import_yes_writes(tmp_path, capsys):
    src = tmp_path / "src"
    seed_home(src)
    pack = export_pack(src)
    pack_file = tmp_path / "pack.json"
    pack_file.write_text(json.dumps(pack), encoding="utf-8")

    dst = tmp_path / "dst"
    args = argparse.Namespace(
        lifepack_action="import", file=str(pack_file), preview=False, yes=True
    )
    rc = cmd_lifepack(args, home=dst)
    assert rc == 0
    assert ProfileStore(path=dst / "profile.json").load().name == "Chauncey"


def test_cmd_export_round_trip(tmp_path, capsys):
    src = tmp_path / "src"
    seed_home(src)
    pack_file = tmp_path / "pack.json"
    args = argparse.Namespace(lifepack_action="export", file=str(pack_file))
    assert cmd_lifepack(args, home=src) == 0
    pack = json.loads(pack_file.read_text(encoding="utf-8"))
    validate_pack(pack)
    assert pack["sections"]["identity"]["name"] == "Chauncey"


# ── secrets filter ─────────────────────────────────────────────────


def test_looks_secret():
    assert looks_secret("api_key")
    assert looks_secret("LEVIL_API_KEY")
    assert looks_secret("oauth-token")
    assert looks_secret("clientSecret")
    assert looks_secret("db_password")
    assert not looks_secret("name")
    assert not looks_secret("goal_this_week")
    assert not looks_secret("theme")


def test_secret_setting_keys_skipped_on_import(tmp_path):
    src = tmp_path / "src"
    seed_home(src)
    pack = export_pack(src)
    pack["sections"]["settings"]["settings.json"] = {
        "theme": "dark",
        "api_key": "sk-live-DO-NOT-TRAVEL",
        "nested": {"db_password": "hunter2", "ok": 1},
    }
    pack["sections"]["memory"].append(
        {
            "id": "secret-note",
            "memory_type": "semantic",
            "content": "my api_key is sk-live-xyz",
            "metadata": {},
            "importance": 0.5,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "source": "user",
            "tags": [],
            "project_id": None,
            "embedding_ref": None,
            "version": 1,
        }
    )
    dst = tmp_path / "dst"
    summary = import_pack(pack, dst, confirm=True)

    written = json.loads((dst / "settings.json").read_text(encoding="utf-8"))
    assert written["theme"] == "dark"
    assert "api_key" not in written
    assert "db_password" not in written["nested"]
    assert written["nested"]["ok"] == 1
    assert any("api_key" in s for s in summary["settings"]["secrets_skipped"])

    store = MemoryStore(data_dir=dst / "memory")
    assert store.get("secret-note") is None
    assert "secret-note" in summary["memory"]["secrets_skipped"]


# ── format v2 ────────────────────────────────────────────────────


def _seed_growth(monkeypatch, home: Path):
    """Seed a growth journal + state via the public journal API.

    Uses the journal's own LEVI_GROWTH_DIR override so the test never
    touches the real ~/.levi/growth.
    """
    from levi.growth import journal

    monkeypatch.setenv("LEVI_GROWTH_DIR", str(home / "growth"))
    journal.save_state({"cycles": 3})
    journal.append_entry({"kind": "cycle", "accepted": 2, "mode": "rules"})
    journal.append_entry({"kind": "cycle", "accepted": 1, "mode": "rules"})
    return journal


def test_export_v2_sections(tmp_path, monkeypatch):
    seed_home(tmp_path)
    _seed_growth(monkeypatch, tmp_path)
    pack = export_pack(tmp_path)
    assert pack["version"] == 2 == PACK_VERSION
    secs = pack["sections"]
    for name in ("capabilities", "growth", "workflows", "manifest"):
        assert name in secs, f"missing v2 section {name!r}"

    # capabilities: atlas landed in this tree — accept any honest status
    caps = secs["capabilities"]
    assert caps["status"] in ("ok", "atlas-not-landed", "atlas-unreadable")
    if caps["status"] == "ok":
        assert isinstance(caps["atlas"], dict)

    # growth: developmental snapshot via the public journal API
    growth = secs["growth"]
    assert growth["status"] == "ok"
    assert growth["cycles"] == 3
    assert growth["learnings"] == 0  # no growth-tagged memory yet
    assert growth["stage"] == "newborn"
    assert len(growth["recent_entries"]) == 2

    # workflows: names + summaries only — step bodies travel with the code
    wfs = secs["workflows"]
    assert wfs["status"] in ("ok", "workflows-not-landed", "workflows-unreadable")
    if wfs["status"] == "ok":
        assert wfs["workflows"]
        assert all(set(w) == {"name", "summary"} for w in wfs["workflows"])

    # manifest: provenance with a non-personal machine id
    mf = secs["manifest"]
    assert mf["pack_version"] == 2
    assert mf["levi_version"]
    assert mf["exported_at"]
    assert len(mf["source_machine_id"]) == 16
    assert all(c in "0123456789abcdef" for c in mf["source_machine_id"])
    assert "not reversible" in mf["source_machine_id_note"]


def test_growth_learnings_counted_from_home_memory(tmp_path, monkeypatch):
    seed_home(tmp_path)
    _seed_growth(monkeypatch, tmp_path)
    store = MemoryStore(data_dir=tmp_path / "memory")
    store.add(
        MemoryType.SEMANTIC,
        "Chauncey likes concise answers",
        source="user",
        tags=["growth", "preference"],
    )
    pack = export_pack(tmp_path)
    growth = pack["sections"]["growth"]
    assert growth["status"] == "ok"
    assert growth["learnings"] == 1
    assert growth["stage"] == "sprouting"  # 1 learning crosses the sprouting threshold


def test_v2_export_tolerates_missing_modules(tmp_path, monkeypatch):
    import sys

    seed_home(tmp_path)
    # Simulate a tree where the atlas / workflows / growth modules never landed.
    for mod in (
        "levi.interop.atlas",
        "levi.workflows",
        "levi.growth",
        "levi.growth.journal",
    ):
        monkeypatch.setitem(sys.modules, mod, None)
    pack = export_pack(tmp_path)
    assert pack["sections"]["capabilities"] == {"status": "atlas-not-landed"}
    assert pack["sections"]["workflows"] == {"status": "workflows-not-landed"}
    assert pack["sections"]["growth"] == {"status": "growth-not-landed"}
    validate_pack(pack)  # still a valid v2 pack


def test_v1_pack_still_validates_and_imports(tmp_path, monkeypatch):
    src = tmp_path / "src"
    seed_home(src)
    v2 = export_pack(src)
    # hand-shape a v1 pack: the four core sections only
    v1 = {
        "format": FORMAT,
        "version": 1,
        "exported_at": v2["exported_at"],
        "levi_version": v2["levi_version"],
        "sections": {
            k: v2["sections"][k] for k in ("identity", "settings", "memory", "skills")
        },
    }
    validate_pack(v1)  # v1 must still be accepted

    dst = tmp_path / "dst"
    summary = import_pack(v1, dst, confirm=True)
    assert summary["identity"]["changed"] is True
    assert summary["memory"]["added"] == 3  # only the durable entries
    # v2-only sections report not-in-pack; nothing is written for them
    for name in ("capabilities", "growth", "workflows", "manifest"):
        assert summary[name]["changed"] is False
        assert summary[name]["status"] == "not-in-pack"
    store = MemoryStore(data_dir=dst / "memory")
    assert len(store.list(limit=10_000)) == 3


def test_v2_roundtrip_preserves_durable_memory(tmp_path, monkeypatch):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    seed_home(src)
    _seed_growth(monkeypatch, src)
    pack = export_pack(src)

    summary = import_pack(pack, dst, confirm=True)
    assert summary["memory"]["added"] == 3
    store = MemoryStore(data_dir=dst / "memory")
    contents = [e.content for e in store.list(limit=10_000)]
    assert "Chauncey prefers dark mode" in contents
    assert "coffee: black" in contents
    assert "deploy with ./deploy.sh" in contents

    # v2 sections are informational: verified and reported, never written
    assert summary["capabilities"]["changed"] is False
    assert summary["workflows"]["changed"] is False
    growth = summary["growth"]
    assert growth["changed"] is False
    assert growth["status"] == "ok"
    assert growth["stage"] == "newborn"
    assert growth["cycles"] == 3
    mf = summary["manifest"]
    assert mf["pack_version"] == 2
    assert mf["source_machine_id"] == pack["sections"]["manifest"]["source_machine_id"]
    # growth state itself was NOT imported into the target home
    assert not (dst / "growth").exists()


def test_preview_v2_sections(tmp_path, monkeypatch):
    src = tmp_path / "src"
    seed_home(src)
    _seed_growth(monkeypatch, src)
    pack = export_pack(src)
    lines = preview_import(pack, tmp_path / "dst")
    assert any(line.startswith("capabilities:") for line in lines)
    assert any(line.startswith("growth:") and "newborn" in line for line in lines), (
        "\n".join(lines)
    )
    assert any(line.startswith("workflows:") for line in lines)
    assert any(line.startswith("manifest:") and "pack v2" in line for line in lines), (
        "\n".join(lines)
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))


# ── variant genome (heredity travels; duplicates can mutate) ─────────


def _seed_genome(home: Path) -> None:
    from levi.identity.cycle import IdentityCycle
    from levi.identity.genome import GenomeStore

    store = GenomeStore(home)
    IdentityCycle(store=store).run_scope_all(n_variants=1, seed="test")
    IdentityCycle(store=store).run_forms(n_variants=1, seed="test")


def test_variant_genome_exports_and_restores(tmp_path):
    from levi.identity.genome import GenomeStore

    src, dst = tmp_path / "src", tmp_path / "dst"
    seed_home(src)
    _seed_genome(src)
    pack = export_pack(src)
    vg = pack["sections"]["variant_genome"]
    assert vg["status"] == "ok"
    assert len(vg["genome"]["candidates"]) == len(GenomeStore(src).load()["candidates"])
    validate_pack(pack)
    summary = import_pack(pack, dst, confirm=True)
    assert summary["variant_genome"]["status"] == "ok"
    assert summary["variant_genome"]["changed"] is True
    assert (
        len(GenomeStore(dst).load()["candidates"])
        == summary["variant_genome"]["candidates"]
    )


def test_variant_genome_absent_in_old_packs(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    seed_home(src)
    pack = export_pack(src)
    del pack["sections"]["variant_genome"]  # simulate a pre-heredity pack
    validate_pack(pack)  # still valid: the section is optional
    summary = import_pack(pack, dst, confirm=True)
    assert summary["variant_genome"]["status"] == "not-in-pack"


def test_variant_genome_import_idempotent(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    seed_home(src)
    _seed_genome(src)
    pack = export_pack(src)
    import_pack(pack, dst, confirm=True)
    summary = import_pack(pack, dst, confirm=True)
    assert summary["variant_genome"]["changed"] is False


def test_lifepack_mutate_requires_seed(tmp_path):
    args = argparse.Namespace(lifepack_action="mutate", seed="")
    assert cmd_lifepack(args, home=tmp_path) == 2


def test_lifepack_mutate_records_divergence(tmp_path):
    from levi.identity.genome import GenomeStore

    seed_home(tmp_path)
    args = argparse.Namespace(lifepack_action="mutate", seed="diverge-test")
    assert cmd_lifepack(args, home=tmp_path) == 0
    genome = GenomeStore(tmp_path).load()
    assert genome["lineage"] and genome["lineage"][-1]["event"] == "mutation"
    assert genome["lineage"][-1]["seed"] == "diverge-test"
    # one organism: modules + forms share one candidate namespace
    # (the "cybrus" form and "cybrus" module are one entry, not two)
    from levi.identity.cycle import ORGANISM_FORMS
    from levi.identity.scope import iter_module_identities

    expected = {i["name"] for i in iter_module_identities()} | set(ORGANISM_FORMS)
    assert set(genome["candidates"]) == expected


def test_run_forms_covers_organism_forms():
    from levi.identity.cycle import ORGANISM_FORMS, IdentityCycle

    out = IdentityCycle().run_forms(n_variants=1, seed="test")
    assert out["forms"] == len(ORGANISM_FORMS) >= 18
    assert {r["form"] for r in out["results"]} == set(ORGANISM_FORMS)
