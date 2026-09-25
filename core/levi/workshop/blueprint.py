"""Blueprints — deterministic agent compositions, saved and loaded.

A blueprint composes five real parts:

  agent      — one id from the agent registry (471 twin-pair agents)
  specialist — one id from the bounded specialist roster
  substrate  — one mind substrate from the roster matrix
  organ      — one organ from the deny-closed organ registry
  legion_role — one named Legion crew role

plus an optional nanobit format (the canonical micro-companion format),
an optional original lineage (one of the eleven originals), an optional
list of capability/semantic claims, and a free-text twin_note.

Determinism: the fingerprint is sha256 over the canonical JSON of the
spec fields only (name, parts, nanobit, original, claims, twin_note). Two identical specs
produce identical fingerprints; ``generated_at`` is stored on the saved
record but never enters the fingerprint.

OPEN DECISION (twin ambiguity): ``twin_note`` is free text and carries
NO semantics. The workshop does not decide whether twins are
hybrid/switchable, always-on, or what "inverse twin" means. Validation
accepts the note without interpreting it.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


@dataclass
class Blueprint:
    """One deterministic agent composition."""

    name: str
    agent: str
    specialist: str
    substrate: str
    organ: str
    legion_role: str
    nanobit: str = ""
    original: str = ""
    claims: List[str] = field(default_factory=list)
    twin_note: str = ""
    fingerprint: str = ""

    def spec(self) -> Dict[str, Any]:
        """The fingerprinted spec: parts + nanobit + original + claims +
        twin note, nothing else."""
        return {
            "name": self.name,
            "agent": self.agent,
            "specialist": self.specialist,
            "substrate": self.substrate,
            "organ": self.organ,
            "legion_role": self.legion_role,
            "nanobit": self.nanobit,
            "original": self.original,
            "claims": sorted(self.claims),
            "twin_note": self.twin_note,
        }

    def seal(self) -> "Blueprint":
        """Compute the deterministic fingerprint over the spec."""
        self.fingerprint = hashlib.sha256(
            _canonical(self.spec()).encode("utf-8")
        ).hexdigest()
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {**self.spec(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Blueprint":
        data = dict(raw)
        data.pop("generated_at", None)
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


def compose_blueprint(
    name: str,
    agent: str,
    specialist: str,
    substrate: str,
    organ: str,
    legion_role: str,
    nanobit: str = "",
    original: str = "",
    claims: List[str] | None = None,
    twin_note: str = "",
) -> Blueprint:
    """Compose and seal a blueprint. Deterministic: same inputs, same seal."""
    return Blueprint(
        name=name,
        agent=agent,
        specialist=specialist,
        substrate=substrate,
        organ=organ,
        legion_role=legion_role,
        nanobit=nanobit,
        original=original,
        claims=list(claims or []),
        twin_note=twin_note,
    ).seal()


def _store_dir() -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    d = Path(base).expanduser() / "workshop" / "blueprints"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def save_blueprint(bp: Blueprint) -> Path:
    """Save a sealed blueprint to disk. Returns the path written."""
    if not bp.fingerprint:
        bp.seal()
    record = {
        **bp.to_dict(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    path = _store_dir() / (bp.name + ".json")
    path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.chmod(path, 0o600)
    return path


def load_blueprint(name: str) -> Blueprint:
    """Load a blueprint by name. Refuses missing or tampered records."""
    path = _store_dir() / (name + ".json")
    if not path.exists():
        raise FileNotFoundError(f"no saved blueprint named {name!r}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    bp = Blueprint.from_dict(raw)
    sealed = bp.seal().fingerprint
    if sealed != raw.get("fingerprint"):
        raise ValueError(
            f"blueprint {name!r} failed integrity check: "
            "stored fingerprint does not match the spec"
        )
    return bp


def list_blueprints() -> List[str]:
    """Names of saved blueprints."""
    d = _store_dir()
    return sorted(p.stem for p in d.glob("*.json"))
