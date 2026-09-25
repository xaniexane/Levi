"""Tests for LEVI life-pack bundles (core/levi/lifepack/bundle.py).

Hermetic: everything runs against fresh tmp_path homes and synthetic
fixtures — no real ~/.levi, no real secrets, no real weights.
"""

from __future__ import annotations

import gzip
import io
import json
import tarfile
from pathlib import Path

import pytest

from levi.identity.profile import ProfileStore, UserProfile
from levi.lifepack.bundle import (
    BUNDLE_FORMAT,
    BUNDLE_VERSION,
    MANIFEST_FILENAME,
    PACK_FILENAME,
    UNENCRYPTED_WARNING,
    LifepackError,
    export_bundle,
    import_bundle,
)
from levi.lifepack.pack import FORMAT
from levi.memory.store import MemoryStore
from levi.memory.types import MemoryType

# Synthetic fixtures only — nothing here is a real secret or real weight.
_SYNTH_SECRET = "TEST-SYNTHETIC-API-KEY-001"
_SYNTH_MEMORY_SECRET = "my api token is TEST-SYNTHETIC-TOKEN-002"
_WEIGHT_MARKER = b"FAKE-WEIGHT-BYTES-MARKER-003"
_PASSPHRASE = "correct horse battery staple"


def seed_home(home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    profile = UserProfile(
        name="Test User", goal_this_week="Test bundles", onboarded=True
    )
    ProfileStore(path=home / "profile.json").save(profile)
    (home / "charter.json").write_text(
        json.dumps({"principle": "local-first"}), encoding="utf-8"
    )
    store = MemoryStore(data_dir=home / "memory")
    store.add(MemoryType.SEMANTIC, "Test User prefers dark mode", source="user")
    store.add(MemoryType.PREFERENCE, "coffee: black", source="user")


def read_tar_members(bundle_path: Path) -> dict:
    """Read every member of an unencrypted bundle tar."""
    out = {}
    with tarfile.open(bundle_path, mode="r:gz") as tar:
        for member in tar.getmembers():
            fobj = tar.extractfile(member)
            assert fobj is not None
            out[member.name] = fobj.read()
    return out


# ── round trips ────────────────────────────────────────────────────


def test_export_import_round_trip_encrypted(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    seed_home(src)
    bundle = tmp_path / "pack.tar.gz.enc"

    report = export_bundle(src, bundle, passphrase=_PASSPHRASE)
    assert report["encrypted"] is True
    assert bundle.is_file()
    # Encrypted bytes must not leak plaintext.
    raw = bundle.read_bytes()
    assert b"Test User" not in raw
    assert _SYNTH_SECRET.encode() not in raw
    envelope = json.loads(raw.decode("utf-8"))
    assert envelope["format"] == BUNDLE_FORMAT
    assert envelope["bundle_version"] == BUNDLE_VERSION
    assert envelope["encrypted"] is True
    assert envelope["kdf"]["name"] == "pbkdf2-hmac-sha256"

    # Preview first: nothing written.
    preview = import_bundle(bundle, dst, passphrase=_PASSPHRASE)
    assert preview["written"] is False
    assert preview["preview"]
    assert not (dst / "profile.json").exists()

    result = import_bundle(bundle, dst, passphrase=_PASSPHRASE, confirm=True)
    assert result["written"] is True
    assert result["encrypted"] is True
    assert ProfileStore(path=dst / "profile.json").load().name == "Test User"
    contents = [
        e.content for e in MemoryStore(data_dir=dst / "memory").list(limit=10_000)
    ]
    assert "Test User prefers dark mode" in contents


def test_export_import_round_trip_unencrypted_warns(tmp_path, capsys):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    seed_home(src)
    bundle = tmp_path / "pack.tar.gz"

    report = export_bundle(src, bundle)  # no passphrase → unencrypted
    assert report["encrypted"] is False
    assert bundle.read_bytes()[:2] == b"\x1f\x8b"  # plain gzip tar
    captured = capsys.readouterr()
    assert "UNENCRYPTED" in captured.err
    assert UNENCRYPTED_WARNING.split(".")[0] in captured.err

    members = read_tar_members(bundle)
    assert set(members) == {PACK_FILENAME, MANIFEST_FILENAME}
    manifest = json.loads(members[MANIFEST_FILENAME].decode("utf-8"))
    assert manifest["bundle_format"] == BUNDLE_FORMAT
    assert manifest["encrypted"] is False
    assert "unencrypted_warning" in manifest
    pack = json.loads(members[PACK_FILENAME].decode("utf-8"))
    assert pack["format"] == FORMAT

    result = import_bundle(bundle, dst, confirm=True)
    assert result["written"] is True
    assert result["encrypted"] is False
    assert ProfileStore(path=dst / "profile.json").load().name == "Test User"


# ── tamper evidence ────────────────────────────────────────────────


def _rewrite_tar_with(bundle: Path, pack_mutation=None, manifest_mutation=None) -> Path:
    """Rebuild the tar of an unencrypted bundle, mutating members."""
    members = read_tar_members(bundle)
    pack = json.loads(members[PACK_FILENAME].decode("utf-8"))
    manifest = json.loads(members[MANIFEST_FILENAME].decode("utf-8"))
    if pack_mutation:
        pack_mutation(pack)
    if manifest_mutation:
        manifest_mutation(manifest)
    new_pack = json.dumps(pack, indent=2, sort_keys=True).encode("utf-8")
    new_manifest = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for name, data in (
                (PACK_FILENAME, new_pack),
                (MANIFEST_FILENAME, new_manifest),
            ):
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                info.mtime = 0
                tar.addfile(info, io.BytesIO(data))
    out = bundle.with_name(bundle.name + ".tampered")
    out.write_bytes(buf.getvalue())
    return out


def test_manifest_tamper_pack_byte_flip_detected(tmp_path):
    src = tmp_path / "src"
    seed_home(src)
    bundle = tmp_path / "pack.tar.gz"
    export_bundle(src, bundle)

    tampered = _rewrite_tar_with(
        bundle, pack_mutation=lambda p: p["sections"].__setitem__("settings", {})
    )
    with pytest.raises(LifepackError, match="[Hh]ash|[Tt]amper"):
        import_bundle(tampered, tmp_path / "dst", confirm=True)


def test_manifest_self_hash_tamper_detected(tmp_path):
    src = tmp_path / "src"
    seed_home(src)
    bundle = tmp_path / "pack.tar.gz"
    export_bundle(src, bundle)

    # Edit the manifest's files table but leave manifest_integrity stale.
    tampered = _rewrite_tar_with(
        bundle,
        manifest_mutation=lambda m: m["files"][PACK_FILENAME].__setitem__(
            "sha256", "0" * 64
        ),
    )
    with pytest.raises(LifepackError, match="[Ii]ntegrity|[Tt]amper"):
        import_bundle(tampered, tmp_path / "dst", confirm=True)


def test_extra_tar_member_rejected(tmp_path):
    src = tmp_path / "src"
    seed_home(src)
    bundle = tmp_path / "pack.tar.gz"
    export_bundle(src, bundle)

    members = read_tar_members(bundle)
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for name, data in members.items():
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                info.mtime = 0
                tar.addfile(info, io.BytesIO(data))
            evil = b"planted"
            info = tarfile.TarInfo(name="evil.sh")
            info.size = len(evil)
            info.mtime = 0
            tar.addfile(info, io.BytesIO(evil))
    evil_bundle = tmp_path / "evil.tar.gz"
    evil_bundle.write_bytes(buf.getvalue())
    with pytest.raises(LifepackError, match="exactly"):
        import_bundle(evil_bundle, tmp_path / "dst", confirm=True)


# ── encryption failures ────────────────────────────────────────────


def test_wrong_passphrase_fails(tmp_path):
    src = tmp_path / "src"
    seed_home(src)
    bundle = tmp_path / "pack.tar.gz.enc"
    export_bundle(src, bundle, passphrase=_PASSPHRASE)
    with pytest.raises(LifepackError, match="[Ww]rong passphrase|[Aa]uthentication"):
        import_bundle(bundle, tmp_path / "dst", passphrase="wrong", confirm=True)


def test_missing_passphrase_fails(tmp_path):
    src = tmp_path / "src"
    seed_home(src)
    bundle = tmp_path / "pack.tar.gz.enc"
    export_bundle(src, bundle, passphrase=_PASSPHRASE)
    with pytest.raises(LifepackError, match="[Pp]assphrase"):
        import_bundle(bundle, tmp_path / "dst", confirm=True)


def test_garbage_file_rejected(tmp_path):
    junk = tmp_path / "junk.bin"
    junk.write_bytes(b"this is not a bundle at all")
    with pytest.raises(LifepackError):
        import_bundle(junk, tmp_path / "dst", confirm=True)


# ── exclusions ─────────────────────────────────────────────────────


def test_secrets_never_land_in_bundle(tmp_path):
    src = tmp_path / "src"
    seed_home(src)
    # Secret-looking settings key + secret-looking memory content.
    (src / "settings.json").write_text(
        json.dumps({"theme": "void", "api_key": _SYNTH_SECRET}), encoding="utf-8"
    )
    MemoryStore(data_dir=src / "memory").add(
        MemoryType.SEMANTIC, _SYNTH_MEMORY_SECRET, source="user"
    )

    for passphrase in (None, _PASSPHRASE):
        bundle = tmp_path / ("s.tar.gz" if passphrase is None else "s.tar.gz.enc")
        report = export_bundle(src, bundle, passphrase=passphrase)
        raw = bundle.read_bytes()
        assert _SYNTH_SECRET.encode() not in raw
        assert _SYNTH_MEMORY_SECRET.encode() not in raw
        # The scrub is also reported…
        assert report["scrubbed"]["settings_skipped"]
        assert report["scrubbed"]["memory_skipped"]
        # …and for the unencrypted bundle we can check pack.json directly.
        if passphrase is None:
            pack = json.loads(read_tar_members(bundle)[PACK_FILENAME].decode("utf-8"))
            assert "api_key" not in pack["sections"]["settings"].get(
                "settings.json", {}
            )
            assert _SYNTH_MEMORY_SECRET not in [
                e["content"] for e in pack["sections"]["memory"]
            ]


def test_weights_never_land_in_bundle(tmp_path):
    src = tmp_path / "src"
    seed_home(src)
    # A fake weights file sitting in the home: must not travel.
    models = src / "models"
    models.mkdir()
    (models / "tiny-gpt.pt").write_bytes(_WEIGHT_MARKER)
    (models / "other.gguf").write_bytes(_WEIGHT_MARKER)

    bundle = tmp_path / "w.tar.gz"
    export_bundle(src, bundle)
    members = read_tar_members(bundle)
    assert not any(n.endswith((".pt", ".gguf")) for n in members)
    for data in members.values():
        assert _WEIGHT_MARKER not in data


def test_weight_reference_in_pack_refuses_export(tmp_path):
    src = tmp_path / "src"
    seed_home(src)
    # Fail closed: even a filename reference to weights aborts the export.
    (src / "brain_table.json").write_text(
        json.dumps({"checkpoint": "tiny-gpt.pt"}), encoding="utf-8"
    )
    with pytest.raises(LifepackError, match="[Ww]eight"):
        export_bundle(src, tmp_path / "w.tar.gz")


def test_ephemeral_and_device_state_stay_home(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    seed_home(src)
    store = MemoryStore(data_dir=src / "memory")
    store.add(MemoryType.WORKING, "ephemeral scratch", source="user")
    store.add(MemoryType.DEVICE, "phone battery 80%", source="device")

    bundle = tmp_path / "e.tar.gz"
    export_bundle(src, bundle)
    import_bundle(bundle, dst, confirm=True)
    contents = [
        e.content for e in MemoryStore(data_dir=dst / "memory").list(limit=10_000)
    ]
    assert "ephemeral scratch" not in contents
    assert "phone battery 80%" not in contents


# ── confirmation discipline ────────────────────────────────────────


def test_import_requires_confirm(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    seed_home(src)
    bundle = tmp_path / "c.tar.gz"
    export_bundle(src, bundle)

    result = import_bundle(bundle, dst)  # confirm=False
    assert result["written"] is False
    assert result["preview"]  # preview shown, nothing written
    assert not (dst / "profile.json").exists()


def test_unsupported_pack_version_rejected(tmp_path):
    src = tmp_path / "src"
    seed_home(src)
    bundle = tmp_path / "v.tar.gz"
    export_bundle(src, bundle)
    tampered = _rewrite_tar_with(bundle, pack_mutation=lambda p: p.update(version=999))
    # The manifest no longer matches the edited pack → tamper error.
    # (Version gating itself is covered by pack.validate_pack tests.)
    with pytest.raises(LifepackError):
        import_bundle(tampered, tmp_path / "dst", confirm=True)
