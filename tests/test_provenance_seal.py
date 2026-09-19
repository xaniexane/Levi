"""Origin Seal tests — sign/verify round-trip, tamper detection, key safety."""

import json

import pytest

from levi.provenance import seal as S


@pytest.fixture(autouse=True)
def _preserve_repo_anchor():
    """init_keypair() rewrites the in-repo origin.pub; never leak test keys there."""
    pub_path = S.repo_pubkey_path()
    had = pub_path.read_text() if pub_path.exists() else None
    yield
    if had is None:
        pub_path.unlink(missing_ok=True)
    else:
        pub_path.write_text(had)


@pytest.fixture()
def keydir(tmp_path, monkeypatch):
    kd = tmp_path / "keys"
    monkeypatch.setenv("LEVI_SEAL_DIR", str(kd))
    return kd


@pytest.fixture()
def fakeroot(tmp_path):
    root = tmp_path / "tree"
    (root / "core" / "levi").mkdir(parents=True)
    (root / "core" / "levi" / "mod.py").write_text("x = 1\n")
    (root / "README.md").write_text("levi\n")
    (root / ".git" / "objects").mkdir(parents=True)
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (root / "core" / "levi" / "__pycache__").mkdir(parents=True)
    (root / "core" / "levi" / "__pycache__" / "mod.pyc").write_bytes(b"\x00" * 16)
    return root


def _trusted(keydir):
    return S.load_private_key(keydir).public_key().public_bytes_raw()


def test_manifest_skips_junk(fakeroot):
    m = S.build_manifest(fakeroot)
    paths = set(m["files"])
    assert "core/levi/mod.py" in paths
    assert "README.md" in paths
    assert not any(p.startswith(".git/") for p in paths)
    assert not any(p.endswith(".pyc") for p in paths)


def test_manifest_byte_stable(fakeroot):
    assert S.canonical(S.build_manifest(fakeroot)) == S.canonical(
        S.build_manifest(fakeroot)
    )


def test_init_writes_key_and_pub(keydir, tmp_path):
    info = S.init_keypair(keydir)
    priv = keydir / "origin.key"
    assert priv.exists()
    assert info["fingerprint"] == S.fingerprint(
        S.load_private_key(keydir).public_key().public_bytes_raw()
    )
    # repo trust anchor written and matches (autouse fixture restores the real one)
    pub_path = S.repo_pubkey_path()
    assert pub_path.exists()
    assert pub_path.read_text().strip() == (
        S.load_private_key(keydir).public_key().public_bytes_raw().hex()
    )


def test_init_refuses_overwrite(keydir):
    S.init_keypair(keydir)
    before = (keydir / "origin.key").read_bytes()
    with pytest.raises(FileExistsError):
        S.init_keypair(keydir)
    assert (keydir / "origin.key").read_bytes() == before


def test_round_trip_sign_verify(fakeroot, keydir):
    S.init_keypair(keydir)
    out = S.sign_release(fakeroot, keydir, notes="test release")
    env = out["envelope"]
    assert env["descriptor"]["name"] == "LEVI"
    assert env["descriptor"]["origin_chain"] == [
        "Alpha",
        "Omega",
        "Wax",
        "LEVI",
        "Nanobit",
    ]
    assert env["descriptor"]["date_of_invention"] == "2026-04-24"
    assert env["descriptor"]["owner"] == "Chauncey Logan"
    assert env["descriptor"]["notes"] == "test release"
    res = S.verify_release(fakeroot, out["seal"], trusted_pubkey=_trusted(keydir))
    assert res.ok, res.errors
    assert res.files_checked == 2


def test_byte_flip_fails_verification(fakeroot, keydir):
    S.init_keypair(keydir)
    out = S.sign_release(fakeroot, keydir)
    (fakeroot / "core" / "levi" / "mod.py").write_text("x = 2\n")  # one byte flipped
    res = S.verify_release(fakeroot, out["seal"], trusted_pubkey=_trusted(keydir))
    assert not res.ok
    assert res.tampered == ["core/levi/mod.py"]


def test_missing_and_added_detected(fakeroot, keydir):
    S.init_keypair(keydir)
    out = S.sign_release(fakeroot, keydir)
    (fakeroot / "README.md").unlink()
    (fakeroot / "evil.py").write_text("malware\n")
    res = S.verify_release(fakeroot, out["seal"], trusted_pubkey=_trusted(keydir))
    assert not res.ok
    assert res.missing == ["README.md"]
    assert res.added == ["evil.py"]


def test_signature_tamper_fails(fakeroot, keydir):
    S.init_keypair(keydir)
    out = S.sign_release(fakeroot, keydir)
    seal_path = out["seal"]
    env = json.loads(open(seal_path).read())
    env["signature"] = "00" * 64  # forged signature
    open(seal_path, "w").write(json.dumps(env))
    res = S.verify_release(fakeroot, seal_path, trusted_pubkey=_trusted(keydir))
    assert not res.ok
    assert any("SIGNATURE INVALID" in e for e in res.errors)


def test_wrong_signer_fails(fakeroot, keydir, tmp_path, monkeypatch):
    S.init_keypair(keydir)
    out = S.sign_release(fakeroot, keydir)
    other = tmp_path / "otherkeys"
    monkeypatch.setenv("LEVI_SEAL_DIR", str(other))
    S.init_keypair(other)  # a different origin key
    res = S.verify_release(fakeroot, out["seal"], trusted_pubkey=_trusted(other))
    assert not res.ok
    assert any("fingerprint" in e for e in res.errors)


def test_anchor_offline_writes_pending(tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise ConnectionError("no route to host")

    monkeypatch.setattr(S.urllib.request, "urlopen", _boom)
    digest = "ab" * 32
    res = S.anchor_digest(digest, out_dir=tmp_path)
    assert res["status"] == "pending"
    pending = tmp_path / f"{digest}.ots.request"
    assert pending.exists()
    body = json.loads(pending.read_text())
    assert body["digest_sha256"] == digest
    assert "not completed" in res["note"] or "NOT completed" in res["note"]


def test_anchor_success_writes_ots(tmp_path, monkeypatch):
    class _Resp:
        status = 200

        def read(self):
            return b"\x00" * 64

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(S.urllib.request, "urlopen", lambda *a, **k: _Resp())
    digest = "cd" * 32
    res = S.anchor_digest(digest, out_dir=tmp_path)
    assert res["status"] == "anchored"
    assert (tmp_path / f"{digest}.ots").exists()
