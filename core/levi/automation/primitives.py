"""LEVI automation primitive registry.

Original LEVI-native design. The *registry concept* (id, platforms,
permissions, HITL flags, workflow templates, NL mapping) is adapted from
the Levi-ai automation-capabilities design reference
(source-sync entry ``levi-ai``); every primitive below is written fresh
for LEVI — nothing is cloned verbatim.

Primitives are capability descriptors, not implementations: they declare
what LEVI may do, on which platforms, and which ones require a human in
the loop. Red primitives never run without explicit confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

# Risk bands mirror docs/AUTOMATION_SAFETY.md: green / yellow / red.
GREEN = "green"
YELLOW = "yellow"
RED = "red"


@dataclass(frozen=True)
class Primitive:
    id: str
    name: str
    platforms: tuple  # e.g. ("android", "termux", "linux")
    band: str  # green | yellow | red
    hitl_required: bool
    description: str
    notes: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "platforms": list(self.platforms),
            "band": self.band,
            "hitl_required": self.hitl_required,
            "description": self.description,
            "notes": self.notes,
        }


PRIMITIVES: List[Primitive] = [
    Primitive(
        "AP-001",
        "Clipboard capture",
        ("android", "termux", "linux"),
        GREEN,
        False,
        "Read the clipboard into a note or log.",
        "User-initiated reads only; no background clipboard polling.",
    ),
    Primitive(
        "AP-002",
        "Share-sheet receive",
        ("android",),
        GREEN,
        False,
        "Accept shared text/URLs from Android share sheet.",
    ),
    Primitive(
        "AP-003",
        "Notification trigger",
        ("android", "termux"),
        GREEN,
        False,
        "Raise a local notification (Termux:API or system).",
    ),
    Primitive(
        "AP-004",
        "File watcher",
        ("termux", "linux"),
        GREEN,
        False,
        "Watch a directory and log new/changed files.",
        "Watches user-chosen directories only.",
    ),
    Primitive(
        "AP-005",
        "Local HTTP bridge",
        ("termux", "linux"),
        GREEN,
        False,
        "Serve/consume HTTP on 127.0.0.1 for on-device bridges.",
        "Loopback only; never bind LAN/WAN.",
    ),
    Primitive(
        "AP-006",
        "Browser plan",
        ("termux", "linux", "android"),
        GREEN,
        False,
        "Build a structured browser-automation plan (no execution).",
        "See levi.automation.browser — plans only.",
    ),
    Primitive(
        "AP-007",
        "CDP session",
        ("termux", "linux"),
        YELLOW,
        False,
        "Attach to a user-owned Chromium via CDP on 127.0.0.1:9222.",
        "Loopback only; auth/captcha paths force HITL.",
    ),
    Primitive(
        "AP-008",
        "Form fill assist",
        ("termux", "linux"),
        YELLOW,
        True,
        "Fill non-auth forms under human confirmation.",
        "Never auth forms; login stays manual.",
    ),
    Primitive(
        "AP-009",
        "Snapshot capture",
        ("termux", "linux", "android"),
        GREEN,
        False,
        "Save page HTML/text snapshot to the output dir.",
    ),
    Primitive(
        "AP-010",
        "OCR pipeline (described)",
        ("android", "termux"),
        YELLOW,
        False,
        "Pipeline description for OCR of user-supplied images.",
        "No bundled OCR engine; user provides the tool.",
    ),
    Primitive(
        "AP-011",
        "QR session handoff",
        ("android", "termux", "linux"),
        GREEN,
        False,
        "Encode a session token as QR to continue on another device.",
        "Tokens are short-lived and single-use.",
    ),
    Primitive(
        "AP-012",
        "Termux script runner",
        ("termux",),
        YELLOW,
        True,
        "Run a user-approved shell script from the LEVI script catalog.",
        "Catalog scripts only; HITL before each run.",
    ),
    Primitive(
        "AP-013",
        "SMS / intent hooks",
        ("android",),
        RED,
        True,
        "Android SMS/intent integration points.",
        "Careful: messaging actions always require explicit confirmation.",
    ),
    Primitive(
        "AP-014",
        "Workflow templates",
        ("termux", "linux", "android"),
        GREEN,
        False,
        "Named multi-step workflows built from the primitives above.",
    ),
    Primitive(
        "AP-015",
        "Backup runner",
        ("termux", "linux"),
        GREEN,
        False,
        "Run the LEVI backup flow to local/flashdrive targets.",
    ),
    Primitive(
        "AP-016",
        "n8n skeleton (described)",
        ("linux", "termux"),
        YELLOW,
        False,
        "Self-hosted n8n workflow skeleton description.",
        "Description only; user hosts n8n themselves.",
    ),
]

# Natural-language → primitive mapping (first-match wins).
NL_MAP: List[tuple] = [
    ("log clipboard", ("AP-001",)),
    ("watch this folder", ("AP-004",)),
    ("open", ("AP-006", "AP-009")),
    ("snapshot", ("AP-009",)),
    ("log in", ("AP-007", "AP-008")),  # HITL forced by AP-008
    ("fill this form", ("AP-008",)),
    ("handoff", ("AP-011",)),
    ("backup", ("AP-015",)),
    ("ocr", ("AP-010",)),
    ("notify", ("AP-003",)),
]


def get_primitive(prim_id: str) -> Optional[Primitive]:
    """Look up a primitive by id (case-insensitive)."""
    want = str(prim_id or "").upper()
    for p in PRIMITIVES:
        if p.id.upper() == want:
            return p
    return None


def list_primitives(band: Optional[str] = None) -> List[Primitive]:
    """List primitives, optionally filtered by risk band."""
    if band is None:
        return list(PRIMITIVES)
    return [p for p in PRIMITIVES if p.band == band]


def match_nl(text: str) -> List[Primitive]:
    """Map a natural-language phrase to candidate primitives."""
    t = str(text or "").lower()
    for phrase, ids in NL_MAP:
        if phrase in t:
            found = [get_primitive(i) for i in ids]
            return [p for p in found if p is not None]
    return []


def red_primitives() -> List[Primitive]:
    """Primitives that always require explicit human confirmation."""
    return [p for p in PRIMITIVES if p.band == RED or p.hitl_required]


# ---------------------------------------------------------------------------
# Skill registration
# ---------------------------------------------------------------------------

try:  # pragma: no cover — import-time fallback keeps module import light
    from levi.skill.registry import Skill, SkillRisk

    def _skill_primitives(args):
        args = args or {}
        band = args.get("band")
        prims = list_primitives(band if band in (GREEN, YELLOW, RED) else None)
        return "\n".join(
            f"{p.id} [{p.band}]{' HITL' if p.hitl_required else ''} {p.name} — {p.description}"
            for p in prims
        )

    def _skill_nl_match(args):
        found = match_nl(str((args or {}).get("text") or ""))
        if not found:
            return "no primitive match"
        return "\n".join(
            f"{p.id} [{p.band}]{' HITL' if p.hitl_required else ''} {p.name}"
            for p in found
        )

    PRIMITIVE_SKILLS = [
        Skill(
            id="automation_primitives",
            name="Automation Primitives",
            description="List LEVI automation primitives with risk bands and HITL flags",
            category="automation",
            risk_level=SkillRisk.INFO,
            handler=_skill_primitives,
            tags=["automation", "primitives", "registry"],
        ),
        Skill(
            id="automation_nl_match",
            name="Automation NL Match",
            description="Map a natural-language request to automation primitives",
            category="automation",
            risk_level=SkillRisk.INFO,
            handler=_skill_nl_match,
            tags=["automation", "nl", "primitives"],
        ),
    ]
except ImportError:  # pragma: no cover
    PRIMITIVE_SKILLS = []  # type: ignore[assignment]
    Skill = object  # type: ignore[assignment,misc]
    SkillRisk = None  # type: ignore[assignment]
