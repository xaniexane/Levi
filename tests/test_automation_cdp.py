"""Hermetic tests for the CDP session manager.

No real browser, no network beyond 127.0.0.1, no HOME writes
(configs point at tmp_path). The websocket client is tested against an
in-process raw-socket echo server.
"""

import asyncio
import base64
import hashlib
import socket
import threading

import pytest

from levi.automation.cdp import (
    CDPConfig,
    CDPSession,
    ErrorClass,
    HITLFlag,
    SessionState,
    classify_error,
    ws_connect,
)

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _echo_server():
    """Raw-socket websocket echo server on 127.0.0.1/ephemeral port."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def _read_exact(conn, n):
        data = b""
        while len(data) < n:
            chunk = conn.recv(n - len(data))
            if not chunk:
                raise ConnectionError("closed")
            data += chunk
        return data

    def _send_text(conn, payload: bytes):
        n = len(payload)
        if n < 126:
            head = b"\x81" + bytes([n])
        elif n < 65536:
            head = b"\x81\x7e" + n.to_bytes(2, "big")
        else:
            head = b"\x81\x7f" + n.to_bytes(8, "big")
        conn.sendall(head + payload)

    def run():
        conn, _ = srv.accept()
        try:
            head = b""
            while b"\r\n\r\n" not in head:
                chunk = conn.recv(1024)
                if not chunk:
                    return
                head += chunk
            key = ""
            for line in head.decode("latin1").split("\r\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    key = line.split(":", 1)[1].strip()
            accept = base64.b64encode(
                hashlib.sha1((key + _WS_GUID).encode()).digest()
            ).decode()
            conn.sendall(
                (
                    "HTTP/1.1 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
                ).encode()
            )
            while True:
                b1, b2 = _read_exact(conn, 2)
                opcode = b1 & 0x0F
                length = b2 & 0x7F
                if length == 126:
                    length = int.from_bytes(_read_exact(conn, 2), "big")
                elif length == 127:
                    length = int.from_bytes(_read_exact(conn, 8), "big")
                mask = _read_exact(conn, 4)
                payload = _read_exact(conn, length) if length else b""
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
                if opcode == 0x8:
                    return
                if opcode == 0x9:
                    conn.sendall(b"\x8a\x00")  # pong
                    continue
                _send_text(conn, payload)
        except (ConnectionError, OSError):
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass
            srv.close()

    threading.Thread(target=run, daemon=True).start()
    return port


def _cfg(tmp_path, **kw):
    kw.setdefault("state_file", tmp_path / "cdp" / "session.json")
    return CDPConfig(**kw)


# --- loopback enforcement --------------------------------------------------


def test_non_loopback_host_rejected(tmp_path):
    with pytest.raises(ValueError, match="loopback"):
        _cfg(tmp_path, host="192.168.1.5").validate()


def test_non_loopback_ws_rejected():
    with pytest.raises(ValueError, match="loopback"):
        asyncio.run(ws_connect("10.0.0.1", 9222, "/"))


def test_loopback_hosts_accepted(tmp_path):
    for host in ("127.0.0.1", "::1", "localhost"):
        _cfg(tmp_path, host=host).validate()


def test_bad_port_rejected(tmp_path):
    with pytest.raises(ValueError, match="port"):
        _cfg(tmp_path, port=99999).validate()


# --- error taxonomy --------------------------------------------------------


def test_classify_timeout():
    assert classify_error(asyncio.TimeoutError()) is ErrorClass.TIMEOUT
    assert classify_error(TimeoutError("x")) is ErrorClass.TIMEOUT


def test_classify_captcha_or_auth():
    assert (
        classify_error(RuntimeError("captcha detected")) is ErrorClass.CAPTCHA_OR_AUTH
    )
    assert classify_error(RuntimeError("login required")) is ErrorClass.CAPTCHA_OR_AUTH
    assert classify_error(RuntimeError("2fa challenge")) is ErrorClass.CAPTCHA_OR_AUTH


def test_classify_session_lost():
    assert classify_error(ConnectionError("reset")) is ErrorClass.SESSION_LOST


def test_classify_unknown():
    assert classify_error(RuntimeError("weird")) is ErrorClass.UNKNOWN


# --- stdlib websocket round-trip -------------------------------------------


def test_ws_roundtrip_echo():
    port = _echo_server()

    async def go():
        ws = await ws_connect("127.0.0.1", port, "/")
        await ws.send_text("hello-levi")
        assert await ws.recv_text() == "hello-levi"
        await ws.ping()
        await ws.send_text("after-ping")
        assert await ws.recv_text() == "after-ping"  # pong skipped cleanly
        await ws.close()
        assert ws.closed is True

    asyncio.run(go())


def test_ws_large_payload():
    port = _echo_server()
    big = "x" * 5000

    async def go():
        ws = await ws_connect("127.0.0.1", port, "/")
        await ws.send_text(big)
        assert await ws.recv_text() == big
        await ws.close()

    asyncio.run(go())


# --- HITL flag file ----------------------------------------------------------


def test_hitl_flag_choice(tmp_path):
    flag = HITLFlag(tmp_path)

    async def go():
        async def answer():
            await asyncio.sleep(0.2)
            flag.flag_file.write_text("retry")

        task = asyncio.create_task(answer())
        choice = await flag.request(
            "T", "B", options=["continue", "abort", "retry"], timeout_sec=10
        )
        await task
        return choice

    assert asyncio.run(go()) == "retry"
    assert not flag.flag_file.exists()  # consumed
    assert flag.message_file.exists()


def test_hitl_timeout_is_not_approval(tmp_path):
    flag = HITLFlag(tmp_path)

    async def go():
        return await flag.request("T", "B", timeout_sec=0.05)

    assert asyncio.run(go()) == "timeout"


def test_hitl_clear(tmp_path):
    flag = HITLFlag(tmp_path)
    flag.flag_file.write_text("x")
    flag.message_file.write_text("y")
    flag.clear()
    assert not flag.flag_file.exists()
    assert not flag.message_file.exists()


# --- session state machine ---------------------------------------------------


def test_send_in_bad_state_raises(tmp_path):
    sess = CDPSession(_cfg(tmp_path))
    assert sess.state is SessionState.DISCONNECTED
    with pytest.raises(RuntimeError, match="bad state"):
        asyncio.run(sess.send("Page.enable"))


def test_recover_dead_port_requires_hitl(tmp_path):
    sess = CDPSession(_cfg(tmp_path, port=1, max_retries=1, base_backoff_sec=0.01))

    async def go():
        return await sess.recover()

    res = asyncio.run(go())
    assert res.success is False
    assert res.required_hitl is True


def test_ws_url_parts():
    host, port, path = CDPSession._ws_parts("ws://127.0.0.1:9222/devtools/page/ABC")
    assert (host, port, path) == ("127.0.0.1", 9222, "/devtools/page/ABC")


def test_save_state_never_auth_shaped(tmp_path):
    sess = CDPSession(_cfg(tmp_path))
    sess.session_id = "s-1"
    sess._save_state()
    import json

    data = json.loads((tmp_path / "cdp" / "session.json").read_text())
    blob = json.dumps(data).lower()
    for needle in ("cookie", "password", "token", "bearer", "auth"):
        assert needle not in blob
