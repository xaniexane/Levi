"""Hermetic tests for levi.serve — live localhost server, ephemeral port."""

import threading
import urllib.request
import urllib.error

import pytest

from levi.serve.server import (
    DEFAULT_BIND,
    DEFAULT_PORT,
    guess_mime,
    looks_like_file,
    make_server,
    resolve_path,
)


@pytest.fixture()
def site(tmp_path):
    (tmp_path / "index.html").write_text("<h1>levi home</h1>")
    (tmp_path / "app.js").write_text("console.log(1)")
    (tmp_path / "style.css").write_text("body{}")
    (tmp_path / "data.json").write_text("{}")
    (tmp_path / "icon.svg").write_text("<svg/>")
    sub = tmp_path / "docs"
    sub.mkdir()
    (sub / "index.html").write_text("<h1>docs</h1>")
    return tmp_path


@pytest.fixture()
def server(site):
    srv = make_server(str(site), port=0, bind="127.0.0.1")
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()
    thread.join(timeout=5)


def _get(server, path):
    host, port = server.server_address[:2]
    url = "http://%s:%s%s" % (host, port, path)
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, resp.headers.get("Content-Type"), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()


def test_serves_index_and_mime_types(server):
    status, ctype, body = _get(server, "/index.html")
    assert status == 200
    assert body == b"<h1>levi home</h1>"
    assert ctype.startswith("text/html")

    for path, expected in [
        ("/app.js", "text/javascript"),
        ("/style.css", "text/css"),
        ("/data.json", "application/json"),
        ("/icon.svg", "image/svg+xml"),
    ]:
        status, ctype, _ = _get(server, path)
        assert status == 200, path
        assert ctype.startswith(expected), (path, ctype)


def test_spa_fallback_for_routes(server):
    for route in ["/finance", "/finance/positions", "/some/deep/route"]:
        status, _, body = _get(server, route)
        assert status == 200, route
        assert body == b"<h1>levi home</h1>", route


def test_missing_asset_404s_not_fallback(server):
    # A missing *file* must 404 honestly, never return index.html.
    for path in ["/nope.js", "/missing.png", "/assets/gone.css"]:
        status, _, body = _get(server, path)
        assert status == 404, path
        assert b"levi home" not in body


def test_no_directory_listing(server, site):
    bare = site / "bare"
    bare.mkdir()
    (bare / "secret.txt").write_text("x")
    status, _, _ = _get(server, "/bare")
    assert status == 404
    status, _, _ = _get(server, "/bare/")
    assert status == 404


def test_subdirectory_index(server):
    status, _, body = _get(server, "/docs")
    assert status == 200
    assert body == b"<h1>docs</h1>"


def test_path_traversal_blocked(server):
    status, _, _ = _get(server, "/..%2f..%2fetc%2fpasswd")
    assert status in (403, 404)


def test_head_request(server):
    import http.client

    host, port = server.server_address[:2]
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request("HEAD", "/index.html")
    resp = conn.getresponse()
    assert resp.status == 200
    assert resp.getheader("Content-Type").startswith("text/html")
    assert resp.read() == b""
    conn.close()


def test_localhost_default_bind():
    import inspect

    from levi.serve import server as srv_mod

    sig = inspect.signature(srv_mod.make_server)
    assert sig.parameters["bind"].default == "127.0.0.1"
    assert DEFAULT_BIND == "127.0.0.1"
    assert DEFAULT_PORT == 8742


def test_non_localhost_bind_warns(site, capsys):
    srv = make_server(str(site), port=0, bind="0.0.0.0")
    srv.server_close()
    assert "warning" in capsys.readouterr().err.lower()


def test_make_server_rejects_missing_dir(tmp_path):
    with pytest.raises(ValueError):
        make_server(str(tmp_path / "nope"))


def test_resolve_path_blocks_escape(tmp_path):
    root = str(tmp_path)
    assert resolve_path(root, "/../outside") is None
    assert resolve_path(root, "/sub/../../outside") is None
    assert resolve_path(root, "/index.html") is not None


def test_looks_like_file():
    assert looks_like_file("/app.js")
    assert looks_like_file("/assets/gone.css")
    assert not looks_like_file("/finance")
    assert not looks_like_file("/finance/")
    assert not looks_like_file("/")


def test_guess_mime_overrides():
    assert guess_mime("x.js") == "text/javascript"
    assert guess_mime("x.wasm") == "application/wasm"
    assert guess_mime("x.webmanifest") == "application/manifest+json"
    assert guess_mime("x.html").startswith("text/html")
    assert guess_mime("x.unknownext") == "application/octet-stream"
