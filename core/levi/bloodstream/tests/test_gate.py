"""Policy gate semantics: no bypass paths, ever."""

from levi.policy.gates import PolicyEngine, RiskLevel

from levi.bloodstream.gate import run_gated


def _gate(engine, **over):
    kwargs = dict(
        engine=engine,
        description="test action",
        risk_level=RiskLevel.MODERATE,
        reason="test",
        execute=lambda: "did the thing",
        verify=lambda: True,
    )
    kwargs.update(over)
    return run_gated(**kwargs)


def test_risk2_without_human_channel_never_executes():
    engine = PolicyEngine()
    called = []
    out = _gate(engine, confirm=None,
                execute=lambda: called.append(True) or "x")
    assert out.awaiting_permission is True
    assert out.executed is False
    assert out.receipt is None
    assert called == []


def test_risk2_with_human_approval_executes_verifies_receipts():
    engine = PolicyEngine()
    seen = []
    out = _gate(engine, confirm=lambda p: seen.append(p) or True)
    assert out.approved is True
    assert out.executed is True
    assert out.verified is True
    assert out.receipt_id
    assert out.receipt.verified is True
    assert seen and seen[0].id == out.proposal.id


def test_risk2_human_denial_executes_nothing():
    engine = PolicyEngine()
    called = []
    out = _gate(engine, confirm=lambda p: False,
                execute=lambda: called.append(True) or "x")
    assert out.approved is False
    assert out.executed is False
    assert out.receipt is None
    assert called == []


def test_dry_run_never_executes_but_still_receipts():
    engine = PolicyEngine()
    called = []
    out = _gate(engine, confirm=lambda p: True, dry_run=True,
                execute=lambda: called.append(True) or "x")
    assert out.dry_run is True
    assert out.executed is False
    assert called == []
    assert out.receipt_id  # a receipt for the previewed plan
    assert "dry-run" in out.receipt.outcome


def test_execute_exception_marks_failed_no_receipt():
    engine = PolicyEngine()

    def boom():
        raise RuntimeError("kaboom")

    out = _gate(engine, confirm=lambda p: True, execute=boom)
    assert out.executed is False
    assert out.error and "RuntimeError" in out.error
    assert out.receipt is None


def test_low_risk_auto_approves_with_no_human():
    engine = PolicyEngine()
    out = _gate(engine, risk_level=RiskLevel.LOW, confirm=None)
    assert out.auto_approved is True
    assert out.executed is True
    assert out.receipt_id


def test_high_risk_requires_human_even_with_strict_ceiling():
    engine = PolicyEngine(auto_approve_up_to=RiskLevel.INFO)
    called = []
    out = _gate(engine, risk_level=RiskLevel.LOW, confirm=None,
                execute=lambda: called.append(True) or "x")
    assert out.awaiting_permission is True
    assert called == []
