"""Tests for the Dweller — the SI that dwells in the depths of the work.

Hermetic: every test runs with an isolated LEVI_HOME in tmp_path, no
network, no real waiting (watch sleeps are monkeypatched).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

from levi.automation.hitl import auto_approve, auto_deny
from levi.dweller import runners
from levi.dweller.ai import (
    BRIDGE_LABEL,
    BridgeError,
    completion_to_grind_request,
    job_to_completion,
    tool_schemas,
)
from levi.dweller.cli import cmd_dweller, register_dweller_parser
from levi.dweller.jobs import Job, JobStep, new_job
from levi.dweller.queue import (
    dweller_home,
    enqueue,
    get_job,
    journal_tail,
    list_jobs,
    load_receipt,
)
from levi.dweller.si import grind, grind_dry_run
from levi.dweller.si.grind import default_steps, grind_job_id


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """Isolated LEVI_HOME for queue tests."""
    h = tmp_path / "levi-home"
    h.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h))
    return h


@pytest.fixture()
def sweep_root(tmp_path):
    """Fixture tree with known module/line counts."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("\n".join("x = %d" % i for i in range(10)) + "\n")
    sub = root / "sub"
    sub.mkdir()
    (sub / "b.py").write_text("y = 1\ny = 2\ny = 3\ny = 4\ny = 5\n")
    (sub / "notes.txt").write_text("not python\n")
    cache = root / "__pycache__"
    cache.mkdir()
    (cache / "d.py").write_text("z = 9\n")
    return root


@pytest.fixture()
def xref_files(tmp_path):
    a = tmp_path / "a_def.py"
    a.write_text("def alpha_func():\n    pass\n\ndef beta_func():\n    pass\n")
    b1 = tmp_path / "b_use.py"
    b1.write_text("from a_def import alpha_func\n\nalpha_func()\n")
    b2 = tmp_path / "b_other.py"
    b2.write_text("print('nothing shared here')\n")
    return a, b1, b2


def _sweep_job(root, **kw):
    params = {"root": str(root)}
    return new_job(
        "repo-sweep",
        params=params,
        sandbox_root=str(root),
        steps=default_steps("repo-sweep", params),
        **kw,
    )


# ---------------------------------------------------------------------------
# job lifecycle: queued -> running -> done | failed, resumable
# ---------------------------------------------------------------------------


def test_full_lifecycle_done(home, sweep_root):
    job = enqueue(_sweep_job(sweep_root))
    assert job.state == "queued"
    receipt = grind(job, responder=auto_approve)
    assert receipt["decision"] == "executed"
    assert receipt["organ"] == "dweller"
    assert job.state == "done"
    assert job.terminal
    stored = get_job(job.id)
    assert stored.state == "done"
    # every job gets a receipt, on disk
    loaded = load_receipt(job.id)
    assert loaded["decision"] == "executed"
    assert loaded["steps"][0]["result"]["files_scanned"] == 2


def test_dry_run_executes_nothing(home, sweep_root):
    job = enqueue(_sweep_job(sweep_root))
    receipt = grind_dry_run(job)
    assert receipt["decision"] == "dry-run"
    assert job.state == "queued"  # untouched
    assert all(s.state == "queued" for s in job.steps)


def test_denied_gate_leaves_job_queued(home, sweep_root):
    job = enqueue(_sweep_job(sweep_root))
    receipt = grind(job, responder=auto_deny)
    assert receipt["decision"] == "denied"
    assert job.state == "queued"
    assert load_receipt(job.id)["decision"] == "denied"


def test_no_responder_fails_closed(home, sweep_root):
    job = enqueue(_sweep_job(sweep_root))
    receipt = grind(job, responder=None)  # nobody to ask: deny
    assert receipt["decision"] == "denied"


def test_failed_job_receipt_and_resume(home, sweep_root, monkeypatch):
    job = new_job(
        "repo-sweep",
        params={"root": str(sweep_root)},
        sandbox_root=str(sweep_root),
        steps=[
            JobStep(id="w1", label="first", kind="repo-sweep"),
            JobStep(id="w2", label="second", kind="repo-sweep"),
        ],
    )
    enqueue(job)
    real = runners.run_repo_sweep
    calls = {"n": 0}

    def flaky(root, sandbox_root, include_tests=True):
        calls["n"] += 1
        if calls["n"] == 2:
            raise runners.RunnerError("boom on second step")
        return real(root, sandbox_root, include_tests=include_tests)

    monkeypatch.setattr(runners, "run_repo_sweep", flaky)
    receipt = grind(job, responder=auto_approve)
    assert receipt["decision"] == "failed"
    assert job.state == "failed"
    assert [s.state for s in job.steps] == ["done", "failed"]
    assert "boom on second step" in job.steps[1].error
    # the failure itself has a receipt
    assert load_receipt(job.id)["decision"] == "failed"

    # resume continues from the first incomplete step — w1 is NOT re-run
    monkeypatch.setattr(runners, "run_repo_sweep", real)
    receipt2 = grind_job_id(job.id, responder=auto_approve, resume=True)
    assert receipt2["decision"] == "executed"
    final = get_job(job.id)  # reload: grind_job_id works on the stored job
    assert final.steps[0].attempts == 1
    assert final.steps[1].attempts == 2
    assert [s.state for s in final.steps] == ["done", "done"]
    assert final.state == "done"


def test_resume_from_wrong_state_raises(home, sweep_root):
    job = enqueue(_sweep_job(sweep_root))
    grind(job, responder=auto_approve)
    with pytest.raises(ValueError, match="cannot resume"):
        job.resume()


def test_jobs_list(home, sweep_root):
    j1 = enqueue(_sweep_job(sweep_root))
    j2 = enqueue(_sweep_job(sweep_root))
    ids = [j.id for j in list_jobs()]
    assert j1.id in ids and j2.id in ids


def test_get_unknown_job_raises(home):
    with pytest.raises(KeyError):
        get_job("nope")


def test_receipt_unknown_job_raises(home):
    with pytest.raises(KeyError):
        load_receipt("nope")


# ---------------------------------------------------------------------------
# sandbox law
# ---------------------------------------------------------------------------


def test_sandbox_violation_refused(home, tmp_path, sweep_root):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    job = new_job(
        "repo-sweep",
        params={"root": str(outside)},
        sandbox_root=str(sweep_root),
        steps=default_steps("repo-sweep", {}),
    )
    enqueue(job)
    receipt = grind(job, responder=auto_approve)
    assert receipt["decision"] == "refused"
    assert "sandbox" in receipt["note"]
    assert job.state == "queued"  # never started
    assert load_receipt(job.id)["decision"] == "refused"


def test_missing_sandbox_root_refused(home, sweep_root):
    job = new_job(
        "repo-sweep",
        params={"root": str(sweep_root)},
        sandbox_root="",
        steps=default_steps("repo-sweep", {}),
    )
    receipt = grind(job, responder=auto_approve)
    assert receipt["decision"] == "refused"
    assert "no sandbox root" in receipt["note"]


# ---------------------------------------------------------------------------
# runners
# ---------------------------------------------------------------------------


def test_repo_sweep_counts(sweep_root):
    out = runners.run_repo_sweep(str(sweep_root), sandbox_root=str(sweep_root))
    assert out["files_scanned"] == 2  # a.py + b.py; txt + __pycache__ excluded
    assert out["total_lines"] == 15
    assert out["per_dir"] == {".": 1, "sub": 1}
    assert out["largest_files"][0]["path"] == "a.py"


def test_repo_sweep_not_a_directory(tmp_path):
    with pytest.raises(runners.RunnerError, match="not a directory"):
        runners.run_repo_sweep(str(tmp_path / "missing"), sandbox_root=str(tmp_path))


def test_crossref_correctness(xref_files, tmp_path):
    a, b1, b2 = xref_files
    out = runners.run_crossref([str(a)], [str(b1), str(b2)], sandbox_root=str(tmp_path))
    assert out["set_a_files"] == 1
    assert out["set_b_files"] == 2
    assert out["hits"]["alpha_func"] == [str(b1)]
    assert "beta_func" not in out["hits"]  # defined in A, unused in B
    assert out["tokens_cross_referenced"] == len(out["hits"])


def test_crossref_missing_file_refused(tmp_path):
    with pytest.raises(runners.RunnerError, match="not a file"):
        runners.run_crossref(
            [str(tmp_path / "ghost.py")], [], sandbox_root=str(tmp_path)
        )


def test_watch_backoff_timings():
    delays = []
    states = iter([False, False, True])
    out = runners.run_watch(
        lambda: next(states),
        times=5,
        initial_delay_s=1.0,
        factor=2.0,
        sleep=delays.append,
    )
    assert out["satisfied"] is True
    assert out["attempts_made"] == 3
    assert delays == [1.0, 2.0]  # exponential backoff between attempts
    assert [a["attempt"] for a in out["attempts"]] == [1, 2, 3]


def test_watch_never_satisfied():
    out = runners.run_watch(
        lambda: False, times=2, initial_delay_s=0.01, sleep=lambda s: None
    )
    assert out["satisfied"] is False
    assert out["attempts_made"] == 2


def test_watch_condition_error_recorded():
    def bad():
        raise RuntimeError("probe exploded")

    out = runners.run_watch(bad, times=1, sleep=lambda s: None)
    assert out["satisfied"] is False
    assert "probe exploded" in out["attempts"][0]["error"]


def test_watch_rejects_zero_times():
    with pytest.raises(runners.RunnerError):
        runners.run_watch(lambda: True, times=0, sleep=lambda s: None)


def test_watch_engine_job_with_probe(home, tmp_path):
    probe = tmp_path / "signal.txt"
    probe.write_text("waiting\n")
    params = {
        "probe_path": str(probe),
        "probe_contains": "READY",
        "times": 2,
        "initial_delay_s": 0.01,
    }
    job = new_job(
        "watch",
        params=params,
        sandbox_root=str(tmp_path),
        steps=default_steps("watch", params),
    )
    enqueue(job)
    receipt = grind(job, responder=auto_approve, watch_sleep=lambda s: None)
    assert receipt["decision"] == "executed"
    assert receipt["steps"][0]["result"]["satisfied"] is False

    probe.write_text("READY now\n")
    job2 = new_job(
        "watch",
        params=params,
        sandbox_root=str(tmp_path),
        steps=default_steps("watch", params),
    )
    enqueue(job2)
    receipt2 = grind(job2, responder=auto_approve, watch_sleep=lambda s: None)
    assert receipt2["steps"][0]["result"]["satisfied"] is True
    assert receipt2["steps"][0]["result"]["attempts_made"] == 1


def test_unknown_grind_kind():
    with pytest.raises(runners.RunnerError, match="unknown grind kind"):
        default_steps("teleport", {})


def test_runner_kinds_known():
    assert set(runners.RUNNER_KINDS) == {"repo-sweep", "crossref", "watch"}


# ---------------------------------------------------------------------------
# queue: LEVI_HOME override, journaling
# ---------------------------------------------------------------------------


def test_queue_uses_levi_home(home, sweep_root):
    job = enqueue(_sweep_job(sweep_root))
    assert dweller_home() == home / ".levi" / "dweller"
    assert (home / ".levi" / "dweller" / "jobs" / (job.id + ".json")).exists()
    events = [e["event"] for e in journal_tail(home=dweller_home())]
    assert "enqueued" in events


def test_queue_journals_transitions(home, sweep_root):
    job = enqueue(_sweep_job(sweep_root))
    grind(job, responder=auto_approve)
    events = [e["event"] for e in journal_tail(home=dweller_home())]
    for expected in ("enqueued", "started", "step-running", "step-done", "done"):
        assert expected in events


def test_enqueue_duplicate_id_refused(home, sweep_root):
    job = _sweep_job(sweep_root, job_id="fixed-id")
    enqueue(job)
    with pytest.raises(ValueError, match="already queued"):
        enqueue(_sweep_job(sweep_root, job_id="fixed-id"))


def test_job_serialization_round_trip(sweep_root):
    job = _sweep_job(sweep_root)
    clone = Job.from_dict(json.loads(json.dumps(job.to_dict())))
    assert clone.id == job.id
    assert clone.state == job.state
    assert [s.id for s in clone.steps] == [s.id for s in job.steps]


# ---------------------------------------------------------------------------
# SI / AI separation + bridge labels
# ---------------------------------------------------------------------------


def test_si_never_imports_ai():
    # Clean-interpreter check: importing the SI core must not pull the
    # AI bridge in. (The test module itself imports the bridge, so we
    # cannot use sys.modules of this process.)
    import subprocess

    code = (
        "import sys; sys.path.insert(0, 'core');"
        "import levi.dweller.si, levi.dweller.si.grind;"
        "assert 'levi.dweller.ai' not in sys.modules, 'si imported ai';"
        "print('clean')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert proc.returncode == 0, proc.stderr
    assert "clean" in proc.stdout
    # Source check: no *import statement* in si/ may reference the ai
    # package (docstrings may mention it — that is not an import).
    import re as _re

    _import_ai = _re.compile(r"^\s*(from|import)\s+[\w.]*\bai\b")
    si_dir = Path(runners.__file__).parent / "si"
    for path in si_dir.glob("*.py"):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            assert not _import_ai.match(line), (path, lineno, line)


def test_bridge_carries_its_label():
    expected = (
        "AI counterpart bridge for dweller — conventional-protocol "
        "interface; the SI core is authoritative; this bridge claims nothing"
    )
    assert BRIDGE_LABEL == expected
    bridge_src = Path(runners.__file__).parent / "ai" / "bridge.py"
    assert expected in bridge_src.read_text()


def test_bridge_tool_schemas():
    names = [s["name"] for s in tool_schemas()]
    assert names == ["dweller.grind", "dweller.jobs", "dweller.receipt"]
    for s in tool_schemas():
        assert "SI core is authoritative" in s["description"]


def test_bridge_job_completion_round_trip(home, sweep_root):
    job = enqueue(_sweep_job(sweep_root))
    completion = job_to_completion(job.to_dict())
    assert completion["object"] == "chat.completion"
    assert completion["bridge"] == BRIDGE_LABEL
    req = completion_to_grind_request(completion)
    assert req["kind"] == "repo-sweep"
    assert req["sandbox_root"] == str(sweep_root)


def test_bridge_refuses_unmarked_completion():
    with pytest.raises(BridgeError, match="marker"):
        completion_to_grind_request(
            {"choices": [{"message": {"content": "Job: x (repo-sweep)"}}]}
        )


def test_no_network_imports_in_dweller():
    base = Path(runners.__file__).parent
    banned = ("import socket", "urllib", "requests", "http.client")
    files = list(base.glob("*.py")) + list((base / "si").glob("*.py"))
    for path in files:
        src = path.read_text()
        for token in banned:
            assert token not in src, (path, token)


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def _parser():
    p = argparse.ArgumentParser(prog="levi")
    sub = p.add_subparsers(dest="_top")
    register_dweller_parser(sub)
    return p


def test_cli_grind_repo_sweep(home, sweep_root, capsys):
    args = _parser().parse_args(
        ["dweller", "grind", "--kind", "repo-sweep", "--root", str(sweep_root), "--yes"]
    )
    assert cmd_dweller(args) == 0
    out = capsys.readouterr().out
    assert "executed" in out
    assert len(list_jobs()) == 1


def test_cli_grind_dry_run(home, sweep_root, capsys):
    args = _parser().parse_args(
        [
            "dweller",
            "grind",
            "--kind",
            "repo-sweep",
            "--root",
            str(sweep_root),
            "--dry-run",
        ]
    )
    assert cmd_dweller(args) == 0
    assert "dry-run" in capsys.readouterr().out


def test_cli_grind_denied_without_yes_non_tty(home, sweep_root, capsys):
    # stdin is not a tty under pytest: the console responder denies
    args = _parser().parse_args(
        ["dweller", "grind", "--kind", "repo-sweep", "--root", str(sweep_root)]
    )
    assert cmd_dweller(args) == 1
    assert "denied" in capsys.readouterr().out


def test_cli_jobs_and_receipt(home, sweep_root, capsys):
    args = _parser().parse_args(
        ["dweller", "grind", "--kind", "repo-sweep", "--root", str(sweep_root), "--yes"]
    )
    cmd_dweller(args)
    capsys.readouterr()
    assert cmd_dweller(_parser().parse_args(["dweller", "jobs"])) == 0
    jobs_out = capsys.readouterr().out
    assert "repo-sweep" in jobs_out
    job_id = list_jobs()[0].id
    assert cmd_dweller(_parser().parse_args(["dweller", "receipt", job_id])) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["decision"] == "executed"


def test_cli_receipt_unknown_job(home, capsys):
    args = _parser().parse_args(["dweller", "receipt", "ghost"])
    assert cmd_dweller(args) == 1


def test_cli_watch(home, tmp_path, capsys):
    probe = tmp_path / "sig.txt"
    probe.write_text("READY\n")
    args = _parser().parse_args(
        [
            "dweller",
            "grind",
            "--kind",
            "watch",
            "--probe-path",
            str(probe),
            "--probe-contains",
            "READY",
            "--yes",
        ]
    )
    assert cmd_dweller(args) == 0
    assert "executed" in capsys.readouterr().out
