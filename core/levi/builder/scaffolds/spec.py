"""BuildSpec — the strict output contract of the planner stage.

Every later stage (frontend, backend, data, tester) consumes this spec.
It is produced by the planner subtask as JSON, or by the heuristic
fallback when generation is unavailable.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List


@dataclass
class ApiRoute:
    method: str = "GET"
    path: str = "/api/health"
    handler: str = "health"
    description: str = ""


@dataclass
class Entity:
    name: str = "item"
    fields: List[str] = field(default_factory=lambda: ["id", "body"])


@dataclass
class BuildSpec:
    name: str = "app"
    title: str = "App"
    description: str = ""
    stack: str = "fullstack"  # "static" | "fullstack"
    entities: List[Entity] = field(default_factory=list)
    api_routes: List[ApiRoute] = field(default_factory=list)
    pages: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)
    spec_source: str = "planner"  # "planner" | "heuristic"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BuildSpec":
        entities = [
            Entity(**e) for e in data.get("entities", []) if isinstance(e, dict)
        ]
        routes = [
            ApiRoute(**r) for r in data.get("api_routes", []) if isinstance(r, dict)
        ]
        return cls(
            name=str(data.get("name", "app")),
            title=str(data.get("title", "App")),
            description=str(data.get("description", "")),
            stack=str(data.get("stack", "fullstack")),
            entities=entities,
            api_routes=routes,
            pages=[str(p) for p in data.get("pages", [])],
            features=[str(f) for f in data.get("features", [])],
            spec_source=str(data.get("spec_source", "planner")),
        )


SPEC_JSON_SCHEMA_HINT = """{
  "name": "url-safe-slug",
  "title": "Human Title",
  "description": "one-line description",
  "stack": "static" | "fullstack",
  "entities": [{"name": "entity", "fields": ["id", "name"]}],
  "api_routes": [{"method": "GET", "path": "/api/things",
                  "handler": "list_things", "description": "..."}],
  "pages": ["home"],
  "features": ["feature one", "feature two"]
}"""


def parse_spec_json(text: str, description: str, stack: str) -> BuildSpec:
    """Parse planner output into a BuildSpec; raises ValueError on failure."""
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("planner output is not a JSON object")
    data.setdefault("description", description)
    data["stack"] = stack
    return BuildSpec.from_dict(data)


def heuristic_spec(description: str, stack: str, name: str) -> BuildSpec:
    """Rule-based fallback spec when the planner generator is unavailable.

    Honestly labeled ``spec_source="heuristic"`` in the manifest so
    nobody mistakes it for a model-produced plan.
    """
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", description.lower())
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "app",
        "application",
        "build",
        "make",
        "create",
        "want",
        "need",
    }
    keywords = [w for w in words if w not in stop][:6]
    entity_name = keywords[0] if keywords else "item"
    title = name.replace("-", " ").replace("_", " ").title()
    return BuildSpec(
        name=name,
        title=title,
        description=description.strip(),
        stack=stack,
        entities=[Entity(name=entity_name, fields=["id", "name", "body", "created"])],
        api_routes=[
            ApiRoute("GET", "/api/health", "health", "liveness probe"),
            ApiRoute(
                "GET",
                f"/api/{entity_name}s",
                f"list_{entity_name}s",
                f"list all {entity_name}s",
            ),
            ApiRoute(
                "POST",
                f"/api/{entity_name}s",
                f"create_{entity_name}",
                f"create a {entity_name}",
            ),
        ],
        pages=["home"],
        features=[
            f"Manage your {entity_name}s locally",
            "Zero-dependency, runs offline",
        ],
        spec_source="heuristic",
    )
