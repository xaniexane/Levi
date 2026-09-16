"""Hermetic tests for levi.ephemera.

No network, no real HOME: every test monkeypatches HOME and the store
resolves paths at call time (EphemeraStore() -> ephemera_home(None) ->
os.path.expanduser("~")). TTL sweeps use ttl=0 so expiry is immediate.
"""

from __future__ import annotations

import json

import pytest

from levi.ephemera import crypto
from levi.ephemera.__main__ import main as cli_main
from levi.ephemera.store import EphemeraError, EphemeraStore

PW = "correct horse battery staple"


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return EphemeraStore()


# --------------------------------------------------------------------------
# crypto unit tests
# --------------------------------------------------------------------------


def test_seal_open_roundtrip():
    key = crypto.derive_key(b"pw", b"salt")
    ct = crypto.seal(key, b"hello secret")
    assert crypto.open_seal(key, ct) == b"hello secret"


def test_seal_randomized():
    key = crypto.derive_key(b"pw", b"salt")
    assert crypto.seal(key, b"x") != crypto.seal(key, b"x")


def test_tamper_rejected():
    key = crypto.derive_key(b"pw", b"salt")
    blob = bytearray(crypto.seal(key, b"secret"))
    blob[20] ^= 1
    with pytest.raises(ValueError):
        crypto.open_seal(key, bytes(blob))


def test_wrong_key_rejected():
    blob = crypto.seal(crypto.derive_key(b"pw", b"salt"), b"secret")
    with pytest.raises(ValueError):
        crypto.open_seal(crypto.derive_key(b"other", b"salt"), blob)


def test_derive_key_deterministic_and_salted():
    k1 = crypto.derive_key(b"pw", b"salt")
    k2 = crypto.derive_key(b"pw", b"salt")
    k3 = crypto.derive_key(b"pw", b"other")
    assert k1 == k2 and k1 != k3


# --------------------------------------------------------------------------
# store tests
# --------------------------------------------------------------------------


def test_create_and_list_channels(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.create_channel("fam", 3600, PW)
    st.create_channel("work", 60, PW)
    assert st.list_channels() == ["fam", "work"]
    with pytest.raises(EphemeraError):
        st.create_channel("fam", 60, PW)  # duplicate


def test_bad_channel_names_rejected(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    with pytest.raises(EphemeraError):
        st.create_channel("../evil", 60, PW)
    with pytest.raises(EphemeraError):
        st.create_channel("x", -1, PW)


def test_post_read_roundtrip(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.create_channel("fam", 3600, PW)
    r = st.post("fam", "chauncey", "dinner at 7?", PW, forwarding_discouraged=True)
    msg = st.read_message("fam", r["id"], PW)
    assert msg["body"] == "dinner at 7?"
    assert msg["forwarding_discouraged"] is True
    assert msg["author"] == "chauncey"


def test_read_wrong_passphrase_fails(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.create_channel("fam", 3600, PW)
    r = st.post("fam", "chauncey", "secret", PW)
    with pytest.raises(ValueError):
        st.read_message("fam", r["id"], "wrong passphrase")


def test_message_bodies_not_plaintext_on_disk(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.create_channel("fam", 3600, PW)
    st.post("fam", "chauncey", "the eagle has landed", PW)
    disk = "".join(
        p.read_text() for p in (tmp_path / ".levi" / "ephemera").rglob("msg_*.json")
    )
    assert "the eagle has landed" not in disk


def test_sweep_deletes_expired_and_receipts_verify(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.create_channel("quick", 0, PW)  # expires immediately
    st.create_channel("slow", 3600, PW)
    r1 = st.post("quick", "a", "bye", PW)
    r2 = st.post("slow", "a", "stays", PW)
    deleted = st.sweep()
    assert {d["id"] for d in deleted} == {r1["id"]}
    # file is gone from disk
    assert not list((tmp_path / ".levi" / "ephemera").rglob("msg_%s.json" % r1["id"]))
    # unexpired message survived
    assert st.read_message("slow", r2["id"], PW)["body"] == "stays"
    # receipt chain verifies
    v = st.verify_receipts("quick")
    assert v["ok"] and v["count"] == 1


def test_receipt_chain_tamper_detected(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.create_channel("quick", 0, PW)
    st.post("quick", "a", "bye", PW)
    st.sweep()
    p = tmp_path / ".levi" / "ephemera" / "channels" / "quick" / "receipts.jsonl"
    lines = p.read_text().splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["event"] = "forged"
    p.write_text(json.dumps(rec) + "\n")
    v = st.verify_receipts("quick")
    assert not v["ok"]


def test_access_log_records_reads(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.create_channel("fam", 3600, PW)
    r = st.post("fam", "a", "hi", PW, forwarding_discouraged=True)
    st.read_message("fam", r["id"], PW, reader="chauncey")
    rows = st.access_log("fam")
    assert len(rows) == 1
    assert rows[0]["reader"] == "chauncey"
    assert "forwarding" in rows[0]["note"]


def test_unknown_channel_errors(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    with pytest.raises(EphemeraError):
        st.post("nope", "a", "x", PW)


# --------------------------------------------------------------------------
# CLI tests
# --------------------------------------------------------------------------


def test_cli_create_post_sweep(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert cli_main(["--passphrase", PW, "create", "q", "--ttl", "0"]) == 0
    assert (
        cli_main(
            ["--passphrase", PW, "post", "q", "--author", "a", "--body", "gone soon"]
        )
        == 0
    )
    assert cli_main(["--passphrase", PW, "sweep", "q"]) == 0
    out = capsys.readouterr().out
    assert "deleted" in out


def test_cli_receipts_verify(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    cli_main(["--passphrase", PW, "create", "q", "--ttl", "0"])
    cli_main(["--passphrase", PW, "post", "q", "--author", "a", "--body", "x"])
    cli_main(["--passphrase", PW, "sweep", "q"])
    assert cli_main(["--passphrase", PW, "receipts", "q"]) == 0
    assert "OK" in capsys.readouterr().out


def test_cli_duplicate_create_fails(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert cli_main(["--passphrase", PW, "create", "q"]) == 0
    assert cli_main(["--passphrase", PW, "create", "q"]) == 1
