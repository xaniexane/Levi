"""BLUE regression tests: audit integrity (RED-1 batch A, HIGH + MEDIUM,
L4/L10).

Fail-closed: tail truncation (or a full wipe) is detected by the
truncation anchor — verify() no longer blesses a shortened chain.
Over-long caller-shaped strings are scrubbed to digest+length
descriptors (L4: metadata only). The legitimate path — appends verify,
byte-tampering is still caught at the right index, short fields stay
readable — keeps working.
"""

import hashlib
import json

import pytest

from levi.cybrus.audit import AuditEngine


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _audit_path(home):
    return home / ".levi" / "cybrus" / "audit.jsonl"


def _state_path(home):
    return home / ".levi" / "cybrus" / "audit.state.json"


class TestTruncationAnchor:
    def test_anchor_written_on_append(self, home):
        eng = AuditEngine()
        eng.append("evt", "tester", {"i": 1})
        state = json.loads(_state_path(home).read_text(encoding="utf-8"))
        assert state["count"] == 1
        assert state["tip_hash"] == eng.tail(1)[0]["hash"]

    def test_truncated_tail_detected(self, home):
        eng = AuditEngine()
        for i in range(5):
            eng.append(f"evt.{i}", "tester", {"i": i})
        assert eng.verify() == (True, None)
        path = _audit_path(home)
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[:3]) + "\n", encoding="utf-8")
        ok, bad = AuditEngine().verify()
        assert ok is False
        assert bad == 3  # the first missing anchored record

    def test_wipe_detected(self, home):
        eng = AuditEngine()
        for i in range(3):
            eng.append(f"evt.{i}", "tester", {"i": i})
        _audit_path(home).write_text("", encoding="utf-8")
        ok, _ = AuditEngine().verify()
        assert ok is False

    def test_append_after_truncation_leaves_gap_evidence(self, home):
        eng = AuditEngine()
        for i in range(5):
            eng.append(f"evt.{i}", "tester", {"i": i})
        path = _audit_path(home)
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[:3]) + "\n", encoding="utf-8")
        # The next append detects the gap and records it in-band.
        eng.append("evt.after", "tester", {})
        gaps = [
            r for r in AuditEngine().tail(10) if r["event"] == "audit.tail_gap"
        ]
        assert len(gaps) == 1
        assert gaps[0]["details"]["expected_count"] == 5
        assert gaps[0]["details"]["found_count"] == 3
        # Chain + anchor are consistent again; the evidence is in the log.
        assert AuditEngine().verify() == (True, None)

    def test_unanchored_nonempty_log_fails_closed(self, home):
        eng = AuditEngine()
        eng.append("evt", "tester", {})
        _state_path(home).unlink()  # anchor lost: legacy / tampered state
        ok, _ = AuditEngine().verify()
        assert ok is False

    def test_reanchor_repairs_legacy_log_explicitly(self, home):
        eng = AuditEngine()
        eng.append("evt", "tester", {})
        _state_path(home).unlink()
        assert AuditEngine().verify()[0] is False
        result = AuditEngine().reanchor()
        assert result["count"] == 2  # 1 record + the reanchor event
        assert AuditEngine().verify() == (True, None)
        events = [r["event"] for r in AuditEngine().tail(5)]
        assert "audit.state_reanchored" in events

    def test_reanchor_refuses_broken_chain(self, home):
        eng = AuditEngine()
        eng.append("evt", "tester", {"note": "aaaa"})
        path = _audit_path(home)
        lines = path.read_text(encoding="utf-8").splitlines()
        lines[0] = lines[0].replace("aaaa", "aaab")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _state_path(home).unlink(missing_ok=True)
        with pytest.raises(ValueError):
            AuditEngine().reanchor()

    def test_empty_log_verifies(self, home):
        assert AuditEngine().verify() == (True, None)


class TestPayloadScrubbing:
    SECRET = "SK-BLUE-" + "y" * 5000

    def test_overlong_string_becomes_digest_descriptor(self, home):
        eng = AuditEngine()
        eng.append("evt", "tester", {"blob": self.SECRET, "ok": "short"})
        rec = eng.tail(1)[0]
        blob = rec["details"]["blob"]
        assert blob["__audit_redacted__"] == "overlong-string"
        assert blob["sha256"] == hashlib.sha256(self.SECRET.encode()).hexdigest()
        assert blob["len"] == len(self.SECRET)
        # Short fields pass through verbatim.
        assert rec["details"]["ok"] == "short"
        # The secret appears nowhere in the log file.
        raw = _audit_path(home).read_text(encoding="utf-8")
        assert self.SECRET not in raw

    def test_nested_overlong_strings_scrubbed(self, home):
        eng = AuditEngine()
        eng.append(
            "evt", "tester", {"meta": {"blob": self.SECRET}, "lst": [self.SECRET]}
        )
        dumped = json.dumps(eng.tail(5))
        assert self.SECRET not in dumped
        assert eng.verify() == (True, None)

    def test_boundary_256_chars_passes_through(self, home):
        eng = AuditEngine()
        exact = "z" * 256
        eng.append("evt", "tester", {"v": exact})
        assert eng.tail(1)[0]["details"]["v"] == exact
        over = "z" * 257
        eng.append("evt", "tester", {"v": over})
        assert eng.tail(1)[0]["details"]["v"]["len"] == 257


class TestLegitimatePathUnchanged:
    def test_appends_verify_and_tamper_caught_at_index(self, home):
        eng = AuditEngine()
        eng.append("one", "owner", {"note": "aaaa"})
        eng.append("two", "owner", {"note": "bbbb"})
        eng.append("three", "owner", {"note": "cccc"})
        assert eng.verify() == (True, None)
        path = _audit_path(home)
        lines = path.read_text(encoding="utf-8").splitlines()
        lines[1] = lines[1].replace("bbbb", "bbbc")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok, bad = AuditEngine().verify()
        assert ok is False
        assert bad == 1

    def test_tail_and_count_still_work(self, home):
        eng = AuditEngine()
        for i in range(5):
            eng.append(f"event-{i}", "owner")
        assert eng.count() == 5
        assert [r["event"] for r in eng.tail(2)] == ["event-3", "event-4"]
