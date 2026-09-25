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
- ``verify_build(blueprint, files)`` — check a compiled files dict
  against the blueprint: every expected artifact present and non-empty.
  Returns ``{"ok", "missing", "empty", "verdict"}``; never raises.
- ``require_valid_blueprint(blueprint)`` — the invariant's guard: raises
  ``ValueError`` on anything ``validate_blueprint`` rejects.
- ``publish_blueprint(substrate, prompt, product_types=None)`` — build,
  validate, and record a ``"blueprint"`` receipt in the shared substrate;
  raises ``ValueError`` on invalid (Echo never publishes unvalidated).
  Attaches shared learnings that mention the detected product types.
- ``challenge_build(substrate, build_receipt_id, blueprint, files)`` —
  Echo's interrogation path against Alpha's builds: runs
  ``verify_build`` and raises a substrate challenge (quarantining the
  build receipt) when it fails; returns ``None`` when there is nothing
  to challenge.

ECHO INVARIANT: Every blueprint Echo publishes is valid and verifiable —
``validate_blueprint`` passes on it and ``verify_build`` can check any
build against it. Echo never publishes an unvalidated blueprint. The
guard is ``require_valid_blueprint`` (raises before any receipt is
written); the proof is the matching test suite in
``tests/test_omega_echo_symbiotic.py``.

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
from typing import Any, Dict, List, Optional, Tuple

from levi.revival.omega import substrate as sub

ORIGIN = "levi-revival-omega/echo"

# product_type -> {title, keywords (scored), artifacts, layers}
# artifacts may use the {module} placeholder (the app slug with dashes
# turned into underscores) — Echo's expectation tracks what Alpha's
# generators actually emit, so verify_build can judge real builds.
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
        "artifacts": ["{module}.py", "README.md"],
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
        "artifacts": ["{module}.py", "requirements.txt", "README.md"],
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
        "artifacts": ["{module}.py", "README.md"],
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
        "artifacts": ["SKILL.md", "skill.py"],
        "layers": ["logic"],
    },
    # --- Original Omega Platform catalog (recovered from the founder's
    # omega_alpha_generators.py / omega_echo.py; LEVI-native metadata) ---
    "app": {
        "title": "Web App",
        "keywords": {
            'web app': 3,
            'application': 2,
            'dashboard': 2,
            'portal': 2,
            'crud app': 2,
        },
        "artifacts": ["webpage/", "ui/", "backend/"],
        "layers": ["presentation"],
    },
    "streamlit_app": {
        "title": "Streamlit App",
        "keywords": {
            'streamlit': 3,
            'st app': 2,
            'data app': 2,
            'interactive dashboard': 2,
        },
        "artifacts": ["streamlit/app.py", "streamlit/requirements.txt"],
        "layers": ["presentation"],
    },
    "saas_landing": {
        "title": "SaaS Landing Page",
        "keywords": {
            'saas': 3,
            'pricing page': 2,
            'product landing': 2,
            'signup page': 2,
            'startup landing': 2,
        },
        "artifacts": ["saas_landing/index.html", "saas_landing/pricing.json"],
        "layers": ["presentation"],
    },
    "widget": {
        "title": "Embeddable Widget",
        "keywords": {
            'widget': 3,
            'embed': 2,
            'iframe': 2,
            'embeddable': 2,
            'snippet': 2,
        },
        "artifacts": ["widget/widget.js", "widget/embed.html"],
        "layers": ["presentation"],
    },
    "mobile_app": {
        "title": "Mobile App",
        "keywords": {
            'mobile app': 3,
            'ios app': 2,
            'android app': 2,
            'react native': 2,
            'expo': 2,
        },
        "artifacts": ["mobile/App.tsx", "mobile/package.json"],
        "layers": ["presentation"],
    },
    "electron_app": {
        "title": "Desktop App",
        "keywords": {
            'electron': 3,
            'desktop app': 2,
            'desktop application': 2,
            'cross-platform app': 2,
        },
        "artifacts": ["electron/main.js", "electron/package.json"],
        "layers": ["presentation"],
    },
    "documentation_site": {
        "title": "Documentation Site",
        "keywords": {
            'docs': 3,
            'documentation': 2,
            'api reference': 2,
            'readme site': 2,
            'wiki': 2,
        },
        "artifacts": ["docs/index.html", "docs/navigation.json"],
        "layers": ["presentation"],
    },
    "fastapi_service": {
        "title": "FastAPI Service",
        "keywords": {
            'fastapi': 3,
            'python api': 2,
            'rest service': 2,
            'microservice': 2,
            'python backend': 2,
        },
        # Echo's expectation tracks what Alpha's generators actually emit:
        # _gen_fastapi_service namespaces the LEVI FastAPI scaffold under
        # "fastapi_service/" (generators_x._namespaced).
        "artifacts": [
            "fastapi_service/{module}.py",
            "fastapi_service/requirements.txt",
            "fastapi_service/README.md",
        ],
        "layers": ["logic", "data"],
    },
    "rest_api": {
        "title": "REST API",
        "keywords": {
            'rest api': 3,
            'api server': 2,
            'openapi': 2,
            'swagger': 2,
            'http api': 2,
        },
        "artifacts": ["api/openapi.json", "api/routes.py"],
        "layers": ["logic", "data"],
    },
    "graphql_api": {
        "title": "GraphQL API",
        "keywords": {
            'graphql': 3,
            'gql': 2,
            'graph ql': 2,
        },
        "artifacts": ["graphql/schema.graphql", "graphql/resolvers.py"],
        "layers": ["logic", "data"],
    },
    "cli_tool": {
        "title": "CLI Tool",
        "keywords": {
            'cli': 3,
            'command line': 2,
            'terminal tool': 2,
            'shell tool': 2,
            'command-line': 2,
            'grok cli': 2,
            'agent cli': 2,
            'coding cli': 2,
        },
        # Echo's expectation tracks what Alpha's generators actually emit:
        # _gen_cli_tool namespaces the LEVI CLI scaffold under "cli_tool/"
        # (generators_x._namespaced), so the manifest names those paths.
        "artifacts": ["cli_tool/{module}.py", "cli_tool/README.md"],
        "layers": ["logic", "data"],
    },
    "python_package": {
        "title": "Python Package",
        "keywords": {
            'python package': 3,
            'pypi': 2,
            'python library': 2,
            'python sdk': 2,
            'pip package': 2,
        },
        "artifacts": ["package/pyproject.toml", "package/src/__init__.py"],
        "layers": ["logic", "data"],
    },
    "npm_package": {
        "title": "NPM Package",
        "keywords": {
            'npm': 3,
            'node package': 2,
            'javascript library': 2,
            'typescript package': 2,
            'js sdk': 2,
        },
        "artifacts": ["npm/package.json", "npm/src/index.ts"],
        "layers": ["logic", "data"],
    },
    "api_client": {
        "title": "API Client",
        "keywords": {
            'api client': 3,
            'sdk': 2,
            'client library': 2,
            'api wrapper': 2,
        },
        "artifacts": ["client/client.py", "client/types.json"],
        "layers": ["logic", "data"],
    },
    "workflow": {
        "title": "Workflow",
        "keywords": {
            'workflow': 3,
            'pipeline': 2,
            'orchestration': 2,
            'dag': 2,
            'process flow': 2,
        },
        "artifacts": ["workflows/workflows.json"],
        "layers": ["logic"],
    },
    "bot": {
        "title": "Bot",
        "keywords": {
            'bot': 3,
            'chatbot': 2,
            'telegram bot': 2,
            'chat bot': 2,
        },
        "artifacts": ["bot/bot.py", "bot/config.json"],
        "layers": ["logic"],
    },
    "slack_app": {
        "title": "Slack App",
        "keywords": {
            'slack': 3,
            'slack bot': 2,
            'slack app': 2,
            'slash command': 2,
        },
        "artifacts": ["slack/app.py", "slack/manifest.json"],
        "layers": ["logic"],
    },
    "discord_bot": {
        "title": "Discord Bot",
        "keywords": {
            'discord': 3,
            'discord bot': 2,
        },
        "artifacts": ["discord/bot.py", "discord/config.json"],
        "layers": ["logic"],
    },
    "webhook_handler": {
        "title": "Webhook Handler",
        "keywords": {
            'webhook': 3,
            'callback': 2,
            'event handler': 2,
            'http hook': 2,
        },
        "artifacts": ["webhook/handler.py", "webhook/routes.json"],
        "layers": ["logic"],
    },
    "zapier_integration": {
        "title": "Zapier Integration",
        "keywords": {
            'zapier': 3,
            'make.com': 2,
            'integromat': 2,
            'no-code integration': 2,
        },
        "artifacts": ["integrations/zapier.json"],
        "layers": ["logic"],
    },
    "agent": {
        "title": "AI Agent",
        "keywords": {
            'agent': 3,
            'ai agent': 2,
            'autonomous agent': 2,
            'assistant agent': 2,
        },
        "artifacts": ["agents/agent.json"],
        "layers": ["logic"],
    },
    "langchain_chain": {
        "title": "LangChain Chain",
        "keywords": {
            'langchain': 3,
            'llm chain': 2,
            'rag': 2,
            'retrieval': 2,
            'prompt chain': 2,
        },
        "artifacts": ["langchain/chain.py", "langchain/config.json"],
        "layers": ["logic"],
    },
    "chrome_extension": {
        "title": "Chrome Extension",
        "keywords": {
            'chrome extension': 3,
            'browser extension': 2,
            'extension': 2,
            'chrome plugin': 2,
        },
        "artifacts": ["chrome_extension/manifest.json", "chrome_extension/background.js"],
        "layers": ["interface"],
    },
    "vscode_extension": {
        "title": "VS Code Extension",
        "keywords": {
            'vscode': 3,
            'vs code extension': 2,
            'editor extension': 2,
            'code extension': 2,
        },
        "artifacts": ["vscode/package.json", "vscode/extension.ts"],
        "layers": ["interface"],
    },
    "plugin": {
        "title": "Plugin",
        "keywords": {
            'plugin': 3,
            'addon': 2,
            'add-on': 2,
            'module': 2,
        },
        "artifacts": ["plugin/plugin.json", "plugin/index.js"],
        "layers": ["interface"],
    },
    "docker_compose": {
        "title": "Docker Compose",
        "keywords": {
            'docker': 3,
            'docker compose': 2,
            'container': 2,
            'containers': 2,
            'dockerfile': 2,
        },
        "artifacts": ["docker/docker-compose.yml", "docker/Dockerfile"],
        "layers": ["data"],
    },
    "database_schema": {
        "title": "Database Schema",
        "keywords": {
            'database': 3,
            'schema': 2,
            'sql': 2,
            'postgres': 2,
            'sqlite': 2,
            'migration': 2,
            'erd': 2,
        },
        "artifacts": ["database/schema.sql", "database/erd.json"],
        "layers": ["data"],
    },
    "terraform_infra": {
        "title": "Terraform Infrastructure",
        "keywords": {
            'terraform': 3,
            'iac': 2,
            'infrastructure': 2,
            'aws': 2,
            'gcp': 2,
            'azure': 2,
        },
        "artifacts": ["terraform/main.tf", "terraform/variables.tf"],
        "layers": ["data"],
    },
    "kubernetes_manifest": {
        "title": "Kubernetes Manifest",
        "keywords": {
            'kubernetes': 3,
            'k8s': 2,
            'helm': 2,
            'kubectl': 2,
            'kube': 2,
        },
        "artifacts": ["k8s/deployment.yaml", "k8s/service.yaml"],
        "layers": ["data"],
    },
    "spreadsheet": {
        "title": "Spreadsheet",
        "keywords": {
            'spreadsheet': 3,
            'excel': 2,
            'csv template': 2,
            'google sheets': 2,
            'xlsx': 2,
        },
        "artifacts": ["spreadsheet/data.csv", "spreadsheet/schema.json"],
        "layers": ["presentation"],
    },
    "email_template": {
        "title": "Email Template",
        "keywords": {
            'email': 3,
            'email template': 2,
            'newsletter': 2,
            'transactional email': 2,
        },
        "artifacts": ["email/template.html", "email/subject.txt"],
        "layers": ["presentation"],
    },
    "pdf_report": {
        "title": "PDF Report",
        "keywords": {
            'pdf': 3,
            'report': 2,
            'document template': 2,
            'printable': 2,
        },
        "artifacts": ["report/report.html", "report/structure.json"],
        "layers": ["presentation"],
    },
    "static_site": {
        "title": "Static Site",
        "keywords": {
            'static site': 3,
            'blog': 2,
            'jekyll': 2,
            'hugo': 2,
            'multi-page site': 2,
        },
        "artifacts": ["static_site/index.html", "static_site/pages.json"],
        "layers": ["presentation"],
    },
    "game": {
        "title": "Game",
        "keywords": {
            'game': 3,
            'canvas game': 2,
            'browser game': 2,
            'mini game': 2,
        },
        "artifacts": ["game/index.html", "game/game.js"],
        "layers": ["presentation", "logic"],
    },
    "iot_firmware": {
        "title": "IoT Firmware",
        "keywords": {
            'iot': 3,
            'firmware': 2,
            'embedded': 2,
            'arduino': 2,
            'esp32': 2,
            'raspberry pi': 2,
        },
        "artifacts": ["iot/firmware.ino", "iot/config.json"],
        "layers": ["presentation", "logic"],
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
    module = name.replace("-", "_")
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
            candidate = f"{name}/{artifact.format(module=module)}"
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


# ---------------------------------------------------------------------------
# Symbiotic surface: verification, publication, interrogation.
# ---------------------------------------------------------------------------


def verify_build(blueprint: Any, files: Any) -> Dict[str, Any]:
    """Check a compiled build against the blueprint Echo designed.

    Every artifact the blueprint expects must be present in ``files``
    (a ``{path: content}`` dict) and non-empty. Honest heuristic: Echo
    checks *presence and substance*, not correctness — a file that
    exists with content may still be wrong code, and that stays outside
    this check's claims.

    Never raises; bad input yields a failing verdict instead.
    """
    missing: List[str] = []
    empty: List[str] = []
    expected: List[str] = []
    if isinstance(blueprint, dict) and isinstance(
        blueprint.get("artifacts"), list
    ):
        expected = [a for a in blueprint["artifacts"] if isinstance(a, str)]
    name = blueprint.get("name", "<no-name>") if isinstance(blueprint, dict) else "<no-name>"

    if not expected:
        return {
            "ok": False,
            "missing": [],
            "empty": [],
            "verdict": f"blueprint {name!r} has no usable artifact list — cannot verify",
        }
    if not isinstance(files, dict):
        missing = list(expected)
    else:
        for artifact in expected:
            if artifact not in files:
                missing.append(artifact)
            else:
                content = files[artifact]
                text = content if isinstance(content, str) else str(content)
                if not text.strip():
                    empty.append(artifact)

    ok = not missing and not empty
    if ok:
        verdict = (
            f"build matches blueprint {name!r}: "
            f"{len(expected)} artifacts present and non-empty"
        )
    else:
        parts = []
        if missing:
            parts.append(f"{len(missing)} missing: {', '.join(missing)}")
        if empty:
            parts.append(f"{len(empty)} empty: {', '.join(empty)}")
        verdict = (
            f"build does NOT match blueprint {name!r}: " + "; ".join(parts)
        )
    return {"ok": ok, "missing": missing, "empty": empty, "verdict": verdict}


def require_valid_blueprint(blueprint: Any) -> Dict[str, Any]:
    """The invariant's guard: return the blueprint only if it validates.

    Raises ``ValueError`` naming every structural problem on anything
    ``validate_blueprint`` rejects — including non-dict input. Callers
    that would *publish* a blueprint must pass through here first.
    """
    result = validate_blueprint(blueprint)
    if not result["ok"]:
        raise ValueError(
            "refusing to publish an invalid blueprint: "
            + "; ".join(result["errors"])
        )
    return blueprint


def _lessons_for(
    substrate: "sub.SharedSubstrate", product_types: List[str]
) -> List[str]:
    """Shared learnings whose lesson text mentions a detected product type.

    Echo draws on the shared pool, not just its own inputs.
    """
    out: List[str] = []
    for entry in substrate.learnings():
        text = (entry.lesson or "").lower()
        if any(ptype in text for ptype in product_types):
            out.append(entry.lesson)
    return out


def publish_blueprint(
    substrate: "sub.SharedSubstrate",
    prompt: str,
    product_types: Optional[List[str]] = None,
) -> Tuple[Dict[str, Any], "sub.Receipt"]:
    """Build a blueprint, validate it, and record it in the shared substrate.

    Returns ``(blueprint, receipt)``. The receipt is organ ``"echo"``,
    kind ``"blueprint"``, risk ``"standard"`` (Echo's declared ceiling —
    design is reversible), and its payload carries the blueprint summary
    plus the detection scores and any shared learnings that mention the
    detected product types.

    Raises ``ValueError`` if the blueprint cannot validate — Echo never
    publishes an unvalidated blueprint. Also propagates ``ValueError``
    from ``build_blueprint`` (empty prompt, unknown product types).
    """
    blueprint = build_blueprint(prompt, product_types)
    require_valid_blueprint(blueprint)  # the invariant, guarded
    types = blueprint["product_types"]
    lessons = _lessons_for(substrate, types)
    payload = {
        "name": blueprint["name"],
        "title": blueprint["title"],
        "product_types": types,
        "artifacts": blueprint["artifacts"],
        "artifact_count": len(blueprint["artifacts"]),
        "layers": blueprint["layers"],
        "detection_scores": blueprint.get("detection_scores", {}),
        "lessons_attached": lessons,
        "created": blueprint["created"],
        "origin": blueprint["origin"],
    }
    receipt = substrate.record_receipt(
        organ="echo",
        kind="blueprint",
        payload=payload,
        risk=sub.RISK_STANDARD,
    )
    return blueprint, receipt


def challenge_build(
    substrate: "sub.SharedSubstrate",
    build_receipt_id: str,
    blueprint: Any,
    files: Any,
) -> Optional["sub.Challenge"]:
    """Echo's interrogation path against an Alpha build receipt.

    Runs ``verify_build``; if the build fails the check, raises a
    substrate challenge as organ ``"echo"`` with the verdict in plain
    words — the build receipt is quarantined immediately and no organ
    may consume it until the challenge resolves.

    Returns ``None`` when the build verifies — nothing to challenge.
    """
    result = verify_build(blueprint, files)
    if result["ok"]:
        return None
    name = (
        blueprint.get("name", "<unknown blueprint>")
        if isinstance(blueprint, dict)
        else "<unknown blueprint>"
    )
    grounds = (
        f"Echo checked the build against blueprint {name!r}: {result['verdict']}. "
        "The compiled output does not match the design it was built from."
    )
    return substrate.challenge(
        challenger="echo",
        target_receipt_id=build_receipt_id,
        grounds=grounds,
    )
