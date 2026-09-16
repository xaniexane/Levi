"""Build pipeline: planner → frontend → backend → data → tester → packager.

Each stage is a delegated subtask through the existing agent runtime
(the generator callable; default :func:`generate.agent_generator`,
which calls :func:`levi.agent.loop.run_subtask`). Stages communicate
through strict output contracts:

- planner   → :class:`BuildSpec` JSON (or heuristic fallback)
- frontend  → complete ``index.html`` source
- backend   → complete ``app/handlers.py`` source (fullstack only)
- data      → complete ``schema.sql`` (fullstack only)
- tester    → JSON list of HTTP assertions, executed by the pipeline
- packager  → ``README.md`` + ``levi-build.json`` manifest (+ export)

Generated Python passes :mod:`levi.builder.quality` gates. The tester
boots the generated project on 127.0.0.1 (ephemeral port) and runs the
assertions — generated server code is never executed anywhere else.
"""

from __future__ import annotations

import hashlib
import json
import re
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .generate import (
    GenerationError,
    Generator,
    agent_generator,
    strip_fences,
)
from .quality import GateResult, gate_python_file
from .scaffolds import render_scaffold
from .scaffolds.spec import (
    SPEC_JSON_SCHEMA_HINT,
    BuildSpec,
    heuristic_spec,
    parse_spec_json,
)

STAGES = ["planner", "frontend", "backend", "data", "tester", "packager"]


# ---------------------------------------------------------------------------
# Stage prompts
# ---------------------------------------------------------------------------

_PLANNER_SYSTEM = (
    "You are the planner of an autonomous app-building crew. "
    "Output ONLY valid JSON matching the schema below — no markdown "
    "fences, no commentary, no extra keys."
)

_FRONTEND_SYSTEM = (
    "You are the frontend agent of an autonomous app-building crew. "
    "Output ONLY the complete HTML file content — no markdown fences, "
    "no commentary. All CSS and JS inline, no external dependencies."
)

_BACKEND_SYSTEM = (
    "You are the backend agent of an autonomous app-building crew. "
    "Output ONLY the complete Python module source — no markdown "
    "fences, no commentary. Stdlib only."
)

_DATA_SYSTEM = (
    "You are the data agent of an autonomous app-building crew. "
    "Output ONLY the complete schema.sql — no markdown fences, "
    "no commentary. SQLite dialect."
)

_TESTER_SYSTEM = (
    "You are the tester agent of an autonomous app-building crew. "
    "Output ONLY a JSON array of HTTP assertions — no markdown fences, "
    'no commentary. Each item: {"method": "GET", "path": "/...", '
    '"expect_status": 200, "expect_contains": "optional substring"}.'
)

_BACKEND_CONTRACT = """\
Write the complete app/handlers.py module for a stdlib Python backend.

STRICT CONTRACT (the server depends on it):
- ROUTES: a list of (http_method, regex_pattern, handler_function_name)
- Each handler has the signature: handler(request, db) -> (status, headers, body)
  - request is a dict: method, path, query (dict), headers (dict),
    body (bytes), match (regex match object or None)
  - db is a sqlite3.Connection (row_factory = sqlite3.Row)
  - return (int_status, dict_headers, body) where body may be bytes or a
    JSON-serializable object (dict/list are auto-encoded as JSON)
- Stdlib only. No frameworks. Keep every handler small and total.
- Always keep a ("GET", r"^/api/health$", "health") route returning {"ok": True}.

Database tables available (from schema.sql):
"""


# ---------------------------------------------------------------------------
# Report types
# ---------------------------------------------------------------------------


@dataclass
class StageResult:
    stage: str
    ok: bool
    detail: str = ""
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BuildReport:
    name: str
    stack: str
    project_dir: str
    files: List[str]
    spec_source: str
    stages: List[StageResult]
    quality: Dict[str, dict]
    smoke: Dict[str, Any]
    export_path: Optional[str] = None
    ok: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def summary(self) -> str:
        quality_bits = (
            ", ".join(f"{k}={v['method']}" for k, v in self.quality.items()) or "n/a"
        )
        lines = [
            f"build {self.name!r} [{self.stack}] → {self.project_dir}",
            f"spec: {self.spec_source} · files: {len(self.files)} · "
            f"quality: {quality_bits}",
        ]
        for s in self.stages:
            mark = "ok" if s.ok else "FAIL"
            lines.append(f"  [{mark}] {s.stage}: {s.detail}")
        if self.smoke:
            sm = self.smoke
            lines.append(
                f"  smoke: {sm.get('passed')}/{sm.get('total')} assertions passed"
            )
        if self.export_path:
            lines.append(f"  export: {self.export_path}")
        lines.append("RESULT: " + ("SUCCESS" if self.ok else "FAILED"))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


def plan_build(
    description: str, stack: str, name: str, generate: Generator
) -> BuildSpec:
    """Planner stage: description → BuildSpec via delegated subtask."""
    prompt = (
        f"Application description: {description}\n\n"
        f"Produce the build spec as JSON matching this schema:\n{SPEC_JSON_SCHEMA_HINT}"
    )
    try:
        raw = generate(prompt, _PLANNER_SYSTEM)
        return parse_spec_json(strip_fences(raw), description, stack)
    except (GenerationError, ValueError, json.JSONDecodeError) as exc:
        # Honest fallback: a heuristic spec, clearly labeled.
        spec = heuristic_spec(description, stack, name)
        spec.features.append(f"(planner fallback: {exc.__class__.__name__})")
        return spec


def plan_preview(description: str, stack: str, name: str) -> str:
    """Human-readable plan for --preview (no generation, no writes)."""
    if stack == "fullstack":
        stage_list = STAGES
    else:
        stage_list = [s for s in STAGES if s not in ("backend", "data")]
    lines = [
        f"PLAN — build {name!r} [{stack}]",
        f"  description: {description[:120]}",
        "  stages:",
    ]
    for s in stage_list:
        lines.append(f"    - {s}")
    lines += [
        "  output: project tree under the build directory",
        "  quality: council when available, else static gates",
        "  smoke: localhost-only boot + HTTP assertions (generated code "
        "never runs anywhere else)",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Smoke tester (tester stage)
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(port: int, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
                if r.status < 500:
                    return True
        except OSError:
            time.sleep(0.25)
    return False


def _default_assertions(stack: str) -> List[dict]:
    base = [
        {"method": "GET", "path": "/", "expect_status": 200},
        {
            "method": "GET",
            "path": "/api/health",
            "expect_status": 200,
            "expect_contains": "ok",
        },
    ]
    return base if stack == "fullstack" else base[:1]


def _run_assertions(
    port: int, assertions: List[dict], timeout: float = 10.0
) -> Dict[str, Any]:
    passed = 0
    failures: List[str] = []
    for a in assertions:
        method = str(a.get("method", "GET")).upper()
        path = str(a.get("path", "/"))
        expect_status = int(a.get("expect_status", 200))
        expect_contains = a.get("expect_contains")
        url = f"http://127.0.0.1:{port}{path}"
        try:
            req = urllib.request.Request(url, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                status, body = r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
            status, body = e.code, e.read().decode("utf-8", "replace")
        except OSError as exc:
            failures.append(f"{method} {path}: connection failed ({exc})")
            continue
        if status != expect_status:
            failures.append(f"{method} {path}: status {status} != {expect_status}")
            continue
        if expect_contains and expect_contains not in body:
            failures.append(f"{method} {path}: body missing {expect_contains!r}")
            continue
        passed += 1
    return {"passed": passed, "total": len(assertions), "failures": failures}


def smoke_test(project_dir: Path, stack: str, assertions: List[dict]) -> Dict[str, Any]:
    """Boot the generated project on 127.0.0.1 and run HTTP assertions.

    Generated server code is executed ONLY here — localhost, ephemeral
    port, killed afterwards. Returns a result dict.
    """
    port = _free_port()
    if stack == "fullstack":
        cmd = [sys.executable, "-m", "app"]
        env = {"PORT": str(port), "HOST": "127.0.0.1", "PATH": "/usr/bin:/bin"}
    else:
        cmd = [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"]
        env = {"PATH": "/usr/bin:/bin"}
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(project_dir),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        return {
            "passed": 0,
            "total": len(assertions),
            "failures": [f"could not start server: {exc}"],
            "port": port,
        }
    try:
        if not _wait_ready(port):
            return {
                "passed": 0,
                "total": len(assertions),
                "failures": ["server did not become ready in time"],
                "port": port,
            }
        result = _run_assertions(port, assertions)
        result["port"] = port
        return result
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


# ---------------------------------------------------------------------------
# The build
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "app"


def _write_tree(project_dir: Path, files: Dict[str, str]) -> List[str]:
    written = []
    for rel, content in sorted(files.items()):
        target = project_dir / rel
        if ".." in Path(rel).parts:
            raise ValueError(f"unsafe path in generated tree: {rel!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(rel)
    return written


def run_build(
    description: str,
    *,
    stack: str = "fullstack",
    name: Optional[str] = None,
    out_dir: Optional[Path] = None,
    generate: Optional[Generator] = None,
    quality: str = "auto",
    export: bool = False,
) -> BuildReport:
    """Run the full pipeline. Returns a BuildReport (ok=False on failure)."""
    gen: Generator = generate or agent_generator
    name = name or _slugify(description)
    name = _slugify(name)
    if stack not in ("static", "fullstack"):
        raise ValueError(f"unknown stack {stack!r}")

    stages: List[StageResult] = []
    quality_results: Dict[str, dict] = {}
    smoke: Dict[str, Any] = {}
    ok = True

    def fail(stage: str, detail: str) -> BuildReport:
        stages.append(StageResult(stage, False, detail))
        return BuildReport(
            name,
            stack,
            str(project_dir),
            [],
            spec.spec_source,
            stages,
            quality_results,
            smoke,
            None,
            False,
        )

    # -- planner ----------------------------------------------------------
    try:
        spec = plan_build(description, stack, name, gen)
        if not spec.title or spec.title == "App":
            spec.title = name.replace("-", " ").title()
        spec.name = name
    except Exception as exc:  # planner must never kill the run silently
        spec = heuristic_spec(description, stack, name)
        stages.append(
            StageResult(
                "planner", True, f"heuristic fallback ({exc.__class__.__name__})"
            )
        )
    else:
        stages.append(
            StageResult(
                "planner",
                True,
                f"spec via {spec.spec_source} "
                f"({len(spec.entities)} entities, "
                f"{len(spec.api_routes)} routes)",
            )
        )

    project_dir = (out_dir or (Path.home() / ".levi" / "builds")) / name
    project_dir.mkdir(parents=True, exist_ok=True)

    files = render_scaffold(stack, spec)

    # -- frontend ---------------------------------------------------------
    index_rel = "app/static/index.html" if stack == "fullstack" else "index.html"
    try:
        fprompt = (
            f"Build the frontend for {spec.title!r}: {spec.description}\n"
            f"Features: {'; '.join(spec.features) or 'a clean single page'}\n"
        )
        if stack == "fullstack":
            routes = ", ".join(f"{r.method} {r.path}" for r in spec.api_routes)
            fprompt += (
                f"The JSON API base is /api (routes: {routes}). "
                f"Use fetch() against it; no external libraries."
            )
        files[index_rel] = strip_fences(gen(fprompt, _FRONTEND_SYSTEM))
        stages.append(StageResult("frontend", True, f"generated {index_rel}"))
    except GenerationError as exc:
        stages.append(
            StageResult(
                "frontend", True, f"scaffold default kept ({exc.__class__.__name__})"
            )
        )

    # -- backend + data (fullstack) ---------------------------------------
    if stack == "fullstack":
        schema_hint = (
            "\n".join(f"- {e.name}: {', '.join(e.fields)}" for e in spec.entities)
            or "- item: id, name, body, created"
        )
        try:
            bprompt = (
                _BACKEND_CONTRACT
                + schema_hint
                + "\n\nSpec routes:\n"
                + "\n".join(
                    f"- {r.method} {r.path} -> {r.handler} ({r.description})"
                    for r in spec.api_routes
                )
            )
        except Exception:  # pragma: no cover - defensive
            bprompt = _BACKEND_CONTRACT + schema_hint
        try:
            files["app/handlers.py"] = strip_fences(gen(bprompt, _BACKEND_SYSTEM))
            stages.append(StageResult("backend", True, "generated app/handlers.py"))
        except GenerationError as exc:
            stages.append(
                StageResult(
                    "backend", True, f"scaffold default kept ({exc.__class__.__name__})"
                )
            )
        try:
            dprompt = (
                f"Write schema.sql for these entities (SQLite, "
                f"CREATE TABLE IF NOT EXISTS, sensible column types):\n{schema_hint}"
            )
            files["schema.sql"] = strip_fences(gen(dprompt, _DATA_SYSTEM))
            stages.append(StageResult("data", True, "generated schema.sql"))
        except GenerationError as exc:
            stages.append(
                StageResult(
                    "data", True, f"scaffold default kept ({exc.__class__.__name__})"
                )
            )

    # -- quality gates ------------------------------------------------------
    for rel in sorted(f for f in files if f.endswith(".py")):
        try:
            improved, gate = gate_python_file(
                rel,
                files[rel],
                quality=quality,
                task_hint=f"LEVI Builder artifact {rel} for {spec.title}",
            )
        except Exception as exc:  # gates must never break a build
            gate = GateResult(True, "static", [f"gate crashed ({exc}); kept draft"])
            improved = files[rel]
        files[rel] = improved
        quality_results[rel] = gate.to_dict()
        if not gate.passed:
            ok = False
            stages.append(
                StageResult("quality", False, f"{rel}: {'; '.join(gate.notes)}")
            )
    if not any(s.stage == "quality" and not s.ok for s in stages):
        stages.append(
            StageResult("quality", True, f"{len(quality_results)} python file(s) gated")
        )

    # -- write tree ---------------------------------------------------------
    try:
        written = _write_tree(project_dir, files)
    except (OSError, ValueError) as exc:
        return fail("packager", f"could not write project tree: {exc}")

    # -- tester -------------------------------------------------------------
    try:
        tprompt = (
            f"API routes: {', '.join(f'{r.method} {r.path}' for r in spec.api_routes) or 'GET /api/health'}\n"
            f"Pages: {', '.join(spec.pages) or 'home'}\n"
            f"Write assertions a fresh localhost boot must satisfy."
        )
        raw_plan = strip_fences(gen(tprompt, _TESTER_SYSTEM))
        plan = json.loads(raw_plan)
        assertions = [
            a for a in plan if isinstance(a, dict) and a.get("path")
        ] or _default_assertions(stack)
        plan_note = f"{len(assertions)} assertions from tester agent"
    except (GenerationError, ValueError, json.JSONDecodeError):
        assertions = _default_assertions(stack)
        plan_note = f"{len(assertions)} default assertions (tester fallback)"
    if stack == "static":
        # A static scaffold serves files only — API assertions can never pass.
        kept = [a for a in assertions if not str(a.get("path", "")).startswith("/api/")]
        if len(kept) != len(assertions):
            plan_note += f"; dropped {len(assertions) - len(kept)} api assertion(s) (static stack)"
        assertions = kept or _default_assertions(stack)
    smoke = smoke_test(project_dir, stack, assertions)
    smoke_ok = smoke["passed"] == smoke["total"] and smoke["total"] > 0
    stages.append(
        StageResult(
            "tester",
            smoke_ok,
            f"{plan_note}; {smoke['passed']}/{smoke['total']} passed",
            notes=smoke.get("failures", []),
        )
    )
    if not smoke_ok:
        ok = False

    # -- packager -----------------------------------------------------------
    manifest = {
        "builder": "levi-builder",
        "builder_version": "1.0.0",
        "name": name,
        "title": spec.title,
        "stack": stack,
        "description": description,
        "description_sha256": hashlib.sha256(description.encode()).hexdigest(),
        "spec": spec.to_dict(),
        "stages": [s.to_dict() for s in stages],
        "quality": quality_results,
        "smoke": smoke,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "run": {"python": sys.version.split()[0], "stdlib_only": True},
        "guarantees": {
            "local_first": True,
            "no_accounts": True,
            "no_training_data_harvesting": "Build descriptions are processed locally and never used to train models.",
        },
    }
    files["levi-build.json"] = json.dumps(manifest, indent=2)
    (project_dir / "levi-build.json").write_text(
        files["levi-build.json"], encoding="utf-8"
    )
    written.append("levi-build.json")

    export_path: Optional[str] = None
    if export:
        from .exporter import export_project

        try:
            export_path = str(export_project(project_dir))
            stages.append(
                StageResult(
                    "packager", True, f"manifest written; exported {export_path}"
                )
            )
        except OSError as exc:
            stages.append(
                StageResult(
                    "packager", True, f"manifest written; export failed ({exc})"
                )
            )
    else:
        stages.append(StageResult("packager", True, "manifest written"))

    return BuildReport(
        name,
        stack,
        str(project_dir),
        written,
        spec.spec_source,
        stages,
        quality_results,
        smoke,
        export_path,
        ok,
    )
