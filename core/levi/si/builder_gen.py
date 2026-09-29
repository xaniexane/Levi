"""Builder wiring for the SI layer (additive — no core files touched).

Two seams, both through the Builder's existing public interfaces:

1. ``si_planner_generator`` — a real ``Generator`` callable for the
   planner stage of ``levi.builder.pipeline``. It answers the planner
   prompt with schema-valid spec JSON built from the SI engine's
   deterministic plan-brief (spec_source="si-rules"). Brain text never
   forms the payload (L5).

2. ``si_generator`` — a full-pipeline ``Generator``: planner prompts go
   to SI; every other stage raises ``GenerationError`` with an honest
   message, so the pipeline's own scaffold fallbacks run. This lets
   ``run_build(..., generate=si_generator)`` complete fully offline.

3. ``si_refine_notes`` — rules-tier refinement notes from a
   ``levi.builders`` plan summary, for the plan/refine steps to consult.

Alpha's seat: the Builder is his builder/developer twin's seat; this
module is the intelligence that seat consults. Nothing more built on
that framing — his words stay the spec.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List

from .engine import SIEngine
from .laws import LAWS  # noqa: F401

_PLANNER_MARKER = "Produce the build spec as JSON"
_DESC_PREFIX = "Application description:"


def _extract_description(prompt: str) -> str:
    """Pull the build description back out of the planner-stage prompt."""
    if _DESC_PREFIX in prompt:
        tail = prompt.split(_DESC_PREFIX, 1)[1]
        desc = tail.split("\n\nProduce the build spec", 1)[0]
        desc = desc.strip()
        if desc:
            return desc
    return prompt.strip()[:2000]


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "app"


def _route_to_api(route: str, entity: str) -> Dict[str, str]:
    """'GET /notes' -> ApiRoute dict. Paths are rooted at /api to match
    the scaffold's backend contract."""
    parts = route.split(None, 1)
    method = parts[0].upper() if parts else "GET"
    path = parts[1] if len(parts) > 1 else "/"
    path = path.replace("{id}", "{id}")
    if not path.startswith("/api"):
        path = "/api" + path
    one = "{id}" in path
    handler = f"{method.lower()}_{entity}_{'one' if one else 'all'}"
    handler = re.sub(r"[^a-z0-9_]", "_", handler)
    return {
        "method": method,
        "path": path,
        "handler": handler,
        "description": f"{method} {path}",
    }


def si_planner_generator(
    prompt: str,
    system_prompt: str,
    *,
    engine: SIEngine | None = None,
) -> str:
    """Answer the Builder's planner prompt with SI-built spec JSON.

    Raises GenerationError (imported lazily from levi.builder.generate)
    when SI cannot produce valid JSON, so the pipeline's honest
    heuristic fallback runs (L5).
    """
    from levi.builder.generate import GenerationError

    eng = engine or SIEngine()
    description = _extract_description(prompt)
    try:
        brief = eng.consult("plan-brief", {"description": description})
        data = brief.data
        entities = data.get("entities") or [{"name": "item", "fields": ["id"]}]
        entity_names = [e["name"] for e in entities]
        primary = entity_names[0]
        routes: List[Dict[str, str]] = []
        for surf in data.get("api_surface", [])[:15]:
            routes.append(_route_to_api(str(surf), primary))
        if not routes:
            routes.append(_route_to_api("GET /health", primary))
        slug = _slug(data.get("app_slug") or description)
        features = [
            f"manage {name}" for name in entity_names
        ] + [d for d in data.get("design_directives", [])[:4]]
        spec = {
            "name": slug,
            "title": slug.replace("-", " ").title(),
            "description": description[:280],
            "entities": [
                {"name": e["name"], "fields": ["id"] + e.get("fields", [])[:5]}
                for e in entities
            ],
            "api_routes": routes,
            "pages": ["home"],
            "features": features[:10],
            "spec_source": "si-rules",
        }
        text = json.dumps(spec)
        # L5: verify our own contract before returning it.
        from levi.builder.scaffolds.spec import parse_spec_json

        parsed = parse_spec_json(text, description, "static")
        assert parsed.spec_source == "si-rules"
        assert parsed.entities, "SI produced a spec with no entities"
        return text
    except Exception as exc:
        raise GenerationError(
            f"SI planner could not build a valid spec "
            f"({exc.__class__.__name__}); pipeline fallback applies"
        ) from exc


def si_generator(prompt: str, system_prompt: str) -> str:
    """Full-pipeline generator: SI plans, other stages honestly decline.

    Non-planner stages raise GenerationError so run_build's scaffold
    fallbacks (frontend/backend/data/tester) run instead of faked code.
    """
    from levi.builder.generate import GenerationError

    if _PLANNER_MARKER in prompt:
        return si_planner_generator(prompt, system_prompt)
    raise GenerationError(
        "SI layer covers the planner stage only; code stages need the "
        "agent runtime (or Chauncey's approval to wire more). The "
        "pipeline's scaffold fallbacks apply."
    )


def si_refine_notes(plan_summary: Dict) -> List[str]:
    """Rules-tier refinement notes for builders plan/refine steps to consult.

    Takes a ``plan_summary()`` dict (domain, entities, modules,
    api_surface, ambiguities) and returns concrete notes. Deterministic.
    """
    notes: List[str] = []
    ambiguities = plan_summary.get("ambiguities", [])
    for amb in ambiguities[:5]:
        notes.append(f"resolve before generating: {amb}")
    entities = plan_summary.get("entities", [])
    if len(entities) > 3:
        notes.append(
            f"{len(entities)} entities is a lot for one build — "
            "consider splitting the app"
        )
    modules = plan_summary.get("modules", [])
    if modules:
        notes.append(
            f"verify each of the {len(modules)} modules against the plan "
            "after generation (contracts gate)"
        )
    api = plan_summary.get("api_surface", [])
    if not api:
        notes.append("no API surface derived — confirm the app needs none")
    notes.append("smoke-test on localhost; generated code never runs elsewhere")
    return notes


__all__ = [
    "si_planner_generator",
    "si_generator",
    "si_refine_notes",
]
