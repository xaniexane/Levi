"""Hermetic tests for revival.plan9 (namespaces + 9P-style IPC).

No network (socketpair is loopback-local), no HOME dependence, deterministic.
Subprocess tools used are POSIX basics (sh/echo/env/pwd/sleep) available in
the sandbox; tests skip gracefully if missing.
"""

import os
import shutil
import threading
import time

import pytest

from core.levi.revival import plan9


SH = shutil.which("sh")
ECHO = shutil.which("echo") or "echo"


# ===========================================================================
# (a) Namespace
# ===========================================================================


def test_run_captures_output_and_returncode():
    with plan9.Namespace() as ns:
        r = ns.run([SH, "-c", "echo hello-stdout; echo hello-stderr >&2; exit 3"])
    assert r.returncode == 3
    assert r.stdout.strip() == "hello-stdout"
    assert r.stderr.strip() == "hello-stderr"
    assert not r.timed_out


def test_cwd_is_restricted_to_namespace_root():
    with plan9.Namespace() as ns:
        r = ns.run([SH, "-c", "pwd"])
    assert os.path.realpath(r.stdout.strip()) == os.path.realpath(ns.root)


def test_explicit_root_is_used():
    import tempfile

    root = tempfile.mkdtemp(prefix="levi-ns-test-")
    try:
        with plan9.Namespace(root=root) as ns:
            assert ns.root == root
            r = ns.run([SH, "-c", "pwd"])
            assert os.path.realpath(r.stdout.strip()) == os.path.realpath(root)
        assert os.path.isdir(root)  # explicit roots are NOT deleted
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_env_is_scrubbed_by_default():
    os.environ["LEVI_TEST_SECRET_MARKER"] = "should-not-leak"
    try:
        with plan9.Namespace() as ns:
            r = ns.run([SH, "-c", 'echo "marker=${LEVI_TEST_SECRET_MARKER:-absent}"'])
        assert "marker=absent" in r.stdout
    finally:
        del os.environ["LEVI_TEST_SECRET_MARKER"]


def test_env_allowlist_passes_selected_vars():
    os.environ["LEVI_TEST_PASS_THROUGH"] = "visible"
    try:
        with plan9.Namespace(env_allow=("LEVI_TEST_PASS_THROUGH",)) as ns:
            r = ns.run([SH, "-c", 'echo "v=${LEVI_TEST_PASS_THROUGH:-absent}"'])
        assert "v=visible" in r.stdout
    finally:
        del os.environ["LEVI_TEST_PASS_THROUGH"]


def test_explicit_env_is_used_verbatim():
    with plan9.Namespace(env={"PATH": "/usr/bin:/bin", "CUSTOM": "yes"}) as ns:
        r = ns.run([SH, "-c", 'echo "c=${CUSTOM:-no}"'])
    assert "c=yes" in r.stdout


def test_timeout_kills_tool():
    with plan9.Namespace(timeout=30) as ns:
        start = time.monotonic()
        with pytest.raises(plan9.NamespaceTimeout):
            ns.run([SH, "-c", "sleep 30"], timeout=0.5)
        elapsed = time.monotonic() - start
    assert elapsed < 10  # killed promptly, did not wait out the sleep


def test_stdin_input_is_piped():
    with plan9.Namespace() as ns:
        r = ns.run([SH, "-c", "cat"], input="piped-data\n")
    assert r.stdout == "piped-data\n"


def test_write_and_read_file_inside_root():
    with plan9.Namespace() as ns:
        path = ns.write_file("sub/input.txt", "payload")
        assert path.startswith(ns.root)
        r = ns.run([SH, "-c", "cat sub/input.txt"])
        assert r.stdout == "payload"
        assert ns.read_file("sub/input.txt") == "payload"


def test_path_escape_rejected():
    with plan9.Namespace() as ns:
        with pytest.raises(plan9.NamespaceError):
            ns.write_file("../../escape.txt", "nope")
        with pytest.raises(plan9.NamespaceError):
            ns.read_file("../../escape.txt")


def test_auto_root_cleaned_up():
    ns = plan9.Namespace()
    root = ns.root
    assert os.path.isdir(root)
    ns.close()
    assert not os.path.exists(root)


def test_resource_limits_accepted_and_run():
    # RLIMIT_AS may be unavailable; the run must work either way.
    with plan9.Namespace(cpu_seconds=10, mem_bytes=512 * 1024 * 1024) as ns:
        r = ns.run([ECHO, "ok"])
    assert r.stdout.strip() == "ok"
    assert r.returncode == 0


def test_closed_namespace_refuses_run():
    ns = plan9.Namespace()
    ns.close()
    with pytest.raises(plan9.NamespaceError):
        ns.run([ECHO, "x"])


# ===========================================================================
# (b) 9P-style message surface
# ===========================================================================


def test_request_response_round_trip():
    client, server = plan9.create_channel()
    done = threading.Event()

    def handler(msg_type, payload):
        assert msg_type == "ping"
        done.set()
        return {"pong": payload}

    t = threading.Thread(target=plan9.serve, args=(server, handler), daemon=True)
    t.start()
    try:
        reply = client.request("ping", {"n": 1}, timeout=5)
        assert reply == {"pong": {"n": 1}}
        assert done.is_set()
    finally:
        client.close()
        t.join(timeout=5)


def test_handler_exception_becomes_error_reply():
    client, server = plan9.create_channel()

    def handler(msg_type, payload):
        raise ValueError("handler blew up")

    t = threading.Thread(target=plan9.serve, args=(server, handler), daemon=True)
    t.start()
    try:
        with pytest.raises(plan9.ChannelError, match="handler blew up"):
            client.request("ping", None, timeout=5)
    finally:
        client.close()
        t.join(timeout=5)


def test_unknown_message_type_refused():
    client, server = plan9.create_channel()
    t = threading.Thread(
        target=plan9.serve,
        args=(server, lambda mt, p: None),
        kwargs={"request_types": {"known"}},
        daemon=True,
    )
    t.start()
    try:
        with pytest.raises(plan9.ChannelError, match="unknown message type"):
            client.request("bogus", None, timeout=5)
        assert client.request("known", {"a": 1}, timeout=5) is None
    finally:
        client.close()
        t.join(timeout=5)


def test_one_way_send_and_recv():
    client, server = plan9.create_channel()
    try:
        msg_id = client.send("notify", {"event": "x"})
        assert isinstance(msg_id, str) and msg_id
        msg_type, payload, got_id = server.recv(timeout=5)
        assert (msg_type, payload, got_id) == ("notify", {"event": "x"}, msg_id)
    finally:
        client.close()
        server.close()


def test_request_timeout():
    client, server = plan9.create_channel()
    # Server side never responds: request must time out, not hang.
    try:
        with pytest.raises(plan9.ChannelTimeout):
            client.request("ping", None, timeout=0.3)
    finally:
        client.close()
        server.close()


def test_serve_in_background_helper():
    served = plan9.serve_in_background(lambda mt, p: f"echo:{p}")
    try:
        assert served.client.request("anything", "hi", timeout=5) == "echo:hi"
    finally:
        served.stop()


def test_out_of_order_replies_are_buffered():
    client, server = plan9.create_channel()
    # Manually interleave: send a one-way, then a request; server answers the
    # request while the one-way stays queued, then we still receive it.
    server.send("note", "first")
    _req_id_holder = {}

    def responder():
        msg_type, payload, msg_id = server.recv(timeout=5)
        assert msg_type == "do"
        server._send_frame(
            {
                "id": "r1",
                "type": "reply",
                "in_reply_to": msg_id,
                "ok": True,
                "payload": "done",
                "error": None,
            }
        )

    t = threading.Thread(target=responder, daemon=True)
    t.start()
    try:
        assert client.request("do", None, timeout=5) == "done"
        # The earlier one-way message was buffered, not lost:
        msg_type, payload, _ = client.recv(timeout=5)
        assert (msg_type, payload) == ("note", "first")
    finally:
        client.close()
        t.join(timeout=5)


def test_stop_serving_ends_loop():
    client, server = plan9.create_channel()

    def handler(msg_type, payload):
        raise plan9.StopServing()

    t = threading.Thread(target=plan9.serve, args=(server, handler), daemon=True)
    t.start()
    try:
        client.request("quit", None, timeout=5)  # StopServing still replies ok
    finally:
        client.close()
        t.join(timeout=5)
    assert not t.is_alive()
