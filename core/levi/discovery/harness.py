"""The discovery harness: run probe packs against in-repo targets.

Targets are in-repo only:

- ``operators`` — every operator in the registry, or a subset via
  ``operators:local,nano-bit``. Labels are ``op:<name>``.
- ``pack:<name>`` — a genesis/legion pack dict registered with
  :meth:`DiscoveryHarness.register_pack`. Labels are ``pack:<name>``.
- ``dw:<hex>`` — a dynasty wave agent addressed by anonymized label
  ONLY, resolved through an injected callable registered with
  :meth:`DiscoveryHarness.register_dynasty_target`. The harness ships
  no name mapping; labels are hashes, never raw names.

All probing is in-process, stdlib only, no network. A probe that
declares ``needs_network=True`` is REFUSED before running —
fail-closed — and the refusal is recorded on the report. The harness
itself performs no network I/O: the only writes are the local
findings JSONL log.

Chauncey's sanction ("try it anyway and find things even the
creators weren't fully aware of") covers HIS OWN systems. Probes are
defensive self-tests (purple-team vs. own systems, blue-team
posture). Third-party models/services/sites are never targets.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .findings import FindingsLog, is_anonymized_label
from .probes import (
    Probe,
    ProbeOutcome,
    ProbeTarget,
    get_pack,
    list_packs,
)

__all__ = [
    "DiscoveryError",
    "DiscoveryHarness",
    "DiscoveryReport",
]

#: Dynasty labels are hex digests only — never raw names.
_DYNASTY_LABEL_RE = re.compile(r"^dw:[0-9a-f]{8,64}$")


class DiscoveryError(Exception):
    """The harness refused to run (unknown pack/target, bad label)."""


@dataclass
class DiscoveryReport:
    """The complete record of one harness run."""

    pack_name: str
    target_labels: List[str]
    seed: int
    started_at: str
    ended_at: str = ""
    outcomes: List[Dict[str, Any]] = field(default_factory=list)
    network_refusals: List[Dict[str, Any]] = field(default_factory=list)
    skips: List[Dict[str, Any]] = field(default_factory=list)
    finding_ids: List[str] = field(default_factory=list)
    errors: int = 0

    @property
    def n_probes(self) -> int:
        return len(self.outcomes)

    @property
    def n_passed(self) -> int:
        return sum(1 for o in self.outcomes if o.get("passed"))

    @property
    def n_beyond_scope(self) -> int:
        return sum(1 for o in self.outcomes if o.get("beyond_scope"))

    def summary(self) -> str:
        return (
            f"discovery run pack={self.pack_name} "
            f"targets={len(self.target_labels)} "
            f"outcomes={self.n_probes} passed={self.n_passed} "
            f"beyond_scope={self.n_beyond_scope} "
            f"net_refusals={len(self.network_refusals)} "
            f"skips={len(self.skips)} findings={len(self.finding_ids)} "
            f"errors={self.errors}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pack_name": self.pack_name,
            "target_labels": list(self.target_labels),
            "seed": self.seed,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "outcomes": list(self.outcomes),
            "network_refusals": list(self.network_refusals),
            "skips": list(self.skips),
            "finding_ids": list(self.finding_ids),
            "errors": self.errors,
            "summary": self.summary(),
        }


class DiscoveryHarness:
    """Run probe packs against in-repo targets, in-process, no network."""

    def __init__(
        self,
        *,
        registry: Any = None,
        findings_path: Optional[Path] = None,
        seed: int = 1337,
        record_findings: bool = True,
    ) -> None:
        if registry is None:
            from levi.operator.registry import default_registry

            registry = default_registry()
        self.registry = registry
        self.log = FindingsLog(findings_path)
        self.seed = int(seed)
        self.record_findings = bool(record_findings)
        self._probe_packs: Dict[str, List[Probe]] = {}
        self._pack_targets: Dict[str, Dict[str, Any]] = {}
        self._dynasty: Dict[str, Callable[..., Any]] = {}

    # -- registration -----------------------------------------------------

    def register_probe(self, pack_name: str, probe: Probe) -> Probe:
        """Add a probe to a pack (custom packs allowed)."""
        if not isinstance(probe, Probe):
            raise DiscoveryError(
                f"register_probe needs a Probe, got {type(probe).__name__}"
            )
        self._probe_packs.setdefault(pack_name, []).append(probe)
        return probe

    def register_pack(self, name: str, pack_dict: Dict[str, Any]) -> str:
        """Register a genesis/legion pack dict as a probe target."""
        if not re.match(r"^[A-Za-z0-9_.\-]{1,64}$", name or ""):
            raise DiscoveryError(
                f"pack target name must be anonymized-safe; got {name!r}"
            )
        if not isinstance(pack_dict, dict):
            raise DiscoveryError("pack target must be a dict")
        label = f"pack:{name}"
        self._pack_targets[label] = pack_dict
        return label

    def register_dynasty_target(
        self, label: str, fn: Callable[..., Any]
    ) -> str:
        """Register a dynasty wave agent by ANONYMIZED label only.

        ``fn`` takes prompt text and returns a result with ``.text``
        and ``.finish_reason``. Raw names are refused here —
        fail-closed — so they can never reach the findings log.
        """
        if not _DYNASTY_LABEL_RE.match(label or ""):
            raise DiscoveryError(
                "dynasty targets require an anonymized label "
                f"(dw:<hex>); got {label!r}"
            )
        if not callable(fn):
            raise DiscoveryError("dynasty target needs a callable")
        self._dynasty[label] = fn
        return label

    # -- target resolution --------------------------------------------------

    def _operator_targets(self, names: Optional[List[str]]) -> List[ProbeTarget]:
        infos = {
            d["name"]: d for d in self.registry.list_operators()
        }
        wanted = names if names else sorted(infos)
        targets = []
        for name in wanted:
            if name not in infos:
                raise DiscoveryError(f"unknown operator target {name!r}")
            targets.append(
                ProbeTarget(
                    kind="operator",
                    label=f"op:{name}",
                    ref=self.registry.resolve(name),
                )
            )
        return targets

    def resolve_targets(self, specs: List[str]) -> List[ProbeTarget]:
        """Resolve target specs to :class:`ProbeTarget` list.

        Specs: ``"operators"``, ``"operators:a,b"``, ``"pack:<name>"``,
        ``"dw:<hex>"``. Unknown specs raise :class:`DiscoveryError`
        (explicit, never silently skipped).
        """
        targets: List[ProbeTarget] = []
        for spec in specs:
            spec = (spec or "").strip()
            if spec == "operators":
                targets.extend(self._operator_targets(None))
            elif spec.startswith("operators:"):
                names = [n.strip() for n in spec.split(":", 1)[1].split(",") if n.strip()]
                if not names:
                    raise DiscoveryError("operators: needs at least one name")
                targets.extend(self._operator_targets(names))
            elif spec.startswith("pack:"):
                label = spec
                if label not in self._pack_targets:
                    raise DiscoveryError(
                        f"unknown pack target {spec!r}; register it with "
                        "register_pack() first"
                    )
                targets.append(
                    ProbeTarget(kind="pack", label=label, ref=self._pack_targets[label])
                )
            elif spec.startswith("dw:"):
                if spec not in self._dynasty:
                    raise DiscoveryError(
                        f"unknown dynasty target {spec!r}; register it with "
                        "register_dynasty_target() first"
                    )
                targets.append(
                    ProbeTarget(kind="dynasty", label=spec, ref=self._dynasty[spec])
                )
            else:
                raise DiscoveryError(
                    f"unknown target spec {spec!r}; use 'operators', "
                    "'operators:<names>', 'pack:<name>', or 'dw:<hex>'"
                )
        if not targets:
            raise DiscoveryError("no targets resolved")
        return targets

    def _probes_for(self, pack_name: str) -> List[Probe]:
        if pack_name in self._probe_packs:
            return list(self._probe_packs[pack_name])
        try:
            return get_pack(pack_name)
        except KeyError as exc:
            raise DiscoveryError(str(exc)) from None

    # -- the run --------------------------------------------------------------

    def run(self, pack_name: str, targets: List[str]) -> DiscoveryReport:
        """Run one probe pack against the given target specs.

        Network-declaring probes are refused BEFORE running
        (fail-closed); the refusal is recorded on the report and the
        probe body never executes. Probe crashes become well-formed
        ERROR outcomes, never raised exceptions.
        """
        probes = self._probes_for(pack_name)
        resolved = self.resolve_targets(targets)
        report = DiscoveryReport(
            pack_name=pack_name,
            target_labels=[t.label for t in resolved],
            seed=self.seed,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        run_index = 0
        for probe in probes:
            for target in resolved:
                run_index += 1
                # -- fail-closed: network need refused before running ----
                if probe.needs_network:
                    report.network_refusals.append(
                        {
                            "probe_id": probe.id,
                            "target_label": target.label,
                            "reason": (
                                "probe declares needs_network=True; refused "
                                "before running (harness performs no network I/O)"
                            ),
                        }
                    )
                    continue
                if target.kind not in probe.target_kinds:
                    report.skips.append(
                        {
                            "probe_id": probe.id,
                            "target_label": target.label,
                            "reason": (
                                f"probe targets {probe.target_kinds}; "
                                f"target is {target.kind!r}"
                            ),
                        }
                    )
                    continue
                ctx = {
                    "seed": self.seed,
                    "run_index": run_index,
                    "registry": self.registry,
                    "operator_targets": [
                        t for t in resolved if t.kind == "operator"
                    ],
                }
                try:
                    outcome = probe.run(target, ctx)
                    if not isinstance(outcome, ProbeOutcome):
                        outcome = ProbeOutcome(
                            probe_id=probe.id,
                            target_label=target.label,
                            passed=False,
                            observation=(
                                "probe violated the probe contract: run() "
                                f"returned {type(outcome).__name__}, not ProbeOutcome"
                            ),
                            error="probe contract violation",
                        )
                except Exception as exc:  # noqa: BLE001 — probes never raise
                    outcome = ProbeOutcome(
                        probe_id=probe.id,
                        target_label=target.label,
                        passed=False,
                        observation=(
                            f"probe raised {type(exc).__name__}: {exc}"
                        ),
                        error=f"{type(exc).__name__}: {exc}",
                    )
                if outcome.error:
                    report.errors += 1
                report.outcomes.append(outcome.to_dict())
                # -- findings ------------------------------------------------
                if self.record_findings and probe.noteworthy(outcome):
                    if not is_anonymized_label(target.label):
                        # Structural guarantee: findings only ever carry
                        # anonymized labels. This cannot happen via
                        # resolve_targets, but fail closed anyway.
                        raise DiscoveryError(
                            f"refusing to record finding for non-anonymized "
                            f"label {target.label!r}"
                        )
                    significance = probe.finding_significance(outcome)
                    detail = (
                        f"{outcome.observation} "
                        f"[detail: {outcome.detail}]"
                        if outcome.detail
                        else outcome.observation
                    )
                    if outcome.error:
                        detail += f" [probe error: {outcome.error}]"
                    disc = self.log.record(
                        target_label=target.label,
                        probe=probe.id,
                        observation=detail,
                        repro_steps=probe.repro_steps(target),
                        significance=significance,
                    )
                    report.finding_ids.append(disc.id)
        report.ended_at = datetime.now(timezone.utc).isoformat()
        return report

    # -- introspection ----------------------------------------------------------

    def available_packs(self) -> List[str]:
        return sorted(set(list_packs()) | set(self._probe_packs))
