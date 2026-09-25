"""Door 3 — Hub surface: developers / enterprise.

Adopted, never duplicated (the Hub way): the Hub imports this organ and
adds only surface concerns — a JSON-able summary for the Hub API and a
route-table fragment following :mod:`levi.hub.api`'s
``{(method, path): handler}`` convention. No engine logic lives here;
:func:`build_managed` is the same shared engine, tagged.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, Dict, Optional, Tuple

from levi.builders.doors.project import DoorReport, Project, open_project
from levi.builders.economy import PLATFORM_CUT, BuildLedger
from levi.builders.pipeline import build as _engine_build

DOOR_NAME = "hub"
DEMAND_CLASS = "developers / enterprise"


def build_managed(
    prompt: str,
    workdir: Optional[str] = None,
    ledger: Optional[BuildLedger] = None,
) -> DoorReport:
    """Scaffold through the Hub door — the same engine, tagged.

    "Managed" is a property of the Hub surface around the build (auth,
    HITL, run log); generation itself is identical across doors by
    construction — see ``DoorReport.continue_via``.
    """
    return DoorReport(
        door=DOOR_NAME,
        prompt=prompt,
        build_report=_engine_build(prompt, workdir=workdir, ledger=ledger),
    )


def surface_summary(report: DoorReport) -> Dict:
    """JSON-able summary of a build for the Hub surface.

    Pure presentation over the engine's report: outcome, provenance,
    file list, the always-zero ledger total, and the marketplace hook
    math. Collecting money stays owner-gated — this only *describes*.
    """
    ledger_total = sum(
        (e.units_charged for e in report.build_report.ledger_entries),
        Decimal("0.00"),
    )
    return {
        "door": report.door,
        "demand_class": DEMAND_CLASS,
        "ok": report.ok,
        "outcome": report.outcome.value,
        "app": report.provenance.get("app"),
        "entities": report.provenance.get("entities", []),
        "prompt_sha256": report.provenance.get("prompt_sha256"),
        "files": report.files,
        "target_dir": report.target_dir,
        "attempts": report.attempts,
        "repairs": report.repairs,
        "charged": str(ledger_total),
        "platform_cut": str(PLATFORM_CUT),
        "note": (
            "builds are meter-free by construction; the 12% cut applies "
            "only to marketplace-monetized digital products, and "
            "collection is owner-gated"
        ),
    }


def hub_routes() -> Dict[Tuple[str, str], Callable]:
    """Route-table fragment in :mod:`levi.hub.api`'s convention.

    Handlers take ``(query, body, user)`` and return
    ``(code, payload, kind)``. The Hub merges this into its ROUTES when
    it is ready — this module never touches the Hub's own table.
    """

    def r_builder_build(query, body, user):
        prompt = (body or {}).get("prompt", "")
        if not prompt or not str(prompt).strip():
            return 400, {"ok": False, "error": "prompt required"}, "json"
        report = build_managed(str(prompt))
        return 200, {"ok": True, "build": surface_summary(report)}, "json"

    def r_builder_doors(query, body, user):
        from levi.builders.doors import DOORS  # local import: no cycle

        return (
            200,
            {
                "ok": True,
                "engine": "levi.builders (single shared engine)",
                "doors": [
                    {"door": name, "demand_class": mod.DEMAND_CLASS}
                    for name, mod in DOORS.items()
                ],
                "graduation": (
                    "same prompt through any door yields byte-identical "
                    "output — graduation is a change of surface, never a "
                    "rebuild"
                ),
            },
            "json",
        )

    return {
        ("POST", "/api/builders/build"): r_builder_build,
        ("GET", "/api/builders/doors"): r_builder_doors,
    }


__all__ = [
    "DEMAND_CLASS",
    "DOOR_NAME",
    "Project",
    "build_managed",
    "hub_routes",
    "open_project",
    "surface_summary",
]
