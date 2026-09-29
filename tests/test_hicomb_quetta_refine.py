"""Tests for the Quetta-Pan refinement pass in Pollen's save pipeline.

Laws under test (see quetta_refine.py):
  Q1 GATE-STANDS   agent pass covered by the abort gate — file byte-identical.
  Q2 ADVISORY      suggestions apply only on builder confirm; receipted always.
  Q3 DETERMINISTIC same text + same genome state = same report (modulo ts).
  Q4 OFFLINE       no network imports in the refine path (grep gate).
  Q5 NO-SILENT-DELETE refined text re-runs Pollen's gates before the write.
"""

import json
from pathlib import Path


from levi.hicomb.buffer import Buffer
from levi.hicomb.pipeline import save_pipeline
from levi.hicomb.quetta_refine import (
    INSTANCE_ID,
    QuettaRefiner,
    RefineReceipt,
    RefineReport,
    _utcnow,
)

BARE_EXCEPT_PY = "try:\n    x = 1\nexcept:\n    pass\n"
CLEAN_PY = "x = 1\n"


def _refiner(tmp_path: Path) -> QuettaRefiner:
    return QuettaRefiner(
        store_dir=tmp_path / "store",
        log_path=tmp_path / "refine.jsonl",
    )


def _strip_ts(report: RefineReport) -> dict:
    return {
        "language": report.language,
        "has_changes": report.has_changes,
        "suggestions": report.suggestions,
        "suppressed": report.suppressed,
        "fix_ids": report.fix_ids,
        "new_content": report.new_content,
        "receipts": [
            {k: v for k, v in r.as_dict().items() if k != "ts"}
            for r in report.receipts
        ],
    }


# ---- Q2: advisory, receipted --------------------------------------------

def test_review_emits_receipt_per_suggestion(tmp_path):
    refiner = _refiner(tmp_path)
    report = refiner.review(BARE_EXCEPT_PY, "python", "t.py")
    assert report.has_changes
    assert any(s["id"] == "PY_BARE_EXCEPT" for s in report.suggestions)
    for s in report.suggestions:
        matches = [r for r in report.receipts if r.rule_id == s["id"]]
        assert matches, f"no receipt for {s['id']}"
        for r in matches:
            assert r.decision == "advisory"
            assert r.applied is False
            assert r.instance == INSTANCE_ID


def test_review_unsupported_language_is_honest(tmp_path):
    refiner = _refiner(tmp_path)
    report = refiner.review("# hello\n", "markdown", "t.md")
    assert not report.has_changes
    assert report.receipts[0].decision == "unsupported-language"
    text, receipts = refiner.decide(report, "confirmed")
    assert text is None
    assert receipts[0].decision == "unsupported-language"


def test_review_clean_python_no_changes(tmp_path):
    refiner = _refiner(tmp_path)
    report = refiner.review(CLEAN_PY, "python", "t.py")
    assert not report.has_changes
    assert report.new_content is None


# ---- Q3: determinism -----------------------------------------------------

def test_review_deterministic_same_store_state(tmp_path):
    r1 = _refiner(tmp_path / "a")
    r2 = _refiner(tmp_path / "b")
    rep1 = r1.review(BARE_EXCEPT_PY, "python", "t.py")
    rep2 = r2.review(BARE_EXCEPT_PY, "python", "t.py")
    assert _strip_ts(rep1) == _strip_ts(rep2)


# ---- Q1/Q2/Q5: pipeline integration --------------------------------------

def test_confirm_applies_refinement(tmp_path):
    target = tmp_path / "app.py"
    buf = Buffer(BARE_EXCEPT_PY, path=str(target))
    store, log = tmp_path / "store", tmp_path / "refine.jsonl"
    result = save_pipeline(
        buf,
        run_quetta=True,
        confirm_refine=lambda report: True,
        refine_store_dir=str(store),
        refine_log_path=str(log),
    )
    assert result.ok
    assert result.quetta_refined
    assert result.quetta_suggestions >= 1
    written = target.read_text(encoding="utf-8")
    assert "except Exception:" in written
    assert "except:" not in written.replace("except Exception:", "")
    receipts = [json.loads(line) for line in log.read_text().splitlines()]
    applied = [r for r in receipts if r["rule_id"] == "PY_BARE_EXCEPT"]
    assert applied and all(r["decision"] == "confirmed" and r["applied"] for r in applied)


def test_decline_keeps_pollen_only(tmp_path):
    target = tmp_path / "app.py"
    buf = Buffer(BARE_EXCEPT_PY, path=str(target))
    store, log = tmp_path / "store", tmp_path / "refine.jsonl"
    result = save_pipeline(
        buf,
        run_quetta=True,
        confirm_refine=lambda report: False,
        refine_store_dir=str(store),
        refine_log_path=str(log),
    )
    assert result.ok
    assert not result.quetta_refined
    written = target.read_text(encoding="utf-8")
    assert "except Exception:" not in written  # Q2: nothing silently rewritten
    receipts = [json.loads(line) for line in log.read_text().splitlines()]
    declined = [r for r in receipts if r["rule_id"] == "PY_BARE_EXCEPT"]
    assert declined and all(r["decision"] == "declined" and not r["applied"] for r in declined)


def test_advisory_without_callback_applies_nothing(tmp_path):
    target = tmp_path / "app.py"
    buf = Buffer(BARE_EXCEPT_PY, path=str(target))
    store, log = tmp_path / "store", tmp_path / "refine.jsonl"
    result = save_pipeline(
        buf,
        run_quetta=True,
        refine_store_dir=str(store),
        refine_log_path=str(log),
    )
    assert result.ok
    assert not result.quetta_refined
    assert "except Exception:" not in target.read_text(encoding="utf-8")
    receipts = [json.loads(line) for line in log.read_text().splitlines()]
    assert receipts and all(r["decision"] == "advisory" for r in receipts)


def test_crashing_refiner_never_breaks_save(tmp_path, monkeypatch):
    """Advisory must never break the save: a crashing refiner degrades
    to skipped (reported via on_quetta_skip), the write proceeds."""
    from levi.hicomb import quetta_refine as qr_mod

    def _boom(self, text, language, path_hint="buffer"):
        raise RuntimeError("refiner exploded")

    monkeypatch.setattr(qr_mod.QuettaRefiner, "review", _boom)
    skipped = []
    target = tmp_path / "app.py"
    buf = Buffer(BARE_EXCEPT_PY, path=str(target))
    result = save_pipeline(
        buf,
        run_quetta=True,
        refine_store_dir=str(tmp_path / "store"),
        refine_log_path=str(tmp_path / "refine.jsonl"),
        on_quetta_skip=skipped.append,
    )
    assert result.ok, "save must survive a crashing refiner"
    assert not result.quetta_refined
    assert skipped and "exploded" in skipped[0]
    assert target.read_text(encoding="utf-8") == buf.get_text()


def test_gate_aborts_on_bad_agent_output(tmp_path, monkeypatch):
    """Q1: even a corrupted agent pass cannot touch the file."""
    import levi.hicomb.pipeline as pipeline_mod

    target = tmp_path / "app.py"
    target.write_text(CLEAN_PY, encoding="utf-8")
    before = target.read_bytes()
    buf = Buffer(CLEAN_PY, path=str(target))

    bad_report = RefineReport(
        language="python",
        path=str(target),
        has_changes=True,
        suggestions=[{"id": "FAKE", "title": "fake", "severity": "info"}],
        new_content="def broken(:\n",
        receipts=[
            RefineReceipt(
                ts=_utcnow(),
                instance=INSTANCE_ID,
                language="python",
                path=str(target),
                rule_id="FAKE",
                title="fake",
                severity="info",
                decision="advisory",
                applied=False,
            )
        ],
    )

    def fake_review(self, text, language, path_hint="buffer"):
        return bad_report

    monkeypatch.setattr(QuettaRefiner, "review", fake_review)
    result = pipeline_mod.save_pipeline(
        buf,
        run_quetta=True,
        confirm_refine=lambda report: True,
        refine_store_dir=str(tmp_path / "store"),
        refine_log_path=str(tmp_path / "refine.jsonl"),
    )
    assert not result.ok
    assert "quetta" in result.aborted
    assert target.read_bytes() == before  # Q1: byte-identical
    assert buf.get_text() == CLEAN_PY  # buffer restored to pre-format state


# ---- genome learning -----------------------------------------------------

def test_genome_learns_confirm_and_decline(tmp_path):
    from levi.quetta_pan import RiemGenome

    target = tmp_path / "app.py"
    store, log = tmp_path / "store", tmp_path / "refine.jsonl"

    buf = Buffer(BARE_EXCEPT_PY, path=str(target))
    save_pipeline(
        buf,
        run_quetta=True,
        confirm_refine=lambda report: True,
        refine_store_dir=str(store),
        refine_log_path=str(log),
    )
    genome = RiemGenome(store / ".quetta_genome.json")
    stats = genome.stats("PY_BARE_EXCEPT", "py")
    assert stats["successes"] >= 1

    buf2 = Buffer(BARE_EXCEPT_PY, path=str(target))
    save_pipeline(
        buf2,
        run_quetta=True,
        confirm_refine=lambda report: False,
        refine_store_dir=str(store),
        refine_log_path=str(log),
    )
    genome2 = RiemGenome(store / ".quetta_genome.json")
    stats2 = genome2.stats("PY_BARE_EXCEPT", "py")
    assert stats2["failures"] >= 1


# ---- Q4: offline grep gate -----------------------------------------------

def test_no_network_imports_in_refine_path():
    import levi.hicomb.quetta_refine as qr

    tokens = ("socket", "urllib", "requests", "http.client", "http.server", "ssl")
    files = [Path(qr.__file__)] + sorted(
        (Path(qr.__file__).parent.parent / "quetta_pan").glob("*.py")
    )
    assert files, "expected quetta_pan sources beside the test"
    for path in files:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            for token in tokens:
                assert token not in code, (
                    f"{path.name}:{lineno}: network token {token!r} in refine path"
                )
