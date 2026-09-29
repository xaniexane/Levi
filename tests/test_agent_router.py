"""Tests for core/levi/agent/router.py (Chauncey's fixed request router).

Plain speech: we prove the router (1) escalates when the local answer is too
uncertain and the teacher flag is on, (2) falls back to the local answer when
the teacher dies instead of crashing, (3) actually honors the threshold env
var, (4) hides raw prompts in the log when the privacy gate is off, and
(5) closes the training loop with an append-only outcome record.
"""

import hashlib
import json
import os
from pathlib import Path

import pytest

from levi.agent.router import Router, StubLocal, make_router


class ConfidentLocal(StubLocal):
    def confidence(self, prompt, answer):
        return 0.99


class UnsureLocal(StubLocal):
    def confidence(self, prompt, answer):
        return 0.10


class WorkingTeacher:
    name = "gemini"
    last_usage = (12, 30, 120.5)

    def answer(self, prompt):
        return "[gemini] considered answer"

    def confidence(self, prompt, answer):
        return 0.95


class FailingTeacher:
    name = "gemini"

    def answer(self, prompt):
        raise ConnectionError("cloud unreachable")

    def confidence(self, prompt, answer):
        return 0.95


def _router(tmp_path, local, teachers=None, log_raw_text=True):
    return Router(
        local_model=local,
        cloud_teachers=teachers or {},
        threshold=0.62,
        log_path=tmp_path / "esc.jsonl",
        log_raw_text=log_raw_text,
    )


def _rows(log_path):
    return [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]


def test_low_confidence_escalates_to_enabled_teacher(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_CLOUD_GEMINI", "1")
    r = _router(tmp_path, UnsureLocal(), {"gemini": WorkingTeacher()})
    result = r.route("some long uncertain request about deep things")
    assert result.escalated is True
    assert result.teacher_used == "gemini"
    assert result.final_answer == "[gemini] considered answer"
    assert result.prompt_tokens == 12 and result.completion_tokens == 30
    rows = _rows(r.log_path)
    assert rows[0]["kind"] == "escalation"
    assert rows[0]["escalated"] is True
    assert rows[0]["outcome"] is None


def test_teacher_failure_falls_back_to_local_and_records_failure(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("LEVI_CLOUD_GEMINI", "1")
    r = _router(tmp_path, UnsureLocal(), {"gemini": FailingTeacher()})
    result = r.route("some long uncertain request")
    assert result.escalated is True  # the attempt is marked
    assert result.teacher_error.startswith("ConnectionError")
    assert result.final_answer == result.local_answer  # local stands in
    rows = _rows(r.log_path)
    assert "cloud unreachable" in rows[0]["teacher_error"]


def test_threshold_env_override_is_honored(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_CLOUD_GEMINI", "1")
    monkeypatch.setenv("LEVI_CONFIDENCE_THRESHOLD", "0.05")
    r = make_router(local_model=UnsureLocal(), teachers={"gemini": WorkingTeacher()})
    assert r.threshold == pytest.approx(0.05)
    result = r.route("short uncertain request")
    assert result.escalated is False  # 0.10 >= 0.05: no escalation


def test_high_confidence_never_escalates(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_CLOUD_GEMINI", "1")
    r = _router(tmp_path, ConfidentLocal(), {"gemini": WorkingTeacher()})
    result = r.route("hi")
    assert result.escalated is False
    assert result.final_answer == result.local_answer


def test_prompt_hiding_gate_logs_hashes_only(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_CLOUD_GEMINI", "1")
    monkeypatch.setenv("LEVI_ESCALATION_LOG_PROMPTS", "0")
    r = _router(
        tmp_path, UnsureLocal(), {"gemini": WorkingTeacher()}, log_raw_text=False
    )
    secret = "user said their password is hunter2"
    r.route(secret)
    row = _rows(r.log_path)[0]
    digest = hashlib.sha256(secret.encode()).hexdigest()
    assert row["prompt"] == digest
    assert secret not in json.dumps(row)
    # log file permissions locked down
    mode = os.stat(r.log_path).st_mode & 0o777
    assert mode == 0o600


def test_record_outcome_appends_outcome_row(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_CLOUD_GEMINI", "1")
    r = _router(tmp_path, UnsureLocal(), {"gemini": WorkingTeacher()})
    result = r.route("some uncertain request")
    r.record_outcome(result.request_id, "kept", note="teacher answer was good")
    rows = _rows(r.log_path)
    assert len(rows) == 2
    # original row untouched
    assert rows[0]["kind"] == "escalation"
    assert rows[0]["outcome"] is None
    # outcome appended, keyed by request_id
    assert rows[1]["kind"] == "outcome"
    assert rows[1]["request_id"] == result.request_id
    assert rows[1]["outcome"] == "kept"
    assert rows[1]["note"] == "teacher answer was good"
