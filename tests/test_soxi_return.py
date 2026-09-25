"""Proof tests for the SOXI teaching return loop.

Property/invariant checks over the laws in
``levi/soxi/return/laws.py`` — honest invariant tests, not a formal
proof. Storage is isolated per test via LEVI_SOXI_RETURN_DIR.

Covered: intake receipts + raw immutability, verification verdicts,
malformed-batch quarantine, re-teach duplicate detection,
receipt chain integrity, refinement versioning, verdict-gated
promotion, promotion reversibility, sync-package round-trips, and
the cadence dial.
"""

from __future__ import annotations

import json

import pytest

from levi.soxi.return_loop import (
    build_package,
    get_config,
    intake,
    promote_batch,
    refine_batch,
    revert_promotion,
    set_cadence_days,
    store_count,
    sync_due,
    verify_batch,
    version_vector,
)
from levi.soxi.return_loop import sync as _sync
from levi.soxi.return_loop.common import (
    base_dir,
    read_chain,
    verify_chain,
)
from levi.soxi.return_loop.inbox import arrivals_path
from levi.soxi.return_loop.verify import verdicts_path


@pytest.fixture
def iso(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_SOXI_RETURN_DIR", str(tmp_path / "return"))
    return tmp_path


def lesson(kind="qa", topic="arithmetic", text="Q: What is 2 + 3? A: 5.",
           persona="void", topic_id=None):
    l = {
        "persona_condition": {
            "persona_id": persona, "role": "mentor", "tone": "deadpan",
            "ei": {"presence": 0.85, "empathy": 0.55, "regulation": 0.95,
                   "relational": 0.65, "integrity": 1.0},
            "traits": ["terse", "high-signal", "anti-hype"],
            "provisional": True,
        },
        "kind": kind,
        "topic": topic,
        "text": text,
    }
    if topic_id:
        l["topic_id"] = topic_id
    return l


def make_batch(iso, name, lessons, manifest=None):
    p = iso / (name + ".jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for l in lessons:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")
    if manifest is not None:
        m = iso / (name + ".manifest.json")
        m.write_text(json.dumps(manifest), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Intake: receipts, raw immutability
# ---------------------------------------------------------------------------


def test_intake_receipt_and_raw_immutable(iso):
    p = make_batch(iso, "b1", [lesson()],
                   manifest={"batch_id": "b1", "teacher": "grok",
                             "date_from": "2026-09-22", "date_to": "2026-09-22"})
    rec = intake(p)
    assert rec["batch_id"] == "b1"
    assert rec["teacher"] == "grok"
    raw = base_dir() / "raw" / "b1.jsonl"
    assert raw.exists()
    before = raw.read_bytes()
    # raw must never change: a second intake of the same batch id
    # keeps the original bytes
    intake(p)
    assert raw.read_bytes() == before
    ok, errors = verify_chain(arrivals_path())
    assert ok, errors


def test_intake_rejects_non_jsonl(iso):
    p = iso / "nope.txt"
    p.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        intake(p)


# ---------------------------------------------------------------------------
# Verification: verdicts
# ---------------------------------------------------------------------------


def test_clean_batch_passes(iso):
    p = make_batch(iso, "clean", [
        lesson(topic_id="arith-001"),
        lesson(kind="reasoning", topic="algebra",
               text="Solve x+2=5: subtract 2 from both sides, x=3.",
               topic_id="alg-001"),
    ], manifest={"batch_id": "clean"})
    intake(p)
    rec = verify_batch("clean")
    assert rec["verdict"] == "PASS"
    assert rec["clean_count"] == 2


def test_hype_and_bad_arithmetic_pass_with_corrections(iso):
    p = make_batch(iso, "fixme", [
        lesson(topic_id="arith-010", text="Q: What is 6 * 7? A: 41."),
        lesson(topic_id="alg-010", topic="algebra",
               text="An amazing trick for factoring quadratics."),
    ], manifest={"batch_id": "fixme"})
    intake(p)
    rec = verify_batch("fixme")
    assert rec["verdict"] == "PASS_WITH_CORRECTIONS"
    assert len(rec["corrections_needed"]) == 2
    reasons = " ".join(r for c in rec["corrections_needed"] for r in c["reasons"])
    assert "wrong" in reasons and "hype" in reasons


def test_malformed_batch_quarantined_bytes_preserved(iso):
    p = iso / "broken.jsonl"
    p.write_text('{"kind": "qa"}\nNOT JSON AT ALL\n', encoding="utf-8")
    intake(p)
    rec = verify_batch("broken")
    assert rec["verdict"] == "QUARANTINE"
    assert len(rec["malformed"]) >= 1
    q = base_dir() / "quarantine" / "broken.jsonl"
    assert q.exists()
    # nothing thrown away: quarantine holds the exact original bytes
    assert q.read_bytes() == (base_dir() / "raw" / "broken.jsonl").read_bytes()


def test_non_ascii_and_unknown_frame_corrected(iso):
    p = make_batch(iso, "odd", [
        lesson(topic_id="geo-001", topic="geometry",
               text="Triangles have 3 sides — the acute kind."),
        lesson(topic_id="phy-001", topic="physics", persona="oracle",
               text="Force equals mass times acceleration."),
    ], manifest={"batch_id": "odd"})
    intake(p)
    rec = verify_batch("odd")
    assert rec["verdict"] == "PASS_WITH_CORRECTIONS"
    assert len(rec["corrections_needed"]) == 2


def test_double_verdict_refused(iso):
    p = make_batch(iso, "once", [lesson(topic_id="arith-020")],
                   manifest={"batch_id": "once"})
    intake(p)
    verify_batch("once")
    with pytest.raises(ValueError):
        verify_batch("once")


# ---------------------------------------------------------------------------
# R4: re-teach duplicate detection
# ---------------------------------------------------------------------------


def test_reteach_duplicate_caught(iso):
    same = lesson(topic_id="arith-030")
    p1 = make_batch(iso, "first", [same], manifest={"batch_id": "first"})
    intake(p1)
    assert verify_batch("first")["verdict"] == "PASS"
    p2 = make_batch(iso, "second", [dict(same)], manifest={"batch_id": "second"})
    intake(p2)
    rec = verify_batch("second")
    assert rec["verdict"] == "PASS_WITH_CORRECTIONS"
    assert any("re-teach" in r
               for c in rec["corrections_needed"] for r in c["reasons"])


# ---------------------------------------------------------------------------
# Chain integrity: tamper evidence on verdicts
# ---------------------------------------------------------------------------


def test_verdict_chain_break_detected(iso):
    p = make_batch(iso, "chain", [lesson(topic_id="arith-040")],
                   manifest={"batch_id": "chain"})
    intake(p)
    verify_batch("chain")
    vp = verdicts_path()
    # simulate tampering: flip a byte in the verdict file
    lines = vp.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("PASS", "P4SS")
    vp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok, errors = verify_chain(vp)
    assert not ok and errors


# ---------------------------------------------------------------------------
# Refinement: versioned corrections, raw originals untouched
# ---------------------------------------------------------------------------


def test_refine_produces_versioned_corrections(iso):
    p = make_batch(iso, "ref", [
        lesson(topic_id="arith-050", text="Q: What is 6 * 7? A: 41."),
    ], manifest={"batch_id": "ref"})
    intake(p)
    verify_batch("ref")
    raw_before = (base_dir() / "raw" / "ref.jsonl").read_bytes()
    out = refine_batch("ref")
    assert out["corrections"] == 1
    assert (base_dir() / "raw" / "ref.jsonl").read_bytes() == raw_before
    corr = json.loads(
        (base_dir() / "corrections" / "ref.jsonl").read_text(encoding="utf-8"))
    assert corr["kind"] == "correction"
    assert corr["correction_of"]
    assert corr["version"] == 2


def test_refine_quarantined_batch_refused(iso):
    p = iso / "qref.jsonl"
    p.write_text("garbage\n", encoding="utf-8")
    intake(p)
    verify_batch("qref")
    with pytest.raises(ValueError):
        refine_batch("qref")


# ---------------------------------------------------------------------------
# Promotion: verdict-gated, duplicates skipped, reversible
# ---------------------------------------------------------------------------


def test_promote_requires_verdict(iso):
    p = make_batch(iso, "nov", [lesson(topic_id="arith-060")],
                   manifest={"batch_id": "nov"})
    intake(p)
    with pytest.raises(ValueError):
        promote_batch("nov")


def test_promote_verified_only_corrections_versioned(iso):
    p = make_batch(iso, "prom", [
        lesson(topic_id="arith-070"),
        lesson(topic_id="arith-071", text="Q: What is 6 * 7? A: 41."),
    ], manifest={"batch_id": "prom", "teacher": "grok"})
    intake(p)
    assert verify_batch("prom")["verdict"] == "PASS_WITH_CORRECTIONS"
    refine_batch("prom")
    out = promote_batch("prom")
    # the clean lesson promotes; the flawed lesson's slot is taken by
    # its correction-kind version, not the flawed original
    assert out["lessons_promoted"] == 2
    sc = store_count()
    assert sc["active"] == 2 and sc["reverted"] == 0
    # provenance landed
    import sqlite3
    conn = sqlite3.connect(str(base_dir() / "store.db"))
    rows = conn.execute(
        "SELECT kind, version, batch_id, teacher FROM lessons WHERE reverted = 0"
    ).fetchall()
    conn.close()
    kinds = sorted(r[0] for r in rows)
    assert kinds == ["correction", "qa"]
    assert all(r[2] == "prom" and r[3] == "grok" for r in rows)


def test_revert_promotion(iso):
    p = make_batch(iso, "rev", [lesson(topic_id="arith-080")],
                   manifest={"batch_id": "rev"})
    intake(p)
    verify_batch("rev")
    out = promote_batch("rev")
    back = revert_promotion(out["promotion_id"])
    assert back["lessons_reverted"] == 1
    sc = store_count()
    assert sc["active"] == 0 and sc["reverted"] == 1
    with pytest.raises(ValueError):
        revert_promotion(out["promotion_id"])  # already reverted


# ---------------------------------------------------------------------------
# Sync: package round-trips, cadence dial, due logic
# ---------------------------------------------------------------------------


def test_cadence_default_three_and_flip(iso):
    assert get_config()["cadence_days"] == 3
    cfg = set_cadence_days(1)
    assert cfg["cadence_days"] == 1
    assert get_config()["cadence_days"] == 1
    with pytest.raises(ValueError):
        set_cadence_days(0)


def test_sync_package_roundtrips(iso):
    p = make_batch(iso, "syn", [
        lesson(topic_id="arith-090"),
        lesson(topic_id="his-090", topic="history",
               text="The Roman Empire fell in 476 CE (western)."),
    ], manifest={"batch_id": "syn"})
    intake(p)
    verify_batch("syn")
    promote_batch("syn")
    out = build_package()
    ok, msg = _sync.roundtrip_ok(out["path"])
    assert ok, msg
    manifest = json.loads(
        (open(out["path"] + "/manifest.json").read())
    )
    assert manifest["delta_count"] == 2
    assert set(manifest["files"]) == {"manifest.json", "deltas.jsonl",
                                      "receipts.jsonl", "version_vector.json"}
    assert manifest["version_vector"]["promotions"] >= 1


def test_sync_due_logic(iso):
    due, info = sync_due()
    assert due is False  # nothing promoted yet
    p = make_batch(iso, "due", [lesson(topic_id="arith-095")],
                   manifest={"batch_id": "due"})
    intake(p)
    verify_batch("due")
    promote_batch("due")
    due, _ = sync_due()
    assert due is True  # content waiting, no package yet
    build_package()
    due, info = sync_due()
    assert due is False  # just shipped
    assert info["cadence_days"] == 3


def test_chains_all_intact_after_pipeline(iso):
    p = make_batch(iso, "full", [lesson(topic_id="arith-100")],
                   manifest={"batch_id": "full"})
    intake(p)
    verify_batch("full")
    refine_batch("full")
    promote_batch("full")
    base = base_dir()
    for name in ("arrivals", "verdicts", "refinements", "promotions"):
        ok, errors = verify_chain(base / (name + ".jsonl"))
        assert ok, (name, errors)
    vv = version_vector()
    assert set(vv) == {"arrivals", "verdicts", "refinements", "promotions"}
