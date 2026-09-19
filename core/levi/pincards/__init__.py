"""Pincards: the keeper's always-on facts.

A pincard is a short pinned statement LEVI always has on hand --
"answers in metric", "phone numbers in +1 E.164 form", the Wi-Fi fix
steps -- surfaced into context by plain keyword overlap, ranked by count.
No embeddings, no ML, no inference implied by the name.

The twist over the upload's flat notes list ("notes.py", the consolidated
offline-first scaffold):

* cards are never deleted, only *retired*: the stone never forgets, so a
  retired card stays in the file with its full history. `purge()` exists
  only for the keeper and says so loudly.
* every card carries provenance: who pinned it, when, and optional scope
  tags so context-surfacing can prefer matching scopes.
* secrets are refused at the pin, not redacted later: a card that looks
  like it carries a credential or PII is rejected with a reason, because
  a pinned fact lands in every prompt it matches.

Storage is one JSON file (default ``~/.levi/pincards/cards.json``,
overridable via ``LEVI_PINCARDS_PATH``); writes are atomic
(temp + rename). stdlib-only.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_PATH = Path.home() / ".levi" / "pincards" / "cards.json"
STORE_PATH = Path(os.environ.get("LEVI_PINCARDS_PATH", str(_DEFAULT_PATH)))

MAX_CARD_CHARS = 2000

# A pinned card lands in prompts it matches, so secret-shaped text must not
# be pinnable. Best-effort: reduces accidents, never a guarantee.
_CREDENTIAL_ASSIGN = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|auth[_-]?token|"
    r"access[_-]?token|client[_-]?secret)\b\s*[:=]\s*\S+"
)
_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
_CARD_RUN = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")

_WORD_RE = re.compile(r"[a-z0-9]{3,}")


def _load() -> List[Dict[str, Any]]:
    if not STORE_PATH.exists():
        return []
    try:
        data = json.loads(STORE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    return [c for c in data if isinstance(c, dict)] if isinstance(data, list) else []


def _save(cards: List[Dict[str, Any]]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(STORE_PATH.parent), prefix="pincards-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(cards, f, indent=2)
        os.replace(tmp, STORE_PATH)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _next_id(cards: List[Dict[str, Any]]) -> int:
    ids = [c.get("id") for c in cards if isinstance(c.get("id"), int)]
    return (max(ids) + 1) if ids else 1


def _secret_reason(text: str) -> Optional[str]:
    if _CREDENTIAL_ASSIGN.search(text):
        return "looks like a credential assignment (key=value)"
    if _SSN.search(text) or _CARD_RUN.search(text):
        return "looks like an SSN or card number"
    return None


def pin(
    text: str, *, by: str = "keeper", scopes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Pin a new card. Raises ValueError on empty/overlong/secret-shaped text."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("card text must not be empty")
    if len(cleaned) > MAX_CARD_CHARS:
        raise ValueError(f"card too long (>{MAX_CARD_CHARS} chars)")
    reason = _secret_reason(cleaned)
    if reason:
        raise ValueError(f"card refused: {reason} -- never pin secrets")
    cards = _load()
    card = {
        "id": _next_id(cards),
        "text": cleaned,
        "by": by,
        "scopes": [s for s in (scopes or []) if s],
        "pinned_at": time.time(),
        "retired": False,
        "history": [],
    }
    cards.append(card)
    _save(cards)
    return card


def list_active() -> List[Dict[str, Any]]:
    """Active (non-retired) cards, oldest first."""
    return [c for c in _load() if not c.get("retired")]


def list_all(include_retired: bool = False) -> List[Dict[str, Any]]:
    cards = _load()
    return cards if include_retired else [c for c in cards if not c.get("retired")]


def retire(card_id: int, *, reason: str = "") -> bool:
    """Retire a card: it stops surfacing but stays in the file with history."""
    cards = _load()
    for card in cards:
        if card.get("id") == card_id and not card.get("retired"):
            card["retired"] = True
            card["history"].append(
                {"event": "retired", "at": time.time(), "reason": reason}
            )
            _save(cards)
            return True
    return False


def purge(card_id: int) -> bool:
    """Keeper-only: erase a card entirely, history and all. Prefer retire()."""
    cards = _load()
    kept = [c for c in cards if c.get("id") != card_id]
    if len(kept) == len(cards):
        return False
    _save(kept)
    return True


def _tokens(text: str) -> set:
    return set(_WORD_RE.findall(text.lower()))


def surface(query: str, k: int = 3, *, scope: Optional[str] = None) -> List[str]:
    """Keyword-overlap surfacing over active cards, ranked by count.

    Cards whose scope tags include `scope` sort first when scope is given.
    """
    active = list_active()
    if not active:
        return []
    q_tokens = _tokens(query or "")
    if not q_tokens:
        return []
    scored = []
    for card in active:
        text = str(card.get("text", ""))
        overlap = len(q_tokens & _tokens(text))
        if not overlap:
            continue
        boost = 1 if scope and scope in (card.get("scopes") or []) else 0
        scored.append((boost, overlap, text))
    scored.sort(key=lambda t: (-t[0], -t[1]))
    return [text for _, _, text in scored[:k]]
