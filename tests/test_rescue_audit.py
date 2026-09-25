"""Audit honesty: no finding without evidence; deterministic scoring.

Hermetic: tmp rescue home, hand-built walk contexts, no network.
"""

import pytest

from levi.rescue import audit, intake
from levi.rescue.audit import Check, Evidence, run_audit


SITE = "https://tacos.example"


def _home_inv(tmp_path):
    inv = intake.issue_invitation(
        tmp_path, owner="M. Torres", business="Torres Tacos", site_url=SITE
    )
    return intake.accept_invitation(tmp_path, inv.id)


def _page(**over):
    p = {
        "url": SITE,
        "status": 200,
        "title": "Torres Tacos",
        "text": "# Torres Tacos\nBest tacos in town. Call 217-555-0100.",
        "links": [{"target": SITE + "/menu"}],
        "forms": [],
        "structure": "heading",
    }
    p.update(over)
    return p


def test_clean_site_scores_100_with_no_findings(tmp_path):
    inv = _home_inv(tmp_path)
    report = run_audit(tmp_path, inv.id, audit.DEFAULT_CHECKS, {SITE: _page()})
    assert report.findings == []
    assert report.score == 100
    assert report.dropped_hypotheses == []


def test_findings_carry_evidence_and_score_is_deterministic(tmp_path):
    inv = _home_inv(tmp_path)
    walk = {SITE: _page(title="", text="Welcome to our page.")}
    report = run_audit(tmp_path, inv.id, audit.DEFAULT_CHECKS, walk)
    by_check = {f.check_id: f for f in report.findings}
    # has-title (medium=8) + contact-visible (high=15) → 100-23 = 77
    assert set(by_check) == {"has-title", "contact-visible"}
    assert report.score == 77
    for f in report.findings:
        assert f.evidence, "finding shipped without evidence: %r" % f.title
        for e in f.evidence:
            assert isinstance(e, Evidence)
            assert e.kind and e.ref and e.note


def test_evidence_free_finding_is_dropped_never_shipped(tmp_path):
    inv = _home_inv(tmp_path)
    ghost = Check(
        "ghost",
        "Ghost problem",
        "critical",
        lambda walk: {"title": "something feels off"},
    )
    report = run_audit(tmp_path, inv.id, [ghost], {SITE: _page()})
    assert report.findings == []
    assert report.score == 100
    assert len(report.dropped_hypotheses) == 1
    dropped = report.dropped_hypotheses[0]
    assert dropped["check_id"] == "ghost"
    assert "no evidence" in dropped["reason"]


def test_broken_probe_is_dropped_not_a_finding(tmp_path):
    inv = _home_inv(tmp_path)
    boom = Check(
        "boom", "Boom", "high", lambda walk: (_ for _ in ()).throw(ValueError("kaput"))
    )
    report = run_audit(tmp_path, inv.id, [boom], {SITE: _page()})
    assert report.findings == []
    assert "probe error" in report.dropped_hypotheses[0]["reason"]


def test_empty_walk_refused(tmp_path):
    inv = _home_inv(tmp_path)
    with pytest.raises(ValueError):
        run_audit(tmp_path, inv.id, audit.DEFAULT_CHECKS, {})


def test_severity_weights_are_published_and_complete(tmp_path):
    assert set(audit.SEVERITY_WEIGHTS) == {"critical", "high", "medium", "low"}
    assert all(w > 0 for w in audit.SEVERITY_WEIGHTS.values())


def test_audit_persists_and_reloads(tmp_path):
    inv = _home_inv(tmp_path)
    report = run_audit(tmp_path, inv.id, audit.DEFAULT_CHECKS, {SITE: _page(title="")})
    again = audit.get_audit(tmp_path, report.id)
    assert again.score == report.score
    assert [f.check_id for f in again.findings] == [f.check_id for f in report.findings]
