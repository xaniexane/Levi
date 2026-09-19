"""Local broadcast serving for teletext pages, stdlib-only.

``serve(store)`` starts a ThreadingHTTPServer on 127.0.0.1 that renders
the page store:

- ``/``            the index (page 100 if present, else a listing)
- ``/<number>``   that numbered page as plain text in the 40x24 grid
- ``/carousel``    advances the carousel one page and renders it — the
                   sushi conveyor belt, one step per request

Nothing leaves localhost. No accounts, no tracking, no cookies.
"""

from __future__ import annotations

import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator, Optional, Tuple

from levi.teletext.pages import Page, PageStore, render_frame

__all__ = ["serve", "build_local_pages", "index_page"]

PAGE_RE = re.compile(r"^/(\d{3})$")


def index_page(store: PageStore) -> Page:
    """Page 100: the front page — a listing of every numbered page."""
    lines = [f"{n:03d}  {(_title_of(store, n))}" for n in store.numbers()]
    return Page(number=100, title="LEVI-PAGES INDEX", body=lines or ["no pages on air"])


def _title_of(store: PageStore, number: int) -> str:
    page = store.get(number)
    return page.title if page else ""


def build_local_pages() -> PageStore:
    """Pages generated from real local data — no network, no account.

    100: index (built at serve time)  101: today / this machine
    102: perpetual-hunt pulse  200: archive counts (real local JSONL)
    """
    from datetime import datetime
    from pathlib import Path

    store = PageStore()
    now = datetime.now()

    store.add(
        Page(
            number=101,
            title="TODAY",
            body=[
                now.strftime("%A %d %B %Y"),
                now.strftime("%H:%M local time"),
                "",
                "Broadcast one-to-many:",
                "these pages loop whether",
                "or not anyone is watching.",
                "No login. No tracking.",
                "The receiver does the",
                "addressing.",
            ],
        )
    )

    perpetual = Path.home() / ".levi" / "perpetual"
    hunt_state = perpetual / "hunt_state.json"
    waves = 0
    if hunt_state.exists():
        try:
            import json

            waves = len(json.loads(hunt_state.read_text()).get("waves", []))
        except Exception:
            waves = -1  # honest: could not read, say so
    pending = sum(
        1 for p in (perpetual / "pending").glob("*.jsonl") if p.stat().st_size > 0
    ) if (perpetual / "pending").exists() else -1
    store.add(
        Page(
            number=102,
            title="PERPETUAL HUNT PULSE",
            body=[
                f"hunt waves recorded : {waves if waves >= 0 else 'unreadable'}",
                f"pending wave files  : {pending if pending >= 0 else 'unreadable'}",
                "",
                "Ceefax ran 38 years on the",
                "broadcast loop. This pulse",
                "is the same idea: the",
                "engine reports by coming",
                "around.",
            ],
        )
    )

    archive = Path.home() / ".levi" / "archive"
    records = 0
    if archive.exists():
        for f in archive.glob("*.jsonl"):
            try:
                records += sum(1 for line in f.read_text().splitlines() if line.strip())
            except OSError:
                continue
    store.add(
        Page(
            number=200,
            title="ARCHIVE COUNTS",
            body=[
                f"archive records on disk: {records}",
                "",
                "The Archive is the",
                "'everything'. This page is",
                "the 'never stops' saying",
                "hello.",
            ],
        )
    )
    return store


class _Handler(BaseHTTPRequestHandler):
    store: PageStore
    cycle: Iterator[Page]

    def log_message(self, *args: object) -> None:  # quiet by default
        pass

    def _send(self, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (stdlib name)
        path = (self.path or "/").split("?", 1)[0]
        if path == "/":
            self._send(render_frame(index_page(self.store)))
            return
        if path == "/carousel":
            self._send(render_frame(next(self.cycle)))
            return
        m = PAGE_RE.match(path)
        if m:
            page = self.store.get(int(m.group(1)))
            if page is None:
                self.send_error(404, "page not on air")
                return
            self._send(render_frame(page))
            return
        self.send_error(404, "no such page")


def serve(
    store: PageStore, host: str = "127.0.0.1", port: int = 8477
) -> Tuple[ThreadingHTTPServer, threading.Thread]:
    """Start the broadcast server in a background thread.

    Returns (server, thread). Call ``server.shutdown()`` to stop.
    Binds localhost only — the pages never leave the machine.
    """
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("teletext serves localhost only")
    handler = type(
        "_TeletextHandler",
        (_Handler,),
        {"store": store, "cycle": store.carousel()},
    )
    server = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
