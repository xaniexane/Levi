"""
LEVI Constructive DNA — Software Factory (embedded, not a side feature)

Builds software: idea→requirements→architecture→scaffold→implement→build→
test→debug→security→package. Not the Income Factory (levi.income.factory),
which composes service/offer plans — different job, different package.

LEVI × L.W.P. × Factory = one coherent super-system.
Factory stages are L.W.P. cascade instances under governor/circuit-breaker/policy.
Companion integrity still applies while building.

Pipeline: IDEA → REQUIREMENTS → ARCHITECTURE → SCAFFOLD → IMPLEMENT → BUILD → TEST → DEBUG → SECURITY → PACKAGE

Phase 1: state machine + persistence + receipts.
Full codegen activates with model + sandbox — still the same organism.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime, timezone
import uuid
import json
from pathlib import Path


class FactoryStage(str, Enum):
    IDEA = "idea"
    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    SCAFFOLD = "scaffold"
    IMPLEMENT = "implement"
    BUILD = "build"
    TEST = "test"
    DEBUG = "debug"
    SECURITY = "security"
    PACKAGE = "package"
    COMPLETE = "complete"
    FAILED = "failed"
    PAUSED = "paused"


STAGE_ORDER = [
    FactoryStage.IDEA,
    FactoryStage.REQUIREMENTS,
    FactoryStage.ARCHITECTURE,
    FactoryStage.SCAFFOLD,
    FactoryStage.IMPLEMENT,
    FactoryStage.BUILD,
    FactoryStage.TEST,
    FactoryStage.DEBUG,
    FactoryStage.SECURITY,
    FactoryStage.PACKAGE,
    FactoryStage.COMPLETE,
]


@dataclass
class StageResult:
    stage: FactoryStage
    status: str  # ok | fail | skip | pending
    summary: str = ""
    artifacts: List[str] = field(default_factory=list)
    error: Optional[str] = None
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["stage"] = self.stage.value
        return d


@dataclass
class FactoryProject:
    id: str
    name: str
    idea: str
    stage: FactoryStage = FactoryStage.IDEA
    history: List[StageResult] = field(default_factory=list)
    requirements: Dict[str, Any] = field(default_factory=dict)
    architecture_notes: str = ""
    risk_ceiling: int = 2
    max_iterations: int = 10
    iteration: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "idea": self.idea,
            "stage": self.stage.value,
            "history": [h.to_dict() for h in self.history],
            "requirements": self.requirements,
            "architecture_notes": self.architecture_notes,
            "risk_ceiling": self.risk_ceiling,
            "max_iterations": self.max_iterations,
            "iteration": self.iteration,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


DEFAULT_FACTORY_DIR = Path.home() / ".levi" / "factory"


class SoftwareFactory:
    """
    Bounded software factory runtime.
    Does not claim code generation is complete without model + sandbox.
    Advances stage state machine with verification hooks.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_FACTORY_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.projects: Dict[str, FactoryProject] = {}
        self._load()

    def _load(self) -> None:
        index = self.data_dir / "projects.json"
        if index.exists():
            try:
                raw = json.loads(index.read_text(encoding="utf-8"))
                for p in raw.get("projects", []):
                    hist = [
                        StageResult(
                            stage=FactoryStage(h["stage"]),
                            status=h["status"],
                            summary=h.get("summary", ""),
                            artifacts=h.get("artifacts", []),
                            error=h.get("error"),
                            at=h.get("at", ""),
                        )
                        for h in p.get("history", [])
                    ]
                    proj = FactoryProject(
                        id=p["id"],
                        name=p["name"],
                        idea=p["idea"],
                        stage=FactoryStage(p["stage"]),
                        history=hist,
                        requirements=p.get("requirements", {}),
                        architecture_notes=p.get("architecture_notes", ""),
                        risk_ceiling=p.get("risk_ceiling", 2),
                        max_iterations=p.get("max_iterations", 10),
                        iteration=p.get("iteration", 0),
                        created_at=p.get("created_at", ""),
                        updated_at=p.get("updated_at", ""),
                        metadata=p.get("metadata", {}),
                    )
                    self.projects[proj.id] = proj
            except Exception:
                pass

    def _persist(self) -> None:
        index = self.data_dir / "projects.json"
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "projects": [p.to_dict() for p in self.projects.values()],
        }
        tmp = index.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(index)

    def create(self, name: str, idea: str, risk_ceiling: int = 2) -> FactoryProject:
        pid = f"proj.{uuid.uuid4().hex[:10]}"
        proj = FactoryProject(id=pid, name=name, idea=idea, risk_ceiling=risk_ceiling)
        proj.history.append(StageResult(
            stage=FactoryStage.IDEA,
            status="ok",
            summary=f"Idea captured: {idea[:120]}",
        ))
        self.projects[pid] = proj
        self._persist()
        # Formula: everything in LEVI interpenetrates — register project on Capability Graph
        try:
            from levi.graph.interpenetration import InterpenetrationEngine
            eng = InterpenetrationEngine()
            parts = ["cap.software_factory", "lwp.cascade", "lwp.governor"]
            # Prefer nodes that exist
            parts = [p for p in parts if p in eng.nodes]
            if len(parts) >= 2:
                eng.propose_composite(
                    name=f"Project:{proj.name[:40]}",
                    part_ids=parts,
                    description=f"Factory project {pid}: {proj.idea[:100]}",
                    behavior_summary="Live factory instance under L.W.P. cascade/governor",
                    tags=["factory", "project", "interpenetrable", pid],
                )
        except Exception:
            pass
        return proj

    def _next_stage(self, current: FactoryStage) -> Optional[FactoryStage]:
        try:
            idx = STAGE_ORDER.index(current)
        except ValueError:
            return None
        if idx + 1 < len(STAGE_ORDER):
            return STAGE_ORDER[idx + 1]
        return None

    def advance(self, project_id: str, summary: str = "", artifacts: Optional[List[str]] = None) -> FactoryProject:
        """Advance one stage with a result. Circuit-breaks on max iterations."""
        proj = self.projects[project_id]
        if proj.stage in (FactoryStage.COMPLETE, FactoryStage.FAILED):
            raise RuntimeError(f"Project already terminal: {proj.stage.value}")
        if proj.iteration >= proj.max_iterations:
            proj.stage = FactoryStage.FAILED
            proj.history.append(StageResult(
                stage=proj.stage,
                status="fail",
                summary="Circuit breaker: max iterations",
                error="max_iterations",
            ))
            self._persist()
            return proj

        proj.iteration += 1
        stage_artifacts = list(artifacts or [])
        stage_summary = summary or f"Completed stage {proj.stage.value}"

        # Constructive DNA: when leaving architecture → scaffold, write real files
        if proj.stage == FactoryStage.ARCHITECTURE:
            try:
                from levi.factory.sandbox import Sandbox
                sb = Sandbox(proj.id)
                sr = sb.scaffold_python_cli(proj.name[:40], proj.idea[:200])
                if sr.ok:
                    stage_artifacts.extend(sr.artifacts)
                    stage_summary = f"{stage_summary}; sandbox scaffold: {sr.summary}"
                    proj.metadata["sandbox_path"] = str(sb.work)
                else:
                    stage_summary = f"{stage_summary}; scaffold warn: {sr.error or sr.summary}"
            except Exception as e:
                stage_summary = f"{stage_summary}; scaffold error: {e}"

        # Closed-loop: when leaving SCAFFOLD, run local smoke on main.py
        if proj.stage == FactoryStage.SCAFFOLD:
            try:
                from levi.factory.sandbox import Sandbox
                sb = Sandbox(proj.id)
                smoke = sb.run_smoke(["status"])
                proj.metadata["last_smoke"] = {
                    "ok": smoke.get("ok"),
                    "returncode": smoke.get("returncode"),
                    "error": smoke.get("error"),
                    "stdout_head": (smoke.get("stdout") or "")[:200],
                }
                if smoke.get("ok"):
                    stage_summary = f"{stage_summary}; smoke ok"
                    stage_artifacts.append("smoke:ok")
                else:
                    stage_summary = f"{stage_summary}; smoke fail: {smoke.get('error') or smoke.get('stderr') or smoke.get('returncode')}"
                    stage_artifacts.append("smoke:fail")
            except Exception as e:
                stage_summary = f"{stage_summary}; smoke error: {e}"

        proj.history.append(StageResult(
            stage=proj.stage,
            status="ok",
            summary=stage_summary,
            artifacts=stage_artifacts,
        ))
        nxt = self._next_stage(proj.stage)
        if nxt is None or nxt == FactoryStage.COMPLETE:
            proj.stage = FactoryStage.COMPLETE
            proj.history.append(StageResult(
                stage=FactoryStage.COMPLETE,
                status="ok",
                summary="Pipeline complete (scaffold artifacts in sandbox when architecture advanced)",
            ))
        else:
            proj.stage = nxt
        proj.updated_at = datetime.now(timezone.utc).isoformat()
        proj.metadata["lwp"] = {
            "cascade_stage": proj.stage.value,
            "spiral_iteration": proj.iteration,
            "max_iterations": proj.max_iterations,
        }
        self._persist()
        return proj

    def run_smoke_test(self, project_id: str) -> Dict[str, Any]:
        """Execute sandbox main.py status — factory closed loop."""
        from levi.factory.sandbox import Sandbox
        proj = self.projects.get(project_id)
        if not proj:
            return {"ok": False, "error": "unknown project"}
        sb = Sandbox(project_id)
        result = sb.run_smoke(["status"])
        proj.metadata["last_smoke"] = {
            "ok": result.get("ok"),
            "returncode": result.get("returncode"),
            "error": result.get("error"),
            "stdout_head": (result.get("stdout") or "")[:200],
        }
        proj.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        return result

    def fail(self, project_id: str, error: str) -> FactoryProject:
        proj = self.projects[project_id]
        proj.history.append(StageResult(
            stage=proj.stage,
            status="fail",
            summary="Stage failed",
            error=error,
        ))
        proj.stage = FactoryStage.FAILED
        proj.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        return proj

    def get(self, project_id: str) -> Optional[FactoryProject]:
        return self.projects.get(project_id)

    def list(self) -> List[FactoryProject]:
        return sorted(self.projects.values(), key=lambda p: p.updated_at, reverse=True)

    def status(self) -> Dict[str, Any]:
        by_stage: Dict[str, int] = {}
        for p in self.projects.values():
            by_stage[p.stage.value] = by_stage.get(p.stage.value, 0) + 1
        return {
            "projects": len(self.projects),
            "by_stage": by_stage,
            "data_dir": str(self.data_dir),
            "note": "Foundation pipeline — full autonomous codegen requires model + sandbox + policy",
        }
