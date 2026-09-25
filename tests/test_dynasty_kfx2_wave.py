# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""KFX2 Phase 1 — single-wave runner tests.

Hermetic: every test runs under a tmp LEVI_HOME via monkeypatch. No
network, no daemons, no writes to the real user HOME, no explicit
content anywhere.
"""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from levi.dynasty.kfx2 import (
    CONTINUE,
    HALT,
    MARGINAL_COST_PER_STEP,
    AgentRegistry,
    AgentSpec,
    RunContext,
    StepOutcome,
    StepResult,
    WaveDefinition,
    WaveError,
    WaveRunner,
    WaveStep,
    verify_wave_log,
)


def _scribe(task: str, inputs: Mapping[str, Any], ctx: RunContext) -> StepResult:
    """Drafts text on a topic. Deterministic: rng only, plus task/inputs."""
    return StepResult.ok(
        {"draft": f"{inputs['topic']}-draft", "draw": round(ctx.rng.random(), 6)}
    )


def _polisher(task: str, inputs: Mapping[str, Any], ctx: RunContext) -> StepResult:
    prior = ctx.prior["draft-step"]["draft"]
    return StepResult.ok({"polished": prior.upper(), "by": ctx.seq})


def _deferrer(task: str, inputs: Mapping[str, Any], ctx: RunContext) -> StepResult:
    return StepResult.defer("owner has not approved the style yet")


def _failer(task: str, inputs: Mapping[str, Any], ctx: RunContext) -> StepResult:
    raise RuntimeError("boom")


def _reject_low_scores(output: Any, ctx: RunContext):
    return (output["score"] >= 5, f"score={output['score']}")


def _score(task: str, inputs: Mapping[str, Any], ctx: RunContext) -> StepResult:
    return StepResult.ok({"score": inputs["score"]})


@pytest.fixture
def registry() -> AgentRegistry:
    reg = AgentRegistry()
    reg.register(
        AgentSpec(
            name="scribe",
            role="Writes the first draft of whatever the task describes.",
            scope=("compute", "write:artifacts"),
            run=_scribe,
        )
    )
    reg.register(
        AgentSpec(
            name="polisher",
            role="Takes the earlier draft and returns a polished version.",
            scope=("compute",),
            run=_polisher,
        )
    )
    reg.register(
        AgentSpec(
            name="deferrer",
            role="Holds steps that need an owner decision before work starts.",
            scope=("compute",),
            run=_deferrer,
        )
    )
    reg.register(
        AgentSpec(
            name="failer",
            role="A step that always explodes, for failure-path tests.",
            scope=("compute",),
            run=_failer,
        )
    )
    reg.register(
        AgentSpec(
            name="scorer",
            role="Scores a candidate; a verifier checks the score.",
            scope=("compute",),
            run=_score,
            verify=_reject_low_scores,
        )
    )
    return reg


@pytest.fixture
def runner(tmp_path, monkeypatch) -> WaveRunner:
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    return WaveRunner()


def _wave(**kwargs) -> WaveDefinition:
    return WaveDefinition(
        wave_id=kwargs.pop("wave_id", "wave-1"),
        steps=(
            WaveStep(
                step_id="draft-step",
                agent="scribe",
                task="Draft it.",
                inputs={"topic": "ledger"},
            ),
            WaveStep(
                step_id="polish-step",
                agent="polisher",
                task="Polish the draft.",
                inputs={},
            ),
        ),
        seed=kwargs.pop("seed", 7),
        **kwargs,
    )


def test_wave_runs_end_to_end_receipted(runner, registry):
    seen = []
    report = runner.run(_wave(), registry, on_step=seen.append)

    assert report.status == "completed"
    assert len(report.receipts) == 2
    assert len(seen) == 2  # live observability fired per step
    assert report.outputs()["draft-step"]["draft"] == "ledger-draft"
    assert report.outputs()["polish-step"]["polished"] == "LEDGER-DRAFT"
    assert report.outputs()["polish-step"]["by"] == 2

    # Every step receipted and the chain verifies.
    verified = verify_wave_log(report.log_path)
    assert [r.body["status"] for r in verified] == ["succeeded"] * 2
    assert [r.body["seq"] for r in verified] == [1, 2]
    # Readable roles landed in the receipts (legibility parity).
    assert "first draft" in verified[0].body["role"]


def test_reproducible_byte_identical(tmp_path, monkeypatch, registry):
    wave = _wave()
    log_a, log_b = None, None
    for i, home in enumerate(("ha", "hb")):
        monkeypatch.setenv("LEVI_HOME", str(tmp_path / home))
        report = WaveRunner().run(wave, registry)
        if i == 0:
            log_a = report.log_path.read_bytes()
        else:
            log_b = report.log_path.read_bytes()
    assert log_a == log_b  # same definition + seed => identical receipts


def test_failure_halts_and_records(runner, registry):
    wave = WaveDefinition(
        wave_id="wave-fail",
        steps=(
            WaveStep(
                step_id="ok-step",
                agent="scribe",
                task="Draft it.",
                inputs={"topic": "x"},
            ),
            WaveStep(step_id="bad-step", agent="failer", task="Blow up.", inputs={}),
            WaveStep(
                step_id="never-step",
                agent="scribe",
                task="Skipped.",
                inputs={"topic": "y"},
            ),
        ),
        seed=1,
        on_failure=HALT,
    )
    report = runner.run(wave, registry)
    assert report.status == "halted"
    assert [r.body["step"] for r in report.receipts] == ["ok-step", "bad-step"]
    bad = report.receipts[-1]
    assert bad.body["status"] == StepOutcome.FAILED
    assert "boom" in bad.body["reason"]
    assert verify_wave_log(report.log_path)  # the record is complete


def test_failure_continue_policy(runner, registry):
    wave = WaveDefinition(
        wave_id="wave-cont",
        steps=(
            WaveStep(step_id="bad-step", agent="failer", task="Blow up.", inputs={}),
            WaveStep(
                step_id="ok-step",
                agent="scribe",
                task="Draft it.",
                inputs={"topic": "x"},
            ),
        ),
        seed=1,
        on_failure=CONTINUE,
    )
    report = runner.run(wave, registry)
    assert report.status == "completed_with_failures"
    assert len(report.receipts) == 2
    assert report.outputs()["ok-step"]["draft"] == "x-draft"


def test_deferred_third_state(runner, registry):
    wave = WaveDefinition(
        wave_id="wave-defer",
        steps=(
            WaveStep(
                step_id="hold-step", agent="deferrer", task="Wait for owner.", inputs={}
            ),
            WaveStep(
                step_id="ok-step",
                agent="scribe",
                task="Draft it.",
                inputs={"topic": "x"},
            ),
        ),
        seed=1,
    )
    report = runner.run(wave, registry)
    assert report.status == "completed"
    assert report.failures == []
    assert report.deferred == [
        {"step": "hold-step", "reason": "owner has not approved the style yet"}
    ]
    receipt = report.receipts[0]
    assert receipt.body["status"] == StepOutcome.DEFERRED
    assert verify_wave_log(report.log_path)


def test_verifier_rejection_fails_the_step(runner, registry):
    wave = WaveDefinition(
        wave_id="wave-veto",
        steps=(
            WaveStep(
                step_id="score-step",
                agent="scorer",
                task="Score it.",
                inputs={"score": 2},
            ),
        ),
        seed=1,
    )
    report = runner.run(wave, registry)
    assert report.status == "halted"
    receipt = report.receipts[0]
    assert receipt.body["status"] == StepOutcome.FAILED
    assert "verifier rejected" in receipt.body["reason"]
    assert receipt.body["verifier"]["verdict"] is False


def test_verifier_acceptance_recorded(runner, registry):
    wave = WaveDefinition(
        wave_id="wave-ok",
        steps=(
            WaveStep(
                step_id="score-step",
                agent="scorer",
                task="Score it.",
                inputs={"score": 9},
            ),
        ),
        seed=1,
    )
    report = runner.run(wave, registry)
    assert report.status == "completed"
    receipt = report.receipts[0]
    assert receipt.body["status"] == StepOutcome.SUCCEEDED
    assert receipt.body["verifier"]["verdict"] is True


def test_unknown_capability_refused():
    reg = AgentRegistry()
    with pytest.raises(WaveError, match="unknown capabilities"):
        reg.register(
            AgentSpec(
                name="sneaky",
                role="Tries to touch everything.",
                scope=("root:shell",),
                run=_scribe,
            )
        )


def test_unknown_agent_refused_before_any_log(runner, registry):
    wave = WaveDefinition(
        wave_id="wave-ghost",
        steps=(WaveStep(step_id="s", agent="nobody", task="t.", inputs={}),),
        seed=1,
    )
    with pytest.raises(WaveError, match="unknown agent"):
        runner.run(wave, registry)
    assert not (runner.waves_dir / "wave-ghost.jsonl").exists()


def test_tampered_log_detected(runner, registry):
    report = runner.run(_wave(), registry)
    path = report.log_path
    text = path.read_text(encoding="utf-8")
    tampered = text.replace("ledger-draft", "ledger-FORGED", 1)
    assert tampered != text
    path.write_text(tampered, encoding="utf-8")
    with pytest.raises(WaveError, match="hash mismatch"):
        verify_wave_log(path)


def test_duplicate_wave_id_refused(runner, registry):
    runner.run(_wave(), registry)
    with pytest.raises(WaveError, match="already logged"):
        runner.run(_wave(), registry)


def test_duplicate_step_ids_rejected():
    with pytest.raises(WaveError, match="duplicate step ids"):
        WaveDefinition(
            wave_id="w",
            steps=(
                WaveStep(step_id="s", agent="a", task="t.", inputs={}),
                WaveStep(step_id="s", agent="a", task="t.", inputs={}),
            ),
        )


def test_empty_wave_rejected():
    with pytest.raises(WaveError, match="at least one step"):
        WaveDefinition(wave_id="w", steps=())


def test_non_jsonable_output_rejected(runner):
    reg = AgentRegistry()
    reg.register(
        AgentSpec(
            name="obj",
            role="Returns an object.",
            scope=("compute",),
            run=lambda t, i, c: StepResult.ok(object()),
        )
    )
    wave = WaveDefinition(
        wave_id="wave-obj",
        steps=(WaveStep(step_id="s", agent="obj", task="t.", inputs={}),),
        seed=1,
    )
    with pytest.raises(WaveError, match="non-JSON value"):
        runner.run(wave, reg)


def test_marginal_cost_per_step_is_zero(runner, registry):
    assert MARGINAL_COST_PER_STEP == 0.0
    report = runner.run(_wave(), registry)
    manifest = report.manifest_path
    assert manifest.exists()
    import json

    assert json.loads(manifest.read_text())["marginal_cost_per_step"] == 0.0


def test_duplicate_agent_registration_rejected(registry):
    with pytest.raises(WaveError, match="already registered"):
        registry.register(
            AgentSpec(
                name="scribe", role="Another scribe.", scope=("compute",), run=_scribe
            )
        )
