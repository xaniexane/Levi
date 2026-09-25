"""Domain skill packs (the planner's knowledge, as data).

A pack is everything the planner needs to turn a prompt in a given domain
into a skilled, multi-module project: the module blueprint (many small
files, never a monolith), design directives (skill specified, not hoped
for), verification rules, and forbidden patterns.

Packs are registered data, inspected and versioned like any other source.
Complexity comes from this knowledge — not from model improvisation.
Deterministic: same domain -> same blueprint, always.
"""

from __future__ import annotations

from typing import Dict, List

PACKS: Dict[str, Dict] = {
    "web-api": {
        "label": "Web API service",
        "detect": [
            "api",
            "endpoint",
            "rest",
            "server",
            "backend",
            "service",
            "http",
            "webhook",
        ],
        "entry": "app.py",
        "modules": [
            {
                "path": "app.py",
                "kind": "entry",
                "purpose": "CLI entry: parses args, wires routes, serves HTTP.",
            },
            {
                "path": "api/__init__.py",
                "kind": "package",
                "purpose": "Marks api as a package.",
            },
            {
                "path": "api/models.py",
                "kind": "models",
                "purpose": "Entity dataclasses, validation, serialization.",
            },
            {
                "path": "api/routes.py",
                "kind": "routes",
                "purpose": "HTTP route handlers: CRUD per entity.",
            },
            {
                "path": "store.py",
                "kind": "store",
                "purpose": "JSON file store with atomic writes.",
            },
            {
                "path": "auth.py",
                "kind": "auth",
                "purpose": "Bearer-token auth backed by a token file.",
            },
            {
                "path": "migrations/__init__.py",
                "kind": "package",
                "purpose": "Marks migrations as a package.",
            },
            {
                "path": "migrations/m0001_init.py",
                "kind": "migration",
                "purpose": "Schema bootstrap: creates the data file.",
            },
            {
                "path": "tests/__init__.py",
                "kind": "package",
                "purpose": "Marks tests as a package.",
            },
            {
                "path": "tests/test_models.py",
                "kind": "test",
                "purpose": "Model validation and serialization tests.",
            },
            {
                "path": "tests/test_api.py",
                "kind": "test",
                "purpose": "Route handler tests against a live server.",
            },
            {
                "path": "tests/test_smoke.py",
                "kind": "test",
                "purpose": "End-to-end boot check.",
            },
            {
                "path": ".env.example",
                "kind": "config",
                "purpose": "Documents DATA_FILE and AUTH_TOKENS_FILE.",
            },
        ],
        "design_directives": [
            "Every entity gets the same five routes: list, create, read, "
            "update, delete. Uniformity is the design system.",
            "Validation lives in models, never in routes. Routes translate "
            "HTTP; models decide truth.",
            "The store is the only module that touches the data file. No "
            "other module opens it.",
            "Auth wraps routes; it never lives inside them. A route that "
            "checks tokens itself is a defect.",
            "Errors are JSON with a stable shape: "
            '{"error": code, "detail": message}.',
        ],
        "verify_rules": [
            "routes reference every entity in the plan",
            "no module except store opens the data file",
        ],
        "forbidden": [
            "DROP TABLE",
            "DELETE FROM",
            "shutil.rmtree",
            "os.remove(",
        ],
    },
    "realtime": {
        "label": "Realtime event service",
        "detect": ["realtime", "live", "websocket", "events", "stream", "sse", "chat"],
        "entry": "app.py",
        "modules": [
            {
                "path": "app.py",
                "kind": "entry",
                "purpose": "CLI entry: serves HTTP + event stream.",
            },
            {
                "path": "events.py",
                "kind": "events",
                "purpose": "Server-sent event bus: publish/subscribe, replay.",
            },
            {
                "path": "store.py",
                "kind": "store",
                "purpose": "JSON file store with atomic writes.",
            },
            {
                "path": "api/models.py",
                "kind": "models",
                "purpose": "Event and entity schemas with validation.",
            },
            {
                "path": "tests/__init__.py",
                "kind": "package",
                "purpose": "Marks tests as a package.",
            },
            {
                "path": "tests/test_events.py",
                "kind": "test",
                "purpose": "Bus publish/subscribe/replay tests.",
            },
            {
                "path": "tests/test_smoke.py",
                "kind": "test",
                "purpose": "End-to-end boot check.",
            },
        ],
        "design_directives": [
            "Events are the API. Every state change publishes an event; "
            "polling the store directly is a defect.",
            "The bus replays history to late subscribers — a client that "
            "connects mid-stream sees the whole story.",
            "Event names are past tense, namespaced: 'order.placed', not "
            "'placeOrder'.",
        ],
        "verify_rules": ["events module exposes publish and subscribe"],
        "forbidden": ["shutil.rmtree", "os.remove("],
    },
    "data-pipeline": {
        "label": "Data pipeline",
        "detect": ["pipeline", "etl", "ingest", "transform", "import", "sync"],
        "entry": "run.py",
        "modules": [
            {
                "path": "run.py",
                "kind": "entry",
                "purpose": "CLI entry: runs source -> stages -> sink.",
            },
            {
                "path": "sources.py",
                "kind": "source",
                "purpose": "Record producers: file, stdin, directory scan.",
            },
            {
                "path": "stages.py",
                "kind": "stage",
                "purpose": "Pure transforms: each stage is a function.",
            },
            {
                "path": "sinks.py",
                "kind": "sink",
                "purpose": "Record consumers: JSONL file, stdout.",
            },
            {
                "path": "state.py",
                "kind": "store",
                "purpose": "Checkpoint file: resume without reprocessing.",
            },
            {
                "path": "tests/__init__.py",
                "kind": "package",
                "purpose": "Marks tests as a package.",
            },
            {
                "path": "tests/test_stages.py",
                "kind": "test",
                "purpose": "Each stage tested in isolation.",
            },
            {
                "path": "tests/test_smoke.py",
                "kind": "test",
                "purpose": "End-to-end run on fixture input.",
            },
        ],
        "design_directives": [
            "Stages are pure functions: records in, records out, no I/O. "
            "Impure stages are a defect.",
            "Sources and sinks own all I/O. Nothing else touches the "
            "filesystem.",
            "The checkpoint records the last processed offset — a rerun "
            "never duplicates work.",
        ],
        "verify_rules": ["stages import nothing from sources or sinks"],
        "forbidden": ["shutil.rmtree", "os.remove("],
    },
    "cli-tool": {
        "label": "Command-line tool",
        "detect": ["cli", "command line", "terminal", "tool", "script"],
        "entry": "cli.py",
        "modules": [
            {
                "path": "cli.py",
                "kind": "entry",
                "purpose": "argparse surface: subcommands, help text.",
            },
            {
                "path": "core.py",
                "kind": "core",
                "purpose": "All logic; knows nothing about argv.",
            },
            {
                "path": "tests/__init__.py",
                "kind": "package",
                "purpose": "Marks tests as a package.",
            },
            {
                "path": "tests/test_core.py",
                "kind": "test",
                "purpose": "Core logic tests, no subprocess.",
            },
            {
                "path": "tests/test_smoke.py",
                "kind": "test",
                "purpose": "CLI boots and prints help.",
            },
        ],
        "design_directives": [
            "core.py never reads argv and never prints. The CLI layer is a "
            "thin translation of arguments to function calls.",
            "Every subcommand has --help text a stranger could follow.",
        ],
        "verify_rules": ["core imports nothing from cli"],
        "forbidden": ["shutil.rmtree", "os.remove("],
    },
    "general": {
        "label": "General project",
        "detect": [],
        "entry": "app.py",
        "modules": [
            {
                "path": "app.py",
                "kind": "entry",
                "purpose": "HTTP service entry with entity CRUD.",
            },
            {
                "path": "tests/__init__.py",
                "kind": "package",
                "purpose": "Marks tests as a package.",
            },
            {
                "path": "tests/test_smoke.py",
                "kind": "test",
                "purpose": "End-to-end boot check.",
            },
        ],
        "design_directives": [
            "One entity, one route family. Uniform CRUD before cleverness.",
        ],
        "verify_rules": [],
        "forbidden": ["shutil.rmtree", "os.remove("],
    },
}

# Shared non-code files every build carries, regardless of domain.
SHARED_FILES = ["README.md", "theme.yaml", ".provenance.json"]


def detect_domain(prompt: str) -> str:
    """Score keyword hits per pack; highest wins, ties -> first listed.

    Deterministic: iteration order is the PACKS definition order.
    """
    lowered = " %s " % prompt.lower()
    best = "general"
    best_score = 0
    for name, pack in PACKS.items():
        score = sum(1 for kw in pack["detect"] if kw in lowered)
        if score > best_score:
            best, best_score = name, score
    return best


def get_pack(domain: str) -> Dict:
    return PACKS.get(domain, PACKS["general"])
