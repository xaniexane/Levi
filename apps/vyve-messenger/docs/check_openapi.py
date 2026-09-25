#!/usr/bin/env python3
"""OpenAPI consistency check for the VYVE backend (P3.4).

Loads apps/vyve-messenger/docs/openapi.yaml, walks both FastAPI apps'
``app.routes``, and fails (exit 1) when:

  1. a real route in either app is missing from the spec, or
  2. a spec path is missing from the app(s) it claims to belong to, or
  3. a spec operation lacks an explicit ``servers`` entry (every route must
     be attributed to :8080 and/or :8081 — the single-"/v1"-server fiction
     must not creep back in).

Run from the repo root (cwd-independent)::

    python3 apps/vyve-messenger/docs/check_openapi.py

Also wired into CI (.github/workflows/ci.yml, job "python", step
"OpenAPI consistency check").

Intentional exceptions (allowlist below):
  - FastAPI's auto-generated docs routes (/openapi.json, /docs, ...) — they
    are framework machinery, not product API surface, so they stay out of
    the contract.
  - GET/HEAD/OPTIONS method variants FastAPI adds automatically — only the
    method the code declared is compared.
  - The WebSocket upgrade route /ws/{user_id} — OpenAPI 3.0 cannot express
    an HTTP->WebSocket protocol upgrade, so it is documented by hand in the
    YAML (``x-websocket: true``); the checker verifies it exists as a
    websocket route instead of as a normal operation.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

DOCS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = DOCS_DIR.parent / "backend"
SPEC_PATH = DOCS_DIR / "openapi.yaml"

# The servers refuse to start without these; the checker does not need real
# values, it just needs them *set* (fail-closed, P1.2).
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("OAUTH_CLIENT_SECRET", "check-openapi-dummy-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("VYVE_KEY_DIR", tempfile.mkdtemp(prefix="vyve-openapi-check-"))

import yaml  # noqa: E402
from fastapi.routing import APIRoute, APIWebSocketRoute  # noqa: E402

from oauth.server import app as oauth_app  # noqa: E402
from messaging.server import app as msg_app  # noqa: E402

APPS = {"oauth": oauth_app, "messaging": msg_app}

# Port -> app attribution used to resolve operation-level `servers` entries.
PORT_TO_APP = {8080: "oauth", 8081: "messaging"}

# FastAPI framework machinery: real routes in app.routes, but deliberately
# excluded from the contract (interactive docs, not API surface).
FASTAPI_DOC_PATHS = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head"}


def real_routes() -> dict[str, set[tuple[str, str]]]:
    """(method, path) per app, as declared in code.

    FastAPI auto-adds HEAD/OPTIONS to GET routes; those are not declared by
    the code, so they are excluded from the comparison.
    """
    out: dict[str, set[tuple[str, str]]] = {name: set() for name in APPS}
    for name, app in APPS.items():
        for route in app.routes:
            if route.path in FASTAPI_DOC_PATHS:
                continue  # framework docs, not product surface
            if isinstance(route, APIWebSocketRoute):
                out[name].add(("WS", route.path))
            elif isinstance(route, APIRoute):
                for method in sorted(set(route.methods or ()) - {"HEAD", "OPTIONS"}):
                    out[name].add((method, route.path))
    return out


def spec_routes(spec: dict) -> tuple[dict[str, set[tuple[str, str]]], list[str]]:
    """(method, path) per app claimed by the spec + list of problems found."""
    problems: list[str] = []
    out: dict[str, set[tuple[str, str]]] = {name: set() for name in APPS}
    global_servers = [s["url"] for s in spec.get("servers", [])]

    def servers_to_apps(servers: list[dict]) -> set[str]:
        apps: set[str] = set()
        for s in servers:
            port = urlparse(s["url"]).port
            if port in PORT_TO_APP:
                apps.add(PORT_TO_APP[port])
            else:
                problems.append(
                    f"spec server URL {s['url']!r} does not map to :8080/:8081"
                )
        return apps or set(APPS)

    for path, item in spec.get("paths", {}).items():
        if not isinstance(item, dict):
            problems.append(f"spec path {path!r} is not a mapping")
            continue
        if item.get("x-websocket"):
            # Documented-by-hand upgrade route: must exist as a WS route on
            # the messaging app, not as an HTTP operation.
            out["messaging"].add(("WS", path))
            continue
        for key in item:
            if key not in HTTP_METHODS and not key.startswith("x-"):
                problems.append(f"spec path {path!r}: unknown key {key!r}")
        for method in HTTP_METHODS:
            op = item.get(method)
            if op is None:
                continue
            op_servers = (
                op.get("servers")
                or item.get("servers")
                or [{"url": u} for u in global_servers]
            )
            if not (op.get("servers") or item.get("servers")):
                # Falls back to the global list: acceptable only if the global
                # list is unambiguous; require explicit attribution instead.
                problems.append(
                    f"spec {method.upper()} {path}: no operation/path-level "
                    "`servers` entry (every route must be attributed to "
                    ":8080 and/or :8081)"
                )
            for app_name in servers_to_apps(op_servers):
                out[app_name].add((method.upper(), path))
    return out, problems


def main() -> int:
    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    real = real_routes()
    claimed, problems = spec_routes(spec)

    # Direction 1: every real route must be in the spec.
    for app_name, routes in real.items():
        for method, path in sorted(routes):
            if (method, path) not in claimed[app_name]:
                problems.append(
                    f"route in code but missing from spec: [{app_name}] {method} {path}"
                )

    # Direction 2: every spec route must exist in the app it claims.
    for app_name, routes in claimed.items():
        for method, path in sorted(routes):
            if (method, path) not in real[app_name]:
                problems.append(
                    f"path in spec but missing from code: [{app_name}] {method} {path}"
                )

    real_total = sum(len(r) for r in real.values())
    spec_total = sum(len(r) for r in claimed.values())
    print(
        f"spec:  {SPEC_PATH.relative_to(Path.cwd()) if SPEC_PATH.is_relative_to(Path.cwd()) else SPEC_PATH}"
    )
    print(
        f"routes in code: {real_total}  "
        f"(oauth: {len(real['oauth'])}, messaging: {len(real['messaging'])})"
    )
    print(
        f"routes in spec: {spec_total}  "
        f"(oauth: {len(claimed['oauth'])}, messaging: {len(claimed['messaging'])})"
    )

    if problems:
        print(f"\nFAILED: {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("OK: spec and code agree on every route.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
