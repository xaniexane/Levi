"""Hermetic tests for the export covenant verifier (Yahoo Groups purge)."""

import pytest

from levi.liberation.export_covenant import (
    CheckReport,
    CovenantError,
    class_digest,
    declare_manifest,
    export_integrity_check,
    shutdown_gate,
)


def _artifacts():
    return {
        "messages": [b"m1", b"m2", b"m3"],
        "photos": [b"p1"],
        "polls": [b"q1", b"q2"],
    }


def _manifest(arts=None):
    arts = arts if arts is not None else _artifacts()
    return declare_manifest(
        {name: {"count": len(items), "digest": class_digest(items)}
         for name, items in arts.items()}
    )


def test_clean_export_verifies():
    arts = _artifacts()
    report = export_integrity_check(_manifest(arts), arts)
    assert report.ok
    assert report.failures == []
    assert {v["class"] for v in report.verified_classes} == set(arts)


def test_dropped_class_is_a_failure():
    arts = _artifacts()
    manifest = _manifest(arts)
    del arts["photos"]  # the Yahoo Groups failure mode
    report = export_integrity_check(manifest, arts)
    assert not report.ok
    assert any("photos" in f and "MISSING" in f for f in report.failures)


def test_count_mismatch_is_a_failure():
    arts = _artifacts()
    manifest = _manifest(arts)
    arts["messages"] = arts["messages"][:2]
    report = export_integrity_check(manifest, arts)
    assert not report.ok
    assert any("messages" in f and "count mismatch" in f for f in report.failures)


def test_digest_mismatch_is_a_failure():
    arts = _artifacts()
    manifest = _manifest(arts)
    arts["polls"] = [b"q1", b"TAMPERED"]
    report = export_integrity_check(manifest, arts)
    assert not report.ok
    assert any("polls" in f and "digest mismatch" in f for f in report.failures)


def test_undeclared_class_is_a_warning_not_a_failure():
    arts = _artifacts()
    manifest = _manifest(arts)
    arts["sneaky"] = [b"x"]
    report = export_integrity_check(manifest, arts)
    assert report.ok
    assert any("sneaky" in w for w in report.warnings)


def test_class_digest_is_order_free():
    a = class_digest([b"m1", b"m2"])
    b = class_digest([b"m2", b"m1"])
    assert a == b


def test_empty_manifest_refused():
    with pytest.raises(CovenantError):
        declare_manifest({})


def test_malformed_inputs_refused():
    with pytest.raises(CovenantError):
        export_integrity_check({"nope": 1}, {})
    with pytest.raises(CovenantError):
        export_integrity_check(_manifest(), "not-a-mapping")


def test_gate_allows_clean_export_with_receipt():
    report = export_integrity_check(_manifest(), _artifacts())
    decision = shutdown_gate(report)
    assert decision["allowed"] is True
    receipt = decision["receipt"]
    assert receipt["manifest_id"] == report.manifest_id
    assert len(receipt["classes"]) == 3


def test_gate_refuses_incomplete_export():
    arts = _artifacts()
    manifest = _manifest(arts)
    del arts["photos"]
    report = export_integrity_check(manifest, arts)
    decision = shutdown_gate(report)
    assert decision["allowed"] is False
    assert "refused" in decision["reason"]
    assert decision["failures"]


def test_gate_has_no_bypass():
    # The gate takes only the report: there is no force flag to pass.
    import inspect

    assert list(inspect.signature(shutdown_gate).parameters) == ["report"]
    with pytest.raises(CovenantError):
        shutdown_gate("not-a-report")


def test_report_serializes():
    report = export_integrity_check(_manifest(), _artifacts())
    d = report.to_dict()
    assert d["ok"] is True
    assert isinstance(d["failures"], list)
