"""quickdial: Opera's Speed Dial reborn as a LEVI-native addition.

Dead software revived, LEVI-style: the Presto-era Opera turned the new-tab
page into a one-glance launchpad of visual dials — your intentions, not a
feed — and gave power users a full command vocabulary (mouse gestures,
rocker strokes) that needed no visible chrome. The engine switch of 2013
killed the power-user layer.

``levi.quickdial`` is the addition, not a rebuild: named slots pin the
LEVI workflow commands you run constantly (growth status, news refresh,
pulse, agent chat...). ``dial`` recalls one instantly. Opera's gestures
return as single-key *chords*: one keystroke, no visible chrome, no
analytics, no cloud.

Safety contract (hard):
- Slots store argv lists only — never shell strings, never evaluated.
- ``dial`` prints the exact command; it only *runs* with ``--run``, via
  ``os.execvp`` (no shell, no interpolation). There is no backgrounding,
  no piping, no chaining. One argv, one process, owner's eyes only.
- Store is plain JSON under owner-only ``~/.levi/quickdial/``.
- Names are slug-checked; chords are single printable ASCII keys.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
_CHORD_RE = re.compile(r"^[\x21-\x7e]$")  # one printable ASCII char, no space


def home() -> Path:
    """LEVI home honoring the LEVI_HOME override (used by tests)."""
    return Path(os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi"))


def store_dir() -> Path:
    return home() / "quickdial"


def store_path() -> Path:
    return store_dir() / "dials.json"


@dataclass
class Slot:
    name: str
    argv: List[str]
    description: str = ""
    chord: str = ""
    uses: int = 0

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "argv": self.argv,
            "description": self.description,
            "chord": self.chord,
            "uses": self.uses,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Slot":
        return cls(
            name=str(data["name"]),
            argv=[str(a) for a in data["argv"]],
            description=str(data.get("description", "")),
            chord=str(data.get("chord", "")),
            uses=int(data.get("uses", 0)),
        )


def _ensure_store() -> Path:
    d = store_dir()
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    p = store_path()
    if not p.exists():
        _atomic_write(p, {"slots": []})
    return p


def _atomic_write(path: Path, payload: Dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".dials-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    os.chmod(path, 0o600)


def load() -> List[Slot]:
    p = _ensure_store()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {"slots": []}
    slots = []
    for raw in data.get("slots", []):
        try:
            slots.append(Slot.from_dict(raw))
        except (KeyError, TypeError, ValueError):
            continue  # deny-closed: skip corrupt entries, never crash
    return slots


def save(slots: List[Slot]) -> None:
    _atomic_write(store_path(), {"slots": [s.to_dict() for s in slots]})


def check_name(name: str) -> str:
    if not _NAME_RE.match(name):
        raise ValueError(
            "bad slot name %r: lowercase letters, digits, - and _ only, "
            "max 40 chars" % name
        )
    return name


def check_chord(chord: str) -> str:
    if chord and not _CHORD_RE.match(chord):
        raise ValueError(
            "bad chord %r: one printable ASCII character, no spaces" % chord
        )
    return chord


def pin(
    name: str,
    command: "str | List[str]",
    description: str = "",
    chord: str = "",
    replace: bool = False,
) -> Slot:
    """Pin a command to a named slot. Never executes anything.

    ``command`` may be a shell-style string (parsed with shlex) or an
    argv list (used verbatim — this is how the CLI passes the ``--``
    remainder, so arguments containing spaces survive intact).
    """
    check_name(name)
    check_chord(chord)
    if isinstance(command, str):
        try:
            argv = shlex.split(command, posix=True)
        except ValueError as exc:
            raise ValueError("could not parse command %r: %s" % (command, exc)) from exc
    else:
        argv = [str(a) for a in command]
    if not argv:
        raise ValueError("refusing to pin an empty command")
    slots = load()
    existing = next((s for s in slots if s.name == name), None)
    if existing is not None and not replace:
        raise ValueError("slot %r already pinned; use replace=True to overwrite" % name)
    if chord:
        clash = next((s for s in slots if s.chord == chord and s.name != name), None)
        if clash:
            raise ValueError(
                "chord %r is already bound to slot %r" % (chord, clash.name)
            )
    slot = Slot(name=name, argv=argv, description=description, chord=chord)
    if existing is not None:
        slot.uses = existing.uses
        slots = [slot if s.name == name else s for s in slots]
    else:
        slots.append(slot)
    save(slots)
    return slot


def unpin(name: str) -> bool:
    slots = load()
    kept = [s for s in slots if s.name != name]
    if len(kept) == len(slots):
        return False
    save(kept)
    return True


def find(name_or_index: str, slots: Optional[List[Slot]] = None) -> Slot:
    slots = load() if slots is None else slots
    if name_or_index.isdigit():
        idx = int(name_or_index) - 1
        if 0 <= idx < len(slots):
            return slots[idx]
        raise KeyError("no slot #%s" % name_or_index)
    for s in slots:
        if s.name == name_or_index:
            return s
    raise KeyError("no slot named %r" % name_or_index)


def find_by_chord(chord: str, slots: Optional[List[Slot]] = None) -> Slot:
    slots = load() if slots is None else slots
    for s in slots:
        if s.chord == chord:
            return s
    raise KeyError("no slot bound to chord %r" % chord)


def dial(slot: Slot) -> List[str]:
    """Mark a use and return the argv. Printing/running is the CLI's job."""
    slots = load()
    for s in slots:
        if s.name == slot.name:
            s.uses += 1
    save(slots)
    return list(slot.argv)


def render(slot: Slot) -> str:
    """The exact command line this slot would run, safely shell-quoted."""
    return shlex.join(slot.argv)


def seed() -> List[Slot]:
    """Pin a starter set of honest local-first LEVI workflows. Idempotent."""
    starters = [
        (
            "pulse",
            "python3 -m levi.perpetual pulse",
            "perpetual engine proof-of-life",
            "p",
        ),
        ("growth", "python3 -m levi.growth status", "growth loop status", "g"),
        ("news", "python3 -m levi.news refresh", "daily news corpus refresh", "n"),
    ]
    slots = load()
    added = []
    for name, command, desc, chord in starters:
        if any(s.name == name for s in slots):
            continue
        try:
            added.append(pin(name, command, description=desc, chord=chord))
        except ValueError:
            continue
    return added
