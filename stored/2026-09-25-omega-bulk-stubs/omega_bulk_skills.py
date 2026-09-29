"""LEVI omega-bulk skill pack: Chauncey's Omega archive as catalog stubs.

LAWS (invariants — must always hold):
1. Exactly 10,000 entries register, no more, no fewer.
2. Every entry is HONESTLY a stub: category "omega-bulk", INFO risk, no
   permissions, description prefixed "Omega catalog stub:". The registry
   must never be able to misrepresent these as working skills.
3. Stub dispatch returns the catalog instructions text with a stub banner;
   it never claims execution, never acts, never spends.
4. All pre-existing registry skills are unaffected (ids locked to the
   "omega-bulk." prefix, which no other pack uses).
5. Lookup stays O(1): one JSONL parsed once at import into a dict-backed
   list; the registry's own dict does the rest.

SELECTION RULE (deterministic, 2026-09-25):
- Family A — 25,000 archive entries sharing one identical SI micro-op
  instruction block: 250 representatives, stride-sampled over name-sorted
  entries (every 100th), covering all siaa/siab/... families without
  importing 25,000 clones.
- Family B — 233,355 entries with unique instruction blocks: 9,750 via
  largest-remainder proportional allocation across the 5 description
  families (si-variant, other, generic-primitive, domain-op,
  si-complementary), preferring longer (more substantive) instructions,
  deterministic tiebreak by name.

DATA: one compact file, ``omega_bulk_data.jsonl`` next to this module —
one JSON object per line: id, name, description, instructions, family,
omega_path. No hand-maintained list, no 10,000 markdown files.

PROVENANCE: entries drawn from Chauncey's parked Omega archive
(~/workspace/parked/reference-zips/omega-complete.zip, read-only —
the parked original is never modified). Refining a stub into a real
skill is future work; the stub stays labeled until then.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from levi.skill.registry import Skill, SkillRisk

DATA_PATH = Path(__file__).resolve().parent / "omega_bulk_data.jsonl"

EXPECTED_COUNT = 10_000
STUB_PREFIX = "Omega catalog stub:"
_ID_RE = re.compile(r"\Aomega-bulk\.[a-z0-9]+(?:-[a-z0-9]+)*\Z")

_STUB_BANNER = (
    "Omega catalog stub — advisory only. This entry carries the catalog "
    "instructions from Chauncey's Omega archive; it is NOT an implemented "
    "skill and performs no action.\n---\n"
)


def _stub_handler(instructions: str, skill_id: str):
    """A dispatch that returns instructions text and never claims execution."""

    def _run(args: Optional[Dict[str, object]] = None) -> str:
        return (
            f"{_STUB_BANNER}"
            f"[{skill_id}]\n"
            f"{instructions}\n"
            f"---\n"
            f"(stub: nothing was executed)"
        )

    return _run


def _skill_from_record(rec: Dict[str, object]) -> Optional[Skill]:
    skill_id = str(rec.get("id", ""))
    name = str(rec.get("name", ""))
    description = str(rec.get("description", ""))
    instructions = str(rec.get("instructions", ""))
    family = str(rec.get("family", ""))
    if not _ID_RE.match(skill_id) or not name or not instructions:
        return None
    return Skill(
        id=skill_id,
        name=name,
        description=f"{STUB_PREFIX} {description}".strip(),
        category="omega-bulk",
        risk_level=SkillRisk.INFO,
        permissions=[],
        requires_confirmation=False,
        tags=["omega", "catalog-stub", family],
        version="1.0.0",
        handler=_stub_handler(instructions, skill_id),
    )


def _load() -> List[Skill]:
    skills: List[Skill] = []
    if not DATA_PATH.is_file():
        return skills
    seen = set()
    with DATA_PATH.open(encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            skill = _skill_from_record(rec)
            if skill is None or skill.id in seen:
                continue
            seen.add(skill.id)
            skills.append(skill)
    return skills


# The full registration list, built once at import.
# SkillRegistry consumes this (import + extend).
OMEGA_BULK_SKILLS: List[Skill] = _load()


def expected_count() -> int:
    """Locked count — used by the test suite."""
    return EXPECTED_COUNT


def expected_ids() -> List[str]:
    """Every data-file id — used by the test suite."""
    if not DATA_PATH.is_file():
        return []
    ids: List[str] = []
    with DATA_PATH.open(encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                ids.append(str(json.loads(raw)["id"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return ids
