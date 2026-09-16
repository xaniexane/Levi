"""Store-and-forward envelopes (FidoNet + UUCP, revived).

A node seals work into its outbox. Any other node — at its own cadence,
when it can reach the drop directory — *polls*, carrying envelopes for
itself into its inbox, forwarding others onward. No daemon, no network:
the wire is a directory (USB stick, shared folder, plain path).

An envelope carries:
- ``id``: unique (uuid4 hex).
- ``src`` / ``dst``: node names (owner-chosen strings, e.g. ``levi-home``).
- ``kind``: ``note`` | ``file`` | ``echo``. (File bodies are stored inline;
  keep them small — this is a telegraph office, not a cargo port.)
- ``body``: text payload.
- ``grade``: UUCP-style priority, 0 (highest) .. 9 (lowest). Poll moves
  higher grades first.
- ``hops``: node names that have handled the envelope — the visible
  provenance trail. An envelope whose destination already appears in its
  hop trail is dropped: no ping-pong loops.
- ``expires_ts``: optional epoch seconds; expired envelopes are refused.
- ``created_ts``: epoch seconds.

Poll semantics (the Zone Mail Hour, on demand):
``poll(drop_dir, my_node)`` scans ``<drop_dir>/<peer>/outbox/*.json``,
takes envelopes addressed to ``my_node`` into my inbox (recording the
hop), forwards nothing anywhere else (this office is one hop per poll;
multi-hop routes are built by repeated polling, exactly like the nightly
mailer runs). Returning a summary; every refusal is named.

Everything is owner-only on disk (0700 dirs, 0600 files).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import HOME_DIRNAME

KINDS = ("note", "file", "echo")

GRADE_MIN = 0
GRADE_MAX = 9

_VALID_NODE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


def _home() -> Path:
    return Path(os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi"))


def _node_ok(name: str) -> bool:
    return bool(name) and len(name) <= 64 and all(c in _VALID_NODE for c in name)


def _spool(home: Optional[Path] = None) -> Path:
    p = (home or _home()) / HOME_DIRNAME / "spool"
    p.mkdir(parents=True, exist_ok=True)
    os.chmod(p, 0o700)
    return p


def _node_dirs(home: Optional[Path], node: str) -> Tuple[Path, Path]:
    if not _node_ok(node):
        raise ValueError("bad node name %r (a-z A-Z 0-9 _ -, max 64)" % node)
    base = _spool(home) / node
    outbox = base / "outbox"
    inbox = base / "inbox"
    for d in (outbox, inbox):
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o700)
    os.chmod(base, 0o700)
    return outbox, inbox


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def new_envelope(
    src: str,
    dst: str,
    kind: str,
    body: str,
    grade: int = 5,
    expires_in_s: Optional[int] = None,
) -> Dict[str, Any]:
    """Build (but do not store) an envelope. Raises ValueError on bad input."""
    if not _node_ok(src):
        raise ValueError("bad src node %r" % src)
    if not _node_ok(dst):
        raise ValueError("bad dst node %r" % dst)
    if kind not in KINDS:
        raise ValueError("kind must be one of %s, got %r" % (KINDS, kind))
    if not isinstance(body, str) or not body:
        raise ValueError("body must be a non-empty string")
    if not isinstance(grade, int) or not (GRADE_MIN <= grade <= GRADE_MAX):
        raise ValueError("grade must be %d..%d" % (GRADE_MIN, GRADE_MAX))
    now = int(time.time())
    env: Dict[str, Any] = {
        "id": uuid.uuid4().hex,
        "src": src,
        "dst": dst,
        "kind": kind,
        "body": body,
        "grade": grade,
        "hops": [],
        "created_ts": now,
        "expires_ts": (now + expires_in_s) if expires_in_s is not None else None,
    }
    return env


def seal(env: Dict[str, Any], home: Optional[Path] = None) -> Path:
    """Place an envelope in its source node's outbox. Returns the file path."""
    outbox, _ = _node_dirs(home, env["src"])
    path = outbox / (env["id"] + ".json")
    _write_json(path, env)
    return path


def _expired(env: Dict[str, Any], now: int) -> bool:
    exp = env.get("expires_ts")
    return exp is not None and now >= exp


def poll(drop_dir: str, my_node: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Poll a drop directory: collect envelopes addressed to my_node.

    ``drop_dir`` holds peer spool trees (``<drop_dir>/<peer>/outbox``).
    For each peer outbox, envelopes addressed to ``my_node`` are moved
    into my inbox (hop recorded); all others are left for their own
    recipient. Envelopes move higher-grade-first (0 first).

    Returns a summary dict: carried, skipped_not_mine, refused_loop,
    refused_expired. Refusals are named, never silent.
    """
    if not _node_ok(my_node):
        raise ValueError("bad node name %r" % my_node)
    _, my_inbox = _node_dirs(home, my_node)
    drop = Path(drop_dir)
    now = int(time.time())
    summary = {
        "carried": 0,
        "skipped_not_mine": 0,
        "refused_loop": 0,
        "refused_expired": 0,
    }
    if not drop.is_dir():
        return summary

    candidates: List[Tuple[Path, Dict[str, Any]]] = []
    for peer_outbox in sorted(drop.glob("*/outbox")):
        for f in sorted(peer_outbox.glob("*.json")):
            try:
                env = _read_json(f)
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(env, dict) or env.get("dst") != my_node:
                summary["skipped_not_mine"] += 1
                continue
            candidates.append((f, env))

    # UUCP grades: lower number = higher priority = carried first.
    candidates.sort(
        key=lambda pair: (pair[1].get("grade", 9), pair[1].get("created_ts", 0))
    )
    for f, env in candidates:
        if my_node in env.get("hops", []):
            summary["refused_loop"] += 1
            f.unlink(missing_ok=True)  # poisoned envelope: drop it loudly
            continue
        if _expired(env, now):
            summary["refused_expired"] += 1
            f.unlink(missing_ok=True)
            continue
        env["hops"] = list(env.get("hops", [])) + [my_node]
        _write_json(my_inbox / (env["id"] + ".json"), env)
        f.unlink(missing_ok=True)
        summary["carried"] += 1
    return summary


def read_inbox(my_node: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """List my inbox envelopes, highest grade first. Does not remove them."""
    _, inbox = _node_dirs(home, my_node)
    envs = []
    for f in sorted(inbox.glob("*.json")):
        try:
            envs.append(_read_json(f))
        except (json.JSONDecodeError, OSError):
            continue
    envs.sort(key=lambda e: (e.get("grade", 9), e.get("created_ts", 0)))
    return envs


def ack(my_node: str, envelope_id: str, home: Optional[Path] = None) -> bool:
    """Remove an envelope from my inbox after reading. True if it existed."""
    if not envelope_id or "/" in envelope_id or "\\" in envelope_id:
        raise ValueError("bad envelope id")
    _, inbox = _node_dirs(home, my_node)
    path = inbox / (envelope_id + ".json")
    if path.exists():
        path.unlink()
        return True
    return False


def outbox_pending(node: str, home: Optional[Path] = None) -> int:
    """How many envelopes are waiting in a node's outbox."""
    outbox, _ = _node_dirs(home, node)
    return len(list(outbox.glob("*.json")))
