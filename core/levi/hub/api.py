"""hub.api: our own HTTP router on http.server + json.

The original served ~93 endpoints via FastAPI. Proven shape kept: one
JSON API over the organs. Machinery swapped: stdlib ``http.server``,
hand-rolled routing, plain functions behind it. No fastapi, no uvicorn,
no pydantic.

Auth: ``/``, ``/api/status``, ``/api/auth/*`` are open; everything else
needs ``Authorization: Bearer <token>`` from hub.auth.
"""

from __future__ import annotations

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional, Tuple

from . import agent as scout
from . import alpha as alpha_lab
from . import auth as hub_auth
from . import hitl as hitl_mod
from . import jobs as job_engine
from . import orchestrator
from . import ui as hub_ui


def _body(handler: BaseHTTPRequestHandler, limit: int = 1_000_000) -> Dict[str, Any]:
    try:
        n = int(handler.headers.get("Content-Length") or 0)
    except ValueError:
        n = 0
    if n <= 0 or n > limit:
        return {}
    raw = handler.rfile.read(n)
    try:
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _bearer(handler: BaseHTTPRequestHandler) -> Optional[Dict[str, Any]]:
    authz = handler.headers.get("Authorization") or ""
    if not authz.startswith("Bearer "):
        return None
    return hub_auth.verify_token(authz[7:].strip())


# -- route implementations (plain functions) --------------------------------

OPEN = {
    ("GET", "/"),
    ("GET", "/api/status"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
}


def r_index(_q: Dict, _b: Dict, _u: Optional[Dict]) -> Tuple[int, str, str]:
    return 200, hub_ui.PAGE, "text/html; charset=utf-8"


def r_status(_q, _b, _u):
    return 200, orchestrator.status(), "json"


def r_register(_q, b, _u):
    try:
        return (
            200,
            hub_auth.register(b.get("username", ""), b.get("password", "")),
            "json",
        )
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}, "json"


def r_login(_q, b, _u):
    try:
        return (
            200,
            hub_auth.login(
                b.get("username", ""), b.get("password", ""), label=b.get("label", "")
            ),
            "json",
        )
    except ValueError as exc:
        return 401, {"ok": False, "error": str(exc)}, "json"


def r_logout(_q, b, u):
    tok = b.get("token") or ""
    return 200, hub_auth.logout(tok), "json"


def r_agent_run(_q, b, u):
    return (
        200,
        scout.run(
            b.get("task", ""),
            url=b.get("url"),
            command=b.get("command"),
            hitl_id=b.get("hitl_id"),
            net=bool(b.get("net")),
        ),
        "json",
    )


def r_heartbeat(_q, _b, _u):
    return 200, scout.heartbeat(), "json"


def r_alpha_design(_q, b, _u):
    return 200, alpha_lab.design(b.get("prompt", "")), "json"


def r_alpha_preview(_q, b, _u):
    return 200, alpha_lab.preview(b.get("prompt", "")), "json"


def r_alpha_create(_q, b, _u):
    try:
        return (
            200,
            alpha_lab.create(
                b.get("prompt", ""),
                b.get("dest", ""),
                approve=bool(b.get("approve")),
                hitl_id=b.get("hitl_id"),
                overwrite=bool(b.get("overwrite")),
            ),
            "json",
        )
    except hitl_mod.ApprovalRequired as exc:
        return (
            403,
            {"ok": False, "blocked": "approval_required", "error": str(exc)},
            "json",
        )
    except (ValueError, OSError) as exc:
        return 400, {"ok": False, "error": str(exc)}, "json"


def r_jobs_search(q, _b, _u):
    return (
        200,
        job_engine.search_all(
            q.get("q", ""),
            sources=(q.get("sources", "").split(",") if q.get("sources") else None),
        ),
        "json",
    )


def r_jobs_stage(_q, b, _u):
    return (
        200,
        job_engine.stage(
            b.get("listings", []),
            source_board=b.get("source_board", "hub"),
            dry_run=b.get("dry_run", True),
        ),
        "json",
    )


def r_pulse_scan(_q, b, _u):
    from levi.demand import processing as dp

    try:
        return 200, dp.run_scan(b.get("query", "")), "json"
    except Exception as exc:
        return 500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"}, "json"


def r_pulse_heatmap(_q, _b, _u):
    from levi.demand import processing as dp

    scan = dp.load_last_scan()
    if not scan:
        return 200, {"ok": False, "error": "no scan yet — run pulse/scan first"}, "json"
    return (
        200,
        {
            "ok": True,
            "heatmap": scan.get("heatmap"),
            "scanned_at": scan.get("scanned_at"),
        },
        "json",
    )


def r_comp_track(_q, _b, _u):
    from levi.demand import competition as comp

    return 200, {"ok": True, "results": comp.track_all()}, "json"


def r_comp_changes(_q, _b, _u):
    from levi.demand import competition as comp

    return 200, {"ok": True, "changes": comp.check_changes()}, "json"


def r_comp_gaps(_q, _b, _u):
    from levi.demand import competition as comp

    return 200, {"ok": True, "matrix": comp.feature_matrix()}, "json"


def r_comp_propose(_q, _b, _u):
    from levi.demand import competition as comp

    return 200, comp.propose_upgrades(), "json"


def r_hitl_pending(_q, _b, _u):
    return 200, {"ok": True, "pending": hitl_mod.pending()}, "json"


def r_hitl_decide(_q, b, _u):
    try:
        return (
            200,
            hitl_mod.decide(
                int(b.get("id")), bool(b.get("approved")), note=b.get("note", "")
            ),
            "json",
        )
    except (ValueError, TypeError) as exc:
        return 400, {"ok": False, "error": str(exc)}, "json"


def r_cycle_run(_q, b, _u):
    return 200, orchestrator.run_cycle(b.get("goal", "")), "json"


ROUTES: Dict[Tuple[str, str], Callable] = {
    ("GET", "/"): r_index,
    ("GET", "/api/status"): r_status,
    ("POST", "/api/auth/register"): r_register,
    ("POST", "/api/auth/login"): r_login,
    ("POST", "/api/auth/logout"): r_logout,
    ("POST", "/api/agent/run"): r_agent_run,
    ("GET", "/api/agent/heartbeat"): r_heartbeat,
    ("POST", "/api/alpha/design"): r_alpha_design,
    ("POST", "/api/alpha/preview"): r_alpha_preview,
    ("POST", "/api/alpha/create"): r_alpha_create,
    ("GET", "/api/jobs/search"): r_jobs_search,
    ("POST", "/api/jobs/stage"): r_jobs_stage,
    ("POST", "/api/pulse/scan"): r_pulse_scan,
    ("GET", "/api/pulse/heatmap"): r_pulse_heatmap,
    ("POST", "/api/competition/track"): r_comp_track,
    ("GET", "/api/competition/changes"): r_comp_changes,
    ("GET", "/api/competition/gaps"): r_comp_gaps,
    ("GET", "/api/competition/propose"): r_comp_propose,
    ("GET", "/api/hitl/pending"): r_hitl_pending,
    ("POST", "/api/hitl/decide"): r_hitl_decide,
    ("POST", "/api/cycle/run"): r_cycle_run,
}


class HubHandler(BaseHTTPRequestHandler):
    server_version = "levi-hub/0.1"

    def log_message(self, *args: Any) -> None:
        pass  # quiet; the hub logs receipts, not access lines

    def _dispatch(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        route = (self.command, parsed.path.rstrip("/") or "/")
        fn = ROUTES.get(route)
        if fn is None:
            self._send(404, {"ok": False, "error": "no such route"}, "json")
            return
        if route not in OPEN:
            user = _bearer(self)
            if user is None:
                self._send(401, {"ok": False, "error": "bearer token required"}, "json")
                return
        else:
            user = _bearer(self)
        query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        body = _body(self) if self.command == "POST" else {}
        try:
            code, payload, kind = fn(query, body, user)
        except Exception as exc:  # a route bug must not kill the server
            self._send(
                500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"}, "json"
            )
            return
        self._send(code, payload, kind)

    def _send(self, code: int, payload: Any, kind: str) -> None:
        if kind == "json":
            data = json.dumps(payload, default=str).encode("utf-8")
            ctype = "application/json"
        else:
            data = payload.encode("utf-8") if isinstance(payload, str) else payload
            ctype = kind
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()


def serve(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Start the hub server (blocking). Bind localhost by default."""
    srv = ThreadingHTTPServer((host, port), HubHandler)
    print(
        f"hub serving on http://{host}:{port} — token required except / and /api/status"
    )
    srv.serve_forever()
    return srv


def serve_in_thread(
    host: str = "127.0.0.1", port: int = 0
) -> Tuple[ThreadingHTTPServer, threading.Thread]:
    """Start the hub server on a background thread (tests, embedding)."""
    srv = ThreadingHTTPServer((host, port), HubHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, t
