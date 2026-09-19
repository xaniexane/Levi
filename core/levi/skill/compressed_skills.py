"""LEVI compressed-engines skill pack: data-driven registration.

Every playbook in ``playbooks/compressed/*.md`` carries a mandatory YAML
frontmatter block (parsed with stdlib only — same shape as the operator
pack, self-contained parser)::

    ---
    skill_id: compressed.<slug>
    name: Human Readable Title
    description: Single-sentence description.
    risk: info            # info | low | moderate | high | critical
    permissions: []
    requires_confirmation: false
    tags: [tag1, tag2]
    version: 1.0.0
    ---

``COMPRESSED_SKILLS`` is built dynamically at import by scanning the
directory: no hand-maintained list, so later batches register
automatically with zero merge conflicts. ``category`` is always
``"compressed-engine"`` and the id scheme is locked to
``compressed.<slug>``.

This is the vehicle for Chauncey's compressed-engines logic, rebuilt as
LEVI-native originals: the playbooks are advisory (the pattern), and the
runnable half lives in ``levi.engines`` — deterministic decision
machines (triage, cadence, weigh, quietwatch, handshake) exposed
here as INFO-risk executable skills (``compressed.run-<engine>``) whose
handlers call the engine registry directly. Advisory across the pack;
nothing here acts, sends, or spends.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from levi.skill.registry import Skill, SkillRisk

PLAYBOOK_DIR = Path(__file__).resolve().parent / "playbooks" / "compressed"

FRONTMATTER_KEYS = (
    "skill_id",
    "name",
    "description",
    "risk",
    "permissions",
    "requires_confirmation",
    "tags",
    "version",
)

_RISK_BY_NAME = {
    "info": SkillRisk.INFO,
    "low": SkillRisk.LOW,
    "moderate": SkillRisk.MODERATE,
    "high": SkillRisk.HIGH,
    "critical": SkillRisk.CRITICAL,
}

_ID_RE = re.compile(r"compressed\.[a-z0-9_-]+\Z")
_BOOL_RE = re.compile(r"\A(true|false)\Z")


def _parse_frontmatter(path: Path) -> Optional[Dict[str, object]]:
    """Parse the mandatory frontmatter block using stdlib only."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    meta: Dict[str, object] = {}
    for raw in text[4:end].splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = [  # type: ignore[assignment]
                item.strip().strip("'\"")
                for item in value[1:-1].split(",")
                if item.strip()
            ]
        elif _BOOL_RE.match(value.lower()):
            value = value.lower() == "true"  # type: ignore[assignment]
        else:
            value = value.strip("'\"")  # type: ignore[assignment]
        if key:
            meta[key] = value
    return meta


def _skill_from_file(path: Path) -> Optional[Skill]:
    """Build a Skill from one playbook file; None if it is not usable."""
    meta = _parse_frontmatter(path)
    if not meta:
        return None
    skill_id = str(meta.get("skill_id", ""))
    expected_id = f"compressed.{path.stem}"
    if not _ID_RE.match(skill_id) or skill_id != expected_id:
        return None
    if not all(meta.get(k) for k in ("name", "description")):
        return None
    risk = _RISK_BY_NAME.get(str(meta.get("risk", "info")).lower(), SkillRisk.INFO)
    return Skill(
        id=skill_id,
        name=str(meta["name"]),
        description=str(meta["description"]),
        category="compressed-engine",
        risk_level=risk,
        permissions=list(meta.get("permissions") or []),
        requires_confirmation=bool(meta.get("requires_confirmation", False)),
        tags=list(meta.get("tags") or []),
        version=str(meta.get("version", "1.0.0")),
        handler=None,
    )


def _engine_skill(engine_id: str, name: str, description: str, tags: List[str]) -> Skill:
    """An executable skill wrapping one engine in the registry."""

    def _run(args: Optional[Dict[str, object]] = None) -> str:
        # Lazy: engines self-register on import; keep the skill module
        # importable even if the engines package is mid-edit.
        from levi.engines import registry as eng_registry

        try:
            result = eng_registry.run(engine_id, dict(args or {}))
        except (KeyError, ValueError) as exc:
            return f"engine '{engine_id}' refused: {exc}"
        verdict = result.verdict
        lines = [
            f"[{engine_id}] verdict: {verdict}",
            f"confidence: {result.confidence}",
        ]
        lines.extend(f"  {t}" for t in result.trace)
        return "\n".join(lines)

    return Skill(
        id=f"compressed.run-{engine_id}",
        name=name,
        description=description,
        category="compressed-engine",
        risk_level=SkillRisk.INFO,
        permissions=[],
        requires_confirmation=False,
        tags=tags,
        version="1.0.0",
        handler=_run,
    )


def _load_playbook_skills() -> List[Skill]:
    skills: List[Skill] = []
    if not PLAYBOOK_DIR.is_dir():
        return skills
    for path in sorted(PLAYBOOK_DIR.glob("*.md")):
        skill = _skill_from_file(path)
        if skill is not None:
            skills.append(skill)
    return skills


# The full registration list, built dynamically at import.
# SkillRegistry consumes this (import + extend).
COMPRESSED_SKILLS: List[Skill] = _load_playbook_skills() + [
    _engine_skill(
        "triage",
        "Run Triage Engine",
        "Weighted multi-option verdict: rank, winner, margin, full trace.",
        ["engines", "decision", "run"],
    ),
    _engine_skill(
        "cadence",
        "Run Cadence Engine",
        "Rhythm read over timestamps: detected vs expected period, streak, drift, next-due.",
        ["engines", "rhythm", "run"],
    ),
    _engine_skill(
        "weigh",
        "Run Weigh Engine",
        "Two-sided judgment over weighted evidence: lean, margin, decisive factors.",
        ["engines", "judgment", "run"],
    ),
    _engine_skill(
        "quietwatch",
        "Run Quietwatch Engine",
        "Selective calling over a transcript: silent until a registered call sign is heard, then the exact hit and line.",
        ["engines", "attention", "run"],
    ),
    _engine_skill(
        "handshake",
        "Run Handshake Engine",
        "Capability negotiation: tone, offer in preference order, acknowledgment — or a polite close with no common language.",
        ["engines", "negotiation", "run"],
    ),
]


def expected_ids() -> List[str]:
    """Every playbook file's locked id — used by the test suite."""
    if not PLAYBOOK_DIR.is_dir():
        return []
    return [f"compressed.{p.stem}" for p in sorted(PLAYBOOK_DIR.glob("*.md"))]
