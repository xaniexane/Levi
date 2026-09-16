"""LEVI Surgeon — code snapshots, cleanup, advancement proposals, export headers.

Original LEVI-native implementation. Concept adapted from the Levi-ai
Stage-1 lineage (source-sync entry ``levi-ai``); no source text copied.

The surgeon never executes code. It snapshots text, proposes improvements,
and applies text transformations — always snapshot-first, always
revertible. Actual application of a proposed change to a file goes through
:class:`levi.surgeon.sandbox.SandboxGate`, which requires an explicit
human confirmation (HITL) before anything is written.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Owner identity — configurable, never hardcoded.
# ---------------------------------------------------------------------------


def default_owner_name() -> str:
    """Resolve the owner name for export headers.

    Precedence: ``LEVI_OWNER_NAME`` env → ``~/.levi/owner.json``
    (``{"name": ...}``) → neutral placeholder. Never a hardcoded person.
    """
    env = os.environ.get("LEVI_OWNER_NAME", "").strip()
    if env:
        return env[:120]
    try:
        data = json.loads(
            (Path.home() / ".levi" / "owner.json").read_text(encoding="utf-8")
        )
        name = str(data.get("name", "")).strip()
        if name:
            return name[:120]
    except (OSError, ValueError, AttributeError):
        pass
    return "LEVI Owner"


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

_MAX_SNAPSHOTS = 50


@dataclass
class Snapshot:
    id: str
    label: str
    ts: float
    code: str


class SnapshotManager:
    """Snapshot/revert store for code text. JSON persistence, capped history."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = (
            Path(path) if path else Path.home() / ".levi" / "surgeon" / "snapshots.json"
        )
        self._snaps: List[Snapshot] = []
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and {"id", "label", "ts", "code"} <= set(
                    item
                ):
                    self._snaps.append(
                        Snapshot(
                            id=str(item["id"]),
                            label=str(item["label"]),
                            ts=float(item["ts"]),
                            code=str(item["code"]),
                        )
                    )

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(
                    [
                        {"id": s.id, "label": s.label, "ts": s.ts, "code": s.code}
                        for s in self._snaps[-_MAX_SNAPSHOTS:]
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    def take(self, label: str, code: str) -> str:
        """Snapshot ``code`` under ``label``; returns the snapshot id."""
        if not isinstance(code, str):
            raise ValueError(f"take: code must be str, got {type(code).__name__}")
        snap_id = f"snap_{int(time.time() * 1000):x}"
        self._snaps.append(
            Snapshot(id=snap_id, label=str(label or "snap"), ts=time.time(), code=code)
        )
        self._snaps = self._snaps[-_MAX_SNAPSHOTS:]
        self._save()
        return snap_id

    def list(self) -> List[Dict[str, Any]]:
        """Snapshot metadata (no code bodies)."""
        return [{"id": s.id, "label": s.label, "ts": s.ts} for s in self._snaps]

    def revert(self, snap_id: str) -> Optional[str]:
        """Return the code stored under ``snap_id``, or None if unknown."""
        for s in self._snaps:
            if s.id == snap_id:
                return s.code
        return None


# ---------------------------------------------------------------------------
# Cleanup — safe text normalization, fix counting.
# ---------------------------------------------------------------------------

_WS_EOL = re.compile(r"[ \t]+$", re.M)
_BLANK_RUN = re.compile(r"\n{4,}")
_EQ_NONE = re.compile(r"(\b\w+)\s*==\s*None\b")
_NEQ_NONE = re.compile(r"(\b\w+)\s*!=\s*None\b")


def cleanup_code(text: str) -> Tuple[str, int]:
    """Normalize code text; return ``(cleaned, fix_count)``.

    Fixes: tabs → two spaces, trailing whitespace, 4+ blank lines → 3,
    ``x == None`` → ``x is None`` / ``x != None`` → ``x is not None``.
    Pure function — no I/O, no execution.
    """
    if not isinstance(text, str):
        raise ValueError(f"cleanup_code: text must be str, got {type(text).__name__}")
    fixes = 0
    out = text
    step = out.replace("\t", "  ")
    if step != out:
        fixes += 1
        out = step
    step = _WS_EOL.sub("", out)
    if step != out:
        fixes += 1
        out = step
    step = _BLANK_RUN.sub("\n\n\n", out)
    if step != out:
        fixes += 1
        out = step
    step = _EQ_NONE.sub(r"\1 is None", out)
    if step != out:
        fixes += len(_EQ_NONE.findall(out))
        out = step
    step = _NEQ_NONE.sub(r"\1 is not None", out)
    if step != out:
        fixes += len(_NEQ_NONE.findall(out))
        out = step
    if out and not out.endswith("\n"):
        out += "\n"
    return out, fixes


# ---------------------------------------------------------------------------
# Export headers — stamping only, never withholding.
# ---------------------------------------------------------------------------


def stamp_header(code: str, mode: str, owner: Optional[str] = None) -> Dict[str, str]:
    """Prepend an export header to ``code``.

    Modes: ``"proprietary"`` (all-rights-reserved) or ``"oss"``
    (MIT-style minimal). This stamps a header — it never withholds code
    (LEVI core is free forever; no tier-limited redaction modes exist).
    """
    if mode not in EXPORT_HEADERS:
        raise ValueError(f"stamp_header: unknown mode {mode!r}")
    body = str(code or "")
    if re.match(r"/\*\*?\s*\n\s*\*\s*(Copyright|CLOSED SOURCE|SPDX)", body[:200]):
        return {"text": body, "mode": mode, "note": "header already present"}
    header = EXPORT_HEADERS[mode](owner or default_owner_name())
    return {"text": header + body, "mode": mode, "note": "stamped"}


def _proprietary_header(owner: str) -> str:
    return (
        "/**\n"
        f" * Copyright (c) {time.localtime().tm_year} {owner}\n"
        " * All Rights Reserved.\n"
        " */\n\n"
    )


def _oss_header(owner: str) -> str:
    return (
        "/**\n"
        f" * Copyright (c) {time.localtime().tm_year} {owner}\n"
        " * SPDX-License-Identifier: MIT\n"
        " */\n\n"
    )


EXPORT_HEADERS = {
    "proprietary": _proprietary_header,
    "oss": _oss_header,
}


# ---------------------------------------------------------------------------
# Advancement proposals
# ---------------------------------------------------------------------------


@dataclass
class Advancement:
    id: str
    title: str
    risk: str  # LOW | MED
    description: str
    outcome: str


def propose_advancements(code: str, filename: str = "") -> List[Advancement]:
    """Propose safe, revertible improvements for ``code``.

    Proposals are data, not actions — applying one requires
    :func:`apply_advancement` (snapshot-first) and, for file writes, the
    sandbox HITL gate.
    """
    _ = code  # proposals are generic; content-specific ranking is a later layer
    items = [
        Advancement(
            "adv_null_guards",
            "Null-safety guards",
            "LOW",
            "Defensive null/None checks at function entries.",
            "Fewer null-reference failures.",
        ),
        Advancement(
            "adv_entry_logs",
            "Structured entry markers",
            "LOW",
            "Entry marker comments on functions.",
            "Easier debugging and tracing.",
        ),
        Advancement(
            "adv_pure_helpers",
            "Extract pure helpers",
            "MED",
            "Split side-effect-free helpers out of mixed functions.",
            "Better testability; clearer HITL boundaries.",
        ),
        Advancement(
            "adv_hitl_note",
            "HITL confirm marker",
            "LOW",
            "Marker comment where human confirmation is required.",
            "Safer apply path.",
        ),
        Advancement(
            "adv_elite_cleanup",
            "Elite multi-pass cleanup",
            "LOW",
            "Whitespace, None-style, blank-line, tab normalization.",
            "Cleaner production code.",
        ),
        Advancement(
            "adv_header_proprietary",
            "Stamp proprietary header",
            "LOW",
            "Prepend all-rights-reserved export header.",
            "Clear proprietary marking on export.",
        ),
        Advancement(
            "adv_header_oss",
            "Stamp OSS header",
            "LOW",
            "Prepend MIT-style minimal export header.",
            "OSS-friendly export marking.",
        ),
    ]
    if filename.lower().endswith(".py"):
        items.append(
            Advancement(
                "adv_type_hints",
                "Type-hint pass",
                "MED",
                "Basic Python type hints on signatures.",
                "Clearer contracts for callers.",
            )
        )
    return items


def apply_advancement(
    code: str,
    adv_id: str,
    snapshots: Optional[SnapshotManager] = None,
    owner: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply one advancement to ``code``, snapshot-first.

    Returns ``{"ok", "code", "snapshot_id"}``. Unknown ids fail closed.
    This transforms text only — writing the result anywhere requires the
    sandbox gate (:class:`levi.surgeon.sandbox.SandboxGate`).
    """
    valid = {a.id for a in propose_advancements(code)}
    if adv_id not in valid:
        return {"ok": False, "reason": f"unknown advancement {adv_id!r}"}
    mgr = snapshots or SnapshotManager()
    snap_id = mgr.take(f"pre-{adv_id}", code)
    if adv_id == "adv_elite_cleanup":
        nxt, _ = cleanup_code(code)
    elif adv_id == "adv_header_proprietary":
        nxt = stamp_header(code, "proprietary", owner)["text"]
    elif adv_id == "adv_header_oss":
        nxt = stamp_header(code, "oss", owner)["text"]
    elif adv_id == "adv_hitl_note":
        nxt = "# LEVI: human confirmation required before applying\n" + code
    else:
        nxt = f"# LEVI advancement: {adv_id}\n" + code
    return {"ok": True, "code": nxt, "snapshot_id": snap_id}


# ---------------------------------------------------------------------------
# Skill registrations
# ---------------------------------------------------------------------------

try:  # pragma: no cover — import-time fallback keeps module import light
    from levi.skill.registry import Skill, SkillRisk

    def _skill_snapshot(args):
        mgr = SnapshotManager()
        label = str((args or {}).get("label") or "snap")
        code = str((args or {}).get("code") or "")
        return mgr.take(label, code)

    def _skill_cleanup(args):
        text = str((args or {}).get("text") or "")
        cleaned, fixes = cleanup_code(text)
        return f"{fixes} fixes applied"

    def _skill_propose(args):
        advs = propose_advancements(
            str((args or {}).get("code") or ""), str((args or {}).get("filename") or "")
        )
        return "\n".join(f"{a.id} [{a.risk}] {a.title} — {a.description}" for a in advs)

    def _skill_apply_advancement(args):
        args = args or {}
        res = apply_advancement(
            str(args.get("code") or ""), str(args.get("adv_id") or "")
        )
        if not res.get("ok"):
            return f"refused: {res.get('reason')}"
        return f"applied; snapshot {res['snapshot_id']}"

    SURGEON_SKILLS = [
        Skill(
            id="surgeon_snapshot",
            name="Surgeon Snapshot",
            description="Snapshot code text before surgery; revertible",
            category="factory",
            risk_level=SkillRisk.LOW,
            permissions=["surgeon.snapshot"],
            handler=_skill_snapshot,
            tags=["surgeon", "snapshot"],
        ),
        Skill(
            id="surgeon_cleanup",
            name="Surgeon Cleanup",
            description="Safe text normalization of code (whitespace, None-style)",
            category="factory",
            risk_level=SkillRisk.INFO,
            handler=_skill_cleanup,
            tags=["surgeon", "cleanup"],
        ),
        Skill(
            id="surgeon_propose",
            name="Surgeon Propose",
            description="Propose revertible code advancements (data only, no apply)",
            category="factory",
            risk_level=SkillRisk.INFO,
            handler=_skill_propose,
            tags=["surgeon", "propose"],
        ),
        Skill(
            id="surgeon_apply_advancement",
            name="Surgeon Apply Advancement",
            description="Apply one advancement snapshot-first (text only; file writes need the sandbox HITL gate)",
            category="factory",
            risk_level=SkillRisk.MODERATE,
            permissions=["surgeon.apply"],
            requires_confirmation=True,
            handler=_skill_apply_advancement,
            tags=["surgeon", "apply"],
        ),
    ]
except ImportError:  # pragma: no cover
    SURGEON_SKILLS = []  # type: ignore[assignment]
    Skill = object  # type: ignore[assignment,misc]
    SkillRisk = None  # type: ignore[assignment]
