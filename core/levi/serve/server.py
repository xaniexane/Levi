"""LEVI-native static file server — stdlib only.

Serves a directory over HTTP with:

- SPA fallback: routes that do not resolve to a file fall back to
  ``index.html`` (missing *assets* — paths that look like files — 404
  honestly instead of returning HTML).
- Correct MIME types (incl. ``.js``, ``.wasm``, ``.webmanifest``).
- No directory listing, ever.
- Request log to stderr.
- Localhost-first: default bind is ``127.0.0.1``; binding anywhere else
  prints an honest warning.

This is the pure self-reliant half of LEVI's hosting story (see
``docs/HOSTING.md``): on LEVI's own server the platform branding injector
never runs, so the "Created with Grok / Remix" pill simply never exists.
"""

from __future__ import annotations

import argparse
import mimetypes
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 8742
DEFAULT_BIND = "127.0.0.1"
_LOCAL_BINDS = {"127.0.0.1", "::1", "localhost"}

# mimetypes misses a few that matter for web apps; be explicit.
_MIME_OVERRIDES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".wasm": "application/wasm",
    ".webmanifest": "application/manifest+json",
    ".json": "application/json",
    ".svg": "image/svg+xml",
}


def guess_mime(path: str) -> str:
    """MIME type for *path*, with explicit overrides for web-app types."""
    ext = os.path.splitext(path)[1].lower()
    if ext in _MIME_OVERRIDES:
        return _MIME_OVERRIDES[ext]
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def looks_like_file(url_path: str) -> bool:
    """True when the last path segment has a file extension.

    Used to keep SPA fallback honest: a missing ``/app.js`` is a 404,
    while a missing ``/finance`` is a route and falls back to index.html.
    """
    last = url_path.rstrip("/").rsplit("/", 1)[-1]
    return "." in last and not last.startswith(".")


def resolve_path(root: str, url_path: str) -> str | None:
    """Resolve *url_path* under *root*; None on traversal outside root."""
    rel = urllib.parse.unquote(url_path.split("?", 1)[0].split("#", 1)[0])
    rel = rel.lstrip("/")
    candidate = os.path.realpath(os.path.join(root, rel))
    if candidate != root and not candidate.startswith(root + os.sep):
        return None
    return candidate


class ServeHandler(BaseHTTPRequestHandler):
    server_version = "LEVI-Serve/1"
    protocol_version = "HTTP/1.1"

    #: set by :func:`make_server`
    directory: str = os.getcwd()

    def log_message(self, fmt, *args):  # noqa: A002 - stdlib signature
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))
        sys.stderr.flush()

    def _send_file(self, path: str, head_only: bool = False) -> None:
        try:
            size = os.path.getsize(path)
            with open(path, "rb") as fh:
                body = b"" if head_only else fh.read()
        except OSError:
            self.send_error(404, "Not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", guess_mime(path))
        self.send_header("Content-Length", str(0 if head_only else size))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _handle(self, head_only: bool = False) -> None:
        root = os.path.realpath(self.directory)
        target = resolve_path(root, self.path)
        if target is None:
            self.send_error(403, "Forbidden")
            return

        # Exact file hit.
        if os.path.isfile(target):
            self._send_file(target, head_only)
            return

        # Directory with its own index.html.
        if os.path.isdir(target):
            index = os.path.join(target, "index.html")
            if os.path.isfile(index):
                self._send_file(index, head_only)
                return
            # No directory listing, ever.
            self.send_error(404, "Not found")
            return

        # SPA fallback for routes; honest 404 for missing assets.
        fallback = os.path.join(root, "index.html")
        if not looks_like_file(self.path) and os.path.isfile(fallback):
            self._send_file(fallback, head_only)
            return
        self.send_error(404, "Not found")

    def do_GET(self) -> None:
        self._handle(head_only=False)

    def do_HEAD(self) -> None:
        self._handle(head_only=True)


def make_server(
    directory: str, port: int = DEFAULT_PORT, bind: str = DEFAULT_BIND
) -> ThreadingHTTPServer:
    """Build (not start) the server. Warns honestly on non-localhost bind."""
    root = os.path.realpath(os.path.abspath(directory))
    if not os.path.isdir(root):
        raise ValueError("not a directory: %s" % directory)
    if bind not in _LOCAL_BINDS:
        sys.stderr.write(
            "warning: levi serve binding to %s — this exposes your files "
            "to the network. Localhost-first default is %s.\n" % (bind, DEFAULT_BIND)
        )
        sys.stderr.flush()

    class BoundHandler(ServeHandler):
        directory = root

    return ThreadingHTTPServer((bind, port), BoundHandler)


def serve_forever(
    directory: str = ".", port: int = DEFAULT_PORT, bind: str = DEFAULT_BIND
) -> int:
    """Serve *directory* until interrupted. Returns process exit code."""
    server = make_server(directory, port, bind)
    host, bound_port = server.server_address[:2]
    sys.stderr.write(
        "levi serve: %s on http://%s:%s/ (Ctrl-C to stop)\n"
        % (os.path.realpath(directory), host, bound_port)
    )
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Shared argparse parser for ``python -m levi.serve`` and ``levi serve``."""
    p = argparse.ArgumentParser(
        prog="levi serve",
        description="Serve a static directory over HTTP (LEVI-native, stdlib-only).",
    )
    p.add_argument("--dir", default=".", help="directory to serve (default: cwd)")
    p.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="port (default: 8742)"
    )
    p.add_argument(
        "--bind",
        default=DEFAULT_BIND,
        help="bind address (default: 127.0.0.1; non-localhost warns)",
    )
    return p


def cmd_serve(args: argparse.Namespace) -> int:
    """``levi serve`` dispatch entrypoint."""
    return serve_forever(
        directory=getattr(args, "dir", ".") or ".",
        port=int(getattr(args, "port", DEFAULT_PORT) or DEFAULT_PORT),
        bind=getattr(args, "bind", DEFAULT_BIND) or DEFAULT_BIND,
    )


def register_serve_parser(sub) -> None:
    """Register the ``serve`` subparser on a ``levi`` subparsers action."""
    parser = build_parser()
    serve_p = sub.add_parser(
        "serve",
        help="Serve a static directory over HTTP (LEVI-native)",
        description=parser.description,
    )
    serve_p.add_argument("--dir", default=".", help="directory to serve (default: cwd)")
    serve_p.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="port (default: 8742)"
    )
    serve_p.add_argument(
        "--bind",
        default=DEFAULT_BIND,
        help="bind address (default: 127.0.0.1; non-localhost warns)",
    )
