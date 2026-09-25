"""Orkut-style squares — membership squares with join gates, scrap wall, testimonials.

The original hunt finding: "Orkut squares" — interest squares
(communities) with **join gates, scrap wall, testimonials**. LEVI's
boards already have chartered areas (``areas.py``: moderation, seen
tracking, packet export); squares are the social layer on top: you join
a square, you write on its scrap wall, you leave testimonials for its
members.

LAWS
----
1. **Join gate, closed by default.** A square has a join mode:
   ``open`` (anyone joins), ``approval`` (moderator approves), or
   ``invite`` (a member must vouch). Unknown modes are refused.
2. **Scrap wall is members-only.** Only members can write scraps, and
   only on squares they belong to. The wall shows newest first.
3. **Testimonials are signed and retractable.** A testimonial names its
   author, targets a member, and can be withdrawn by its author —
   withdrawal removes it everywhere, not just hides it.
4. **Nothing here replaces areas.** Squares store their own JSON under
   ``~/.levi/boards/squares/``; chartered areas are untouched.

stdlib-only, local-first, no network.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "SquareError",
    "create_square",
    "get_square",
    "list_squares",
    "request_join",
    "approve_join",
    "invite",
    "members",
    "is_member",
    "write_scrap",
    "scraps",
    "leave_testimonial",
    "withdraw_testimonial",
    "testimonials",
    "JOIN_MODES",
]

JOIN_MODES = ("open", "approval", "invite")


class SquareError(Exception):
    """A square operation was refused."""


def _home() -> Path:
    d = Path.home() / ".levi" / "boards" / "squares"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _name_ok(name: str) -> bool:
    name = (name or "").strip()
    return bool(name) and len(name) <= 64 and "/" not in name and "\\" not in name


def _dir(name: str, create: bool = False) -> Path:
    if not _name_ok(name):
        raise SquareError(f"bad square name {name!r}")
    d = _home() / name.strip()
    if create:
        d.mkdir(parents=True, exist_ok=True)
    elif not d.exists():
        raise SquareError(f"unknown square {name!r}")
    return d


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def _load(name: str) -> Dict[str, Any]:
    d = _dir(name)
    state = _read(d / "square.json", None)
    if not isinstance(state, dict):
        raise SquareError(f"square {name!r} is corrupted")
    return state


def _save(name: str, state: Dict[str, Any]) -> None:
    _write(_dir(name, create=True) / "square.json", state)


# ---------------------------------------------------------------- create


def create_square(name: str, description: str, founder: str,
                  join_mode: str = "approval") -> Dict[str, Any]:
    """Found a square. The founder is its first member and moderator."""
    if not _name_ok(name):
        raise SquareError(f"bad square name {name!r}")
    if join_mode not in JOIN_MODES:
        raise SquareError(f"join_mode must be one of {JOIN_MODES}")
    if not (founder or "").strip():
        raise SquareError("founder name is required")
    d = _home() / name.strip()
    if (d / "square.json").exists():
        raise SquareError(f"square {name!r} already exists")
    state = {
        "name": name.strip(),
        "description": (description or "").strip(),
        "founder": founder.strip(),
        "join_mode": join_mode,
        "created_at": _now(),
        "members": {founder.strip(): {"joined_at": _now(), "role": "moderator"}},
        "pending": {},     # name -> requested_at (approval mode)
        "invites": {},     # invitee -> inviter (invite mode)
        "scraps": [],      # newest-first list of dicts
        "testimonials": [],  # list of dicts
    }
    _save(name, state)
    return {"name": state["name"], "join_mode": join_mode,
            "members": list(state["members"])}


def get_square(name: str) -> Dict[str, Any]:
    """Public face of a square (no pending/invite internals)."""
    s = _load(name)
    return {
        "name": s["name"],
        "description": s["description"],
        "founder": s["founder"],
        "join_mode": s["join_mode"],
        "created_at": s["created_at"],
        "member_count": len(s["members"]),
        "scrap_count": len(s["scraps"]),
        "testimonial_count": len(s["testimonials"]),
    }


def list_squares() -> List[Dict[str, Any]]:
    """Every square's public face, sorted by name."""
    out = []
    for d in sorted(_home().iterdir()):
        if (d / "square.json").exists():
            try:
                out.append(get_square(d.name))
            except SquareError:
                continue
    return out


# ---------------------------------------------------------------- joining


def is_member(name: str, person: str) -> bool:
    return person.strip() in _load(name)["members"]


def members(name: str) -> List[str]:
    return sorted(_load(name)["members"])


def request_join(name: str, person: str) -> str:
    """Ask to join. Returns the outcome: ``joined`` | ``pending`` | ``invited-needed``."""
    person = person.strip()
    if not person:
        raise SquareError("a name is required to join")
    s = _load(name)
    if person in s["members"]:
        return "joined"  # already in — idempotent
    mode = s["join_mode"]
    if mode == "open":
        s["members"][person] = {"joined_at": _now(), "role": "member"}
        _save(name, s)
        return "joined"
    if mode == "approval":
        s["pending"][person] = _now()
        _save(name, s)
        return "pending"
    # invite mode
    if person in s["invites"]:
        inviter = s["invites"].pop(person)
        s["members"][person] = {"joined_at": _now(), "role": "member",
                                "invited_by": inviter}
        _save(name, s)
        return "joined"
    return "invited-needed"


def approve_join(name: str, person: str, moderator: str) -> None:
    """Approve a pending join request. Moderators only."""
    s = _load(name)
    mod = s["members"].get(moderator.strip())
    if not mod or mod.get("role") != "moderator":
        raise SquareError(f"{moderator!r} is not a moderator of {name!r}")
    person = person.strip()
    if person not in s["pending"]:
        raise SquareError(f"{person!r} has no pending request in {name!r}")
    s["pending"].pop(person)
    s["members"][person] = {"joined_at": _now(), "role": "member",
                            "approved_by": moderator.strip()}
    _save(name, s)


def invite(name: str, invitee: str, inviter: str) -> None:
    """A member vouches for an invitee (invite-mode squares)."""
    s = _load(name)
    if s["join_mode"] != "invite":
        raise SquareError(f"{name!r} does not use invite mode")
    if inviter.strip() not in s["members"]:
        raise SquareError(f"{inviter!r} is not a member of {name!r}")
    if not invitee.strip():
        raise SquareError("invitee name is required")
    s["invites"][invitee.strip()] = inviter.strip()
    _save(name, s)


# ---------------------------------------------------------------- scrap wall


def write_scrap(name: str, author: str, text: str) -> Dict[str, Any]:
    """Write on the square's scrap wall. Members only."""
    if not is_member(name, author):
        raise SquareError(f"{author!r} is not a member of {name!r}: wall is members-only")
    text = (text or "").strip()
    if not text:
        raise SquareError("scrap text is required")
    if len(text) > 2000:
        raise SquareError("scraps are capped at 2000 characters")
    s = _load(name)
    scrap = {"author": author.strip(), "text": text, "at": _now()}
    s["scraps"].insert(0, scrap)  # newest first
    _save(name, s)
    return scrap


def scraps(name: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Newest-first scraps. Public to read; members-only to write."""
    return _load(name)["scraps"][: max(1, int(limit))]


# ---------------------------------------------------------------- testimonials


def leave_testimonial(name: str, author: str, subject: str, text: str) -> Dict[str, Any]:
    """Leave a signed testimonial for a fellow member."""
    if not is_member(name, author):
        raise SquareError(f"{author!r} is not a member of {name!r}")
    if not is_member(name, subject):
        raise SquareError(f"{subject!r} is not a member of {name!r}")
    text = (text or "").strip()
    if not text:
        raise SquareError("testimonial text is required")
    s = _load(name)
    t = {
        "id": f"t{len(s['testimonials']) + 1:04d}",
        "author": author.strip(),
        "subject": subject.strip(),
        "text": text,
        "at": _now(),
    }
    s["testimonials"].append(t)
    _save(name, s)
    return t


def withdraw_testimonial(name: str, testimonial_id: str, author: str) -> None:
    """Withdraw your own testimonial. Removes it everywhere, not hides it."""
    # MONEY LAW: withdraws a *testimonial* (signed text), never funds.
    # Local JSON only — no currency, no rails, nothing moves.
    s = _load(name)
    for i, t in enumerate(s["testimonials"]):
        if t["id"] == testimonial_id:
            if t["author"] != author.strip():
                raise SquareError("only the author can withdraw a testimonial")
            s["testimonials"].pop(i)
            _save(name, s)
            return
    raise SquareError(f"unknown testimonial {testimonial_id!r}")


def testimonials(name: str, subject: Optional[str] = None) -> List[Dict[str, Any]]:
    """All testimonials, optionally filtered to one member."""
    ts = _load(name)["testimonials"]
    if subject:
        ts = [t for t in ts if t["subject"] == subject.strip()]
    return list(ts)
