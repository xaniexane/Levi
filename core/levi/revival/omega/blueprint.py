"""Echo revival: the Blueprint Architect, reborn as LEVI-native.

Omega's Echo turned a natural-language request into an architecture
blueprint — a JSON spec naming the product types, components, and layers
— which Alpha's generators then compiled. This module is that mechanism,
written from scratch: detect what kind of thing is being asked for, draft
a structured blueprint, and validate it before anything builds from it.

Public surface:

- ``detect_product_types(prompt)`` — keyword-scored detection of which
  product types a prompt asks for (``webpage``, ``cli``, ``api``,
  ``mcp_server``, ``automation``, ``skill``).
- ``build_blueprint(prompt, product_types=None)`` — full blueprint dict:
  app name, title, product types, components, layers, artifacts.
- ``validate_blueprint(blueprint)`` — structural check returning
  ``{"ok": bool, "errors": [...]}``; never raises on bad input.

Defensive notes:

- Detection is a heuristic, reported as one: scores are exposed so a
  caller can see *why* a type was chosen, and ``detect_product_types``
  returns ``["skill"]`` (the smallest useful unit) when nothing matches
  rather than pretending confidence.
- ``validate_blueprint`` treats any non-dict or missing-field blueprint
  as invalid data, not an exception.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

ORIGIN = "levi-revival-omega/echo"

# product_type -> {title, keywords (scored), artifacts, layers}
PRODUCT_TYPES: Dict[str, Dict[str, Any]] = {
    "webpage": {
        "title": "Web page / site",
        "keywords": {
            "website": 3,
            "webpage": 3,
            "web page": 3,
            "web app": 3,
            "site": 2,
            "landing page": 3,
            "dashboard": 2,
            "frontend": 2,
            "html": 2,
            "page": 1,
        },
        "artifacts": ["index.html", "styles.css", "app.js"],
        "layers": ["presentation"],
    },
    "cli": {
        "title": "Command-line tool",
        "keywords": {
            "cli": 3,
            "command line": 3,
            "command-line": 3,
            "terminal": 2,
            "script": 1,
            "tool": 1,
        },
        "artifacts": ["main.py", "README.md"],
        "layers": ["interface", "logic"],
    },
    "api": {
        "title": "HTTP API backend",
        "keywords": {
            "api": 3,
            "backend": 3,
            "back end": 3,
            "rest": 2,
            "server": 2,
            "endpoint": 3,
            "fastapi": 3,
            "service": 1,
        },
        "artifacts": ["app.py", "requirements.txt", "README.md"],
        "layers": ["interface", "logic", "data"],
    },
    "mcp_server": {
        "title": "MCP server",
        "keywords": {
            "mcp": 3,
            "model context protocol": 3,
            "mcp server": 3,
            "tool server": 2,
        },
        "artifacts": ["server.py", "README.md"],
        "layers": ["interface", "logic"],
    },
    "automation": {
        "title": "Automation / agent workflow",
        "keywords": {
            "automat": 2,
            "workflow": 2,
            "schedule": 2,
            "cron": 2,
            "pipeline": 2,
            "bot": 2,
            "agent": 1,
        },
        "artifacts": ["workflow.py", "README.md"],
        "layers": ["logic", "data"],
    },
    "skill": {
        "title": "LEVI skill",
        "keywords": {
            "skill": 3,
            "playbook": 2,
            "capability": 1,
        },
        "artifacts": ["SKILL.md"],
        "layers": ["logic"],
    },
}

_FALLBACK_TYPE = "skill"

_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "that",
    "this",
    "it",
    "is",
    "are",
    "be",
    "as",
    "at",
    "by",
    "from",
    "my",
    "me",
    "i",
    "you",
    "we",
    "us",
    "your",
    "our",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "untitled"


def _score_prompt(prompt: str) -> List[Tuple[str, int]]:
    lowered = prompt.lower()
    scored: List[Tuple[str, int]] = []
    for ptype, meta in PRODUCT_TYPES.items():
        score = 0
        for keyword, weight in meta["keywords"].items():
            if keyword in lowered:
                # word-boundary check for short keywords to cut false hits
                if len(keyword) <= 4 and not re.search(
                    r"\b" + re.escape(keyword), lowered
                ):
                    continue
                score += weight
        if score > 0:
            scored.append((ptype, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def detect_product_types(prompt: str) -> List[str]:
    """Best-effort product-type detection; heuristic, never asserted.

    Returns product types ordered by score. Falls back to ``["skill"]``
    (the smallest useful unit) when nothing scores.
    """
    if not prompt or not prompt.strip():
        return [_FALLBACK_TYPE]
    scored = _score_prompt(prompt)
    if not scored:
        return [_FALLBACK_TYPE]
    return [ptype for ptype, _ in scored]


def detection_scores(prompt: str) -> Dict[str, int]:
    """Expose the raw keyword scores behind :func:`detect_product_types`."""
    return dict(_score_prompt(prompt or ""))


def _infer_app_name(prompt: str, product_types: List[str]) -> str:
    words = [
        w.strip(".,!?;:\"'()").lower()
        for w in prompt.split()
        if w.strip(".,!?;:\"'()").lower() not in _STOPWORDS
        and len(w.strip(".,!?;:\"'()")) > 2
    ]
    base = "-".join(words[:3]) if words else "untitled"
    # disambiguate the name with the primary product type
    primary = product_types[0] if product_types else _FALLBACK_TYPE
    suffix = {
        "webpage": "site",
        "cli": "cli",
        "api": "api",
        "mcp_server": "mcp",
        "automation": "flow",
        "skill": "skill",
    }.get(primary, "app")
    slug = slugify(base)
    if not slug.endswith(suffix):
        slug = f"{slug}-{suffix}"
    return slug[:48]


def build_blueprint(
    prompt: str, product_types: List[str] | None = None
) -> Dict[str, Any]:
    """Draft an architecture blueprint from a natural-language prompt."""
    if not prompt or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    types = list(product_types) if product_types else detect_product_types(prompt)
    unknown = [t for t in types if t not in PRODUCT_TYPES]
    if unknown:
        raise ValueError(f"unknown product types: {unknown}")
    name = _infer_app_name(prompt, types)
    components: List[Dict[str, Any]] = []
    layers: List[str] = []
    artifacts: List[str] = []
    for ptype in types:
        meta = PRODUCT_TYPES[ptype]
        components.append(
            {
                "name": f"{name}-{ptype}",
                "kind": ptype,
                "title": meta["title"],
                "notes": f"Scaffolded from prompt: {prompt[:80]}",
            }
        )
        for layer in meta["layers"]:
            if layer not in layers:
                layers.append(layer)
        for artifact in meta["artifacts"]:
            candidate = f"{name}/{artifact}"
            if candidate not in artifacts:
                artifacts.append(candidate)
    return {
        "name": name,
        "title": name.replace("-", " ").title(),
        "prompt": prompt,
        "product_types": types,
        "detection_scores": detection_scores(prompt),
        "components": components,
        "layers": layers,
        "artifacts": artifacts,
        "created": _now_iso(),
        "origin": ORIGIN,
    }


_REQUIRED_FIELDS = {
    "name": str,
    "title": str,
    "prompt": str,
    "product_types": list,
    "components": list,
    "layers": list,
    "artifacts": list,
}


def validate_blueprint(blueprint: Any) -> Dict[str, Any]:
    """Structural validation; returns ``{"ok", "errors"}``, never raises."""
    errors: List[str] = []
    if not isinstance(blueprint, dict):
        return {"ok": False, "errors": ["blueprint must be a dict"]}
    for field, ftype in _REQUIRED_FIELDS.items():
        if field not in blueprint:
            errors.append(f"missing field: {field}")
        elif not isinstance(blueprint[field], ftype):
            errors.append(f"field {field!r} must be {ftype.__name__}")
    if isinstance(blueprint.get("product_types"), list):
        for ptype in blueprint["product_types"]:
            if ptype not in PRODUCT_TYPES:
                errors.append(f"unknown product type: {ptype!r}")
    if isinstance(blueprint.get("components"), list):
        for i, comp in enumerate(blueprint["components"]):
            if not isinstance(comp, dict) or "name" not in comp or "kind" not in comp:
                errors.append(f"component {i} must be a dict with name/kind")
    return {"ok": not errors, "errors": errors}
