"""
E3–E6 Emergency-style Builder

Tiered authority for scaffolding, upgrading, and improving source —
for LEVI itself *or* independent projects.

E3  Stabilize / patch   — local docs, tests, non-breaking refactors (low HITL)
E4  Scaffold skeleton   — new module/project tree, no production deploy
E5  MVP vertical        — working slice; HITL before merge to main product path
E6  Product uplift      — architecture/source upgrades spanning subsystems; hard HITL

All tiers:
  - Plan first (always)
  - Write only under explicit --apply after HITL when required
  - Never silent production deploy, DNS, payment, or customer contact
  - Free-first / local artifacts under target directory

This is the "builder that can improve the whole system's source code
and other independent projects from skeleton → MVP → final product."
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
from enum import Enum
import json
import os
import re
import uuid


# Reused for names coming back out of persisted state: a hand-edited
# emergency_builder.json must not be able to smuggle a path traversal
# into the workspace layout.
_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]+")


class BuildTier(str, Enum):
    E3 = "E3"  # stabilize
    E4 = "E4"  # scaffold
    E5 = "E5"  # mvp
    E6 = "E6"  # product uplift


TIER_META = {
    BuildTier.E3: {
        "name": "Stabilize / patch",
        "risk": "LOW",
        "hitl_default": False,
        "desc": "Docs, tests, non-breaking fixes, status reports",
    },
    BuildTier.E4: {
        "name": "Scaffold skeleton",
        "risk": "LOW",
        "hitl_default": False,
        "desc": "New project/module tree, README, package layout — no deploy",
    },
    BuildTier.E5: {
        "name": "MVP vertical",
        "risk": "MEDIUM",
        "hitl_default": True,
        "desc": "Working end-to-end slice; HITL before treating as product path",
    },
    BuildTier.E6: {
        "name": "Product uplift",
        "risk": "HIGH",
        "hitl_default": True,
        "desc": "Cross-subsystem source upgrades; hard HITL + explicit apply",
    },
}


STAGES = [
    "skeleton",  # folders + README
    "scaffold",  # modules stubs
    "mvp",  # minimal working path
    "harden",  # tests + policy
    "product",  # package + handoff
]


def _sanitize_name(name: str) -> str:
    """Filesystem-safe project name; never empty, never a path."""
    return _SAFE_NAME_RE.sub("_", str(name or "")).strip("_") or "new_project"


def _package_name(name: str) -> str:
    """Import-safe package name derived from the project name.

    The project name may contain hyphens (valid in project titles and in
    ``pyproject.toml``), but hyphens are NOT valid in Python identifiers:
    ``src/my-app/`` can never be imported and ``from my-app import x`` is
    a SyntaxError. The package directory and every import in generated
    code use this form; the human-readable name stays on the README,
    ``pyproject.toml`` project name, and status strings.
    """
    return _sanitize_name(name).replace("-", "_")


def _goal_literal(goal: str, limit: int) -> str:
    """Python string literal for embedding a goal in generated code.

    Uses json.dumps so quotes/backslashes/newlines in the goal cannot
    break out of the literal and inject code into the generated file.
    """
    return json.dumps(str(goal or "")[:limit])


def _goal_toml(goal: str, limit: int) -> str:
    """TOML basic-string literal for the goal (same escaping rationale)."""
    return json.dumps(str(goal or "")[:limit].replace("\n", " "))


@dataclass
class BuildJob:
    id: str
    tier: str
    target: str  # "levi" | independent project name
    goal: str
    stage: str = "skeleton"
    status: str = "planned"  # planned | awaiting_hitl | applied | rejected
    artifacts: List[str] = field(default_factory=list)
    plan_steps: List[str] = field(default_factory=list)
    requires_hitl: bool = False
    hitl_id: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EmergencyBuilder:
    def __init__(self, workspace: Optional[Path] = None):
        self.workspace = (
            Path(workspace)
            if workspace
            else Path.home() / ".levi" / "builder_workspace"
        )
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.state_path = Path.home() / ".levi" / "emergency_builder.json"
        self.jobs: List[BuildJob] = []
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.jobs = []
            for j in raw.get("jobs") or []:
                self.jobs.append(
                    BuildJob(
                        **{
                            k: v
                            for k, v in j.items()
                            if k in BuildJob.__dataclass_fields__
                        }
                    )
                )
        except Exception:
            pass

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "jobs": [j.to_dict() for j in self.jobs[-50:]],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        # Atomic + owner-only: job goals are the user's raw plans.
        tmp = self.state_path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
        except BaseException:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
        os.replace(tmp, self.state_path)

    def plan(
        self,
        goal: str,
        tier: str = "E4",
        target: str = "independent",
        project_name: str = "new_project",
    ) -> BuildJob:
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError("goal must be a non-empty string")
        if not isinstance(project_name, str) or not project_name.strip():
            raise ValueError("project_name must be a non-empty string")
        if not isinstance(tier, str):
            raise ValueError("tier must be one of E3, E4, E5, E6")
        # No silent coercion: an unknown tier is a caller bug, not a guess.
        # (Previously "X9" silently became E4.)
        t_name = tier.strip().upper()
        if t_name not in BuildTier.__members__:
            raise ValueError(f"tier must be one of E3, E4, E5, E6 (got {tier!r})")
        t = BuildTier[t_name]
        meta = TIER_META[t]
        safe_name = _sanitize_name(project_name)
        steps = [
            f"Tier {t.value}: {meta['name']} — {meta['desc']}",
            f"Target: {target} / {safe_name}",
            f"Goal: {goal}",
            "1) Write plan receipt (this job)",
        ]
        if t is BuildTier.E3:
            # Stabilize / patch works on the EXISTING target: patch kit, not
            # a new project scaffold.
            steps += [
                "2) Write PATCH_PLAN.md (scope: docs, tests, non-breaking refactors)",
                "3) Scaffold docs/ notes + tests/ for the stabilization work",
                "4) No new package: patch kit for the existing target",
                "5) Register capability log entry",
                "6) HITL before any claim of production-ready or self-merge into LEVI core",
            ]
        else:
            steps += [
                "2) Create skeleton under builder_workspace (if apply)",
                "3) Scaffold module stubs + README",
                "4) Optional MVP stub entrypoint",
                "5) Register capability log entry",
                "6) HITL before any claim of production-ready or self-merge into LEVI core",
            ]
        if t in (BuildTier.E5, BuildTier.E6):
            steps.append(
                "7) Hard HITL: source upgrade / product path requires explicit APPROVE + --apply"
            )
        job = BuildJob(
            id=str(uuid.uuid4())[:8],
            tier=t.value,
            target=f"{target}:{safe_name}",
            goal=goal,
            stage="skeleton",
            status="planned",
            plan_steps=steps,
            requires_hitl=bool(meta["hitl_default"]),
        )
        if job.requires_hitl:
            try:
                from levi.project.hitl import HITLGate

                req = HITLGate().propose(
                    what=f"Emergency Builder {job.tier} apply for {job.target}: {goal[:100]}",
                    why="Source scaffold/upgrade can change system or project code",
                    changes=f"Write under {self.workspace / safe_name} only unless further approved",
                    risk=meta["risk"],
                    domain="builder",
                    cost="$0",
                    benefit="Controlled path from skeleton → MVP → product",
                    if_approved="Run builder --apply with this job id",
                    if_denied="Remain plan-only",
                )
                job.hitl_id = req.id
                job.status = "awaiting_hitl"
            except Exception:
                job.status = "awaiting_hitl"
        self.jobs.append(job)
        self._persist()
        return job

    def apply(self, job_id: str, force: bool = False) -> str:
        job = next((j for j in self.jobs if j.id == job_id), None)
        if not job:
            return f"No job {job_id}"
        if job.requires_hitl and not force:
            # Hard gate: the HITL request must exist AND be approved in
            # history. A missing/empty hitl_id (e.g. propose() threw during
            # plan) is treated as NOT approved — never as a silent pass.
            approved = False
            try:
                from levi.project.hitl import HITLGate

                g = HITLGate()
                # if still pending, block
                if job.hitl_id and job.hitl_id in g.pending:
                    return (
                        f"HITL still pending ({job.hitl_id}). "
                        f"Approve: levi project hitl --approve {job.hitl_id} then re-apply."
                    )
                approved = bool(job.hitl_id) and any(
                    h.id == job.hitl_id and h.status == "approved" for h in g.history
                )
            except Exception as e:
                return f"HITL check failed: {e}"
            if not approved:
                return (
                    f"HITL not approved for {job.hitl_id or 'unknown request'} — "
                    "refusing to apply"
                )

        # Re-sanitize: job.target comes from persisted JSON, which may have
        # been hand-edited. The name must never be a path.
        name = _sanitize_name(job.target.split(":")[-1])
        pkg = _package_name(name)
        root = self.workspace / name
        root.mkdir(parents=True, exist_ok=True)

        if job.tier == "E3":
            # Stabilize / patch: a patch kit for the EXISTING target, not a
            # new project scaffold. Scope per the tier contract: local docs,
            # tests, non-breaking refactors.
            artifacts = self._apply_stabilize_kit(job, name, root)
            job.stage = "stabilize"
        else:
            artifacts = self._apply_scaffold(job, name, pkg, root)
            job.stage = "scaffold" if job.tier == "E4" else "mvp"

        job.artifacts = artifacts
        job.status = "applied"
        self._persist()
        job.status = "applied"
        self._persist()

        smoke_note = ""
        try:
            from levi.factory.sandbox import run_smoke

            smoke_note = run_smoke(root)
            job.artifacts.append(
                "sandbox:" + ("ok" if "fail" not in smoke_note.lower() else "issues")
            )
            self._persist()
        except Exception as e:
            smoke_note = f"sandbox skip: {e}"

        try:
            from levi.project.capability_log import CapabilityLog

            CapabilityLog().log(
                task=f"emergency_builder {job.tier} {name}",
                result="completed",
                tools=["builder.emergency"],
                future_skill="EMERGENCY_BUILDER",
                human_required=job.requires_hitl,
                output_summary=str(root),
            )
        except Exception:
            pass

        lines = [
            f"Applied job {job.id} ({job.tier}) → {root}",
            "Artifacts:",
        ]
        for a in artifacts:
            lines.append(f"  · {a}")
        lines.append("")
        lines.append(
            "E5/E6 product claims still require governance — scaffold ≠ final product."
        )
        if smoke_note:
            lines.append("")
            lines.append("--- Sandbox ---")
            lines.append(smoke_note[:800])
        return "\n".join(lines)

    def _apply_stabilize_kit(self, job: BuildJob, name: str, root: Path) -> List[str]:
        """E3 apply: a patch kit for the EXISTING target.

        Scope per the tier contract: local docs, tests, non-breaking
        refactors. Deliberately NOT a new importable package — E3 does not
        scaffold; the target already exists.
        """
        artifacts = []

        readme = root / "README.md"
        readme.write_text(
            f"# {name} — stabilization workspace\n\n"
            f"**Builder tier:** E3 (Stabilize / patch)\n"
            f"**Target:** {job.target}\n"
            f"**Goal:** {job.goal}\n"
            f"**Job:** {job.id}\n"
            f"**Created:** {job.created_at}\n\n"
            "Scope: local docs, tests, non-breaking refactors of the existing target.\n"
            "This is a patch kit, not a new project scaffold.\n",
            encoding="utf-8",
        )
        artifacts.append(str(readme))

        plan = root / "PATCH_PLAN.md"
        plan.write_text(
            f"# Patch plan — {name}\n\n"
            f"Goal: {job.goal}\n\n"
            "## Scope (E3: stabilize / patch)\n"
            "- Local docs: update under docs/\n"
            "- Tests: add or extend under tests/\n"
            "- Non-breaking refactors only\n\n"
            "## Non-goals\n"
            "- No new features\n"
            "- No API changes\n"
            "- No deploys, DNS, payments, or customer contact\n",
            encoding="utf-8",
        )
        artifacts.append(str(plan))

        docs = root / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        notes = docs / "NOTES.md"
        notes.write_text(
            f"# Stabilization notes — {name}\n\n"
            f"Goal: {job.goal}\n\n"
            "_Record what was stabilized here._\n",
            encoding="utf-8",
        )
        artifacts.append(str(notes))

        tests = root / "tests"
        tests.mkdir(parents=True, exist_ok=True)
        test_f = tests / "test_smoke.py"
        test_f.write_text(
            "from pathlib import Path\n"
            "\n"
            "def test_patch_plan_present():\n"
            "    p = Path(__file__).resolve().parents[1] / 'PATCH_PLAN.md'\n"
            "    assert p.is_file() and p.read_text(encoding='utf-8').strip()\n"
            "\n"
            "def test_docs_present():\n"
            "    d = Path(__file__).resolve().parents[1] / 'docs'\n"
            "    assert d.is_dir() and any(d.iterdir())\n",
            encoding="utf-8",
        )
        artifacts.append(str(test_f))

        handoff = root / "HANDOFF.md"
        handoff.write_text(
            f"# Handoff — {name} (E3 stabilize)\n\n"
            f"Goal: {job.goal}\n"
            f"Tier: E3 job={job.id}\n\n"
            "Next: apply the patch plan against the real target (docs, tests,\n"
            "non-breaking refactors), then re-verify the target's own suite.\n",
            encoding="utf-8",
        )
        artifacts.append(str(handoff))
        return artifacts

    def _apply_scaffold(
        self, job: BuildJob, name: str, pkg: str, root: Path
    ) -> List[str]:
        """E4/E5/E6 apply: scaffold a new project tree.

        ``name`` is the human-readable project name (README, pyproject
        project name, status strings). ``pkg`` is the import-safe package
        name (``src/<pkg>/``, every import, ``python -m <pkg>.main``) —
        hyphens in ``name`` must never leak into Python identifiers.
        """
        artifacts = []

        # Skeleton
        readme = root / "README.md"
        readme.write_text(
            f"# {name}\n\n"
            f"**Builder tier:** {job.tier}\n"
            f"**Goal:** {job.goal}\n"
            f"**Job:** {job.id}\n"
            f"**Created:** {job.created_at}\n\n"
            f"Generated by LEVI Emergency Builder (closed-source kernel).\n"
            f"Stages: {' → '.join(STAGES)}\n\n"
            f"## Status\nScaffold applied. Not production until E5/E6 HITL path completes.\n",
            encoding="utf-8",
        )
        artifacts.append(str(readme))

        pkgdir = root / "src" / pkg
        pkgdir.mkdir(parents=True, exist_ok=True)
        init = pkgdir / "__init__.py"
        init.write_text(
            f'"""{name} — scaffolded by LEVI Emergency Builder."""\n__version__ = "0.0.1"\n',
            encoding="utf-8",
        )
        artifacts.append(str(init))

        main = pkgdir / "main.py"
        # The goal is embedded via json-escaped literals so quotes / newlines /
        # backslashes in it cannot break the generated code (code injection).
        goal_lit = _goal_literal(job.goal, 60)
        if job.tier in ("E5", "E6"):
            main.write_text(
                f'"""{name} — MVP entrypoint (LEVI Emergency Builder {job.tier})."""\n'
                f"from __future__ import annotations\n\n"
                f"def status() -> str:\n"
                f"    return {name!r} + ' MVP OK — tier {job.tier} — goal: ' + {goal_lit}\n\n"
                f"def main(argv: list | None = None) -> int:\n"
                f"    import sys\n"
                f"    args = list(argv or sys.argv[1:])\n"
                f'    if args and args[0] in ("status", "--status"):\n'
                f"        print(status())\n"
                f"        return 0\n"
                f"    print(status())\n"
                f'    print("Usage: python -m {pkg}.main status")\n'
                f"    return 0\n\n"
                f'if __name__ == "__main__":\n'
                f"    raise SystemExit(main())\n",
                encoding="utf-8",
            )
        else:
            main.write_text(
                f'"""{name} — entrypoint stub (LEVI Emergency Builder)."""\n'
                f"def status() -> str:\n"
                f"    return {name!r} + ' scaffold OK — tier {job.tier}'\n\n"
                f"def main():\n"
                f"    print(status())\n"
                f"\n"
                f'if __name__ == "__main__":\n'
                f"    main()\n",
                encoding="utf-8",
            )
        artifacts.append(str(main))

        # pyproject for runnable package (goal escaped as a TOML string)
        pyproject = root / "pyproject.toml"
        pyproject.write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
            f"description = {_goal_toml(job.goal, 80)}\n"
            f'requires-python = ">=3.10"\n\n'
            f'[tool.setuptools.packages.find]\nwhere = ["src"]\n',
            encoding="utf-8",
        )
        artifacts.append(str(pyproject))

        tests = root / "tests"
        tests.mkdir(parents=True, exist_ok=True)
        test_f = tests / "test_smoke.py"
        test_f.write_text(
            f"def test_import():\n"
            f"    from {pkg} import __version__\n"
            f"    assert __version__\n\n"
            f"def test_status():\n"
            f"    from {pkg}.main import status\n"
            f"    s = status()\n"
            f"    assert {name!r} in s and 'OK' in s\n",
            encoding="utf-8",
        )
        artifacts.append(str(test_f))

        # handoff note
        handoff = root / "HANDOFF.md"
        handoff.write_text(
            f"# Handoff — {name}\n\n"
            f"Goal: {job.goal}\n"
            f"Tier: {job.tier} job={job.id}\n\n"
            f"Next: implement MVP vertical, then harden, then product package.\n"
            f"Independent of LEVI core unless target was levi (still isolated under workspace).\n",
            encoding="utf-8",
        )
        artifacts.append(str(handoff))
        return artifacts

    def format_job(self, job: BuildJob) -> str:
        lines = [
            f"=== Emergency Builder Job [{job.id}] ===",
            f"Tier: {job.tier}  status={job.status}  stage={job.stage}",
            f"Target: {job.target}",
            f"Goal: {job.goal}",
            f"HITL required: {job.requires_hitl}  hitl_id={job.hitl_id or '—'}",
            "",
            "Plan:",
        ]
        for s in job.plan_steps:
            lines.append(f"  · {s}")
        if job.artifacts:
            lines.append("Artifacts:")
            for a in job.artifacts:
                lines.append(f"  · {a}")
        return "\n".join(lines)

    def format_status(self) -> str:
        lines = [
            "=== LEVI Emergency Builder (E3–E6) ===",
            f"Workspace: {self.workspace}",
            "",
            "E3 Stabilize · E4 Scaffold · E5 MVP (HITL) · E6 Product uplift (HITL)",
            "Can target LEVI improvements *or* independent projects.",
            "Skeleton → scaffold → MVP → harden → product — under gates.",
            "",
        ]
        for j in self.jobs[-8:]:
            lines.append(f"  [{j.id}] {j.tier} {j.status:14} {j.target}: {j.goal[:40]}")
        if not self.jobs:
            lines.append(
                '  (no jobs — levi builder --plan "…" --tier E4 --name my_app)'
            )
        return "\n".join(lines)
