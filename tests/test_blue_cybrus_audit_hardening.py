"""BLUE regression tests: Cybrus audit hardening (L4 + L10).

Guards the RED-1 audit fixes at the LAW level (behavior, not
implementation): the assertions hold regardless of the scrub cap or the
anchor's storage format.

  L4  Audit records carry metadata only — caller-shaped over-long
      strings never land verbatim in the trail (a length + sha256
      descriptor preserves correlation without storing content).
  L10 State only ever grows — a forward-linked chain cannot detect a
      deleted tail, so the engine maintains a truncation anchor and
      verify() fails closed on any tail deletion, log wipe, or append
      that follows detected tampering.

Glyph: ⚖️ (L1–L5 verification pass, 2026-09-22).
"""

import hashlib
import threading

import pytest

from levi.cybrus.audit import AuditEngine


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _audit_path(home):
    return home / ".levi" / "cybrus" / "audit.jsonl"


def _raw_bytes(home):
    return _audit_path(home).read_bytes()


class TestIntactLogVerifies:
    def test_chain_links_and_sequence_are_consistent(self, home):
        eng = AuditEngine()
        records = [
            eng.append(f"blue.evt.{i}", "blue-tester", {"i": i}) for i in range(5)
        ]
        assert eng.count() == 5
        ok, bad = eng.verify()
        assert (ok, bad) == (True, None)
        for i, rec in enumerate(records):
            assert rec["seq"] == i
        for prev_rec, rec in zip(records, records[1:]):
            assert rec["prev"] == prev_rec["hash"]


class TestTruncationIsEvident:
    def test_tail_truncation_fails_verify(self, home):
        eng = AuditEngine()
        for i in range(5):
            eng.append(f"blue.evt.{i}", "blue-tester", {"i": i})
        path = _audit_path(home)
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 5
        # Adversary deletes the two most recent records.
        path.write_text("\n".join(lines[:3]) + "\n", encoding="utf-8")

        ok, _bad = AuditEngine().verify()
        assert ok is False

    def test_append_after_truncation_preserves_gap_evidence(self, home):
        """When an append follows out-of-band truncation, the engine must
        not silently re-bless the altered ledger: evidence of the
        deletion (expected vs found count) must survive IN the
        tamper-evident log itself, where the hash chain then protects
        it."""
        eng = AuditEngine()
        for i in range(3):
            eng.append(f"blue.evt.{i}", "blue-tester", {"i": i})
        path = _audit_path(home)
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[:1]) + "\n", encoding="utf-8")

        eng.append("blue.evt.after", "blue-tester", {"i": 99})

        gap_records = [
            r
            for r in eng.tail(10)
            if isinstance(r.get("details"), dict)
            and "expected_count" in r["details"]
            and "found_count" in r["details"]
        ]
        assert gap_records, "no in-band record documents the tail deletion"
        gap = gap_records[0]["details"]
        assert gap["expected_count"] == 3
        assert gap["found_count"] == 1
        # The gap evidence is itself hash-chained: the chain still verifies
        # and any later deletion of the gap record breaks it again.
        ok, _bad = eng.verify()
        assert ok is True

    def test_concurrent_appends_keep_chain_intact(self, home):
        eng = AuditEngine()
        errors = []

        def worker(n):
            try:
                for i in range(25):
                    eng.append(f"blue.t{n}.{i}", "blue-thread", {"n": n, "i": i})
            except Exception as exc:  # pragma: no cover - diagnostic
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert eng.count() == 200
        ok, bad = eng.verify()
        assert (ok, bad) == (True, None), f"chain broken at {bad}"
        seqs = sorted(r["seq"] for r in eng.tail(200))
        assert seqs == list(range(200))


class TestMetadataOnly:
    SECRET = "BLUE-PROBE-SECRET-" + "x" * 5000

    def test_overlong_secret_never_lands_verbatim(self, home):
        eng = AuditEngine()
        eng.append("blue.egress", "blue-tester", {"purpose": self.SECRET})

        raw = _raw_bytes(home)
        assert self.SECRET.encode("utf-8") not in raw
        for rec in eng.tail(5):
            assert self.SECRET not in repr(rec)

        # Correlation is preserved: length + digest of the redacted value.
        rec = eng.tail(1)[0]
        blob = repr(rec["details"])
        assert str(len(self.SECRET)) in blob
        assert hashlib.sha256(self.SECRET.encode("utf-8")).hexdigest() in blob

    def test_nested_blob_is_scrubbed(self, home):
        blob = "BLUE-NESTED-" + "y" * 4000
        eng = AuditEngine()
        eng.append(
            "blue.internal", "blue-tester", {"meta": {"blob": blob, "note": "ok"}}
        )

        raw = _raw_bytes(home)
        assert blob.encode("utf-8") not in raw
        ok, _bad = eng.verify()
        assert ok is True

    def test_short_metadata_passes_through_verbatim(self, home):
        """Normal operational metadata (digests, ids, stages) is untouched —
        the guard must not blind the audit trail to legitimate fields."""
        eng = AuditEngine()
        digest = "d" * 64
        eng.append(
            "blue.stage",
            "blue-tester",
            {"stage": "sealed", "doc_digest": digest, "attempt": 3},
        )
        rec = eng.tail(1)[0]
        assert rec["details"]["stage"] == "sealed"
        assert rec["details"]["doc_digest"] == digest
        assert rec["details"]["attempt"] == 3
        ok, _bad = eng.verify()
        assert ok is True
