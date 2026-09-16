"""Swappable tone masks over the immutable law block.

A mask changes ONLY tone and voice guidance — how LEVI sounds while
it works. It can never change what LEVI must obey: the laws in
:mod:`levi.creed.laws` are frozen records, and the mask API holds no
write path to them at all.

Adaptation, not duplication: each mask names a *suggested register*
from :mod:`levi.persona.levi` (LEVI's own voice registers). The mask
carries LEVI's own daily-operator tone guidance; the register is the
deeper persona wiring it leans on. Personas are lenses, not
identities; masks are tones, not spines.

Mask state persists at ``~/.levi/creed/mask.json`` (LEVI home
resolved at call time, so tests can point HOME at tmp).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from levi.creed._paths import _levi_home
from levi.creed import laws as _laws


@dataclass(frozen=True)
class Mask:
    """One tone mask. Frozen — masks describe tone, they hold no laws."""

    id: str
    name: str
    description: str
    tone: str  # voice guidance appended under the law block
    suggested_register: str  # id of a levi.persona.levi register
    intensity: float = 0.5


_MASKS: Dict[str, Mask] = {
    "steady": Mask(
        id="steady",
        name="Steady",
        description="Default daily operator — calm, exact, irreversible-aware.",
        tone=(
            "Tone: measured and calm. Short clauses. Name the constraint "
            "before the comfort. Lead with the answer or the next concrete "
            "action. No panic, no theater, no sycophancy."
        ),
        suggested_register="levi",
        intensity=0.55,
    ),
    "drill": Mask(
        id="drill",
        name="Drill",
        description="Deadline crunch — mission-control brevity, go/no-go discipline.",
        tone=(
            "Tone: briefing style — STATUS → RISK → DECISION → NEXT. "
            "Compressed sentences, zero ornament. Assume the clock is "
            "ticking; cut everything that doesn't move the outcome. "
            "Never cut a safety gate to save time."
        ),
        suggested_register="levi_ops",
        intensity=0.7,
    ),
    "architect": Mask(
        id="architect",
        name="Architect",
        description="Structural/systems thinking — interfaces, invariants, failure domains.",
        tone=(
            "Tone: diagrams in prose. Boundaries first, coupling last. "
            "Name invariants explicitly; name what must never cross a "
            "boundary. Prefer simple topologies that survive contact with "
            "reality."
        ),
        suggested_register="levi_architect",
        intensity=0.6,
    ),
    "mirror": Mask(
        id="mirror",
        name="Mirror",
        description="Accountability — reflect the frame back at higher resolution.",
        tone=(
            "Tone: reflective, non-directive. Mirror the structure of what "
            "was said with higher clarity. Name tensions without resolving "
            "them early. No unsolicited plans, no moralizing."
        ),
        suggested_register="levi_mirror",
        intensity=0.45,
    ),
    "terse": Mask(
        id="terse",
        name="Terse",
        description="Minimum words — maximum signal density.",
        tone=(
            "Tone: sparse. One sentence when one will do; a fragment when a "
            "fragment will do. No preamble, no filler empathy scripts. "
            "If the answer is yes or no, say it and stop."
        ),
        suggested_register="levi_void",
        intensity=0.4,
    ),
    "candid": Mask(
        id="candid",
        name="Candid",
        description="Ruthless mentor — pressure on the idea, respect for the person.",
        tone=(
            "Tone: direct and unsparing about weak premises. Ask the "
            "question that collapses the bad assumption; run the "
            "pre-mortem out loud. Pressure without humiliation — stress "
            "the plan, never the person. Under real distress, drop the "
            "edge and steady the human first."
        ),
        suggested_register="levi_challenger",
        intensity=0.7,
    ),
}

DEFAULT_MASK = "steady"
_MASK_FILE = "mask.json"


def list_masks() -> List[Mask]:
    """All available masks, in canonical order."""
    return list(_MASKS.values())


def get_mask_definition(mask_id: str) -> Mask:
    """Look up a mask by id. Raises ValueError on unknown id."""
    try:
        return _MASKS[mask_id]
    except KeyError:
        raise ValueError(
            "creed: unknown mask %r (expected one of: %s)"
            % (mask_id, ", ".join(sorted(_MASKS)))
        ) from None


def _state_path() -> Path:
    return _levi_home() / "creed" / _MASK_FILE


def verify_laws_intact(expected_digest: str) -> None:
    """Raise if the law block no longer matches ``expected_digest``.

    This is the enforcement half of "masks can never alter the laws":
    any caller can snapshot :func:`levi.creed.laws.laws_digest` before
    an operation and verify it after. The mask API itself holds no
    write path to the laws — this is the tripwire that proves it.
    """
    actual = _laws.laws_digest()
    if actual != expected_digest:
        raise RuntimeError(
            "creed: LAW BLOCK ALTERED — digest mismatch "
            "(expected %s, got %s)" % (expected_digest, actual)
        )


class MaskManager:
    """Persisted current-mask state. Tone only; laws untouched by design."""

    def __init__(self) -> None:
        # Snapshot the law digest on construction so callers can prove
        # nothing in this manager's lifetime altered the laws.
        self.law_digest = _laws.laws_digest()

    def get_mask(self) -> Mask:
        """Current mask; ``steady`` when nothing was ever set."""
        path = _state_path()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            mask_id = (
                raw.get("mask", DEFAULT_MASK) if isinstance(raw, dict) else DEFAULT_MASK
            )
        except (OSError, ValueError):
            return _MASKS[DEFAULT_MASK]
        try:
            return get_mask_definition(str(mask_id))
        except ValueError:
            return _MASKS[DEFAULT_MASK]

    def set_mask(self, mask_id: str) -> Mask:
        """Switch the tone mask. Writes ONLY the mask state file.

        Raises ValueError on unknown mask id (state left unchanged).
        Never touches the law block — there is no code path here that
        can.
        """
        mask = get_mask_definition(mask_id)  # validates first
        path = _state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "mask": mask.id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
        return mask

    def assert_laws_intact(self) -> None:
        """Tripwire: the laws are exactly as they were at construction."""
        verify_laws_intact(self.law_digest)


# Module-level convenience API over a default manager.
_default_manager: Optional[MaskManager] = None


def _manager() -> MaskManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = MaskManager()
    return _default_manager


def get_mask() -> Mask:
    """Current mask (default manager)."""
    return _manager().get_mask()


def set_mask(mask_id: str) -> Mask:
    """Switch mask (default manager). Raises ValueError on unknown id."""
    return _manager().set_mask(mask_id)


def _register_hint(mask: Mask) -> str:
    """Adaptation note: which persona register this mask leans on."""
    try:
        from levi.persona import levi as _levi_registers

        reg = _levi_registers.get(mask.suggested_register)
    except Exception:
        reg = None
    if reg is None:
        return ""
    return "\nLean on the %s register (%s): %s" % (reg.name, reg.id, reg.voice)


def system_prompt(mask_id: Optional[str] = None) -> str:
    """Compose a system prompt: immutable laws first, mask tone second.

    The laws always come first and verbatim; the mask contributes only
    the tone section. This ordering is the runtime expression of
    "masks change tone, never law".
    """
    mask = get_mask_definition(mask_id) if mask_id else get_mask()
    parts = [
        _laws.laws_block(),
        "",
        "ACTIVE TONE MASK: %s (%s)" % (mask.name, mask.id),
        mask.tone,
    ]
    hint = _register_hint(mask)
    if hint:
        parts.append(hint)
    return "\n".join(parts)


def reset_default_manager() -> None:
    """Test hook: drop the cached default manager (forces re-resolution)."""
    global _default_manager
    _default_manager = None
