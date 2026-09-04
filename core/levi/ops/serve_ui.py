
"""Serve LEVI static interactive UI locally (no cloud)."""
from __future__ import annotations

from pathlib import Path
import http.server
import socketserver
import webbrowser


def find_static() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "static",
        here.parents[2] / "static",
        Path.cwd() / "static",
        Path.cwd().parent / "static",
    ]
    for c in candidates:
        if (c / "index.html").exists() or (c / "levi-ops.html").exists() or (c / "lwp-model.html").exists():
            return c
    return candidates[0]


def serve(port: int = 8765, open_browser: bool = True) -> str:
    static = find_static()
    static.mkdir(parents=True, exist_ok=True)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(static), **k)

        def log_message(self, fmt, *args):
            pass

    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        url = f"http://127.0.0.1:{port}/console.html"
        msg = f"LEVI UI at {url}\nStatic root: {static}\nCtrl+C to stop."
        print(msg)
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            return "stopped"
    return msg
