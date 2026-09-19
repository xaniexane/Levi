"""Tests for the LEVI EULA/terms-of-service linter (core/levi/eula/)."""

import json
import os
import subprocess
import sys
import tempfile

from levi.eula import RULES, lint, lint_file, summarize

SAMPLE_HOSTILE = """
TERMS OF SERVICE
Effective date: January 1, 2026.

1. ARBITRATION. You agree that any dispute shall be resolved exclusively by
binding arbitration, and you waive your right to a trial by jury.

2. CLASS ACTION WAIVER. You may not bring a class action or collective action
against the Company.

3. MODIFICATIONS. We may modify these terms at any time without notice, and
your continued use constitutes acceptance of the new terms.

4. YOUR CONTENT. You grant us a perpetual, irrevocable, worldwide royalty-free
license to use your content.

5. DATA. We may sell your personal information to third parties and share your
data with third-party partners.

6. BILLING. Your subscription will automatically renew and your card will be
charged the recurring billing amount.

7. REFUNDS. All sales are final. No refunds.

8. TERMINATION. We may terminate your account at any time at our sole discretion
without prior notice.

9. LIABILITY. In no event shall the Company be liable; our liability shall not
exceed the fees you paid. The service is provided as is, without warranty of
any kind.

10. LAW. These terms are governed by the laws of the State of Delaware.
"""


def test_severity_bands_valid():
    assert set(SEVERITIES := ("info", "caution", "hostile"))
    for rule in RULES:
        assert rule["severity"] in SEVERITIES, rule["id"]


def test_every_rule_has_plain_language_flag():
    for rule in RULES:
        assert rule["plain_language_flag"], rule["id"]
        assert len(rule["plain_language_flag"]) > 20, rule["id"]


def test_forced_arbitration_is_hostile():
    findings = lint("All disputes shall be settled by binding arbitration.")
    ids = {f["rule_id"] for f in findings}
    assert "forced_arbitration" in ids
    f = next(f for f in findings if f["rule_id"] == "forced_arbitration")
    assert f["severity"] == "hostile"
    assert f["clause_excerpt"]
    assert (
        "sue" in f["plain_language_flag"].lower()
        or "court" in f["plain_language_flag"].lower()
    )


def test_class_action_waiver_detected():
    findings = lint("You waive the right to participate in a class action lawsuit.")
    assert any(
        f["rule_id"] == "class_action_waiver" and f["severity"] == "hostile"
        for f in findings
    )


def test_unilateral_modification_detected():
    findings = lint("We may modify these terms at any time without notice.")
    assert any(f["rule_id"] == "unilateral_modification" for f in findings)


def test_data_resale_detected():
    findings = lint("We sell your personal data to advertisers.")
    assert any(
        f["rule_id"] == "data_resale" and f["severity"] == "hostile" for f in findings
    )


def test_perpetual_license_detected():
    findings = lint(
        "You grant a perpetual, irrevocable license to your uploaded content."
    )
    assert any(f["rule_id"] == "perpetual_content_license" for f in findings)


def test_auto_renewal_is_caution():
    findings = lint("Your plan will automatically renew each month.")
    assert any(
        f["rule_id"] == "auto_renewal" and f["severity"] == "caution" for f in findings
    )


def test_clean_text_finds_no_hostile():
    findings = lint("Welcome to our friendly app. Be kind to other users. Have fun!")
    assert not any(f["severity"] == "hostile" for f in findings)


def test_sample_terms_summary():
    findings = lint(SAMPLE_HOSTILE)
    counts = summarize(findings)
    assert (
        counts["hostile"] >= 4
    )  # arbitration, class waiver, modification, resale, perpetual license
    assert (
        counts["caution"] >= 3
    )  # auto-renew, no refund, termination, liability, as-is
    assert counts["info"] >= 1  # effective date + jurisdiction


def test_findings_sorted_hostile_first():
    findings = lint(SAMPLE_HOSTILE)
    order = {"hostile": 0, "caution": 1, "info": 2}
    ranks = [order[f["severity"]] for f in findings]
    assert ranks == sorted(ranks)


def test_finding_shape():
    findings = lint("No refunds. All sales are final.")
    assert findings
    for f in findings:
        assert set(f) == {
            "rule_id",
            "title",
            "severity",
            "clause_excerpt",
            "plain_language_flag",
            "why_it_matters",
        }


def test_lint_file_roundtrip():
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("Binding arbitration applies to all disputes.")
        path = fh.name
    try:
        findings = lint_file(path)
        assert any(f["rule_id"] == "forced_arbitration" for f in findings)
    finally:
        os.unlink(path)


def test_cli_text_output():
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("We may sell your personal information.")
        path = fh.name
    try:
        env = dict(os.environ, PYTHONPATH="core")
        proc = subprocess.run(
            [sys.executable, "-m", "levi.eula", "lint", "--file", path],
            capture_output=True,
            text=True,
            env=env,
            cwd=os.path.expanduser("~/workspace/levi"),
        )
        assert proc.returncode == 0, proc.stderr
        assert "HOSTILE" in proc.stdout
    finally:
        os.unlink(path)


def test_cli_json_output():
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("Binding arbitration applies.")
        path = fh.name
    try:
        env = dict(os.environ, PYTHONPATH="core")
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "levi.eula",
                "lint",
                "--file",
                path,
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=os.path.expanduser("~/workspace/levi"),
        )
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        assert any(f["rule_id"] == "forced_arbitration" for f in data)
    finally:
        os.unlink(path)
