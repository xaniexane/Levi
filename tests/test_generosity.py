"""Tests for the Honest Generosity Charter (evening hunt 2026-09-16)."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


from levi.generosity import (
    RULES,
    GenerosityManifest,
    audit,
    audit_giants_showcase,
)


def test_eight_rules():
    assert len(RULES) == 8
    ids = [r.id for r in RULES]
    assert len(set(ids)) == 8


def test_honest_default_manifest_passes():
    result = audit(GenerosityManifest(name="honest-feature"))
    assert result.passed, result.report()
    assert len(result.passes) == 8


def test_each_sly_trade_fails_exactly_its_rule():
    cases = {
        "no_toll_road": GenerosityManifest(name="t", has_toll_road=True),
        "no_gatekeeper_curation": GenerosityManifest(
            name="t", has_gatekeeper_curation=True, curation_criteria_disclosed=False
        ),
        "no_privacy_theater": GenerosityManifest(
            name="t", claims_privacy=True, privacy_verifiable_locally=False
        ),
        "no_kill_switch": GenerosityManifest(name="t", reserves_revoke_rights=True),
        "no_rival_harvest": GenerosityManifest(
            name="t", uses_user_data_to_compete=True
        ),
        "no_engagement_metrics": GenerosityManifest(
            name="t", has_engagement_metrics=True
        ),
        "no_data_tithe": GenerosityManifest(name="t", requires_outbound_data=True),
        "honest_labeling": GenerosityManifest(name="t", labels_free_accurately=False),
    }
    for rule_id, manifest in cases.items():
        result = audit(manifest)
        failed = {f["id"] for f in result.failures}
        assert rule_id in failed, (rule_id, result.report())
        assert len(failed) == 1, (rule_id, failed)


def test_disclosed_editable_curation_passes():
    m = GenerosityManifest(
        name="t",
        has_gatekeeper_curation=True,
        curation_criteria_disclosed=True,
        curation_criteria_editable=True,
    )
    assert audit(m).passed


def test_privacy_claim_without_theater_passes():
    m = GenerosityManifest(
        name="t", claims_privacy=True, privacy_verifiable_locally=True
    )
    assert audit(m).passed


def test_giants_showcase_all_fail():
    results = audit_giants_showcase()
    assert set(results) == {
        "free-basics",
        "privacy-sandbox",
        "x-api",
        "amazon-marketplace",
    }
    for key, result in results.items():
        assert not result.passed, "toothless charter: %s passed" % key


def _run_cli(*args):
    repo = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(repo / "core"))
    return subprocess.run(
        [sys.executable, "-m", "levi.generosity", *args],
        capture_output=True,
        text=True,
        cwd=repo,
        env=env,
    )


def test_cli_charter_lists_rules():
    p = _run_cli("charter")
    assert p.returncode == 0
    for rule in RULES:
        assert rule.id in p.stdout


def test_cli_showcase_all_four_fail():
    p = _run_cli("showcase")
    assert p.returncode == 0
    assert "all four giants fail as expected" in p.stdout


def test_cli_audit_honest_passes_and_dishonest_fails():
    p = _run_cli("audit", "--name", "honest")
    assert p.returncode == 0 and "PASS" in p.stdout
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump({"name": "toll", "has_toll_road": True}, fh)
        path = fh.name
    p = _run_cli("audit", "--manifest", path)
    assert p.returncode == 1 and "no_toll_road" in p.stdout


def test_cli_audit_rejects_unknown_fields():
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump({"name": "t", "has_dark_magic": True}, fh)
        path = fh.name
    p = _run_cli("audit", "--manifest", path)
    assert p.returncode == 2


def test_broken_rule_check_fails_that_rule_only():
    from levi.generosity import CharterRule

    bad = CharterRule(id="bad", title="bad", inversion="x", check=lambda m: 1 / 0)
    assert bad.passes(GenerosityManifest(name="t")) is False
