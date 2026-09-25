"""hub.agent: the Kai-equivalent tool agent ("Scout").

Kai in the original was a tool-using agent whose "sandbox" was a
subprocess + denylist — a security smell we do NOT copy. Scout's tools:

- ``web_fetch`` — polite urllib GET, text extraction, size-capped. Read-only.
- ``note`` — write a memory note into the hub db. Local, safe.
- ``heartbeat`` — hub health snapshot. Local, safe.
- ``shell`` — REAL isolation via ``levi.sandbox`` backends (bubblewrap /
  unshare). The plain-subprocess backend is never used silently: it
  raises unless an approved HITL record explicitly acknowledges the
  degraded sandbox. No denylist theater — either real isolation or an
  explicit, recorded human decision.

Intent routing is a local keyword classifier (no key needed); anything
Scout synthesizes is labeled INFERENCE, fetched material OBSERVED.
Advisory-only: Scout never applies, buys, publishes, or moves money.
"""

from __future__ import annotations

import html
import json
import re
import shlex
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import hitl, store
from levi.sandbox import backends as sb_backends
from levi.sandbox import runner as sb_runner

UA = "LEVI-hub/0.1 (+local agent; contact: founder)"
_FETCH_CAP = 300_000  # bytes


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------


def web_fetch(url: str, timeout: float = 20.0) -> Dict[str, Any]:
    """Polite GET + text extraction. Read-only. Never raises."""
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "only http(s) URLs", "label": "OBSERVED"}
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(_FETCH_CAP + 1)
        truncated = len(raw) > _FETCH_CAP
        text = raw[:_FETCH_CAP].decode("utf-8", "replace")
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "label": "OBSERVED",
        }
    # strip scripts/styles/tags, collapse whitespace
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return {
        "ok": True,
        "url": url,
        "text": text[:20_000],
        "truncated": truncated or len(text) > 20_000,
        "label": "OBSERVED",
    }


def note(text: str, *, path: Optional[Path] = None) -> Dict[str, Any]:
    """Store a memory note in the hub db. Local. Never raises on content."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty note"}
    conn = store.connect(path)
    try:
        conn.execute(
            "INSERT INTO runs (kind, receipt, created) VALUES ('note', ?, ?)",
            (json.dumps({"note": text[:4000], "label": "OBSERVED"}), _now()),
        )
        conn.commit()
        return {"ok": True, "label": "OBSERVED"}
    finally:
        conn.close()


def heartbeat(*, path: Optional[Path] = None) -> Dict[str, Any]:
    """Hub health snapshot. Local. Never raises."""
    conn = store.connect(path)
    try:
        users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        pend = conn.execute(
            "SELECT COUNT(*) AS n FROM hitl WHERE status='pending'"
        ).fetchone()["n"]
        runs = conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"]
        spec = sb_backends.select_backend("auto")
        return {
            "ok": True,
            "users": users,
            "hitl_pending": pend,
            "runs_logged": runs,
            "sandbox_backend": spec.name,
            "sandbox_isolation": spec.isolation_level,
            "at": _now(),
            "label": "OBSERVED",
        }
    finally:
        conn.close()


def shell(
    command: str,
    *,
    hitl_id: Optional[int] = None,
    net: bool = False,
    timeout: float = 60.0,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run a shell command under a REAL sandbox backend.

    Rules (no denylist theater):
    - backend is chosen by ``levi.sandbox`` (bubblewrap > unshare > subprocess);
      we never silently downgrade.
    - ``subprocess`` (no isolation) requires an approved HITL record whose
      detail explicitly sets ``degraded_sandbox: true`` — the human knowingly
      accepts it.
    - any other backend still requires an approved HITL record: running code
      is a consequential act.
    Returns the sandboxed result with captured output.
    """
    parts = shlex.split(command or "")
    if not parts:
        return {"ok": False, "error": "empty command"}
    spec = sb_backends.select_backend("auto")
    degraded = spec.name == "subprocess"
    if degraded:
        if hitl_id is None or not hitl.is_approved(hitl_id, path=path):
            raise hitl.ApprovalRequired(
                "shell needs an approved HITL request first "
                "(degraded sandbox: no isolation available on this machine)"
            )
        # the approval must explicitly name the degraded sandbox
        recs = hitl.pending(path=path)
        _ = recs  # (record lookup below via direct query for honesty)
        conn = store.connect(path)
        try:
            row = conn.execute(
                "SELECT detail FROM hitl WHERE id = ?", (hitl_id,)
            ).fetchone()
        finally:
            conn.close()
        detail = json.loads(row["detail"]) if row else {}
        if not detail.get("degraded_sandbox"):
            raise hitl.ApprovalRequired(
                "degraded sandbox requires the HITL detail to set "
                "degraded_sandbox: true — the human must knowingly accept it"
            )
    else:
        hitl.require(hitl_id, path=path)
    argv = sb_runner.build_argv(spec, parts, net=net)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"timed out after {timeout}s",
            "backend": spec.name,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "backend": spec.name,
        }
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "backend": spec.name,
        "isolation": spec.isolation_level,
        "degraded": degraded,
        "stdout": proc.stdout[-20_000:],
        "stderr": proc.stderr[-5_000:],
        "label": "OBSERVED",
    }


# ---------------------------------------------------------------------------
# intent routing (local, keyword — no key needed)
# ---------------------------------------------------------------------------

_INTENTS = (
    ("fetch", ("fetch", "download", "read url", "get page", "open http")),
    ("shell", ("run ", "execute", "shell", "command")),
    ("note", ("remember", "note ", "jot down", "memorize")),
    ("heartbeat", ("health", "status", "heartbeat", "how are you")),
    ("jobs", ("job", "hiring", "remote work", "apply")),
    ("pulse", ("demand", "trend", "signal", "opportunity", "market")),
    ("alpha", ("build", "create", "generate", "scaffold", "alpha")),
)


def classify(task: str) -> str:
    t = (task or "").lower()
    for name, keys in _INTENTS:
        if any(k in t for k in keys):
            return name
    return "chat"


def run(task: str, *, path: Optional[Path] = None, **kwargs: Any) -> Dict[str, Any]:
    """Run one agent task: classify intent -> dispatch tools -> receipt.

    Advisory-only. ``kwargs`` may carry ``url`` (fetch) or ``command`` +
    ``hitl_id`` (shell). Everything synthesized here is INFERENCE.
    """
    intent = classify(task)
    steps: List[Dict[str, Any]] = []
    try:
        if intent == "fetch" and kwargs.get("url"):
            steps.append({"tool": "web_fetch", "result": web_fetch(kwargs["url"])})
        elif intent == "shell" and kwargs.get("command"):
            steps.append(
                {
                    "tool": "shell",
                    "result": shell(
                        kwargs["command"],
                        hitl_id=kwargs.get("hitl_id"),
                        net=bool(kwargs.get("net")),
                        path=path,
                    ),
                }
            )
        elif intent == "note":
            steps.append({"tool": "note", "result": note(task, path=path)})
        elif intent == "heartbeat":
            steps.append({"tool": "heartbeat", "result": heartbeat(path=path)})
        else:
            steps.append(
                {
                    "tool": "route",
                    "result": {
                        "ok": True,
                        "intent": intent,
                        "note": (
                            "routed locally; hand to the matching organ "
                            "(jobs/pulse/alpha) or ask a sharper question"
                        ),
                        "label": "INFERENCE",
                    },
                }
            )
        ok = all(s["result"].get("ok", True) for s in steps)
    except hitl.ApprovalRequired as exc:
        return {
            "ok": False,
            "intent": intent,
            "blocked": "approval_required",
            "error": str(exc),
            "label": "OBSERVED",
        }
    receipt = {
        "ok": ok,
        "task": task,
        "intent": intent,
        "steps": steps,
        "at": _now(),
        "advisory_only": True,
        "label": "INFERENCE",
    }
    conn = store.connect(path)
    try:
        conn.execute(
            "INSERT INTO runs (kind, receipt, created) VALUES ('agent', ?, ?)",
            (json.dumps(receipt), _now()),
        )
        conn.commit()
    finally:
        conn.close()
    return receipt
