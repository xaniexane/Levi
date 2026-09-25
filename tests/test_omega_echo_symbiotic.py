"""Omega Echo symbiotic proof (worker 🪞).

PROOF STATEMENT (honest, not formal): these tests exercise the Echo
invariant as code — "every blueprint Echo publishes is valid and
verifiable; Echo never publishes an unvalidated blueprint" — by driving
the guard, the publisher, the verifier, and the interrogation path and
asserting the observable consequences (receipts, ValueErrors,
quarantine, release). They do not formally prove anything about
blueprints in general; they prove this implementation holds the line.

Covers:
- verify_build: full match / missing artifact / empty file / bad input.
- publish_blueprint: records an organ="echo" blueprint receipt; refuses
  an unvalidatable blueprint (guard driven directly with a bad dict);
  attaches shared learnings mentioning the detected product types.
- challenge_build: mismatched build quarantines the build receipt
  (is_consumable False); matching build returns None; a dismissed
  challenge releases the receipt; an upheld one holds it forever.
"""

import pytest

from levi.revival.omega import blueprint as bp
from levi.revival.omega import generators as gen
from levi.revival.omega import substrate as sub


def _alpha_build(prompt, product_types=None):
    """A real Alpha-side build dict, via Alpha's own generators."""
    b = bp.build_blueprint(prompt, product_types)
    result = gen.compile_blueprint(b)
    assert result["ok"], result["errors"]
    return b, result["files"]


# ---------------------------------------------------------------------------
# verify_build
# ---------------------------------------------------------------------------


def test_verify_build_full_match():
    b, files = _alpha_build("rest api backend for notes", ["api"])
    result = bp.verify_build(b, files)
    assert result["ok"] is True
    assert result["missing"] == []
    assert result["empty"] == []
    assert str(len(b["artifacts"])) in result["verdict"]


def test_verify_build_missing_artifact():
    b, files = _alpha_build("rest api backend for notes", ["api"])
    dropped = next(iter(files))
    files = {k: v for k, v in files.items() if k != dropped}
    result = bp.verify_build(b, files)
    assert result["ok"] is False
    assert dropped in result["missing"]
    assert "missing" in result["verdict"]


def test_verify_build_empty_file():
    b, files = _alpha_build("landing page for my site", ["webpage"])
    target = next(iter(files))
    files = dict(files)
    files[target] = "   \n  "
    result = bp.verify_build(b, files)
    assert result["ok"] is False
    assert target in result["empty"]
    assert result["missing"] == []
    assert "empty" in result["verdict"]


def test_verify_build_bad_input_never_raises():
    b, files = _alpha_build("landing page for my site", ["webpage"])
    bad_files = bp.verify_build(b, "not-a-dict")
    assert bad_files["ok"] is False
    assert bad_files["missing"] == b["artifacts"]
    bad_bp = bp.verify_build({"name": "broken"}, files)
    assert bad_bp["ok"] is False
    assert "no usable artifact list" in bad_bp["verdict"]


# ---------------------------------------------------------------------------
# publish_blueprint
# ---------------------------------------------------------------------------


def test_publish_records_echo_receipt():
    substrate = sub.SharedSubstrate()
    blueprint, receipt = bp.publish_blueprint(
        substrate, "cli tool to rename photos"
    )
    assert receipt.organ == "echo"
    assert receipt.kind == "blueprint"
    assert receipt.risk == sub.RISK_STANDARD
    assert receipt.payload["name"] == blueprint["name"]
    assert receipt.payload["product_types"] == blueprint["product_types"]
    assert receipt.payload["artifact_count"] == len(blueprint["artifacts"])
    assert "cli" in receipt.payload["detection_scores"]
    stored = substrate.get_receipt(receipt.id)
    assert stored is receipt
    assert substrate.is_consumable(receipt.id)


def test_publish_refuses_unvalidatable_blueprint():
    # Drive the guard directly with a bad dict — the same guard
    # publish_blueprint enforces before any receipt is written.
    with pytest.raises(ValueError) as exc:
        bp.require_valid_blueprint({"name": "broken", "product_types": ["nonsense"]})
    msg = str(exc.value)
    assert "missing field" in msg or "unknown product type" in msg


def test_publish_refuses_bad_prompt():
    substrate = sub.SharedSubstrate()
    with pytest.raises(ValueError):
        bp.publish_blueprint(substrate, "   ")
    with pytest.raises(ValueError):
        bp.publish_blueprint(substrate, "x", product_types=["not_a_type"])
    # and nothing was recorded
    assert substrate.receipts(kind="blueprint") == []


def test_publish_attaches_shared_learnings():
    substrate = sub.SharedSubstrate()
    substrate.record_learning(
        "alpha", "api scaffolds must pin fastapi in requirements.txt"
    )
    substrate.record_learning("daemon", "unrelated night job tidbit")
    _, receipt = bp.publish_blueprint(
        substrate, "rest api backend for notes", ["api"]
    )
    lessons = receipt.payload["lessons_attached"]
    assert any("api" in lesson for lesson in lessons)
    assert not any("unrelated" in lesson for lesson in lessons)


# ---------------------------------------------------------------------------
# challenge_build: Echo → interrogates → Alpha
# ---------------------------------------------------------------------------


def _alpha_build_receipt(substrate, files):
    return substrate.record_receipt(
        organ="alpha",
        kind="build",
        payload={"files": sorted(files), "file_count": len(files)},
        risk=sub.RISK_ELEVATED,
        approved_by="alpha-worker",
    )


def test_challenge_build_quarantines_mismatch():
    substrate = sub.SharedSubstrate()
    b, files = _alpha_build("rest api backend for notes", ["api"])
    build_rcpt = _alpha_build_receipt(substrate, files)
    broken = {k: v for k, v in files.items() if not k.endswith("requirements.txt")}
    challenge = bp.challenge_build(substrate, build_rcpt.id, b, broken)
    assert challenge is not None
    assert challenge.challenger == "echo"
    assert challenge.target_receipt_id == build_rcpt.id
    assert challenge.status == "open"
    assert not substrate.is_consumable(build_rcpt.id)
    assert build_rcpt in substrate.quarantined()


def test_challenge_build_passes_match():
    substrate = sub.SharedSubstrate()
    b, files = _alpha_build("rest api backend for notes", ["api"])
    build_rcpt = _alpha_build_receipt(substrate, files)
    assert bp.challenge_build(substrate, build_rcpt.id, b, files) is None
    assert substrate.is_consumable(build_rcpt.id)


def test_resolve_dismissed_releases_build():
    substrate = sub.SharedSubstrate()
    b, files = _alpha_build("rest api backend for notes", ["api"])
    build_rcpt = _alpha_build_receipt(substrate, files)
    broken = {k: "" for k, v in files.items()}  # all empty
    challenge = bp.challenge_build(substrate, build_rcpt.id, b, broken)
    assert not substrate.is_consumable(build_rcpt.id)
    substrate.resolve_challenge(challenge.id, "dismissed", note="rebuilt and re-verified")
    assert substrate.is_consumable(build_rcpt.id)


def test_resolve_upheld_holds_forever():
    substrate = sub.SharedSubstrate()
    b, files = _alpha_build("rest api backend for notes", ["api"])
    build_rcpt = _alpha_build_receipt(substrate, files)
    broken = {k: v for k, v in files.items() if not k.endswith("requirements.txt")}
    challenge = bp.challenge_build(substrate, build_rcpt.id, b, broken)
    substrate.resolve_challenge(challenge.id, "upheld", note="build truly diverged")
    assert not substrate.is_consumable(build_rcpt.id)
    assert challenge.status == "resolved" and challenge.verdict == "upheld"
