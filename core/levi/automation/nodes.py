"""LEVI-native workflow node packs — real action/trigger implementations.

These are the concrete node kinds the flow engine (``flows.py``) dispatches
to. Each module registers its kinds at import time via
``flows.register_node_kind`` (added by the engine extension; if it has not
landed yet the registrations are deferred until ``ensure_registered()`` is
called).

Contract, per node kind::

    handle(node: dict, ctx: dict, run: dict) -> dict
        {"ok": bool, "output": dict, "evidence": str} or raise FlowError
    preview_fn(node: dict) -> str
        one honest line of what would happen

Node kinds registered here:

- ``webhook-out`` — real HTTP delivery via urllib (stdlib only), with
  template rendering, backoff retries, and secret-sanitized evidence.
- ``python``      — sandboxed subprocess runner: inline script or a
  ``script_path`` confined under ``LEVI_HOME``, scrubbed environment,
  enforced timeout, captured output. ``shell=True`` never used.
- ``macro``       — plays a recorded ``routines.py`` routine through the
  standing rail, permission-gated, threading the run's responder.

Plus the ``webhook-in`` trigger helper: ``register_webhook`` /
``match_webhook`` keep a path -> flow_id registry in
``<LEVI_HOME>/automation/webhooks.json`` (inbound entries live under the
reserved ``"_inbound"`` key so the outbound ``{minion_id: url}`` map used
by the executor is untouched) and produce trigger event dicts for the
dispatcher.

Defensive-only, stdlib-only. FlowError is deny-closed: malformed config
is refused, never half-run.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    # The engine extension adds register_node_kind; until it lands the
    # import fails and registrations are deferred to ensure_registered().
    from .flows import FlowError, register_node_kind
except ImportError:  # pragma: no cover - until the engine extension lands
    from .flows import FlowError

    register_node_kind = None  # type: ignore[assignment]

from .backoff import RetryPolicy

__all__ = [
    "FlowError",
    "register_webhook",
    "unregister_webhook",
    "match_webhook",
    "handle_webhook_out",
    "preview_webhook_out",
    "handle_python",
    "preview_python",
    "handle_macro",
    "preview_macro",
    "ensure_registered",
]


# ---------------------------------------------------------------------------
# Home + shared helpers
# ---------------------------------------------------------------------------


def _levi_home(home: Optional[Path] = None) -> Path:
    if home is not None:
        return Path(home)
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _cfg(node: Dict[str, Any]) -> Dict[str, Any]:
    """Node config: ``node["config"]`` when present, else the node's own
    fields (minus identity keys) so tests and hand-built nodes both work."""
    cfg = node.get("config")
    if isinstance(cfg, dict):
        return cfg
    return {k: v for k, v in node.items() if k not in ("id", "kind", "label", "config")}


_SECRET_PATTERNS = (
    re.compile(
        r'("(?:api[_-]?key|token|secret|password|passwd|pwd)"\s*:\s*")[^"]*(")', re.I
    ),
    re.compile(r"((?:api[_-]?key|token|secret|password)\s*=\s*)\S+", re.I),
    re.compile(r"(Authorization\s*:\s*)\S+", re.I),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", re.I),
)


def sanitize_secrets(text: Any, max_len: int = 2000) -> str:
    """Redact credential-shaped values, then truncate. Evidence stays
    verifiable (status codes, shapes) without leaking keys."""
    s = "" if text is None else str(text)
    for pat in _SECRET_PATTERNS:
        s = pat.sub(
            lambda m: m.group(1) + "***" + (m.group(2) if m.lastindex == 2 else ""), s
        )
    if len(s) > max_len:
        s = s[:max_len] + "\u2026[truncated]"
    return s


# ---------------------------------------------------------------------------
# webhook-in trigger helper (dispatcher-facing, not a node kind)
# ---------------------------------------------------------------------------

_INBOUND_KEY = "_inbound"


def _webhooks_file(home: Optional[Path] = None) -> Path:
    return _levi_home(home) / "automation" / "webhooks.json"


def _load_registry(home: Optional[Path] = None) -> Dict[str, Any]:
    try:
        raw = json.loads(_webhooks_file(home).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _save_registry(raw: Dict[str, Any], home: Optional[Path] = None) -> Path:
    path = _webhooks_file(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _normalize_path(path: str) -> str:
    if not isinstance(path, str) or not path.strip():
        raise FlowError("webhook path must be a non-empty string")
    p = path.strip()
    if not p.startswith("/"):
        raise FlowError(f"webhook path {path!r} must start with '/'")
    if ".." in p.split("/"):
        raise FlowError(f"webhook path {path!r} must not contain '..'")
    p = p.rstrip("/") or "/"
    return p


def register_webhook(
    path: str, flow_id: str, home: Optional[Path] = None
) -> Dict[str, str]:
    """Bind an inbound webhook path to a flow id. The outbound
    ``{minion_id: url}`` map in the same file is preserved untouched."""
    norm = _normalize_path(path)
    if not isinstance(flow_id, str) or not flow_id.strip():
        raise FlowError("webhook registration needs a non-empty flow_id")
    raw = _load_registry(home)
    inbound = raw.get(_INBOUND_KEY)
    if not isinstance(inbound, dict):
        inbound = {}
    inbound[norm] = flow_id.strip()
    raw[_INBOUND_KEY] = inbound
    _save_registry(raw, home)
    return {"path": norm, "flow_id": flow_id.strip()}


def unregister_webhook(path: str, home: Optional[Path] = None) -> bool:
    """Remove an inbound webhook binding. True when one was removed."""
    norm = _normalize_path(path)
    raw = _load_registry(home)
    inbound = raw.get(_INBOUND_KEY)
    if not isinstance(inbound, dict) or norm not in inbound:
        return False
    del inbound[norm]
    raw[_INBOUND_KEY] = inbound
    _save_registry(raw, home)
    return True


def match_webhook(
    path: str, payload: Any, home: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Match an inbound request path against the registry.

    Hit -> trigger event dict ``{"kind": "webhook", "source": path,
    "payload": {...}, "flow_id": ...}`` for the dispatcher.
    Miss -> None (the dispatcher ignores it; never an exception).
    """
    norm = _normalize_path(path)
    inbound = _load_registry(home).get(_INBOUND_KEY)
    if not isinstance(inbound, dict):
        return None
    flow_id = inbound.get(norm)
    if not flow_id:
        return None
    body = dict(payload) if isinstance(payload, dict) else {"value": payload}
    return {
        "kind": "webhook",
        "source": norm,
        "payload": body,
        "flow_id": flow_id,
    }


# ---------------------------------------------------------------------------
# webhook-out action
# ---------------------------------------------------------------------------

_WEBHOOK_METHODS = ("POST", "PUT", "PATCH", "DELETE")
_PLACEHOLDER_RE = re.compile(
    r"\{([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\}"
)


def _resolve_dotted(path: str, namespace: Dict[str, Any]) -> Any:
    cur: Any = namespace
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise FlowError(f"body_template: unknown placeholder {{{path}}}")
    return cur


def render_template(template: str, namespace: Dict[str, Any]) -> str:
    """Render ``{dotted.path}`` placeholders against the namespace.

    No eval, no expressions — plain lookups only. Unresolvable paths
    raise FlowError (deny-closed), never render as empty strings.
    """

    def _sub(match: re.Match) -> str:
        value = _resolve_dotted(match.group(1), namespace)
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=True)

    return _PLACEHOLDER_RE.sub(_sub, template)


def _validate_webhook_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    url = cfg.get("url", "")
    if not isinstance(url, str) or not url.strip():
        raise FlowError("webhook-out needs a non-empty 'url'")
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        raise FlowError(f"webhook-out url must be http(s), got {url!r}")
    method = str(cfg.get("method", "POST")).upper()
    if method not in _WEBHOOK_METHODS:
        raise FlowError(
            f"webhook-out method must be one of {_WEBHOOK_METHODS}, got {method!r}"
        )
    headers = cfg.get("headers", {})
    if not isinstance(headers, dict):
        raise FlowError("webhook-out 'headers' must be a dict")
    for k, v in headers.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise FlowError("webhook-out headers must be str -> str")
    timeout_s = cfg.get("timeout_s", 10)
    if not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
        raise FlowError("webhook-out 'timeout_s' must be a positive number")
    retries = cfg.get("retries", 2)
    if not isinstance(retries, int) or retries < 0:
        raise FlowError("webhook-out 'retries' must be a non-negative int")
    return {
        "url": url,
        "method": method,
        "headers": dict(headers),
        "timeout_s": float(timeout_s),
        "retries": retries,
    }


def _dedupe_key(run: Dict[str, Any]) -> Optional[str]:
    run_id = run.get("run_id") if isinstance(run, dict) else None
    if run_id:
        return f"levi-{run_id}"
    return None


def handle_webhook_out(
    node: Dict[str, Any], ctx: Dict[str, Any], run: Dict[str, Any]
) -> Dict[str, Any]:
    """POST (or PUT/PATCH/DELETE) a rendered body to a URL, with backoff
    retries. Network failure after all retries is ok=False, never an
    exception; malformed config is FlowError."""
    cfg = _validate_webhook_cfg(_cfg(node))
    template = _cfg(node).get("body_template", "")
    body = ""
    if template:
        if not isinstance(template, str):
            raise FlowError("webhook-out 'body_template' must be a string")
        body = render_template(template, dict(ctx or {}))
    data = body.encode("utf-8") if body else None

    policy = RetryPolicy(
        max_attempts=cfg["retries"] + 1, base_delay_s=1.0, max_delay_s=30.0
    )
    headers = {"Content-Type": "application/json"}
    headers.update(cfg["headers"])
    dedupe = _dedupe_key(run)
    if dedupe:
        headers["X-Levi-Dedupe-Key"] = dedupe

    attempts = 0
    last_error = "unknown"
    for attempt in range(1, policy.max_attempts + 1):
        attempts = attempt
        request = urllib.request.Request(
            cfg["url"], data=data, method=cfg["method"], headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=cfg["timeout_s"]) as resp:
                status = getattr(resp, "status", 200)
                raw_body = resp.read(65536)
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw_body = exc.read(65536) if hasattr(exc, "read") else b""
            if 500 <= status < 600 and attempt < policy.max_attempts:
                time.sleep(policy.delay_for(attempt))
                continue
            text = sanitize_secrets(raw_body.decode("utf-8", "replace"))
            evidence = (
                f"{cfg['method']} {sanitize_secrets(cfg['url'], 120)} -> {status} "
                f"(attempt {attempt}/{policy.max_attempts}); body: {text}"
            )
            return {
                "ok": False,
                "output": {
                    "status": status,
                    "body": text,
                    "attempts": attempt,
                },
                "evidence": evidence,
            }
        except Exception as exc:  # noqa: BLE001 - network failure is a receipted outcome
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < policy.max_attempts:
                time.sleep(policy.delay_for(attempt))
                continue
            evidence = (
                f"{cfg['method']} {sanitize_secrets(cfg['url'], 120)} failed after "
                f"{attempt} attempt(s): {sanitize_secrets(last_error, 300)}"
            )
            return {
                "ok": False,
                "output": {"status": None, "error": last_error, "attempts": attempt},
                "evidence": evidence,
            }
        text = sanitize_secrets(raw_body.decode("utf-8", "replace"))
        evidence = (
            f"{cfg['method']} {sanitize_secrets(cfg['url'], 120)} -> {status} "
            f"(attempt {attempt}/{policy.max_attempts}); body: {text}"
        )
        return {
            "ok": 200 <= status < 300,
            "output": {"status": status, "body": text, "attempts": attempt},
            "evidence": evidence,
        }
    # Unreachable: the loop always returns. Kept for the type checker.
    return {
        "ok": False,
        "output": {"status": None, "error": last_error, "attempts": attempts},
        "evidence": "webhook-out: no attempts made",
    }


def preview_webhook_out(node: Dict[str, Any]) -> str:
    cfg = _cfg(node)
    url = cfg.get("url", "<no url>")
    timeout_s = cfg.get("timeout_s", 10)
    retries = cfg.get("retries", 2)
    method = str(cfg.get("method", "POST")).upper()
    return f"{method} {url} (timeout {timeout_s}s, {retries} retries)"


# ---------------------------------------------------------------------------
# python action — sandboxed subprocess runner
# ---------------------------------------------------------------------------

_SANDBOX_SUBDIR = Path("automation") / "sandbox"
_OUT_MAX = 8192
_DEFAULT_ENV_ALLOW = ("LANG", "LC_ALL", "LC_CTYPE", "TZ", "PYTHONIOENCODING", "TERM")


def _sandbox_dir(home: Optional[Path] = None) -> Path:
    path = _levi_home(home) / _SANDBOX_SUBDIR
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def _resolve_script_path(script_path: str, home: Optional[Path] = None) -> Path:
    """Confine script_path under LEVI_HOME. Anything escaping -> FlowError."""
    if not isinstance(script_path, str) or not script_path.strip():
        raise FlowError("python node 'script_path' must be a non-empty string")
    base = _levi_home(home).resolve()
    candidate = Path(script_path.strip())
    if not candidate.is_absolute():
        candidate = base / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise FlowError(
            f"python node: script_path {script_path!r} escapes LEVI_HOME — refused"
        ) from None
    if not resolved.is_file():
        raise FlowError(f"python node: script file not found: {resolved}")
    return resolved


def _scrub_env(allowlist: Any) -> Dict[str, str]:
    """Minimal environment: PATH (+ SYSTEMROOT on Windows) plus only the
    allowlisted names that already exist. Nothing else leaks in."""
    env: Dict[str, str] = {}
    if os.name == "nt":
        for name in ("PATH", "SYSTEMROOT", "TEMP", "TMP"):
            if name in os.environ:
                env[name] = os.environ[name]
    else:
        env["PATH"] = os.environ.get("PATH", "/usr/bin:/bin")
    names = allowlist if isinstance(allowlist, (list, tuple)) else _DEFAULT_ENV_ALLOW
    for name in names:
        if isinstance(name, str) and name in os.environ:
            env[name] = os.environ[name]
    return env


def _truncate_out(text: str) -> str:
    if len(text) > _OUT_MAX:
        return text[:_OUT_MAX] + "\u2026[truncated]"
    return text


def handle_python(
    node: Dict[str, Any], ctx: Dict[str, Any], run: Dict[str, Any]
) -> Dict[str, Any]:
    """Run an inline script or a LEVI_HOME-confined script file with
    ``sys.executable``. No shell, scrubbed env, sandbox cwd, enforced
    timeout. Non-zero exit is ok=False (receipted), never an exception."""
    cfg = _cfg(node)
    script = cfg.get("script")
    script_path = cfg.get("script_path")
    if script and script_path:
        raise FlowError("python node: give 'script' OR 'script_path', not both")
    if not script and not script_path:
        raise FlowError("python node needs 'script' (inline) or 'script_path'")
    if script is not None and not isinstance(script, str):
        raise FlowError("python node 'script' must be a string")

    args = cfg.get("args", [])
    if not isinstance(args, list) or any(not isinstance(a, str) for a in args):
        raise FlowError("python node 'args' must be a list of strings")
    timeout_s = cfg.get("timeout_s", 30)
    if not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
        raise FlowError("python node 'timeout_s' must be a positive number")

    sandbox = _sandbox_dir()
    if script is not None:
        target = sandbox / f"inline-{uuid.uuid4().hex[:12]}.py"
        target.write_text(script, encoding="utf-8")
    else:
        target = _resolve_script_path(script_path)

    env = _scrub_env(cfg.get("env_allowlist", _DEFAULT_ENV_ALLOW))
    argv = [sys.executable, str(target), *args]
    try:
        proc = subprocess.run(  # noqa: S603 - argv list, no shell, confined
            argv,
            cwd=str(sandbox),
            env=env,
            capture_output=True,
            text=True,
            timeout=float(timeout_s),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _truncate_out(exc.stdout or "" if isinstance(exc.stdout, str) else "")
        stderr = _truncate_out(exc.stderr or "" if isinstance(exc.stderr, str) else "")
        evidence = (
            f"python {sanitize_secrets(target.name, 80)}: timed out after "
            f"{timeout_s}s — killed. stdout: {sanitize_secrets(stdout, 400)}; "
            f"stderr: {sanitize_secrets(stderr, 400)}"
        )
        return {
            "ok": False,
            "output": {
                "exit_code": None,
                "timed_out": True,
                "stdout": stdout,
                "stderr": stderr,
            },
            "evidence": evidence,
        }
    except OSError as exc:
        raise FlowError(f"python node: could not launch interpreter: {exc}") from None

    stdout = _truncate_out(proc.stdout or "")
    stderr = _truncate_out(proc.stderr or "")
    evidence = (
        f"python {sanitize_secrets(target.name, 80)}: exit {proc.returncode}. "
        f"stdout: {sanitize_secrets(stdout, 600)}; "
        f"stderr: {sanitize_secrets(stderr, 600)}"
    )
    return {
        "ok": proc.returncode == 0,
        "output": {
            "exit_code": proc.returncode,
            "timed_out": False,
            "stdout": stdout,
            "stderr": stderr,
        },
        "evidence": evidence,
    }


def preview_python(node: Dict[str, Any]) -> str:
    cfg = _cfg(node)
    timeout_s = cfg.get("timeout_s", 30)
    script = cfg.get("script")
    if isinstance(script, str) and script.strip():
        first = script.strip().splitlines()[0].strip()
        if len(first) > 60:
            first = first[:60] + "\u2026"
        return f"python: {first} (timeout {timeout_s}s)"
    return f"python: {cfg.get('script_path', '<no script>')} (timeout {timeout_s}s)"


# ---------------------------------------------------------------------------
# macro action — plays routines.py routines through the rail
# ---------------------------------------------------------------------------


def handle_macro(
    node: Dict[str, Any], ctx: Dict[str, Any], run: Dict[str, Any]
) -> Dict[str, Any]:
    """Play a recorded routine. Every minion step goes through the standing
    rail with the run's responder at the permission gate; a denied gate
    stops the routine fail-closed. Wraps routines.play_routine — never
    duplicates it."""
    from .routines import get_routine, play_routine

    cfg = _cfg(node)
    routine_id = cfg.get("routine_id", "")
    if not isinstance(routine_id, str) or not routine_id.strip():
        raise FlowError("macro node needs a non-empty 'routine_id'")
    routine_id = routine_id.strip()
    if get_routine(routine_id) is None:
        raise FlowError(f"macro node: unknown routine {routine_id!r}")

    responder = run.get("responder") if isinstance(run, dict) else None
    dry_run = run.get("dry_run", True) if isinstance(run, dict) else True
    try:
        result = play_routine(routine_id, responder=responder, dry_run=bool(dry_run))
    except KeyError as exc:
        raise FlowError(f"macro node: {exc}") from None

    receipts = []
    for receipt in result.receipts:
        to_dict = getattr(receipt, "to_dict", None)
        receipts.append(to_dict() if callable(to_dict) else str(receipt))
    evidence_lines = [f"macro '{routine_id}': {result.note}"]
    evidence_lines.extend(f"  {line}" for line in result.step_notes)
    return {
        "ok": result.ok,
        "output": {
            "routine_id": routine_id,
            "dry_run": result.dry_run,
            "step_notes": list(result.step_notes),
            "receipts": receipts,
        },
        "evidence": sanitize_secrets("\n".join(evidence_lines)),
    }


def preview_macro(node: Dict[str, Any]) -> str:
    cfg = _cfg(node)
    routine_id = cfg.get("routine_id", "<no routine>")
    try:
        from .routines import get_routine

        routine = get_routine(routine_id) if isinstance(routine_id, str) else None
    except Exception:  # noqa: BLE001 - preview never breaks on store trouble
        routine = None
    if routine is None:
        return f"macro: play routine '{routine_id}' (unknown — would refuse)"
    return f"macro: play routine '{routine.name}' ({len(routine.steps)} steps)"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_REGISTRATIONS: List[
    Tuple[
        str,
        Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
        Callable[[Dict[str, Any]], str],
    ]
] = [
    ("webhook-out", handle_webhook_out, preview_webhook_out),
    ("python", handle_python, preview_python),
    ("macro", handle_macro, preview_macro),
]


def ensure_registered() -> List[str]:
    """Register this module's node kinds with the flow engine. Safe to call
    repeatedly; returns the kinds registered this call."""
    done: List[str] = []
    if register_node_kind is None:
        return done
    for kind, handler, preview_fn in _REGISTRATIONS:
        register_node_kind(kind, handler, preview_fn)
        done.append(kind)
    return done


ensure_registered()
