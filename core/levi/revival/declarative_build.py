"""declarative_build — repeatable environments from a frozen description.

Studied from: revival-50-more-20260916-0009/report-part1.md [entry #11].

The studied shape: a whole environment (packages, files, variables) is
described declaratively, and a builder turns that description into the
same environment every time — repeatability by construction rather than
by luck. LEVI's version, ``SystemModel``:

* **Immutable manifests.** ``Package``, ``FileEntry``, and ``SystemModel``
  are frozen dataclasses: once declared, a manifest cannot drift.
  Editing means declaring a new manifest.
* **Planning.** ``plan(model)`` derives an ordered step list from the
  manifest: packages install in dependency order (topological sort,
  cycles are a hard error), then files are written, then environment
  variables are set.
* **Reproducible fingerprint.** ``fingerprint(model)`` hashes a
  canonical serialization of the manifest, so two runs of the same
  manifest — or a manifest fetched across machines — can be compared
  for equality with one string.
* **Simulated execution.** ``build(model)`` runs the plan against a
  pure-Python ``Sandbox`` (a dict-based filesystem + env table), so the
  whole thing is testable with no OS side effects. Real effects would be
  a new executor; the plan is the same either way.

Honest limits: this is a planning and fingerprinting engine, not an OS
package manager — it does not download or install anything, and the
sandbox is a simulation. Determinism is over the manifest, not over
third-party mirrors.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/declarative_build"


# ---------------------------------------------------------------------------
# Immutable manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Package:
    """One declared package: name, version pin, and its dependencies."""

    name: str
    version: str
    requires: Tuple[str, ...] = ()


@dataclass(frozen=True)
class FileEntry:
    """One declared file: absolute-ish path and exact content."""

    path: str
    content: str


@dataclass(frozen=True)
class SystemModel:
    """A frozen, whole-environment description."""

    name: str
    packages: Tuple[Package, ...] = ()
    files: Tuple[FileEntry, ...] = ()
    env: Tuple[Tuple[str, str], ...] = ()

    def with_package(self, pkg: Package) -> "SystemModel":
        return SystemModel(self.name, self.packages + (pkg,), self.files, self.env)

    def with_file(self, entry: FileEntry) -> "SystemModel":
        return SystemModel(self.name, self.packages, self.files + (entry,), self.env)

    def with_env(self, key: str, value: str) -> "SystemModel":
        return SystemModel(
            self.name, self.packages, self.files, self.env + ((key, value),)
        )


# ---------------------------------------------------------------------------
# Canonical form + fingerprint
# ---------------------------------------------------------------------------


def canonical(model: SystemModel) -> Dict:
    """Canonical JSON-able form: sorted, so fingerprints are order-free."""
    return {
        "name": model.name,
        "packages": sorted(
            (
                {"name": p.name, "version": p.version, "requires": sorted(p.requires)}
                for p in model.packages
            ),
            key=lambda d: d["name"],
        ),
        "files": sorted(
            ({"path": f.path, "content": f.content} for f in model.files),
            key=lambda d: d["path"],
        ),
        "env": sorted(
            ({"key": k, "value": v} for k, v in model.env), key=lambda d: d["key"]
        ),
    }


def fingerprint(model: SystemModel) -> str:
    """Deterministic SHA-256 over the canonical manifest (hex)."""
    blob = json.dumps(canonical(model), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Step:
    """One executable plan step."""

    kind: str  # "install" | "write" | "export"
    detail: str
    payload: Tuple = ()


def _install_order(packages: Tuple[Package, ...]) -> List[Package]:
    """Topological order over ``requires``; raises on cycles/unknown deps."""
    by_name = {p.name: p for p in packages}
    order: List[Package] = []
    state: Dict[str, str] = {}  # name -> "visiting" | "done"

    def visit(name: str) -> None:
        if name not in by_name:
            raise ValueError(f"unknown dependency {name!r}")
        mark = state.get(name)
        if mark == "done":
            return
        if mark == "visiting":
            raise ValueError(f"dependency cycle at {name!r}")
        state[name] = "visiting"
        for dep in by_name[name].requires:
            visit(dep)
        state[name] = "done"
        order.append(by_name[name])

    for pkg in packages:
        visit(pkg.name)
    return order


def plan(model: SystemModel) -> List[Step]:
    """Derive the build plan: installs (dependency order), then files, env."""
    steps = [
        Step("install", f"{p.name}=={p.version}", (p.name, p.version))
        for p in _install_order(model.packages)
    ]
    steps += [Step("write", f.path, (f.path, f.content)) for f in model.files]
    steps += [Step("export", f"{k}={v}", (k, v)) for k, v in model.env]
    return steps


# ---------------------------------------------------------------------------
# Simulated execution
# ---------------------------------------------------------------------------


@dataclass
class Sandbox:
    """A pure-Python stand-in for a machine: files + env, no real I/O."""

    files: Dict[str, str] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)
    installed: List[str] = field(default_factory=list)


def build(model: SystemModel, sandbox: Sandbox) -> Sandbox:
    """Run the plan against a sandbox. Returns the same sandbox, mutated."""
    for step in plan(model):
        if step.kind == "install":
            sandbox.installed.append(f"{step.payload[0]}=={step.payload[1]}")
        elif step.kind == "write":
            sandbox.files[step.payload[0]] = step.payload[1]
        elif step.kind == "export":
            sandbox.env[step.payload[0]] = step.payload[1]
    return sandbox


def diff(a: SystemModel, b: SystemModel) -> Dict[str, List[str]]:
    """Human-readable manifest diff: added/removed packages and files."""
    ap = {p.name: p.version for p in a.packages}
    bp = {p.name: p.version for p in b.packages}
    af = {f.path for f in a.files}
    bf = {f.path for f in b.files}
    return {
        "packages_added": sorted(f"{k}=={v}" for k, v in bp.items() if k not in ap),
        "packages_removed": sorted(f"{k}=={v}" for k, v in ap.items() if k not in bp),
        "packages_changed": sorted(
            f"{k}: {ap[k]} -> {bp[k]}" for k in ap.keys() & bp.keys() if ap[k] != bp[k]
        ),
        "files_added": sorted(bf - af),
        "files_removed": sorted(af - bf),
    }
