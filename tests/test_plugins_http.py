"""Hermetic tests for the LEVI-native stdlib HTTP helper.

No external network: a local ``http.server`` on 127.0.0.1 serves canned
responses in a background thread. No randomness, no HOME writes.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from levi.plugins.http import (
    ApiError,
    HttpClient,
    NetworkError,
    ResponseParseError,
    parse_url_host,
)


class _Handler(BaseHTTPRequestHandler):
    routes = {
        ("/json", "GET"): (
            200,
            {"Content-Type": "application/json; charset=utf-8"},
            b'{"ok": true, "n": 3}',
        ),
        ("/text", "GET"): (
            200,
            {"Content-Type": "text/plain"},
            b"hello world",
        ),
        ("/empty", "GET"): (204, {}, b""),
        ("/echo-headers", "GET"): (200, {"Content-Type": "application/json"}, None),
        ("/created", "POST"): (
            201,
            {"Content-Type": "application/json"},
            b'{"id": 9}',
        ),
        ("/bad-json", "GET"): (
            200,
            {"Content-Type": "application/json"},
            b"{nope",
        ),
        ("/boom", "GET"): (
            422,
            {"Content-Type": "application/json"},
            b'{"detail": "bad input"}',
        ),
        ("/boom-text", "GET"): (500, {"Content-Type": "text/plain"}, b"kaput"),
        ("/bom", "GET"): (
            200,
            {"Content-Type": "application/json"},
            b'\xef\xbb\xbf{"bom": true}',
        ),
    }

    def _serve(self):
        route = self.routes.get((self.path.split("?")[0], self.command))
        if route is None:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"missing")
            return
        status, headers, body = route
        length = 0
        if self.path == "/echo-headers" and self.command == "GET":
            payload = {
                "authorization": self.headers.get("Authorization"),
                "x-custom": self.headers.get("X-Custom"),
            }
            body = json.dumps(payload).encode()
            length = len(body)
        elif body:
            length = len(body)
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(length))
        self.end_headers()
        if body:
            self.wfile.write(body)
        # drain any request body so the connection stays clean
        clen = int(self.headers.get("Content-Length") or 0)
        if clen:
            self.rfile.read(clen)

    do_GET = _serve
    do_POST = _serve

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    thread.join(timeout=5)


def _client(server, **kw):
    return HttpClient(base_url=server, **kw)


def test_get_json_auto(server):
    assert _client(server).get("/json") == {"ok": True, "n": 3}


def test_get_text_auto(server):
    assert _client(server).get("/text") == "hello world"


def test_empty_body_returns_none(server):
    assert _client(server).get("/empty") is None


def test_bom_stripped(server):
    assert _client(server).get("/bom") == {"bom": True}


def test_post_json_body(server):
    assert _client(server).post("/created", json_body={"a": 1}) == {"id": 9}


def test_get_with_params(server):
    # query string passes through; route matches on path
    assert _client(server).get("/json", params={"q": "x"}) == {"ok": True, "n": 3}


def test_forced_text_mode(server):
    assert _client(server).get("/json", response="text") == '{"ok": true, "n": 3}'


def test_forced_bytes_mode(server):
    assert _client(server).get("/text", response="bytes") == b"hello world"


def test_malformed_json_raises_parse_error(server):
    with pytest.raises(ResponseParseError) as ei:
        _client(server).get("/bad-json")
    assert ei.value.status == 200
    assert ei.value.raw_body == "{nope"


def test_http_error_carries_status_and_data(server):
    with pytest.raises(ApiError) as ei:
        _client(server).get("/boom")
    err = ei.value
    assert err.status == 422
    assert err.data == {"detail": "bad input"}
    assert err.method == "GET"
    assert "bad input" in str(err)


def test_http_error_text_body(server):
    with pytest.raises(ApiError) as ei:
        _client(server).get("/boom-text")
    assert ei.value.data == "kaput"
    assert "kaput" in str(ei.value)


def test_404_raises_api_error(server):
    with pytest.raises(ApiError) as ei:
        _client(server).get("/nope")
    assert ei.value.status == 404


def test_bearer_token_attached(server):
    client = _client(server, auth_token_getter=lambda: "sekret-token")
    echoed = client.get("/echo-headers")
    assert echoed["authorization"] == "Bearer sekret-token"


def test_no_token_no_header(server):
    echoed = _client(server).get("/echo-headers")
    assert echoed["authorization"] is None


def test_explicit_authorization_header_wins(server):
    client = _client(server, auth_token_getter=lambda: "sekret-token")
    echoed = client.get("/echo-headers", headers={"Authorization": "Bearer other"})
    assert echoed["authorization"] == "Bearer other"


def test_custom_header_passes_through(server):
    echoed = _client(server).get("/echo-headers", headers={"X-Custom": "yes"})
    assert echoed["x-custom"] == "yes"


def test_base_url_prepends_relative_paths(server):
    client = _client(server)
    assert client.resolve_url("/json") == server + "/json"
    # absolute URLs pass through untouched
    assert client.resolve_url("https://example.com/x") == "https://example.com/x"


def test_no_base_url_passes_through():
    client = HttpClient()
    assert client.resolve_url("/json") == "/json"


def test_get_with_body_rejected():
    with pytest.raises(ValueError, match="cannot carry a body"):
        HttpClient().request("GET", "http://x/", json_body={})


def test_bad_response_mode_rejected(server):
    with pytest.raises(ValueError, match="unknown response mode"):
        _client(server).get("/json", response="xml")


def test_network_error_on_refused():
    client = HttpClient(base_url="http://127.0.0.1:1")  # nothing listens
    with pytest.raises(NetworkError):
        client.get(
            "/json",
        )


def test_parse_url_host():
    assert parse_url_host("https://example.com/a?b=1") == ("https", "example.com")
    with pytest.raises(ValueError):
        parse_url_host("ftp://example.com/x")
    with pytest.raises(ValueError):
        parse_url_host("not a url")


def test_client_validates_constructor():
    with pytest.raises(ValueError):
        HttpClient(timeout=0)
    with pytest.raises(ValueError):
        HttpClient(auth_token_getter="nope")
    with pytest.raises(ValueError):
        HttpClient().resolve_url("")
