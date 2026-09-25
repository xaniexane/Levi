"""L.W.P. x Legion Pipeline live bridge — Direction 1 (the queued item).

Takes an approved concept brief from the pipeline's 01-creation/ and stages it
as an L.W.P. ``ProductionBrief`` (``core/levi/lwp/machine.py``), per the field
mapping in ``docs/LWP_PIPELINE.md``. A mapping is not a bridge; this module is
the bridge, and the gates are the law in code.

LAWS (invariants — declared first, per the law->guard->prove rule):

1. No verdict, no brief. A concept brief crosses 01 -> press ONLY on
   Chauncey's recorded yes / no / rename. DRAFT stays DRAFT.
2. A NO verdict never becomes a brief — denied concepts compost via REIM.
3. The bridge never invents: no names, no sealed identities, no intelligence
   definitions or placements, no dramatis personae, no verdicts.
4. His rename is used verbatim. The proposed name is kept as-proposed when he
   says YES (recorded, not reworded).
5. The intelligence axis rides as OPEN until he locks INTEL-SPEC. A brief whose
   axis section does not read OPEN is refused — the axis is his to declare.
6. The bridge STAGES, never runs: it produces a ``ProductionBrief`` for the
   press line's human gates (``approve()``/``deny()``, publish_ready seal,
   ``PublishPermissionError``). It never calls ``run_brief`` or ``publish``.
7. stdlib-only at import. The only press import is ``ProductionBrief`` (plus
   ``BriefError``); nothing in this module touches the machine, the ledger,
   or any contested file.

Verdict marker format (a proposal, not canon — the briefs carry no formal
marker yet): a ``**Verdict:**`` line (markdown-bold or plain ``Verdict:``),
value ``YES`` / ``NO`` / ``RENAME — <his name>``, case-insensitive. Anything
else is ambiguous and refused — the bridge never guesses his verdict.

Parse contract: the parser extracts only what the brief labels. Unlabeled or
absent fields come back ``None``. The receipt records the full accounting:
``mapped`` is what crossed into the staged brief, ``absent`` is what the
brief never declares (press-side defaults, never-invented elements), and
``parsed_not_carried`` is what the parser lifted but the bridge deliberately
does NOT stage — nothing is silently dropped. ``brief_text`` is the Nature +
Typeline sections verbatim (his prose, not ours).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from levi.lwp.machine import BriefError, ProductionBrief


class VerdictGateError(Exception):
    """Raised when the 01 -> press gate refuses a concept brief.

    This is the gate as code: missing verdict, denied verdict, invented
    intelligence placement, or an ambiguous marker. The message always says
    whose call it is — Chauncey's — and what the brief must carry to pass.
    """


# docs/LWP_PIPELINE.md kind-to-lane guidance, made deterministic:
# lanes A/C get long-form copy -> manuscript; lanes B/D get prose.
# Recorded in the receipt; locked by tests. "social" is campaign-only and
# never assigned here (social surfaces need his explicit campaign approval).
LANE_KIND: Dict[str, str] = {
    "A": "manuscript",
    "B": "prose",
    "C": "manuscript",
    "D": "prose",
}

OPEN_AXIS_ANGLE = "intelligence-axis: OPEN (awaiting INTEL-SPEC)"

_LABELED = re.compile(r"^\*\*(?P<key>[^*]+):\*\*\s*(?P<val>.*)$")
_PLAIN_VERDICT = re.compile(r"^Verdict:\s*(?P<val>.*)$", re.IGNORECASE)
_HEADING = re.compile(r"^##\s+(?P<title>.+?)\s*$")
_COSMO_MARKER = re.compile(r"\*\*\s*cosmology\s+slot\s*:\s*\*\*", re.IGNORECASE)


@dataclass
class ConceptBrief:
    """What the parser lifted from a concept-brief file. ``None`` = absent."""

    source: str
    title_line: Optional[str] = None
    status: Optional[str] = None
    date: Optional[str] = None
    lane: Optional[str] = None  # lane letter A/B/C/D
    shelf: Optional[str] = None
    cosmology_slot: Optional[str] = None
    proposed_name: Optional[str] = None
    canon_grounding: Optional[str] = None
    nature: Optional[str] = None
    typeline: Optional[str] = None
    intelligence_axis: Optional[str] = None
    gate_note: Optional[str] = None
    verdict_raw: Optional[str] = None


@dataclass
class BridgeReceipt:
    """Provenance for one staging: what mapped, what didn't, what warned."""

    source: str
    verdict: str  # "yes" | "rename"
    approved_name: str
    lane: str
    kind: str
    mapped: Dict[str, str] = field(default_factory=dict)  # brief field -> element
    absent: List[str] = field(default_factory=list)  # brief elements not carried
    parsed_not_carried: List[str] = field(default_factory=list)  # brief elements
    # the parser lifted but the bridge deliberately does NOT stage (the canon
    # grounding stays with the brief as the drafter's record; the shelf and
    # cosmology slot are pipeline placement metadata, not press input).
    warnings: List[str] = field(default_factory=list)


def parse_concept_brief(path: str | Path) -> ConceptBrief:
    """Parse a concept-brief markdown file. Extracts only labeled fields.

    Sections are the ``## Heading`` blocks; ``**Key:** value`` lines carry
    the labeled fields. Anything the brief doesn't label is ``None``.
    """
    text = Path(path).read_text(encoding="utf-8")
    brief = ConceptBrief(source=str(path))
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None

    for raw in text.splitlines():
        line = raw.strip()
        head = _HEADING.match(line)
        if head:
            current = head.group("title").strip().lower()
            sections.setdefault(current, [])
            continue
        lab = _LABELED.match(line)
        if lab:
            key = lab.group("key").strip().lower()
            val = lab.group("val").strip()
            if key == "status":
                brief.status = val
            elif key == "date":
                brief.date = val
            elif key == "lane":
                brief.lane = _lane_letter(val)
            elif key == "shelf":
                brief.shelf, brief.cosmology_slot = _split_shelf_line(val)
            elif key == "proposed name":
                brief.proposed_name = _proposed_name(val)
            elif key == "verdict":
                brief.verdict_raw = val
            if current is not None:
                sections[current].append(raw)
            continue
        plain = _PLAIN_VERDICT.match(line)
        if plain and brief.verdict_raw is None:
            brief.verdict_raw = plain.group("val").strip()
        if current is not None:
            sections[current].append(raw)
        elif line.startswith("# ") and brief.title_line is None:
            brief.title_line = line

    def section(*names: str) -> Optional[str]:
        for name in names:
            body = sections.get(name)
            if body:
                joined = "\n".join(body).strip()
                if joined:
                    return joined
        return None

    brief.nature = section("nature")
    brief.typeline = section(
        "typeline sketch (draft — his word settles it)",
        "typeline sketch",
        "typeline",
    )
    brief.intelligence_axis = section("intelligence-type axis", "intelligence axis")
    brief.canon_grounding = section(
        "canon grounding (his words + the build)",  # creation_writer's heading
        "canon grounding (his words)",  # the six 2026-09-21 briefs' heading
        "canon grounding (the build)",  # one 2026-09-21 brief's variant
        "canon grounding",
    )
    brief.gate_note = section("gate")
    return brief


def _lane_letter(val: str) -> Optional[str]:
    m = re.match(r"\s*([A-Da-d])\b", val)
    return m.group(1).upper() if m else None


def _split_shelf_line(val: str) -> Tuple[Optional[str], Optional[str]]:
    """Split the combined shelf line the writer emits — and the six
    2026-09-21 briefs carry — as ``**Shelf:** X. **Cosmology slot:** Y.``

    Without the split, the greedy labeled-field match swallowed the whole
    line into ``shelf`` and the cosmology slot was lost to the parse. The
    writer's ``—`` placeholder parses back to None on both sides; a lone
    shelf line with no marker keeps the old behavior (whole value as
    shelf). Never synthesized: absent stays None.
    """
    m = _COSMO_MARKER.search(val)
    if not m:
        shelf = val.strip() or None
        return (None if shelf == "—" else shelf, None)
    shelf = val[: m.start()].strip() or None
    cosmo = val[m.end() :].strip() or None
    return (
        None if shelf in (None, "—") else shelf,
        None if cosmo in (None, "—") else cosmo,
    )


def _proposed_name(val: str) -> str:
    """The name as proposed: quoted form when the brief quotes it, else the
    text before the first em-dash commentary. Never reworded."""
    m = re.search(r'"([^"]+)"', val)
    if m:
        return m.group(1).strip()
    return val.split("—")[0].strip()


def verdict_of(brief: ConceptBrief) -> Tuple[str, Optional[str]]:
    """Read the verdict marker. Returns ("yes", None) or ("rename", name).

    Raises VerdictGateError for: no marker at all, an ambiguous value, a NO
    verdict (compost via REIM, never a brief), or RENAME with no name.
    The bridge never fills in his verdict or his rename.
    """
    raw = (brief.verdict_raw or "").strip()
    if not raw:
        raise VerdictGateError(
            f"{brief.source}: no verdict on record — the brief is DRAFT until "
            "Chauncey records yes / no / rename. DRAFT stays DRAFT."
        )
    head = raw.split("—")[0].split("-")[0].strip().lower()
    if head == "yes":
        return ("yes", None)
    if head == "no":
        raise VerdictGateError(
            f"{brief.source}: verdict is NO — denied concepts compost via "
            "REIM; they never become ProductionBriefs."
        )
    if head == "rename":
        name = raw[len(raw.split("—")[0].split("-")[0]) :].lstrip("—- ").strip()
        name = name.strip().strip('"').strip()
        if not name:
            raise VerdictGateError(
                f"{brief.source}: verdict is RENAME but no name follows the "
                "marker — the bridge never invents his rename."
            )
        return ("rename", name)
    raise VerdictGateError(
        f"{brief.source}: verdict marker {raw!r} is ambiguous — expected YES, "
        "NO, or RENAME — <name>. The bridge never guesses his verdict."
    )


def _axis_is_open(brief: ConceptBrief) -> bool:
    """The axis rides as OPEN only when the brief's own axis section says so.

    Refuse-by-default: any axis text that does not read OPEN is a declared
    (or unclear) placement, and placements are his alone.
    """
    if brief.intelligence_axis is None:
        return False
    return "open" in brief.intelligence_axis.lower()


def brief_to_production_brief(
    brief: ConceptBrief,
) -> Tuple[ProductionBrief, BridgeReceipt]:
    """Stage an approved concept brief as a ProductionBrief. Gate first.

    Raises VerdictGateError when the gate refuses (LAWS 1, 2, 5). Returns the
    validated brief plus a provenance receipt (LAW: report, don't declare).
    Never invents (LAW 3): absent elements ride as None and are listed in
    ``receipt.absent``.
    """
    verdict, rename = verdict_of(brief)

    if not _axis_is_open(brief):
        raise VerdictGateError(
            f"{brief.source}: intelligence axis is not declared OPEN — "
            "intelligence definitions and placements are Chauncey's alone "
            "(INTEL-SPEC). Lock the axis or leave the brief at DRAFT."
        )

    if brief.lane is None or brief.lane not in LANE_KIND:
        raise VerdictGateError(
            f"{brief.source}: lane {brief.lane!r} is not A/B/C/D — kind "
            "cannot be derived; the bridge never assigns a kind by guess."
        )
    kind = LANE_KIND[brief.lane]

    if brief.proposed_name:
        base_name = brief.proposed_name
    else:
        raise VerdictGateError(
            f"{brief.source}: no proposed name — a ProductionBrief needs a "
            "title and the bridge never invents one."
        )
    if verdict == "rename":
        assert rename is not None
        title = rename  # his word, verbatim (LAW 4)
        name_note = "his rename, verbatim"
    else:
        title = base_name  # his YES kept the proposal (LAW 4)
        name_note = "proposed name, kept by his YES"

    parts = [p for p in (brief.nature, brief.typeline) if p]
    if not parts:
        raise VerdictGateError(
            f"{brief.source}: no Nature and no Typeline sketch — nothing to "
            "press; the bridge never writes his copy."
        )
    brief_text = "\n\n".join(parts)

    receipt = BridgeReceipt(
        source=brief.source,
        verdict=verdict,
        approved_name=title,
        lane=brief.lane,
        kind=kind,
    )
    receipt.mapped = {
        "title": f"concept title ({name_note})",
        "brief_text": "nature + typeline sketch, verbatim",
        "kind": f"lane {brief.lane} -> {kind} (docs/LWP_PIPELINE.md guidance)",
        "angles": "intelligence axis carried as OPEN",
    }
    receipt.absent = [
        "platform: social kind only; lane kinds never assign it",
        "cast_size: the brief carries no dramatis personae — never invented",
        "pov/direction/phase/power/genres/target_words: press-side defaults; "
        "the brief does not declare them",
    ]
    # The parse contract's third list: these were labeled in the brief and
    # lifted by the parser, but the bridge deliberately does not stage them —
    # recording them here is what keeps the parse from silently dropping them.
    # Only recorded when actually parsed (None means the brief never carried
    # the element; that is the parser's domain, not a drop to report).
    receipt.parsed_not_carried = []
    if brief.canon_grounding:
        receipt.parsed_not_carried.append(
            "canon_grounding: lifted from the brief's canon-grounding section; "
            "stays with the brief as the drafter's record — the staged text "
            "is Nature + Typeline verbatim, never press input"
        )
    if brief.shelf:
        receipt.parsed_not_carried.append(
            "shelf: lifted from the **Shelf:** line — pipeline placement "
            "metadata, not staged into the ProductionBrief"
        )
    if brief.cosmology_slot:
        receipt.parsed_not_carried.append(
            "cosmology_slot: lifted from the **Cosmology slot:** line — "
            "pipeline placement metadata, not staged into the ProductionBrief"
        )
    angles = [OPEN_AXIS_ANGLE]  # gate above guarantees the axis reads OPEN

    try:
        staged = ProductionBrief(
            title=title,
            brief_text=brief_text,
            kind=kind,
            angles=angles,
        ).validate()
    except BriefError as exc:
        raise VerdictGateError(
            f"{brief.source}: staged brief failed press validation: {exc}"
        ) from exc
    return staged, receipt


def stage_for_factory(path: str | Path) -> Tuple[ProductionBrief, BridgeReceipt]:
    """Read a concept-brief file and stage it for the factory gate.

    The single entry point: parse -> gate -> map -> validate. Raises
    VerdictGateError when the gate refuses. Returns (ProductionBrief,
    BridgeReceipt) when Chauncey's verdict is on record.
    """
    return brief_to_production_brief(parse_concept_brief(path))
