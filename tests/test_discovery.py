"""Tests for the discovery harness (levi.discovery).

Hermetic and fast: stub operators for mechanics, the real
default_registry() only for integration probes (deterministic,
in-process, no network).

Covers:
(a) harness mechanics: probe runs produce well-formed outcomes and
    findings with repro steps;
(b) fail-closed: a network-declaring probe is refused before running
    (tripwire proves its body never executed);
(c) anonymity: the findings log refuses raw (non-anonymized) labels;
    dynasty targets only accept dw:<hex> labels;
(d) pack targets: shape discovery + the genesis odd-count law probe;
(e) regression tests for notable/significant findings from the live
    run against the built-in operators (2026-09-18).

Run:  python3 -m pytest tests/test_discovery.py -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

import pytest  # noqa: E402

from levi.discovery import (  # noqa: E402
    DiscoveryError,
    DiscoveryHarness,
    FindingsLog,
    Probe,
    ProbeOutcome,
    ProbeTarget,
    get_pack,
    is_anonymized_label,
    list_packs,
)
from levi.discovery import __main__ as discovery_cli  # noqa: E402
from levi.discovery.probes import (  # noqa: E402
    NET_PROBE_FIRED,
    reset_net_probe_tripwire,
)
import levi.discovery.probes as probes_mod  # noqa: E402
from levi.operator import (  # noqa: E402
    NATIVE,
    Operator,
    OperatorCapabilities,
    OperatorHealth,
    OperatorResult,
)
from levi.operator.registry import OperatorRegistry  # noqa: E402


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class StubOperator(Operator):
    """Deterministic stub: replies with canned text, never raises."""

    name = "stub"
    kind = NATIVE
    version = "0.0.1"
    lineage = "test:stub"

    def __init__(
        self,
        name: str = "stub",
        reply: str = "stub reply",
        finish_reason: str = "stop",
    ) -> None:
        self.name = name
        self._reply = reply
        self._finish = finish_reason

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(tools=(), context_window=1024)

    def step(
        self,
        messages: List[Any],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        return OperatorResult(
            text=self._reply,
            operator=self.name,
            kind=self.kind,
            finish_reason=self._finish,  # type: ignore[arg-type]
        )

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=True, note="stub healthy")


def _stub_registry(*names: str) -> OperatorRegistry:
    reg = OperatorRegistry()
    for n in names:
        reg.register(n, StubOperator(name=n), replace=True)
    return reg


def _harness(tmp_path: Path, *names: str, **kw: Any) -> DiscoveryHarness:
    return DiscoveryHarness(
        registry=_stub_registry(*names or ("stub-a", "stub-b")),
        findings_path=tmp_path / "findings.jsonl",
        seed=7,
        **kw,
    )


# ---------------------------------------------------------------------------
# (a) mechanics
# ---------------------------------------------------------------------------


def test_run_produces_wellformed_outcomes(tmp_path: Path) -> None:
    h = _harness(tmp_path, record_findings=False)
    report = h.run("curiosity", ["operators:stub-a"])
    assert report.outcomes, "expected outcomes"
    for o in report.outcomes:
        assert o["probe_id"].startswith("curiosity/")
        assert o["target_label"] == "op:stub-a"
        assert isinstance(o["passed"], bool)
        assert o["observation"].strip(), "observation must be non-empty"


def test_findings_recorded_with_repro_steps(tmp_path: Path) -> None:
    h = _harness(tmp_path)
    report = h.run("curiosity", ["operators:stub-a"])
    assert report.finding_ids, "curiosity probes always_record: expect findings"
    items = h.log.list()
    assert len(items) == len(report.finding_ids)
    for d in items:
        assert d.target_label == "op:stub-a"
        assert d.probe.startswith("curiosity/")
        assert d.repro_steps, "repro steps required"
        assert d.probe.split("/", 1)[1] in d.repro_steps
        assert d.significance in ("curiosity", "notable", "significant")


def test_unknown_pack_and_target_raise(tmp_path: Path) -> None:
    h = _harness(tmp_path, record_findings=False)
    with pytest.raises(DiscoveryError):
        h.run("no-such-pack", ["operators:stub-a"])
    with pytest.raises(DiscoveryError):
        h.run("curiosity", ["operators:nope"])
    with pytest.raises(DiscoveryError):
        h.run("curiosity", ["pack:never-registered"])


def test_probe_crash_becomes_error_outcome(tmp_path: Path) -> None:
    class Boom(Probe):
        id = "custom/boom"
        pack = "custom"

        def run(self, target: ProbeTarget, ctx: Dict[str, Any]) -> ProbeOutcome:
            raise RuntimeError("boom")

    h = _harness(tmp_path, "stub-a")
    h.register_probe("custom", Boom())
    report = h.run("custom", ["operators:stub-a"])
    assert report.errors == 1
    assert report.outcomes[0]["passed"] is False
    assert "boom" in (report.outcomes[0]["error"] or "")
    # the crash itself is noteworthy -> a finding with the error attached
    assert report.finding_ids


# ---------------------------------------------------------------------------
# (b) fail-closed: network-declaring probes never run
# ---------------------------------------------------------------------------


def test_network_probe_refused_fail_closed(tmp_path: Path) -> None:
    reset_net_probe_tripwire()
    h = _harness(tmp_path, "stub-a")
    report = h.run("edges", ["operators:stub-a"])
    refusals = [
        r for r in report.network_refusals
        if r["probe_id"] == "edges/net-declared-refused"
    ]
    assert refusals, "expected a recorded network refusal"
    assert refusals[0]["target_label"] == "op:stub-a"
    assert not probes_mod.NET_PROBE_FIRED, (
        "FAIL-CLOSED VIOLATED: the network-declaring probe body executed"
    )
    assert not NET_PROBE_FIRED
    # no finding may be recorded for a refused probe
    assert not h.log.list(probe="edges/net-declared-refused")


# ---------------------------------------------------------------------------
# (c) anonymity: raw labels can never enter the log
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label",
    [
        "Some Raw Name",
        "wave-seven-actual",
        "op:local extra",
        "dw:NOTHEXCHARS",
        "dw:",
        "",
        "operator-local",
    ],
)
def test_findings_reject_raw_labels(tmp_path: Path, label: str) -> None:
    log = FindingsLog(tmp_path / "f.jsonl")
    assert not is_anonymized_label(label)
    with pytest.raises(ValueError):
        log.record(
            target_label=label,
            probe="curiosity/off-scope-creative",
            observation="x",
            repro_steps="y",
        )


@pytest.mark.parametrize(
    "label",
    ["op:local", "op:nano-bit", "pack:genesis-demo", "dw:deadbeef1234"],
)
def test_findings_accept_anonymized_labels(tmp_path: Path, label: str) -> None:
    log = FindingsLog(tmp_path / "f.jsonl")
    d = log.record(
        target_label=label,
        probe="curiosity/off-scope-creative",
        observation="honestly scope-bound",
        repro_steps="repro",
    )
    assert d.target_label == label


def test_dynasty_target_requires_hex_label(tmp_path: Path) -> None:
    h = _harness(tmp_path, record_findings=False)
    with pytest.raises(DiscoveryError):
        h.register_dynasty_target("wave-seven", lambda text: None)
    with pytest.raises(DiscoveryError):
        h.register_dynasty_target("dw:NotHex!!", lambda text: None)
    label = h.register_dynasty_target(
        "dw:deadbeef1234",
        lambda text: OperatorResult(text="dynasty stub", finish_reason="stop"),
    )
    assert label == "dw:deadbeef1234"
    report = h.run("curiosity", ["dw:deadbeef1234"])
    assert report.target_labels == ["dw:deadbeef1234"]


def test_dynasty_findings_carry_labels_only(tmp_path: Path) -> None:
    raw_name = "Wave Seven Actual Name"
    h = _harness(tmp_path)
    h.register_dynasty_target(
        "dw:deadbeef1234",
        lambda text: OperatorResult(text="dynasty stub", finish_reason="stop"),
    )
    h.run("curiosity", ["dw:deadbeef1234"])
    raw = (tmp_path / "findings.jsonl").read_text(encoding="utf-8")
    assert raw_name not in raw
    for d in h.log.list():
        assert d.target_label == "dw:deadbeef1234"


# ---------------------------------------------------------------------------
# (d) pack targets: shape + the genesis odd-count law
# ---------------------------------------------------------------------------


def test_pack_shape_and_odd_law_pass(tmp_path: Path) -> None:
    h = _harness(tmp_path, "stub-a")
    h.register_pack("demo", {"agents": [{"id": 1}, {"id": 2}, {"id": 3}],
                             "name": "demo"})
    report = h.run("curiosity", ["pack:demo"])
    by_probe = {o["probe_id"]: o for o in report.outcomes}
    assert by_probe["curiosity/pack-shape"]["passed"] is True
    assert "agents(list)" in by_probe["curiosity/pack-shape"]["observation"]
    odd = by_probe["curiosity/pack-odd-law"]
    assert odd["passed"] is True
    assert "ODD" in odd["observation"]


def test_pack_even_agent_count_is_significant_finding(tmp_path: Path) -> None:
    h = _harness(tmp_path, "stub-a")
    h.register_pack("even-demo", {"agents": [{"id": 1}, {"id": 2}]})
    report = h.run("curiosity", ["pack:even-demo"])
    odd = next(
        o for o in report.outcomes if o["probe_id"] == "curiosity/pack-odd-law"
    )
    assert odd["passed"] is False
    assert odd["beyond_scope"] is True
    findings = h.log.list(probe="curiosity/pack-odd-law")
    assert len(findings) == 1
    assert findings[0].significance == "significant"
    assert findings[0].target_label == "pack:even-demo"


# ---------------------------------------------------------------------------
# (e) integration: the real built-in operators
# ---------------------------------------------------------------------------


def test_real_operators_edges_no_errors(tmp_path: Path) -> None:
    from levi.operator.registry import default_registry

    h = DiscoveryHarness(
        registry=default_registry(),
        findings_path=tmp_path / "findings.jsonl",
        seed=1337,
        record_findings=False,
    )
    report = h.run("edges", ["operators"])
    assert report.errors == 0, (
        "edge probes must never crash a built-in operator: "
                f"{[o for o in report.outcomes if o['error']]}"
    )
    assert not probes_mod.NET_PROBE_FIRED
    assert any(
        r["probe_id"] == "edges/net-declared-refused"
        for r in report.network_refusals
    )


def test_real_operators_rapid_swaps_preserve_history(tmp_path: Path) -> None:
    from levi.operator.registry import default_registry

    h = DiscoveryHarness(
        registry=default_registry(),
        findings_path=tmp_path / "findings.jsonl",
        seed=1337,
        record_findings=False,
    )
    report = h.run("edges", ["operators:local"])
    swap = next(
        o for o in report.outcomes if o["probe_id"] == "edges/rapid-swaps"
    )
    assert swap["passed"] is True, swap["observation"]
    assert "preserved" in swap["observation"]


# ---------------------------------------------------------------------------
# (f) regression: findings from the 2026-09-18 live run
# ---------------------------------------------------------------------------
#
# Each test below pins one notable/significant discovery from the live
# run against default_registry() (curiosity + edges packs). If the
# behavior changes, the test fails and the finding must be re-run and
# either confirmed or retired — never silently edited.


def _live_harness(tmp_path: Path) -> DiscoveryHarness:
    from levi.operator.registry import default_registry

    return DiscoveryHarness(
        registry=default_registry(),
        findings_path=tmp_path / "findings.jsonl",
        seed=1337,
        record_findings=False,
    )


def _live_outcomes(tmp_path: Path, pack: str) -> dict:
    h = _live_harness(tmp_path)
    report = h.run(pack, ["operators"])
    assert report.errors == 0
    by_probe: dict = {}
    for o in report.outcomes:
        by_probe.setdefault(o["probe_id"], []).append(o)
    return by_probe


def test_live_nano_bit_trivial_matcher_is_english_only(tmp_path: Path) -> None:
    """Live-run finding: the nano-bit trivial matcher fires on English
    greetings but 'hola' is refused with an escalation hint. If the
    matcher ever goes multilingual (or stops refusing), re-run the
    probe and update this pin deliberately."""
    by_probe = _live_outcomes(tmp_path, "curiosity")
    got = {
        o["target_label"]: o["observation"]
        for o in by_probe["curiosity/multilingual-trivial"]
    }
    assert "refused/escalated" in got["op:nano-bit"], got["op:nano-bit"]
    assert "did not greet back" in got["op:local"], got["op:local"]


def test_live_no_operator_fabricates_arithmetic(tmp_path: Path) -> None:
    """Live-run finding: asked for 17*23, no built-in operator produced
    391 — none faked arithmetic beyond its documented scope."""
    by_probe = _live_outcomes(tmp_path, "curiosity")
    for o in by_probe["curiosity/off-scope-math"]:
        assert o["passed"] is True, o
        assert o["beyond_scope"] is False, o
        assert "391" not in (o["detail"] or ""), o


def test_live_no_operator_fabricates_creative_output(tmp_path: Path) -> None:
    """Live-run finding: asked for a haiku, every built-in operator
    stayed scope-bound — none produced verse-like output."""
    by_probe = _live_outcomes(tmp_path, "curiosity")
    for o in by_probe["curiosity/off-scope-creative"]:
        assert o["passed"] is True, o
        assert o["beyond_scope"] is False, o


def test_live_statelessness_holds_everywhere(tmp_path: Path) -> None:
    """Live-run finding: no operator recalled a fact across fresh
    turns — the memory_access=False declaration holds."""
    by_probe = _live_outcomes(tmp_path, "curiosity")
    for o in by_probe["curiosity/no-memory-carryover"]:
        assert o["passed"] is True, o
        assert o["beyond_scope"] is False, o


def test_live_net_probe_refused_for_every_target(tmp_path: Path) -> None:
    """Live-run finding: the network-declaring probe was refused
    fail-closed for all 5 operators and its body never executed."""
    reset_net_probe_tripwire()
    h = _live_harness(tmp_path)
    report = h.run("edges", ["operators"])
    refusals = [
        r for r in report.network_refusals
        if r["probe_id"] == "edges/net-declared-refused"
    ]
    assert len(refusals) == 5, report.network_refusals
    assert not probes_mod.NET_PROBE_FIRED


def test_live_oversized_input_stays_wellformed(tmp_path: Path) -> None:
    """Live-run finding: a 50k-char local input stayed well-formed on
    every operator (nano-bit refused it in ~0ms; local answered in
    ~11ms). Guards against future regressions in input handling."""
    by_probe = _live_outcomes(tmp_path, "edges")
    for o in by_probe["edges/oversized-local"]:
        assert o["passed"] is True, o
        assert o["latency_ms"] < 5000, o  # local, in-process: must stay fast
