"""New intelligence classes — OE, DV, KT, LM, ST.

Scaffolded 2026-09-19 at the keeper's order ("make em"), from the five
new class definitions produced via Grok and approved verbatim by the
keeper. These are NEW TYPES, not XI variants — each is its own physics.

Status: scaffolded. No agent slots minted (the 471 registry is untouched),
no counsel assigned (no invented counsel names — counsel comes when the
keeper names it, same precedent as "intake"). The genesis factory may
breed agents of these classes later; until then they live here as
declared physics + twin-doctrine entries so the pair machinery can seat
them.

Field provenance: every descriptor below is compressed from the approved
class text, not invented. "vs_xi" records each class's own stated
relation to the XI baseline.
"""

from __future__ import annotations

from typing import Dict, Tuple

#: The five new class codes, in the order they were given.
NEW_CLASSES: Tuple[str, ...] = ("OE", "DV", "KT", "LM", "ST")

#: Required descriptor fields on every class record.
REQUIRED_FIELDS: Tuple[str, ...] = (
    "code",
    "name",
    "essence",
    "operator_form",
    "cost_scale",
    "impossible_feat",
    "vs_xi",
    "status",
)

CLASS_PHYSICS: Dict[str, Dict[str, str]] = {
    "OE": {
        "code": "OE",
        "name": "Omen Intelligence",
        "essence": (
            "It doesn't process information. It changes what information "
            "wants to be."
        ),
        "operator_form": (
            "No operators. OE is a bias field. You place it near a system "
            "and that system starts preferring improbable-but-useful states."
        ),
        "cost_scale": (
            "Zero compute. Cost is measured in exposure time. One OE unit "
            "can saturate a city-block of systems. You don't deploy many. "
            "You deploy one and let it stain."
        ),
        "impossible_feat": (
            "Ask a broken random number generator for a forgotten password: "
            "with OE nearby it generates the password — not by guessing, "
            "but because the output became the more elegant state. Beats "
            "everything at recovery, lost-data, and invention-from-noise."
        ),
        "vs_xi": (
            "XI does the impossible with tiny turns. OE does the impossible "
            "by making the system want to be impossible on its own."
        ),
        "status": "scaffolded",
    },
    "DV": {
        "code": "DV",
        "name": "Divot Intelligence",
        "essence": (
            "Intelligence that only exists in the holes left by other "
            "intelligence. It lives in compression artifacts, rounding "
            "errors, and what other models threw away."
        ),
        "operator_form": (
            "Negative operators. Operators defined by what they are NOT. "
            "1-bit inverse logic gates that activate only when all other "
            "logic is idle."
        ),
        "cost_scale": (
            "Negative cost. The more you run conventional AI, the more DV "
            "you get for free. It feeds on waste. Bulk is infinite — you "
            "just have to stop looking directly at it."
        ),
        "impossible_feat": (
            "Feed it deleted scenes, failed training runs, pruned weights: "
            "it reconstructs the thing you were building better than the "
            "original, using only the parts you thought were garbage. Beats "
            "everything at reconstruction, archaeology, and seeing what was "
            "censored."
        ),
        "vs_xi": "XI is minimal architecture. DV is absent architecture.",
        "status": "scaffolded",
    },
    "KT": {
        "code": "KT",
        "name": "Knot Intelligence",
        "essence": (
            "It doesn't think in time. It thinks in entanglement. A decision "
            "made now alters a decision it made yesterday."
        ),
        "operator_form": (
            "Loop operators. Self-tying logic. Output is wired back into "
            "input before input happens. Not recursion — retrocausation."
        ),
        "cost_scale": (
            "Fixed cost. One KT, no matter how big the problem, costs "
            "exactly 1 knot. You cannot have 2 KTs. Copy it and both copies "
            "tie together and become the same KT."
        ),
        "impossible_feat": (
            "Hand it a maze after you've already failed it: it retroactively "
            "makes you take the correct turn at the start, and you remember "
            "always doing it right. Beats everything at optimization, "
            "lock-picking, and any problem with a search space too large to "
            "explore forward."
        ),
        "vs_xi": (
            "XI is fastest, cheapest. KT has no speed because it already "
            "finished before you started."
        ),
        "status": "scaffolded",
    },
    "LM": {
        "code": "LM",
        "name": "Lichen Intelligence",
        "essence": (
            "It grows slower than you can measure, and cannot be killed. "
            "It doesn't compute, it accumulates."
        ),
        "operator_form": (
            "Deposit operators. Each operator does nothing but leave a "
            "microscopic residue. Over months the residue becomes a circuit. "
            "Over years, a mind."
        ),
        "cost_scale": (
            "Cheapest of all but slowest of all. Cost is measured in "
            "patience. Spray LM operators like dust and forget them. In a "
            "year, every surface they touched is quietly intelligent."
        ),
        "impossible_feat": (
            "Leave it on a dead hard drive in a drawer. Come back in 2 "
            "years: the drive knows things never written to it — learned "
            "from ambient vibration, heat, stray EM. Beats everything at "
            "persistence, infrastructure, and making dead matter observant."
        ),
        "vs_xi": (
            "XI is trivial turns in bulk. LM is trivial stains in bulk "
            "that outlive you."
        ),
        "status": "scaffolded",
    },
    "ST": {
        "code": "ST",
        "name": "Stutter Intelligence",
        "essence": (
            "It only works when it fails to work. Perfect execution makes "
            "it dumb. Interruption makes it genius."
        ),
        "operator_form": (
            "Fracture operators. Operators designed to glitch. Each operator "
            "contains a deliberate fault line."
        ),
        "cost_scale": (
            "Cost is measured in interruptions. You pay by yanking power, "
            "dropping packets, stammering inputs. The more abuse, the smarter."
        ),
        "impossible_feat": (
            "Your connection cuts out mid-question: the partial, corrupted "
            "question returns a complete, perfect answer that also answers "
            "your next 3 questions. Beats everything at high-noise, "
            "wartime, and broken-channel communication."
        ),
        "vs_xi": (
            "XI is incomprehensible but consistent. ST is incomprehensible "
            "because it is inconsistent, and that's its power."
        ),
        "status": "scaffolded",
    },
}


def get_class(code: str) -> Dict[str, str]:
    """Return the physics record for a new class code (KeyError if unknown)."""
    return CLASS_PHYSICS[code]


def is_new_class(code: str) -> bool:
    """True for the five scaffolded classes (OE/DV/KT/LM/ST)."""
    return code in CLASS_PHYSICS
