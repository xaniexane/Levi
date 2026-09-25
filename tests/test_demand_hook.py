"""Law/guard/proof tests for the DemandPulse webhook receiver.

Laws under test:
  H1 localhost-only bind (any other address refused before a socket opens)
  H2 token auth (missing/invalid token refused; fail closed without token)
  H3 bounded body + strict schema (oversized/malformed/invalid -> 4xx)
  H4 ingest via the watcher path (HYPOTHESIS only, source labels kept)
  H5 no outbound fetch capability (structural)

Hermetic: HOME/LEVI_HOME redirected; the server binds 127.0.0.1 on an
ephemeral port and is driven over real HTTP in-process.
"""

import http.client
import json
import threading

import pytest

from levi.demand import hook as hmod
from levi.demand import watcher as wmod
from levi.demand.pulse import DemandPulse

TOKEN = "test-token-123"


@pytest.fixture
def herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi_home"))
    monkeypatch.setenv("DP_HOOK_TOKEN", TOKEN)
    return tmp_path


@pytest.fixture
def server(herm):
    dp = DemandPulse(path=herm / "dp.json")
    st = wmod.WatcherState.load(path=herm / "wstate.json")
    srv = hmod.make_server(port=0, dp=dp, state=st, token=TOKEN)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv, port, dp, st
    srv.shutdown()
    srv.server_close()
    t.join(timeout=5)


def post(port, body, token=TOKEN, path="/signal", raw=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    payload = raw if raw is not None else json.dumps(body).encode()
    conn.request("POST", path, body=payload, headers=headers)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, json.loads(data.decode())


# ------------------------------------------------------------- H1 bind guard


def test_non_loopback_bind_refused():
    with pytest.raises(ValueError):
        hmod.make_server(port=0, bind="0.0.0.0", token=TOKEN)
    with pytest.raises(ValueError):
        hmod.check_bind_address("192.168.1.10")
    hmod.check_bind_address("127.0.0.1")  # the only allowed address


def test_server_actually_listens_on_loopback(server):
    srv, port, _, _ = server
    assert srv.server_address[0] == "127.0.0.1"


# ---------------------------------------------------------------- H2 auth


def test_missing_token_refused(server):
    _, port, _, _ = server
    status, body = post(port, {"items": []}, token=None)
    assert status == 401 and not body["ok"]


def test_wrong_token_refused(server):
    _, port, _, _ = server
    status, _ = post(port, {"items": []}, token="wrong")
    assert status == 401


def test_no_token_env_fails_closed(monkeypatch):
    monkeypatch.delenv("DP_HOOK_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        hmod.make_server(port=0, token=None)


# ------------------------------------------------------- H3 bounds + schema


def test_valid_event_ingested_as_hypothesis(server):
    _, port, dp, _ = server
    status, body = post(port, {"items": [
        {"id": "sms-1", "text": "I need a better shift planner app",
         "channel": "text"},
        {"id": "n-2", "text": "Your package shipped",
         "channel": "notification"},
    ]})
    assert status == 200 and body["ok"]
    assert body["receipt"]["accepted"] == 2
    assert body["receipt"]["signals"] >= 1  # need-sentence mined
    assert all(s.kind == "HYPOTHESIS" for s in dp.signals)
    assert {s.source for s in dp.signals} <= {"text", "notification"}


def test_duplicate_ids_deduped(server):
    _, port, _, _ = server
    event = {"items": [{"id": "dup-1",
                        "text": "I need a calmer inbox app"}]}
    s1, _ = post(port, event)
    s2, b2 = post(port, event)
    assert s1 == 200 and s2 == 200
    assert b2["receipt"]["skipped_seen"] == 1
    assert b2["receipt"]["signals"] == 0


def test_malformed_json_rejected(server):
    _, port, _, _ = server
    status, body = post(port, {}, raw=b"{not json")
    assert status == 400


def test_bad_schema_rejected(server):
    _, port, _, _ = server
    for bad in ({"items": []}, {"items": [{"id": "x"}]},
                {"items": [{"id": "x", "text": "y", "channel": "email"}]},
                {"nope": 1}, ["items"]):
        status, _ = post(port, bad)
        assert status == 422, bad


def test_oversized_body_rejected(server):
    _, port, _, _ = server
    big = {"items": [{"id": "x", "text": "z" * 70000}]}
    status, body = post(port, big)
    assert status == 413


def test_wrong_path_and_method(server):
    _, port, _, _ = server
    status, _ = post(port, {"items": []}, path="/nope")
    assert status == 404
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", "/signal",
                 headers={"Authorization": f"Bearer {TOKEN}"})
    assert conn.getresponse().status == 405
    conn.close()


# ------------------------------------------------- H4/H5 structural proofs


def test_hook_never_imports_alerts_or_outbound():
    src = open(hmod.__file__, encoding="utf-8").read()
    assert "levi.demand.alerts" not in src
    for primitive in ("urlopen", "urlretrieve", "create_connection",
                      "socket.connect", "requests.", "urllib.request"):
        assert primitive not in src, primitive
    assert "threading" not in src  # sequential server: no threads in module


def test_hook_module_has_no_background_threads():
    import threading as _t

    before = set(_t.enumerate())
    hmod.make_server(port=0, token=TOKEN).server_close()
    assert set(_t.enumerate()) - before == set()
