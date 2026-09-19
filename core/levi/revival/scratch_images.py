"""scratch_images — multi-stage builds and FROM-scratch image analysis.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md
[§4 — cited numbers].

Shape studied: multi-stage Docker builds with FROM-scratch final images —
the cited shape is a ~50x build speedup and ~86x size reduction (a 1.3GB
build image slimming to a ~15MB runtime image) when Docker is used.

Mechanism:
* parse(): a small, honest parser for a Dockerfile subset — FROM (with
  optional AS name), COPY --from=<stage>, and RUN. Anything else is
  ignored, not guessed at.
* analyze(): given base-image sizes and copied-artifact sizes, compute
  the naive single-stage size, the final multi-stage size, and the
  reduction factor. Sizes are *inputs*, not inventions.
* lint(): flags the classic waste patterns — single-stage builds, final
  stage not scratch/distroless/static, COPY --from an unknown stage,
  package-manager RUN lines in the final stage.
* speedup_notes(): where the ~50x-style speedups come from (layer cache
  reuse, parallel stages), as a checklist, not a promise.

Honest limits: the parser covers a documented subset; image and artifact
sizes must be supplied by the operator (from a real `docker images`
listing, for example). The famous 1.3GB → 15.5MB figures are cited as
the studied shape, not computed.

This is an original, from-scratch implementation for LEVI.
Not artificial. Synthetic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/scratch_images"

_FROM_RE = re.compile(r"^FROM\s+(\S+)(?:\s+AS\s+(\S+))?", re.IGNORECASE)
_COPY_FROM_RE = re.compile(r"^COPY\s+--from=(\S+)\s+(\S+)\s+(\S+)", re.IGNORECASE)

#: Final-stage bases considered minimal (no OS userland to pay for).
MINIMAL_BASES = {"scratch", "distroless", "distroless/static", "static", "alpine"}


@dataclass
class Stage:
    name: str
    base: str
    copies_from: List[str] = field(default_factory=list)
    run_lines: List[str] = field(default_factory=list)


@dataclass
class ImageModel:
    stages: List[Stage]
    final_stage: Stage


def parse(text: str) -> ImageModel:
    """Parse a Dockerfile subset into stages.

    Recognizes FROM (with optional AS), COPY --from=, and RUN. All other
    instructions are ignored. Raises ValueError on COPY --from an unknown
    stage name.
    """
    stages: List[Stage] = []
    by_name: Dict[str, Stage] = {}
    current: Optional[Stage] = None
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _FROM_RE.match(line)
        if m:
            base, alias = m.group(1), m.group(2)
            name = alias or f"stage{len(stages)}"
            current = Stage(name=name, base=base)
            stages.append(current)
            by_name[name.lower()] = current
            continue
        if current is None:
            raise ValueError(f"line {lineno}: instruction before any FROM")
        m = _COPY_FROM_RE.match(line)
        if m:
            src = m.group(1)
            if src.lower() not in by_name:
                raise ValueError(f"line {lineno}: COPY --from unknown stage {src!r}")
            current.copies_from.append(src)
            continue
        if line.upper().startswith("RUN"):
            current.run_lines.append(line)
    if not stages:
        raise ValueError("no FROM instruction found")
    return ImageModel(stages=stages, final_stage=stages[-1])


@dataclass
class ImageReport:
    stages: int
    final_base: str
    naive_mb: float
    final_mb: float

    @property
    def reduction_factor(self) -> float:
        if self.final_mb <= 0:
            return float("inf")
        return self.naive_mb / self.final_mb

    @property
    def saved_mb(self) -> float:
        return max(0.0, self.naive_mb - self.final_mb)

    def summary(self) -> str:
        return (
            f"{self.stages} stages, final base {self.final_base}: "
            f"{self.naive_mb:.1f}MB -> {self.final_mb:.1f}MB "
            f"({self.reduction_factor:.1f}x smaller)"
        )


def analyze(
    model: ImageModel,
    base_sizes_mb: Dict[str, float],
    artifact_sizes_mb: Optional[Dict[str, float]] = None,
) -> ImageReport:
    """Compute naive vs final image size from operator-supplied sizes.

    ``base_sizes_mb`` maps base image names to their size in MB;
    ``artifact_sizes_mb`` maps stage names to the MB of artifacts copied
    out of them (default 5MB per COPY --from when unspecified).
    """
    artifact_sizes_mb = artifact_sizes_mb or {}

    def base_size(base: str) -> float:
        key = base.lower()
        if key not in base_sizes_mb and key not in (k.lower() for k in base_sizes_mb):
            raise KeyError(f"no size supplied for base image {base!r}")
        for k, v in base_sizes_mb.items():
            if k.lower() == key:
                return v
        raise KeyError(f"no size supplied for base image {base!r}")  # pragma: no cover

    naive = max(base_size(s.base) for s in model.stages)
    final = base_size(model.final_stage.base)
    for src in model.final_stage.copies_from:
        final += artifact_sizes_mb.get(src, artifact_sizes_mb.get(src.lower(), 5.0))
    return ImageReport(
        stages=len(model.stages),
        final_base=model.final_stage.base,
        naive_mb=naive,
        final_mb=final,
    )


def lint(text: str) -> List[str]:
    """Flag classic image-waste patterns. Empty list means no findings."""
    findings: List[str] = []
    try:
        model = parse(text)
    except ValueError as exc:
        return [f"unparseable: {exc}"]
    if len(model.stages) == 1:
        findings.append("single-stage build: build tools ship in the final image")
    final_base = model.final_stage.base.lower()
    if not any(minimal in final_base for minimal in MINIMAL_BASES):
        findings.append(
            f"final stage FROM {model.final_stage.base}: not a minimal base "
            "(consider scratch/distroless/static)"
        )
    for i, line in enumerate(model.final_stage.run_lines, start=1):
        low = line.lower()
        if any(
            tool in low for tool in ("apt-get", "apk add", "yum install", "pip install")
        ):
            findings.append(
                f"final stage RUN #{i} installs packages — build them in an earlier stage"
            )
    return findings


def speedup_notes() -> List[str]:
    """Where multi-stage build speedups come from (checklist, not promise)."""
    return [
        "layer cache: unchanged early stages are never rebuilt",
        "parallel stages: independent build stages run concurrently",
        "smaller context: final image pushes/pulls less over the wire",
        "scratch final: nothing to scan, patch, or rebuild for CVEs in the base",
    ]
