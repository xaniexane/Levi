"""Node identity — the telex WRU ritual, revived.

On a 1930s telex circuit you could transmit WRU ("Who aRe yoU") and the
far-end machine's answerback drum would automatically reply with its
programmed identity. Every LEVI node gets the same discipline:

- Each node registers an *identity card*: node name, answerback string
  (<= 40 chars, owner-written), capability list, registered timestamp.
- ``answerback(node)`` is the node's answer to "who are you" — exactly
  what a peer would hear.
- ``handshake(my_node, peer_node, presented)`` compares the presented
  answerback against the card the *directory* holds for ``peer_node``:
  match → ``"verified"``; unknown node → ``"unknown"`` (the office may
  still carry its mail, but marks it); mismatch → ``"quarantined"``
  (deny-closed: carried envelopes from a mismatched node are flagged,
  never silently trusted).

HONEST LIMIT: this is *detection*, not cryptographic trust. The answerback
is compared against a locally registered card; the drop directory is
assumed owner-trusted. On a hostile wire, use the vault and capproto.
The module says this on every quarantine rather than implying security
it does not have.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import HOME_DIRNAME

ANSWERBACK_MAX = 40


def _home() -> Path:
    return Path(os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi"))


def _cards_path(home: Optional[Path] = None) -> Path:
    p = (home or _home()) / HOME_DIRNAME
    p.mkdir(parents=True, exist_ok=True)
    os.chmod(p, 0o700)
    path = p / "identity_cards.json"
    if not path.exists():
        path.write_text("{}", encoding="utf-8")
        os.chmod(path, 0o600)
    return path


def _load(home: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    path = _cards_path(home)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    return data if isinstance(data, dict) else {}


def _save(home: Optional[Path], data: Dict[str, Dict[str, Any]]) -> None:
    path = _cards_path(home)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def register_card(
    node: str,
    answerback: str,
    capabilities: Optional[List[str]] = None,
    home: Optional[Path] = None,
    replace: bool = False,
) -> Dict[str, Any]:
    """Register (or replace, with ``replace=True``) this node's identity card."""
    node = node.strip()
    if not node or len(node) > 64:
        raise ValueError("node name required, max 64 chars")
    answerback = answerback.strip()
    if not answerback or len(answerback) > ANSWERBACK_MAX:
        raise ValueError("answerback required, max %d chars" % ANSWERBACK_MAX)
    caps = [c.strip() for c in (capabilities or []) if c and c.strip()]
    data = _load(home)
    if node in data and not replace:
        raise ValueError(
            "node %r already has a card; pass replace=True to re-register" % node
        )
    card = {
        "node": node,
        "answerback": answerback,
        "capabilities": caps,
        "registered_ts": int(time.time()),
    }
    data[node] = card
    _save(home, data)
    return card


def answerback(node: str, home: Optional[Path] = None) -> str:
    """The node's answer to WRU. Raises KeyError if the node has no card."""
    data = _load(home)
    if node not in data:
        raise KeyError("no identity card for node %r" % node)
    return data[node]["answerback"]


def get_card(node: str, home: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Return a node's registered card, or None."""
    return _load(home).get(node)


def handshake(
    my_node: str, peer_node: str, presented: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Compare a peer's presented answerback against its registered card.

    Returns ``{"peer": ..., "verdict": "verified"|"unknown"|"quarantined",
    "detail": ...}``. A mismatch is quarantine, never silent acceptance;
    an unknown node is named as unknown so the caller can decide.
    """
    card = get_card(peer_node, home)
    if card is None:
        return {
            "peer": peer_node,
            "verdict": "unknown",
            "detail": "no registered card for %r — mail may be carried "
            "but is marked unverified" % peer_node,
        }
    if presented == card["answerback"]:
        return {
            "peer": peer_node,
            "verdict": "verified",
            "detail": "answerback matches registered card",
        }
    return {
        "peer": peer_node,
        "verdict": "quarantined",
        "detail": "presented answerback does not match the registered "
        "card for %r — possible spoofing; detection only, no "
        "cryptographic proof involved" % peer_node,
    }
