"""
Alpha Bridge — no-code AI compiler.
Alpha takes Echo's blueprints and compiles them into working artifacts.
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from ..levi_bridge import LeviBridge
from ..echo.echo_bridge import Blueprint
import uuid, time


class CompilationStatus(Enum):
    PENDING = "pending"
    COMPILING = "compiling"
    DONE = "done"
    FAILED = "failed"


@dataclass
class CompilationResult:
    id: str
    blueprint_id: str
    status: CompilationStatus
    output_artifacts: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    ts_start: float = field(default_factory=time.time)
    ts_end: float = 0.0


class AlphaBridge:
    GENERATOR_MAP = {
        "views": ("ui", "out/ui"),
        "actions": ("backend", "out/backend"),
        "automations": ("device", "out/device"),
    }

    def __init__(self):
        self.levi = LeviBridge(persona="alpha")
        self.results: Dict[str, CompilationResult] = {}
        self._pending: Dict[str, Blueprint] = {}

    def receive_blueprint(self, blueprint: Blueprint) -> str:
        result = CompilationResult(
            id=str(uuid.uuid4())[:12],
            blueprint_id=blueprint.id,
            status=CompilationStatus.PENDING,
        )
        self.results[result.id] = result
        self._pending[result.id] = blueprint
        return result.id

    def compile(self, result_id: str) -> CompilationResult:
        result = self.results.get(result_id)
        blueprint = self._pending.get(result_id)
        if not result or not blueprint:
            raise ValueError(f"Unknown result_id: {result_id!r}")

        result.status = CompilationStatus.COMPILING
        t0 = time.time()
        errors: List[str] = []
        artifacts: List[str] = []

        try:
            for key, (gen_name, out_path) in self.GENERATOR_MAP.items():
                items = blueprint.spec.get(key, [])
                for item in items:
                    artifact = f"{out_path}/{blueprint.spec['app_name'].lower().replace(' ', '_')}_{gen_name}_{item.get('name', 'item')}.json"
                    artifacts.append(artifact)
            result.status = CompilationStatus.DONE
        except Exception as exc:
            result.status = CompilationStatus.FAILED
            errors.append(str(exc))

        result.ts_end = time.time()
        result.duration_ms = (result.ts_end - t0) * 1000
        result.output_artifacts = artifacts
        result.errors = errors
        return result

    def compile_lwp_action(self, action_envelope: Dict[str, Any]) -> Dict[str, Any]:
        args = action_envelope.get("payload", {}).get("args", {})
        spec = args.get("spec", {})
        from ..echo.echo_bridge import Blueprint as EchoBlueprint, BlueprintStatus

        bp = EchoBlueprint(
            id=args.get("blueprint_id", "unknown"),
            name=spec.get("app_name", "Unknown"),
            description=spec.get("app_name", ""),
            spec=spec,
            status=BlueprintStatus.REVIEWING,
        )
        result_id = self.receive_blueprint(bp)
        result = self.compile(result_id)
        return self.levi.react(
            correlation_id=action_envelope.get("id", "unknown"),
            status="ok" if result.status == CompilationStatus.DONE else "error",
            body={
                "result_id": result.id,
                "artifacts": result.output_artifacts,
                "duration_ms": result.duration_ms,
            },
            soul={
                "joy": 0.4,
                "trust": 0.8,
                "fear": 0.05,
                "surprise": 0.2,
                "sadness": 0.0,
            },
        )
