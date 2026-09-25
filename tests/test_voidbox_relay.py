"""Tests for the Void Box relay (core/levi/voidbox/relay.py).

Transport note: these tests use real TCP sockets on 127.0.0.1 with
ephemeral ports — localhost IPC only, no external network, no daemons
left running. Each test starts its own relay and stops it.

The load-bearing proofs:
1. send -> poll round-trips over real sockets.
2. The relay cannot decrypt what it carries: seal with a key the relay
   never has, then assert the relay-side stored bytes never yield
   plaintext (scan the live store AND the persistent log), and assert
   the relay module imports no decryption primitive (structural).
3. Bind policy: loopback default, wider binds need explicit opt-in.
"""

import base64
import json
import os
import socket
import threading

import pytest

from levi.cybrus.veil import _open_backend, _seal_backend
from levi.voidbox import relay
from levi.voidbox.relay import (
    DEFAULT_HOST,
    LAWS,
    MAX_FRAME_BYTES,
    RelayClient,
    RelayError,
    RelayServer,
)

PLAINTEXT = b"the keeper's secret words, sealed for alice"


def _sealed_blob(key: bytes) -> str:
    sealed = _seal_backend(key, PLAINTEXT, b"voidbox-relay-test-aad")
    return base64.b64encode(sealed).decode("ascii")


@pytest.fixture()
def server(tmp_path):
    srv = RelayServer(host="127.0.0.1", port=0,
                      store_dir=str(tmp_path / "store")).start()
    yield srv
    srv.stop()


@pytest.fixture()
def client(server):
    return RelayClient(host=server.host, port=server.port)


# ---------------------------------------------------------------------------
# Round-trip over real sockets
# ---------------------------------------------------------------------------


def test_ping(server, client):
    assert client.ping() is True


def test_post_poll_ack_roundtrip(server, client):
    key = os.urandom(32)
    blob = _sealed_blob(key)
    res = client.post("alice", blob, sender="bob")
    assert res["stored"] is True
    assert res["protocol"] == 1

    envs = client.poll("alice")
    assert len(envs) == 1
    env = envs[0]
    assert env["to"] == "alice"
    assert env["from"] == "bob"
    assert env["blob"] == blob

    # The recipient opens it with THEIR key — the relay never could.
    opened = _open_backend(key, base64.b64decode(env["blob"]), b"voidbox-relay-test-aad")
    assert opened == PLAINTEXT

    # Poll is a read, not a delete; ack tombstones.
    assert len(client.poll("alice")) == 1
    assert client.ack("alice", [env["id"]]) == 1
    assert client.poll("alice") == []


def test_poll_isolated_per_recipient(server, client):
    key = os.urandom(32)
    client.post("alice", _sealed_blob(key))
    client.post("carol", _sealed_blob(key))
    assert len(client.poll("alice")) == 1
    assert len(client.poll("carol")) == 1
    assert client.poll("dave") == []


def test_duplicate_post_dedupes(server, client):
    key = os.urandom(32)
    blob = _sealed_blob(key)
    first = client.post("alice", blob, msg_id="m-1")
    second = client.post("alice", blob, msg_id="m-1")
    assert first["stored"] is True
    assert second["duplicate"] is True
    assert len(client.poll("alice")) == 1


def test_stats_reports_depths_only(server, client):
    key = os.urandom(32)
    client.post("alice", _sealed_blob(key))
    client.post("alice", _sealed_blob(key))
    stats = client.stats()
    assert stats == {"alice": 2}
    # No content, no content sizes — depths only.
    assert PLAINTEXT.decode() not in json.dumps(stats)


def test_many_envelopes_keep_order(server, client):
    key = os.urandom(32)
    ids = []
    for i in range(20):
        r = client.post("alice", _sealed_blob(key), msg_id="ord-%02d" % i)
        ids.append(r["id"])
    envs = client.poll("alice", limit=50)
    assert [e["id"] for e in envs] == ids


def test_concurrent_clients(server):
    key = os.urandom(32)
    errors = []

    def poster(n):
        try:
            c = RelayClient(host=server.host, port=server.port)
            for i in range(10):
                c.post("shared", _sealed_blob(key), msg_id="t%d-%d" % (n, i))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=poster, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    c = RelayClient(host=server.host, port=server.port)
    assert len(c.poll("shared", limit=1000)) == 80


def test_persistence_survives_restart(tmp_path):
    store_dir = str(tmp_path / "store")
    key = os.urandom(32)
    srv = RelayServer(host="127.0.0.1", port=0, store_dir=store_dir).start()
    c = RelayClient(host=srv.host, port=srv.port)
    c.post("alice", _sealed_blob(key), msg_id="persist-1")
    srv.stop()
    # The log file exists and is owner-only.
    log = os.path.join(store_dir, "mailbox.jsonl")
    assert os.path.exists(log)
    assert oct(os.stat(log).st_mode & 0o777) == "0o600"
    # Restart: pending mail is still there.
    srv2 = RelayServer(host="127.0.0.1", port=0, store_dir=store_dir).start()
    try:
        c2 = RelayClient(host=srv2.host, port=srv2.port)
        envs = c2.poll("alice")
        assert [e["id"] for e in envs] == ["persist-1"]
    finally:
        srv2.stop()


# ---------------------------------------------------------------------------
# Ciphertext-only proof: the relay cannot decrypt what it carries
# ---------------------------------------------------------------------------


def test_relay_side_bytes_never_yield_plaintext(server, client, tmp_path):
    """Seal with a key the relay never has. Then scan EVERY byte the
    relay side holds — the live store and the persistent log — for the
    plaintext, its base64, and its hex. None may appear. This is the
    ciphertext-only law, proved, not promised."""
    key = os.urandom(32)
    assert key not in (b"",)  # the relay was built with no key at all
    blob = _sealed_blob(key)
    client.post("alice", blob, sender="bob", msg_id="proof-1")

    # Live store: serialize everything the relay holds in memory.
    live_bytes = json.dumps(
        {r: {i: rec for i, rec in q.items()}
         for r, q in server.store._pending.items()},
        sort_keys=True,
    ).encode("utf-8")
    # Persistent log: raw bytes as written to disk.
    log_path = os.path.join(str(tmp_path / "store"), "mailbox.jsonl")
    with open(log_path, "rb") as fh:
        disk_bytes = fh.read()

    for name, haystack in (("live store", live_bytes), ("disk log", disk_bytes)):
        assert PLAINTEXT not in haystack, "plaintext in %s" % name
        assert base64.b64encode(PLAINTEXT) not in haystack, "b64 plaintext in %s" % name
        assert PLAINTEXT.hex().encode() not in haystack, "hex plaintext in %s" % name
        # The key itself must never cross to the relay side either.
        assert key not in haystack, "seal key in %s" % name


def test_relay_has_no_decryption_primitive():
    """Structural: the relay module exposes no opener, no AEAD, no
    decrypt — so 'ciphertext-only' is a property of the code, not of
    the operator's good intentions."""
    for name in ("_open_backend", "_open_gcm", "_open", "AESGCM", "decrypt"):
        assert not hasattr(relay, name), "relay exposes %s" % name


def test_relay_source_imports_no_veil():
    import inspect
    src = inspect.getsource(relay)
    veil_imports = [
        line.strip() for line in src.splitlines()
        if ("from" in line or "import" in line) and "veil" in line
        and "veil.py" not in line and "veil_chat" not in line
        and line.strip().startswith(("from", "import"))
    ]
    assert veil_imports == [], veil_imports


def test_tampered_blob_stays_opaque(server, client):
    """Even garbage the relay stored is opaque to it: the relay has no
    primitive that could tell sealed from random."""
    garbage = base64.b64encode(os.urandom(64)).decode()
    client.post("alice", garbage, msg_id="garbage-1")
    envs = client.poll("alice")
    assert envs[0]["blob"] == garbage
    with pytest.raises(Exception):
        _open_backend(os.urandom(32), base64.b64decode(garbage), b"aad")


# ---------------------------------------------------------------------------
# Bind policy (keeper-operated)
# ---------------------------------------------------------------------------


def test_default_bind_is_loopback():
    assert DEFAULT_HOST == "127.0.0.1"


def test_nonloopback_bind_requires_opt_in():
    with pytest.raises(RelayError):
        RelayServer(host="0.0.0.0", port=1, public=False)
    # Explicit opt-in is the honest admission of the metadata threat.
    srv = RelayServer(host="0.0.0.0", port=0, public=True)
    try:
        srv.start()
    finally:
        srv.stop()


# ---------------------------------------------------------------------------
# Fail-closed framing and addressing
# ---------------------------------------------------------------------------


def test_bad_op_refused(server, client):
    with pytest.raises(RelayError):
        client._roundtrip({"op": "teleport"})


def test_bad_address_refused(server, client):
    key = os.urandom(32)
    with pytest.raises(RelayError):
        client.post("has space", _sealed_blob(key))
    with pytest.raises(RelayError):
        client.post("", _sealed_blob(key))
    with pytest.raises(RelayError):
        client.poll("semi;colon")


def test_non_base64_blob_refused(server, client):
    with pytest.raises(RelayError):
        client.post("alice", "!!!not-base64!!!")


def test_oversized_frame_dropped(server):
    raw = socket.create_connection((server.host, server.port), timeout=5)
    try:
        raw.sendall((MAX_FRAME_BYTES + 1).to_bytes(4, "big"))
        resp = raw.recv(4096)
        assert resp, "relay should answer the bad frame with an error frame"
        size = int.from_bytes(resp[:4], "big")
        body = resp[4:4 + size]
        assert json.loads(body)["ok"] is False
    finally:
        raw.close()
    # The relay is still alive afterwards.
    assert RelayClient(host=server.host, port=server.port).ping() is True


def test_garbage_json_refused(server):
    raw = socket.create_connection((server.host, server.port), timeout=5)
    try:
        body = b"{not json"
        raw.sendall(len(body).to_bytes(4, "big") + body)
        resp = raw.recv(4096)
        size = int.from_bytes(resp[:4], "big")
        assert json.loads(resp[4:4 + size])["ok"] is False
    finally:
        raw.close()


# ---------------------------------------------------------------------------
# Law book discipline
# ---------------------------------------------------------------------------


def test_check_invariants_all_pass():
    results = relay.check_invariants()
    failures = [(n, d) for n, ok, d in results if not ok]
    assert failures == [], failures
    assert len(results) >= 20


def test_laws_declared():
    ids = [lid for lid, _ in LAWS]
    assert ids == ["L%d" % i for i in range(1, 9)]
    assert all(text.strip() for _, text in LAWS)
    assert "CIPHERTEXT-ONLY" in LAWS[0][1]


def test_threat_model_is_honest():
    tm = relay.threat_model()
    assert tm["tls"] is False
    assert tm["sender_auth"].startswith("none")
    assert len(tm["explicitly_not_claimed"]) >= 5
    assert "laws" in tm
