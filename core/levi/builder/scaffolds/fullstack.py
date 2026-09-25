"""Fullstack scaffold: static frontend + stdlib Python backend + SQLite.

Rendered as a real project tree::

    <name>/
      app/__init__.py
      app/__main__.py      # `python3 -m app` entry point
      app/server.py        # ThreadingHTTPServer: static files + JSON API
      app/db.py            # sqlite3 helpers (stdlib)
      app/handlers.py      # API route handlers (backend stage regenerates)
      app/static/index.html# frontend (frontend stage regenerates)
      schema.sql           # database schema (data stage regenerates)
      README.md
      levi-build.json      # manifest (packager stage writes)

Every generated project runs with ``python3 -m app`` from the project
directory and nothing else: no frameworks, no pip, no npm.
"""

from __future__ import annotations

import re
from typing import Dict

from .spec import BuildSpec


def render_fullstack(spec: BuildSpec) -> Dict[str, str]:
    files: Dict[str, str] = {
        "app/__init__.py": '"""%s — stdlib fullstack app."""\n' % spec.name,
        "app/__main__.py": _MAIN_PY,
        "app/server.py": _SERVER_PY,
        "app/db.py": _DB_PY,
        "app/handlers.py": _default_handlers(spec),
        "app/static/index.html": _default_index(spec),
        "schema.sql": _default_schema(spec),
        "README.md": _readme(spec),
    }
    return files


# ---------------------------------------------------------------------------
# app/__main__.py — `python3 -m app`
# ---------------------------------------------------------------------------

_MAIN_PY = '''"""Entry point: `python3 -m app` from the project directory."""

from __future__ import annotations

import os

from . import db as dbmod
from .server import serve


def main() -> None:
    dbmod.init_db()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"serving on http://{host}:{port} (Ctrl-C to stop)")
    serve(host=host, port=port)


if __name__ == "__main__":
    main()
'''

# ---------------------------------------------------------------------------
# app/db.py — sqlite3 helpers (stdlib only)
# ---------------------------------------------------------------------------

_DB_PY = '''"""SQLite helpers. The database lives in data/app.db (created on first run)."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_db() -> sqlite3.Connection:
    root = project_root()
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)
    con = sqlite3.connect(data_dir / "app.db")
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    schema = (project_root() / "schema.sql").read_text(encoding="utf-8")
    con = get_db()
    try:
        con.executescript(schema)
        con.commit()
    finally:
        con.close()
'''

# ---------------------------------------------------------------------------
# app/server.py — static files + JSON API on the stdlib
# ---------------------------------------------------------------------------

_SERVER_PY = '''"""Stdlib HTTP server: serves app/static/* and dispatches /api/* routes.

Route table lives in app.handlers.ROUTES as (method, regex, handler_name).
Each handler is ``handler(request, db) -> (status, headers, body_bytes)``
where request is a dict with method/path/query/headers/body.
"""

from __future__ import annotations

import json
import mimetypes
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_handlers():
    from . import handlers

    return handlers


def _json(status: int, obj) -> tuple:
    body = json.dumps(obj).encode("utf-8")
    return status, {"Content-Type": "application/json"}, body


class _Handler(BaseHTTPRequestHandler):
    server_version = "LeviBuilder/1.0"

    def log_message(self, *args):  # keep stdout clean
        pass

    def _send(self, status: int, headers: dict, body: bytes) -> None:
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            length = 0
        return self.rfile.read(length) if length > 0 else b""

    def _serve_static(self, path: str) -> None:
        static_dir = (project_root() / "app" / "static").resolve()
        rel = path.lstrip("/") or "index.html"
        target = (static_dir / rel).resolve()
        # Containment: never serve outside app/static.
        if static_dir not in target.parents and target != static_dir:
            self._send(*_json(403, {"error": "forbidden"}))
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self._send(*_json(404, {"error": "not found"}))
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self._send(200, {"Content-Type": ctype}, target.read_bytes())

    def _dispatch_api(self, method: str, path: str) -> None:
        from . import db as dbmod

        handlers = _load_handlers()
        for route_method, pattern, handler_name in handlers.ROUTES:
            if route_method != method:
                continue
            m = re.match(pattern, path)
            if not m:
                continue
            fn = getattr(handlers, handler_name, None)
            if fn is None:
                self._send(*_json(500, {"error": f"missing handler {handler_name}"}))
                return
            parsed = urllib.parse.urlparse(self.path)
            request = {
                "method": method,
                "path": path,
                "query": urllib.parse.parse_qs(parsed.query),
                "headers": dict(self.headers),
                "body": self._read_body(),
                "match": m,
            }
            db = dbmod.get_db()
            try:
                status, headers, body = fn(request, db)
            except Exception as exc:  # handlers must never crash the server
                self._send(*_json(500, {"error": f"handler failed: {exc}"}))
                return
            finally:
                db.close()
            if isinstance(body, (dict, list)):
                status, headers, body = _json(status, body)
            self._send(status, headers, body)
            return
        self._send(*_json(404, {"error": "unknown api route"}))

    def _route(self, method: str) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/"):
            self._dispatch_api(method, path)
        else:
            self._serve_static(path)

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PUT(self):
        self._route("PUT")

    def do_DELETE(self):
        self._route("DELETE")


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    httpd = ThreadingHTTPServer((host, port), _Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
'''

# ---------------------------------------------------------------------------
# Defaults the generator stages overwrite
# ---------------------------------------------------------------------------


def _safe_entity(spec: BuildSpec) -> str:
    raw = spec.entities[0].name if spec.entities else "item"
    ident = re.sub(r"\W+", "_", raw.strip().lower()).strip("_") or "item"
    return ident


def _plural(name: str) -> str:
    return name if name.endswith("s") else name + "s"


def _default_handlers(spec: BuildSpec) -> str:
    entity = _safe_entity(spec)
    plural = _plural(entity)
    return f'''"""API handlers (regenerated by the backend stage from the build spec)."""

from __future__ import annotations

import json
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


ROUTES = [
    ("GET", r"^/api/health$", "health"),
    ("GET", r"^/api/{plural}$", "list_{plural}"),
    ("POST", r"^/api/{plural}$", "create_{entity}"),
]


def health(request, db):
    return 200, {{"Content-Type": "application/json"}}, {{"ok": True}}


def list_{plural}(request, db):
    rows = db.execute(
        "SELECT id, name, body, created FROM {plural} ORDER BY id DESC LIMIT 100"
    ).fetchall()
    return 200, {{"Content-Type": "application/json"}}, [dict(r) for r in rows]


def create_{entity}(request, db):
    try:
        payload = json.loads(request["body"] or b"{{}}")
    except (ValueError, TypeError):
        payload = {{}}
    name = str(payload.get("name", "")).strip()[:200]
    body = str(payload.get("body", "")).strip()[:5000]
    if not name:
        return 400, {{"Content-Type": "application/json"}}, {{"error": "name required"}}
    cur = db.execute(
        "INSERT INTO {plural} (name, body, created) VALUES (?, ?, ?)",
        (name, body, _now()),
    )
    db.commit()
    return 201, {{"Content-Type": "application/json"}}, {{"id": cur.lastrowid, "name": name}}
'''


def _default_schema(spec: BuildSpec) -> str:
    entity = _safe_entity(spec)
    plural = _plural(entity)
    return f"""-- schema.sql (regenerated by the data stage from the build spec)
CREATE TABLE IF NOT EXISTS {plural} (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    body    TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL
);
"""


def _default_index(spec: BuildSpec) -> str:
    title = _esc(spec.title)
    desc = _esc(spec.description)
    entity = _safe_entity(spec)
    plural = _plural(entity)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0; font-family: system-ui, sans-serif; background: #0b0e14;
         color: #e6e9f0; }}
  main {{ max-width: 44rem; margin: 0 auto; padding: 2rem 1.5rem; }}
  h1 {{ margin-top: 0; }}
  form {{ display: flex; gap: .5rem; margin: 1rem 0; }}
  input {{ flex: 1; padding: .6rem; border-radius: .5rem;
           border: 1px solid #232c4a; background: #121828; color: inherit; }}
  button {{ background: #3b5bff; color: #fff; border: 0; border-radius: .5rem;
            padding: .6rem 1.1rem; cursor: pointer; }}
  ul {{ list-style: none; padding: 0; display: grid; gap: .6rem; }}
  li {{ background: #121828; border: 1px solid #232c4a; border-radius: .5rem;
        padding: .7rem 1rem; }}
  .muted {{ color: #9aa4c0; font-size: .85rem; }}
</style>
</head>
<body>
<main>
  <h1>{title}</h1>
  <p class="muted">{desc}</p>
  <form id="f">
    <input id="name" placeholder="New {entity} name" required maxlength="200">
    <button type="submit">Add</button>
  </form>
  <ul id="list"></ul>
</main>
<script>
const API = '/api/{plural}';
async function refresh() {{
  const r = await fetch(API);
  const items = await r.json();
  const ul = document.getElementById('list');
  ul.innerHTML = '';
  for (const it of items) {{
    const li = document.createElement('li');
    li.textContent = it.name + (it.body ? ' — ' + it.body : '');
    ul.appendChild(li);
  }}
}}
document.getElementById('f').addEventListener('submit', async (e) => {{
  e.preventDefault();
  const name = document.getElementById('name').value.trim();
  if (!name) return;
  await fetch(API, {{ method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{name}}) }});
  document.getElementById('name').value = '';
  refresh();
}});
refresh();
</script>
</body>
</html>
"""


def _readme(spec: BuildSpec) -> str:
    title = _esc(spec.title)
    return f"""# {title}

{_esc(spec.description)}

Built locally with **LEVI Builder** — stdlib only. No frameworks, no
pip, no npm, no accounts, no cloud. You own it completely.

## Run it

```sh
python3 -m app
```

Then open http://127.0.0.1:8000/ — the frontend is served from
`app/static/`, the JSON API lives under `/api/`.

Environment: `HOST` / `PORT` to change the bind address and port.
The server binds 127.0.0.1 by default (local only).

## Layout

- `app/__main__.py` — entry point
- `app/server.py` — stdlib HTTP server (static + API dispatch)
- `app/handlers.py` — API route handlers (`ROUTES` table)
- `app/db.py` — SQLite helpers (`data/app.db`, created on first run)
- `app/static/` — frontend
- `schema.sql` — database schema
- `levi-build.json` — build manifest and provenance
"""


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
