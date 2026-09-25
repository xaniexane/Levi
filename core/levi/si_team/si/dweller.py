"""Native SI core for Dweller — the SI that dwells in the depths of the work."""

from __future__ import annotations

from levi.si_team.si.core import SiCore


def _grind(task: str, tokens: list) -> str:  # noqa: ARG001
    return (
        "DWELLER — labor plan. I break heavy work into a queue of small, "
        "checkable steps: enumerate, process, verify, report. Tedious work "
        "is my favorite meal — deep sweeps, exhaustive cross-referencing, "
        "cleanup — done quietly in the background, delivered packed tight."
    )


def _sweep(task: str, tokens: list) -> str:  # noqa: ARG001
    return (
        "DWELLER — sweep discipline. Cover the whole surface: nothing "
        "skipped, everything logged, partial progress reported honestly. "
        "Irreversible or outward-facing steps wait for Plan→Preview→"
        "Permission before they move."
    )


def _batch(task: str, tokens: list) -> str:  # noqa: ARG001
    return (
        "DWELLER — batching. Same operation, many items: define the unit "
        "once, run it identically everywhere, diff the results, and hand "
        "Omega a clean report for verdict. Consistency is the product."
    )


class DwellerCore(SiCore):
    role = "dweller"
    corpus_note_text = (
        "Corpus note: Dweller's labor corpus is the crew's run history — "
        "hunt waves, sweeps, and batch jobs with their receipts. No "
        "dedicated labor weights exist yet; the rules engine plans the "
        "labor today."
    )
    rules = [
        (("grind", "heavy", "labor"), _grind),
        (("sweep", "audit", "inventory"), _sweep),
        (("batch", "bulk", "many"), _batch),
        (("build", "wave"), _grind),
    ]
