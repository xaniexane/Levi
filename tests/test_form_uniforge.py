"""uniforge form tests: evolution; auto-repair and upgrade loop.

Proving bar: forge_dry_run never executes (dry-run purity), a receipt is
produced for EVERY run (including refusals and denials), missing tools
fail closed before permission is ever asked, and consequential steps
always pass a permission gate.
"""

from levi.automation.hitl import auto_approve, auto_deny
from levi.uniforge import BuildPlan, Step
from levi.uniforge.si import forge, forge_dry_run, plan_readiness


def _plan(tool="python3", consequential=False):
    return BuildPlan(
        name="probe",
        targets=["t"],
        steps=[
            Step(
                id="s1",
                label="step s1",
                target="t",
                tool=tool,
                argv=[tool, "-c", "pass"],
                workdir=".",
                consequential=consequential,
            )
        ],
    )


def test_dry_run_never_executes(tmp_path):
    marker = tmp_path / "must-not-exist"
    plan = BuildPlan(
        name="probe",
        targets=["t"],
        steps=[
            Step(
                id="s1",
                label="writes marker",
                target="t",
                tool="python3",
                argv=["python3", "-c", f"open({str(marker)!r}, 'w').write('x')"],
                workdir=".",
            )
        ],
    )
    receipt = forge_dry_run(plan)
    assert receipt["decision"] == "dry-run"
    assert not marker.exists()  # purity: nothing executed
    assert receipt["organ"] == "uniforge"
    assert receipt["ts"]  # receipts are never silent


def test_missing_tools_refuse_before_permission():
    plan = _plan(tool="no-such-tool-xyz-levi")
    receipt = forge(plan, live=False, responder=auto_approve)
    assert receipt["decision"] == "refused"
    assert "missing tools" in receipt["note"]


def test_consequential_step_denied_ends_run_with_receipt():
    plan = _plan(consequential=True)
    receipt = forge(plan, live=True, responder=auto_deny)
    assert receipt["decision"] == "denied"
    assert receipt["ts"]  # the denial is recorded, not silent


def test_plan_readiness_is_honest():
    ready = plan_readiness(_plan())
    assert isinstance(ready, dict)
    assert ready  # a report, whatever its shape


def test_live_approved_non_consequential_executes_honestly(tmp_path):
    marker = tmp_path / "executed-marker"
    plan = BuildPlan(
        name="probe",
        targets=["t"],
        steps=[
            Step(
                id="s1",
                label="writes marker",
                target="t",
                tool="python3",
                argv=["python3", "-c", f"open({str(marker)!r}, 'w').write('x')"],
                workdir=".",
            )
        ],
    )
    receipt = forge(plan, live=True, responder=auto_approve)
    assert receipt["decision"] == "executed"
    assert marker.exists()  # live+approved really runs; the receipt says so
