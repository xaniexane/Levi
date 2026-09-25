"""Omega Triple Threat Elite — host-agnostic code-surgeon core.

Chauncey's confirmed term (2026-09-22) for the surgeon/converter logic
family. This module is the ONE consolidated, host-agnostic implementation:
zero Acode APIs, zero editor-specific imports — pure functions and classes
plus thin per-host adapters (Acode, Hicomb) showing how each side calls it.
The hosts own all I/O and all permission UX; this core never touches an
editor, a file, or a network socket except through the single gated
``approve_and_write`` path.

Lineage (originals-first):
- ``levi_surgeon.js`` (``LeviSurgeon`` class) from Chauncey's August-2026
  Acode plugin lineage — the true original: snapshot/revert, ``cleanup()``,
  four version modes with headers and body limiting, advancement proposals,
  ``applyAdvancement`` gated on ``cybrus.allow('enhance', opts)``.
- ``ENCYCLOPEDIA.md`` (same lineage): "Surgeon — Multi-pass cleanup (tabs,
  trailing space, blank lines, None style). Four version modes with headers
  and body limiting. Snapshots before every mutation. Advancement proposals
  (ranked by MathVerse). Apply only after Cybrus allow."
- ``surgeonCleanup`` / ``addClosedHeader`` in his Acode plugin file
  (``~/workspace/user/files/main.js``): the phone-side Omega Surgeon —
  per-line trailing-whitespace counting, tabs -> 4 spaces. Ported
  faithfully as :mod:`levi.uniforge.surgeon`; this canonical core follows
  ``levi_surgeon.js``'s 2-space rules.

Known-bad patterns from the old Omega scripts are FORBIDDEN here, not
ported: the lossy "comment compression" that deleted documentation runs
(``omega_code_surgeon_elite.py``) is refused by construction — the
``assert_no_doc_loss`` guard machine-checks that no comment line is ever
removed. There is no ``--yes``-style bypass anywhere in this module.

LAWS (invariants; each has a machine-checkable gate in
``tests/test_triple_threat.py``):
1. Snapshot before every mutation.
2. Never silent apply — transforms return proposed text; the ONLY
   target-file write is ``approve_and_write``, which requires explicit
   ``confirmed=True``. (The snapshot journal persists beside it — his
   original kept every snapshot in localStorage; the journal is
   provenance, not a target write.)
3. Documentation is never deleted.
4. Behavioral parity with the original's cleanup rules: tabs -> 2 spaces
   (NOT 4 — the 4-space ports in ``levi.surgeon.elite`` and
   ``levi.uniforge.surgeon`` deviate from the original), trailing
   whitespace stripped, 4+ newlines -> 3, ``== None`` -> ``is None`` /
   ``!= None`` -> ``is not None`` per occurrence, trailing-newline state
   preserved.
5. The four version modes keep his exact semantics; the two body-limiting
   modes withhold code and therefore require explicit owner confirmation.
6. Advancement apply consults an injected Cybrus-style ``allow`` hook and
   fails closed on denial — his ``cybrus.allow('enhance', opts)`` gate,
   host-agnostic.

Deliberate hardenings vs the original (his laws, applied where the
original was looser): unknown version modes raise instead of silently
falling back to ``closed_private``; the allow hook fails closed when no
hook is attached (the original skips the gate when cybrus is absent);
unknown advancement ids fail closed (the original prepends a generic
comment); the two withholding modes require explicit owner confirmation
(the original applies them freely).

Legacy shims (kept working, NOT reimplemented here — nothing is thrown
away): ``levi.surgeon.surgeon`` (2-space port, always appends newline,
only 2 of 4 version modes), ``levi.surgeon.elite`` (4-space, adds
augmented-assignment and missing-colon passes beyond the original),
``levi.uniforge.surgeon`` (4-space, diagnose->fix->verify with an
un-gated ``apply=True`` file write — route new work through
``approve_and_write`` instead).

stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

__all__ = [
    "VERSION_MODES",
    "ORIGINAL_SURGEON_VERSION",
    "CleanupResult",
    "DocLossError",
    "Snapshot",
    "SnapshotStore",
    "Advancement",
    "AllowHook",
    "StampedResult",
    "VersionMode",
    "cleanup",
    "assert_no_doc_loss",
    "default_owner",
    "format_version",
    "propose_advancements",
    "apply_advancement",
    "approve_and_write",
    "AcodeAdapter",
    "HicombAdapter",
]


#: Version string of Chauncey's original ``levi_surgeon.js`` this core ports.
ORIGINAL_SURGEON_VERSION = "15.4.1-private"


# ---------------------------------------------------------------------------
# Owner identity — explicit arg → env → his original default (overridable).
# ---------------------------------------------------------------------------


def default_owner(explicit: Optional[str] = None) -> str:
    """Resolve the owner name stamped into export headers.

    Precedence: explicit argument → ``LEVI_OWNER_NAME`` env → Chauncey's
    original default from ``levi_surgeon.js``. Never unchangeable.
    """
    if explicit and explicit.strip():
        return explicit.strip()[:120]
    env = os.environ.get("LEVI_OWNER_NAME", "").strip()
    if env:
        return env[:120]
    return "Chauncey (CJ) Logan — LEVI Apex"


# ---------------------------------------------------------------------------
# Cleanup — his five rules, verbatim semantics.
# ---------------------------------------------------------------------------

_EQ_NONE = re.compile(r"(\b\w+)\s*==\s*None\b")
_NE_NONE = re.compile(r"(\b\w+)\s*!=\s*None\b")
_WS_EOL = re.compile(r"[ \t]+$", re.M)
_BLANK_RUN = re.compile(r"\n{4,}")


@dataclass
class CleanupResult:
    text: str
    fixes: Dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.fixes.values())


def cleanup(text: str) -> CleanupResult:
    """Apply the original's five cleanup rules. Pure — no I/O, no execution.

    1. tabs -> 2 spaces (his original; NOT 4)
    2. strip trailing whitespace on every line
    3. 4+ consecutive newlines -> exactly 3
    4. ``<name> == None`` -> ``<name> is None`` (counted per occurrence)
    5. ``<name> != None`` -> ``<name> is not None`` (counted per occurrence)
    Trailing-newline state of the input is preserved (his guard, verbatim).
    """
    if not isinstance(text, str):
        raise ValueError(f"cleanup: text must be str, got {type(text).__name__}")
    fixes: Dict[str, int] = {
        "tabs": 0,
        "trailing_whitespace": 0,
        "blank_lines": 0,
        "eq_none": 0,
        "ne_none": 0,
    }
    t = text
    step = t.replace("\t", "  ")
    if step != t:
        fixes["tabs"] = 1
        t = step
    step = _WS_EOL.sub("", t)
    if step != t:
        fixes["trailing_whitespace"] = 1
        t = step
    step = _BLANK_RUN.sub("\n\n\n", t)
    if step != t:
        fixes["blank_lines"] = 1
        t = step
    step, n = _EQ_NONE.subn(r"\1 is None", t)
    fixes["eq_none"] = n
    t = step
    step, n = _NE_NONE.subn(r"\1 is not None", t)
    fixes["ne_none"] = n
    t = step
    # His verbatim guard: only restore the trailing newline if the input had one.
    if not t.endswith("\n") and text.endswith("\n"):
        t += "\n"
    assert_no_doc_loss(text, t)
    return CleanupResult(text=t, fixes=fixes)


# ---------------------------------------------------------------------------
# Documentation-loss guard — the old comment-compression bug is forbidden.
# ---------------------------------------------------------------------------


class DocLossError(ValueError):
    """Raised when a transform would delete documentation."""


def _is_comment_line(ln: str) -> bool:
    stripped = ln.lstrip()
    return stripped.startswith("#") or stripped.startswith("//")


def _normalized_comment_line(ln: str) -> str:
    """A comment line with the documented non-deleting rewrites applied.

    The guard must tolerate exactly what ``cleanup()`` is allowed to do to
    a comment — tabs -> 2 spaces, trailing-whitespace strip, ``== None``
    -> ``is None`` / ``!= None`` -> ``is not None`` — and flag everything
    else. None of these rewrites can delete a line, so anything still
    missing after normalization is a genuine deletion.
    """
    ln = ln.replace("\t", "  ")
    ln = _EQ_NONE.sub(r"\1 is None", ln)
    ln = _NE_NONE.sub(r"\1 is not None", ln)
    return ln.rstrip()


def _comment_lines(src: str) -> List[str]:
    """Every ``#``/``//``-comment line of ``src``, normalized (see above)."""
    return [
        _normalized_comment_line(ln) for ln in src.splitlines() if _is_comment_line(ln)
    ]


def assert_no_doc_loss(before: str, after: str) -> None:
    """Guard: no comment line present before may vanish after.

    Machine-checks LAW 3. Comment lines are compared after normalizing
    the documented non-deleting rewrites, so ``cleanup()``'s own lawful
    touch-ups (tab expansion, ``None``-style) never trip the guard.
    Raises :class:`DocLossError` naming the lost lines. (Duplicate
    identical comment lines are counted with multiplicity.)
    """
    want: Dict[str, int] = {}
    for ln in _comment_lines(before):
        want[ln] = want.get(ln, 0) + 1
    have: Dict[str, int] = {}
    for ln in _comment_lines(after):
        have[ln] = have.get(ln, 0) + 1
    lost = [ln for ln, c in want.items() if have.get(ln, 0) < c]
    if lost:
        raise DocLossError(
            "surgeon would delete documentation: %d comment line(s) lost, e.g. %r"
            % (len(lost), lost[0][:80])
        )


# ---------------------------------------------------------------------------
# Version modes — his four, exact semantics (headers + body limiting).
# ---------------------------------------------------------------------------


def _closed_private_header(author: str, year: int) -> str:
    return (
        "/**\n"
        " * CLOSED SOURCE – All Rights Reserved\n"
        f" * Copyright (c) {year} {author}\n"
        " * Unauthorized copying, redistribution, or resale prohibited.\n"
        " * Generated by LEVI Apex Private\n"
        " */\n\n"
    )


def _opensource_minimal_header(author: str, year: int) -> str:
    return (
        "/**\n"
        f" * Copyright (c) {year} {author}\n"
        " * SPDX-License-Identifier: MIT\n"
        " * Permission notice retained; provided as-is.\n"
        " */\n\n"
    )


def _encrypted_stub_header(author: str, year: int) -> str:
    return (
        "/**\n"
        f" * ENCRYPTED DISTRIBUTION STUB – {year} {author}\n"
        " * Full body withheld; load via licensed runtime.\n"
        " */\n\n"
    )


def _pay_tier_limited_header(author: str, year: int) -> str:
    return (
        "/**\n"
        f" * TRIAL / TIER-LIMITED BUILD – {year} {author}\n"
        " * Capability surface intentionally reduced.\n"
        " */\n\n"
    )


@dataclass(frozen=True)
class VersionMode:
    id: str
    label: str
    header: Callable[[str, int], str]
    limit_scale: float  # fraction of body kept; 1.0 = full body
    withholds: bool  # True when the mode deliberately withholds code


VERSION_MODES: Dict[str, VersionMode] = {
    "closed_private": VersionMode(
        id="closed_private",
        label="Closed Source Private",
        header=_closed_private_header,
        limit_scale=1.0,
        withholds=False,
    ),
    "opensource_minimal": VersionMode(
        id="opensource_minimal",
        label="Open Source Minimal (MIT-style)",
        header=_opensource_minimal_header,
        limit_scale=1.0,
        withholds=False,
    ),
    "encrypted_stub": VersionMode(
        id="encrypted_stub",
        label="Encrypted / Stub Export",
        header=_encrypted_stub_header,
        limit_scale=0.12,
        withholds=True,
    ),
    "pay_tier_limited": VersionMode(
        id="pay_tier_limited",
        label="Pay Tier Limited (trial-scale)",
        header=_pay_tier_limited_header,
        limit_scale=0.40,
        withholds=True,
    ),
}

_HEADER_PRESENT = re.compile(
    r"CLOSED SOURCE|SPDX-License|ENCRYPTED DISTRIBUTION|TRIAL / TIER", re.I
)
_LEADING_BLOCK_COMMENT = re.compile(r"^/\*[\s\S]*?\*/\s*", re.M)


@dataclass
class StampedResult:
    text: str
    mode: str
    note: str
    ok: bool = True  # False when a withholding mode was refused


def format_version(
    code: str,
    mode_id: str,
    owner: Optional[str] = None,
    confirmed: bool = False,
) -> StampedResult:
    """Stamp an export header and apply the mode's body limiting.

    His ``formatVersion`` semantics: existing leading block comment
    stripped, body truncated per ``limit_scale`` for the two withholding
    modes, header prepended. Header-already-present input is returned
    untouched. (One deliberate hardening: unknown modes raise — the
    original silently falls back to ``closed_private``.)

    The withholding modes (``encrypted_stub``, ``pay_tier_limited``)
    deliberately withhold code — a consequential act — so they fail closed
    unless ``confirmed=True`` (explicit owner approval).
    """
    if mode_id not in VERSION_MODES:
        raise ValueError(f"format_version: unknown mode {mode_id!r}")
    mode = VERSION_MODES[mode_id]
    if mode.withholds and not confirmed:
        return StampedResult(
            text=str(code or ""),
            mode=mode.id,
            note="refused: withholding mode requires explicit owner confirmation",
            ok=False,
        )
    src = str(code or "")
    if _HEADER_PRESENT.search(src[:320]):
        return StampedResult(text=src, mode=mode.id, note="header already present")
    author = default_owner(owner)
    year = time.localtime().tm_year
    body = _LEADING_BLOCK_COMMENT.sub("", src, count=1)
    if mode.id == "encrypted_stub":
        keep = max(40, int(len(body) * mode.limit_scale))
        body = body[:keep] + "\n\n/* --- encrypted body omitted (%d chars) --- */\n" % (
            len(src) - keep
        )
    elif mode.id == "pay_tier_limited":
        lines = body.split("\n")
        keep_lines = max(20, int(len(lines) * mode.limit_scale))
        body = (
            "\n".join(lines[:keep_lines])
            + "\n\n/* --- tier limit: remaining implementation in licensed build --- */\n"
        )
    return StampedResult(
        text=mode.header(author, year) + body, mode=mode.id, note="stamped"
    )


# ---------------------------------------------------------------------------
# Snapshots — his model (take/list/revert, capped, persisted).
# ---------------------------------------------------------------------------

_MAX_SNAPSHOTS = 50


@dataclass
class Snapshot:
    id: str
    label: str
    ts: float
    code: str


class SnapshotStore:
    """Snapshot/revert store for code text. JSON persistence, capped history."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = (
            Path(path)
            if path
            else Path.home() / ".levi" / "surgeon" / "triple_threat_snaps.json"
        )
        self._snaps: List[Snapshot] = []
        self._seq = 0  # per-process uniqueness for same-millisecond takes
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
        self._seq += 1
        snap_id = f"snap_{int(time.time() * 1000):x}_{self._seq:x}"
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
# Advancement proposals — his ids, his semantics.
# ---------------------------------------------------------------------------


@dataclass
class Advancement:
    id: str
    title: str
    risk: str  # LOW | MED
    description: str
    outcome: str


def propose_advancements(code: str, filename: str = "") -> List[Advancement]:
    """Propose safe, revertible improvements. Proposals are data, not actions."""
    items = [
        Advancement(
            "adv_guard_null",
            "Null-safety guards",
            "LOW",
            "Defensive null checks.",
            "Fewer TypeErrors.",
        ),
        Advancement(
            "adv_log_entry",
            "Structured entry logs",
            "LOW",
            "Entry markers on functions.",
            "Easier debug.",
        ),
        Advancement(
            "adv_pure_helpers",
            "Extract pure helpers",
            "MED",
            "Split pure functions.",
            "Better tests; HITL boundaries.",
        ),
        Advancement(
            "adv_hitl_wrap",
            "HITL confirm wrapper",
            "LOW",
            "Comments for Cybrus policy.",
            "Safer apply path.",
        ),
        Advancement(
            "adv_version_closed",
            "Emit closed_private version",
            "LOW",
            "Apply closed-source header/mode.",
            "Proprietary marking.",
        ),
        Advancement(
            "adv_version_oss",
            "Emit opensource_minimal version",
            "LOW",
            "MIT-style minimal header.",
            "OSS-friendly export.",
        ),
        Advancement(
            "adv_elite_cleanup",
            "Elite multi-pass cleanup",
            "LOW",
            "Whitespace, None style, blank lines, tabs.",
            "Cleaner production code.",
        ),
    ]
    if str(filename or "").lower().endswith(".py"):
        items.append(
            Advancement(
                "adv_type_hints",
                "Type hints pass",
                "MED",
                "Basic Python hints.",
                "Clearer contracts.",
            )
        )
    return items


# Cybrus-allow hook: his ``cybrus.allow('enhance', opts)`` gate, host-agnostic.
# Signature: allow(action, context) -> bool. Default fails closed unless the
# caller passes confirmed=True — there is no silent-approval path.
AllowHook = Callable[[str, Dict[str, Any]], bool]


def _default_allow(action: str, context: Dict[str, Any]) -> bool:
    return bool(context.get("confirmed"))


def _comment_prefix(filename: str) -> str:
    return "#" if str(filename or "").lower().endswith(".py") else "//"


def apply_advancement(
    code: str,
    adv_id: str,
    filename: str = "",
    snapshots: Optional[SnapshotStore] = None,
    allow: Optional[AllowHook] = None,
    owner: Optional[str] = None,
    confirmed: bool = False,
) -> Dict[str, Any]:
    """Apply one advancement, snapshot-first, approval-gated.

    His ``applyAdvancement`` semantics: consult the Cybrus-allow hook first
    (``allow('enhance', ...)``); on approval, snapshot the input, transform
    the text, return ``{"ok", "code", "snapshot_id"}``. Unknown ids and
    denied approvals fail closed. This transforms text only — writing the
    result to disk requires :func:`approve_and_write`. Raises
    :class:`DocLossError` if the transform would delete documentation.
    """
    valid = {a.id for a in propose_advancements(code, filename)}
    if adv_id not in valid:
        return {"ok": False, "reason": f"unknown advancement {adv_id!r}"}
    gate = allow or _default_allow
    if not gate("enhance", {"adv_id": adv_id, "confirmed": confirmed}):
        return {"ok": False, "reason": "blocked: approval required (allow hook denied)"}
    mgr = snapshots or SnapshotStore()
    snap_id = mgr.take(f"pre-{adv_id}", code)
    cp = _comment_prefix(filename)
    nxt = code
    if adv_id == "adv_hitl_wrap":
        nxt = f"{cp} LEVI HITL: confirm + snapshot required\n" + code
    elif adv_id == "adv_log_entry":
        js = re.sub(
            r"(function\s+(\w+)\s*\([^)]*\)\s*\{)",
            r"\1\n  // LEVI entry: \2\n",
            code,
            count=1,
        )
        py = re.sub(
            r"(def\s+(\w+)\s*\([^)]*\)\s*:)",
            r"\1\n    # LEVI entry: \2\n",
            js,
            count=1,
        )
        nxt = py
    elif adv_id == "adv_guard_null":
        nxt = f"{cp} LEVI: explicit null checks preferred\n" + code
    elif adv_id == "adv_version_closed":
        nxt = format_version(code, "closed_private", owner, confirmed=True).text
    elif adv_id == "adv_version_oss":
        nxt = format_version(code, "opensource_minimal", owner, confirmed=True).text
    elif adv_id == "adv_elite_cleanup":
        nxt = cleanup(code).text
    elif adv_id == "adv_type_hints":
        nxt = (
            f"{cp} LEVI advancement: adv_type_hints (proposal — apply manually)\n"
            + code
        )
    elif adv_id == "adv_pure_helpers":
        nxt = (
            f"{cp} LEVI advancement: adv_pure_helpers (proposal — apply manually)\n"
            + code
        )
    assert_no_doc_loss(code, nxt)
    return {"ok": True, "code": nxt, "snapshot_id": snap_id}


# ---------------------------------------------------------------------------
# The single gated disk-write path. No other function here writes files.
# ---------------------------------------------------------------------------


def approve_and_write(
    path: str | Path,
    proposed: str,
    snapshots: Optional[SnapshotStore] = None,
    label: str = "apply",
    confirmed: bool = False,
    root: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Write ``proposed`` to ``path`` — snapshot-first, approval-gated.

    Requires ``confirmed=True`` (explicit human approval). Fails closed
    otherwise, and the file is never touched on the failure path. The
    pre-write content is snapshotted so every write is revertible. When
    ``root`` is given, the resolved target must stay inside the resolved
    root — otherwise the write fails closed (path confinement).
    """
    target = Path(path)
    if not confirmed:
        return {
            "ok": False,
            "reason": "HITL confirmation required",
            "path": str(target),
        }
    if root is not None:
        try:
            target.resolve().relative_to(Path(root).resolve())
        except ValueError:
            return {
                "ok": False,
                "reason": "path escapes confinement root",
                "path": str(target),
            }
    if not isinstance(proposed, str) or not proposed.strip():
        return {"ok": False, "reason": "proposed text is empty", "path": str(target)}
    mgr = snapshots or SnapshotStore()
    try:
        original = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        original = ""
    snap_id = mgr.take(f"{label}:{target.name}", original)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(proposed, encoding="utf-8")
    except OSError as exc:
        return {
            "ok": False,
            "reason": f"write failed: {exc}",
            "path": str(target),
            "snapshot_id": snap_id,
        }
    return {"ok": True, "path": str(target), "snapshot_id": snap_id}


# ---------------------------------------------------------------------------
# Thin per-host adapters. The hosts own ALL I/O and ALL permission UX:
# they hand text in and take text out. Nothing here imports an editor API.
# ---------------------------------------------------------------------------


class AcodeAdapter:
    """How the Acode host (plugin or native side) calls the surgeon core.

    Usage from the host: ``AcodeAdapter.cleanup(editor_text)`` ->
    ``{"text", "fixes", "total"}``; the host decides what to do with the
    result (preview diff, ask the user, write back). Approval-gated paths
    take ``confirmed`` from the host's own HITL UX.
    """

    @staticmethod
    def cleanup(editor_text: str) -> Dict[str, Any]:
        res = cleanup(editor_text)
        return {"text": res.text, "fixes": res.fixes, "total": res.total}

    @staticmethod
    def stamp(
        editor_text: str,
        mode: str,
        owner: Optional[str] = None,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        r = format_version(editor_text, mode, owner, confirmed=confirmed)
        return {"text": r.text, "mode": r.mode, "note": r.note, "ok": r.ok}

    @staticmethod
    def propose(editor_text: str, filename: str = "") -> List[Dict[str, Any]]:
        return [a.__dict__ for a in propose_advancements(editor_text, filename)]

    @staticmethod
    def apply(
        editor_text: str,
        adv_id: str,
        filename: str = "",
        owner: Optional[str] = None,
        confirmed: bool = False,
        allow: Optional[AllowHook] = None,
        snapshots: Optional[SnapshotStore] = None,
    ) -> Dict[str, Any]:
        return apply_advancement(
            editor_text,
            adv_id,
            filename=filename,
            snapshots=snapshots,
            allow=allow,
            owner=owner,
            confirmed=confirmed,
        )


class HicombAdapter:
    """How Hicomb (his from-scratch editor) calls the surgeon core.

    Same core, Hicomb-flavored receipt: ``{"ok", "buffer", "receipt"}``
    shaped for a buffer-oriented host. As with Acode, the host owns I/O
    and permission UX; ``confirmed`` arrives from Hicomb's own HITL.
    """

    @staticmethod
    def cleanup(buffer_text: str, uri: str = "") -> Dict[str, Any]:
        res = cleanup(buffer_text)
        return {
            "ok": True,
            "buffer": res.text,
            "receipt": {
                "instrument": "triple_threat.cleanup",
                "uri": uri,
                "fixes": res.fixes,
                "total_fixes": res.total,
            },
        }

    @staticmethod
    def stamp(
        buffer_text: str,
        mode: str,
        uri: str = "",
        owner: Optional[str] = None,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        r = format_version(buffer_text, mode, owner, confirmed=confirmed)
        return {
            "ok": r.ok,
            "buffer": r.text,
            "receipt": {
                "instrument": "triple_threat.stamp",
                "uri": uri,
                "mode": r.mode,
                "note": r.note,
            },
        }

    @staticmethod
    def operate(
        buffer_text: str,
        uri: str = "",
        filename: str = "",
        owner: Optional[str] = None,
        confirmed: bool = False,
        allow: Optional[AllowHook] = None,
        snapshots: Optional[SnapshotStore] = None,
    ) -> Dict[str, Any]:
        """Diagnose -> propose -> (gated) apply, all on text.

        Never writes the host's buffer to disk — the host owns that. The
        gated apply snapshots to the surgeon's journal (pass your own
        ``snapshots`` store to control where it persists).
        """
        res = cleanup(buffer_text)
        advs = [a.__dict__ for a in propose_advancements(res.text, filename)]
        applied = None
        if confirmed:
            r = apply_advancement(
                res.text,
                "adv_elite_cleanup",
                filename=filename,
                snapshots=snapshots,
                allow=allow,
                owner=owner,
                confirmed=True,
            )
            if r.get("ok"):
                applied = {
                    "adv_id": "adv_elite_cleanup",
                    "snapshot_id": r["snapshot_id"],
                }
        return {
            "ok": True,
            "buffer": res.text,
            "receipt": {
                "instrument": "triple_threat.operate",
                "uri": uri,
                "fixes": res.fixes,
                "total_fixes": res.total,
                "proposals": [a["id"] for a in advs],
                "applied": applied,
                "confirmed": confirmed,
            },
        }
