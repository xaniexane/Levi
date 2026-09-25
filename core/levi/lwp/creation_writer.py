"""L.W.P. x Legion Pipeline — Direction 2 (the queued item).

Writes a press draft (or a grounded loop innovation) out as a dated DRAFT
concept brief for the pipeline's ``01-creation/``, per the anatomy in
``docs/LWP_PIPELINE.md`` "Direction 2": proposed name, nature, typeline
sketch, intelligence-type axis OPEN. The writer drafts; it never publishes,
never declares, never crosses a gate.

LAWS (invariants — declared first, per the law->guard->prove rule):

1. Drafts only. Every brief carries ``**Status:** DRAFT — nothing here is
   canon. Awaiting Chauncey's yes / no / rename.`` No other status is
   emittable; the writer has no other status to emit.
2. Propose, never declare. The name is recorded as a working title
   ("Chauncey renames"); a verdict line is never written. The intelligence
   axis always rides OPEN — the module has no field for a declared type.
3. The writer never invents sealed identities, intelligence definitions or
   placements, or canon claims. Prose that claims a sealed identity (an
   ordinal of the eleven, a list naming the eleven) or declares an
   intelligence type/placement is REFUSED, not fixed.
4. Nothing is grounded by the writer: canon grounding (his words) and the
   loop commit hashes that prove the build are REQUIRED input. Absent
   grounding raises DraftError. The writer cites, never supplies.
5. Denied-by-him stays denied: a draft he denied is refused outright —
   compost, never a second door. A failed press draft with a good image may
   be marked compost-fed (an angle re-enters; denied copy does not).
6. stdlib-only at import. No machine, no ledger, no CLI, no contested file.
   The target directory is caller-chosen (default the real 01-creation/);
   the writer creates nothing else and never overwrites an existing brief.

Pairing honesty: the Direction-1 gate refuses these briefs until he writes
a verdict marker — parse with ``pipeline_bridge.parse_concept_brief`` and
``verdict_of`` raises "no verdict on record". That is the gates holding,
not a bug. The honest line runs through both machines: report, don't
declare.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

STATUS_LINE = (
    "**Status:** DRAFT — nothing here is canon. Awaiting Chauncey's yes / no / rename."
)
GATE_LINE = "Nothing moves to 02-factory without his yes / no / rename."
AXIS_SECTION = (
    "**OPEN — extensible.** This brief deliberately proposes NO intelligence "
    "type: {axis_note}. Definitions and placements are Chauncey's per the "
    "RUNBOOK gate."
)


class DraftError(Exception):
    """Raised when the Direction-2 writer refuses a draft.

    The message always says whose call it is — Chauncey's — and what the
    draft must carry (or stop carrying) to be writable. Nothing is fixed
    silently; refusal is the whole point of the gate.
    """


# LAW 3 — sealed-law refusal patterns. Conservative by design: a prose
# mention of the law itself ("the eleven stay sealed — no names, no order")
# does NOT match; attaching an ordinal or a list to the eleven DOES match.
# The guard is a tripwire, not a theory — the LAW is in the emitted text.
_SEALED_ORDINAL = re.compile(
    r"(?i)\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"eleventh)\s+of\s+the\s+eleven\b"
)
_SEALED_LIST = re.compile(r"(?i)\bthe\s+eleven\b\s*[:=]\s*[\"'\w]")
# Intelligence definitions/placements are his alone (INTEL-SPEC). The module
# has no field for them, so any prose that declares one is refused.
_INTEL_CLAIM = re.compile(
    r"(?i)\bintelligence\s+type\s*(is|:)\s*['\"]?\w|"
    r"\bplacement\s*(is|:)\s*['\"]?\w"
)
# A proposed name may not smuggle a declaration ("approved", "sealed",
# "canon") into the working title.
_DECLARED_NAME = re.compile(r"(?i)\b(approved|sealed|canon)\b")
_COMMIT_HASH = re.compile(r"^[0-9a-f]{7,40}$")
_LANE_LETTER = re.compile(r"^\s*([A-Da-d])\b")


def _lane_letter(lane: str) -> str:
    m = _LANE_LETTER.match(lane)
    if not m:
        raise DraftError(
            f"lane {lane!r} does not start with a letter A/B/C/D — the "
            "Direction-1 bridge derives the press kind from the lane letter "
            "(docs/LWP_PIPELINE.md), and the writer never assigns a kind by "
            "guess. Start the lane with its letter, e.g. 'B — spells/traps'."
        )
    return m.group(1).upper()


def brief_slug(proposed_name: str) -> str:
    """`The Brain-Voice` -> `the-brain-voice`. Deterministic, ascii, dashy."""
    return re.sub(r"[^a-z0-9]+", "-", proposed_name.lower()).strip("-")


def creation_dir() -> Path:
    """The real 01-creation/ dir. Tests pass their own tmp dirs."""
    return Path.home() / "workspace" / "legion-pipeline" / "01-creation"


@dataclass
class DraftInput:
    """Everything the writer needs — and refuses to work without.

    All prose is the drafter's own; the writer records it verbatim. Fields
    the machine has no business declaring simply don't exist (verdict,
    intelligence type, canon text).
    """

    proposed_name: str  # working title; Chauncey renames
    lane: str  # must start with the A/B/C/D letter
    nature: str  # tightened prose, verbatim
    typeline_sketch: str  # THE ASCENT / FANG/HIDE / ambience / species-word
    canon_grounding: str  # his words + the build that grounds it
    loop_commits: List[str]  # short hashes, cited not verified
    source_label: str  # e.g. "loop journal 2026-09-23" / "press ledger ..."
    date_str: str = ""  # YYYY-MM-DD; defaults to today
    shelf: Optional[str] = None
    cosmology_slot: Optional[str] = None
    axis_note: str = "it is an operating pattern, not a type"
    compost_fed: bool = False  # a failed press draft's surviving image
    denied_by_him: bool = False  # refused outright — compost, no second door
    gate_note: Optional[str] = None  # honest-limits note for the factory lane


@dataclass
class DraftReceipt:
    """Provenance for one written brief: what mapped, what stayed absent."""

    path: str
    slug: str
    proposed_name: str
    lane_letter: str
    date_str: str
    mapped: Dict[str, str] = field(default_factory=dict)
    absent: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _refuse_claims(inp: DraftInput) -> None:
    """LAW 3: scan every prose field for sealed-law or intel claims.

    Refuses (not fixes): the writer never rewrites the drafter's prose into
    compliance — the draft comes back for his or the drafter's rewording.
    """
    scanned = {
        "proposed_name": inp.proposed_name,
        "nature": inp.nature,
        "typeline_sketch": inp.typeline_sketch,
        "canon_grounding": inp.canon_grounding,
    }
    for field_name, text in scanned.items():
        if _SEALED_ORDINAL.search(text):
            raise DraftError(
                f"draft {field_name} claims an ordinal of the eleven — the "
                "eleven stay sealed: no names, no order. His call, not the "
                "draft's. Remove the claim."
            )
        if _SEALED_LIST.search(text):
            raise DraftError(
                f"draft {field_name} lists the eleven — the eleven stay "
                "sealed: no names, no order. Remove the list."
            )
        if _INTEL_CLAIM.search(text):
            raise DraftError(
                f"draft {field_name} declares an intelligence type or "
                "placement — definitions and placements are Chauncey's alone "
                "(INTEL-SPEC, RUNBOOK gate). The axis rides OPEN; remove the "
                "declaration."
            )
    if _DECLARED_NAME.search(inp.proposed_name):
        raise DraftError(
            f"proposed name {inp.proposed_name!r} smuggles a declaration "
            "('approved'/'sealed'/'canon') into a working title — propose, "
            "never declare."
        )


def _validate(inp: DraftInput) -> Tuple[str, str]:
    """Required-field checks. Returns (lane_letter, date_str)."""
    if inp.denied_by_him:
        raise DraftError(
            "this draft was denied by Chauncey — denied copy composts via "
            "REIM; it never re-enters as a concept brief. No second door."
        )
    for field_name in (
        "proposed_name",
        "nature",
        "typeline_sketch",
        "canon_grounding",
        "source_label",
    ):
        if not getattr(inp, field_name) or not getattr(inp, field_name).strip():
            raise DraftError(
                f"draft {field_name} is empty — the writer cites, never "
                "supplies. Bring the grounding."
            )
    if not inp.loop_commits:
        raise DraftError(
            "draft carries no loop commits — a concept brief must cite the "
            "build that grounds it (short hashes). The writer cites, never "
            "supplies."
        )
    for h in inp.loop_commits:
        if not _COMMIT_HASH.match(h):
            raise DraftError(
                f"loop commit {h!r} is not a short hex hash — cite the real "
                "commit, not a placeholder."
            )
    lane_letter = _lane_letter(inp.lane)
    date_str = inp.date_str or date.today().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        raise DraftError(f"date {date_str!r} is not YYYY-MM-DD.")
    _refuse_claims(inp)
    return lane_letter, date_str


def _render(inp: DraftInput, lane_letter: str, date_str: str) -> str:
    """Build the brief markdown — the full concept-brief anatomy."""
    lines = [
        f"# Concept brief — {inp.proposed_name.upper()}",
        "",
        STATUS_LINE,
        f"**Date:** {date_str}",
        f"**Lane:** {inp.lane.strip()}",
        f"**Shelf:** {inp.shelf or '—'} "
        f"**Cosmology slot:** {inp.cosmology_slot or '—'}",
        f'**Proposed name:** "{inp.proposed_name}" — working title only. '
        "Chauncey renames.",
        f"**Source:** {inp.source_label}",
        f"**Loop commits:** {', '.join(inp.loop_commits)}",
    ]
    if inp.compost_fed:
        lines.append(
            "**Compost-fed:** yes — a failed press draft's surviving image, "
            "re-entered as a concept angle. Never a revival of denied copy."
        )
    lines += [
        "",
        "## Canon grounding (his words + the build)",
        inp.canon_grounding.strip(),
        "",
        "## Nature",
        inp.nature.strip(),
        "",
        "## Typeline sketch (draft — his word settles it)",
        inp.typeline_sketch.strip(),
        "",
        "## Intelligence-type axis",
        AXIS_SECTION.format(axis_note=inp.axis_note.strip()),
        "",
        "## Gate",
        GATE_LINE + (f" {inp.gate_note.strip()}" if inp.gate_note else ""),
        "",
    ]
    return "\n".join(lines)


def write_concept_brief(
    inp: DraftInput,
    target_dir: Optional[Path] = None,
) -> Tuple[Path, DraftReceipt]:
    """Write the draft as a dated DRAFT brief into ``target_dir``.

    Default target is the real ``01-creation/`` (``creation_dir()``); pass
    a tmp dir in tests. Raises DraftError on any refusal — no partial
    writes, no silent overwrites: an existing dated file is refused, not
    replaced.
    """
    lane_letter, date_str = _validate(inp)
    target = Path(target_dir) if target_dir is not None else creation_dir()
    slug = brief_slug(inp.proposed_name)
    if not slug:
        raise DraftError(
            f"proposed name {inp.proposed_name!r} yields an empty slug — "
            "the brief needs a fileable name."
        )
    path = target / f"{date_str}-{slug}.md"
    if path.exists():
        raise DraftError(
            f"{path} already exists — dated briefs are never silently "
            "overwritten. Pick a new date or a new name."
        )
    text = _render(inp, lane_letter, date_str)
    target.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

    receipt = DraftReceipt(
        path=str(path),
        slug=slug,
        proposed_name=inp.proposed_name,
        lane_letter=lane_letter,
        date_str=date_str,
    )
    receipt.mapped = {
        "title": "proposed name, as-proposed (working title; he renames)",
        "status": "DRAFT — the writer emits no other status",
        "canon grounding": "his words + build, verbatim from input",
        "nature": "drafter's prose, verbatim",
        "typeline sketch": "drafter's sketch, verbatim; his word settles it",
        "intelligence axis": "OPEN — the module has no field for a type",
        "gate": "his yes/no/rename; nothing moves to 02-factory",
    }
    receipt.absent = [
        "verdict: never written — DRAFT stays DRAFT until he marks it",
        "intelligence type: deliberately absent (axis is OPEN)",
        "cast_size / platform / angles: press-side concerns, never invented "
        "into a brief",
    ]
    receipt.warnings = [
        "loop commits are cited from the input, not verified against git",
        "prose is recorded verbatim — the writer attests nothing the "
        "drafter didn't supply",
    ]
    return path, receipt
