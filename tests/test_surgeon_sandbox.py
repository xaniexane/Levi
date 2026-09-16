"""Hermetic tests for the surgeon sandbox gate.

The gate never executes code and never writes without a clean report
AND explicit human confirmation. All fixtures synthetic.
"""

import pytest

from levi.surgeon.sandbox import SandboxGate


def _gate():
    return SandboxGate()


def test_analyze_clean_code_ok():
    rep = _gate().analyze("x = 1\n", "x = 2\n")
    assert rep.ok is True
    assert rep.errors == []
    assert rep.metrics["orig_len"] == 6
    assert rep.metrics["delta"] == 0


def test_analyze_empty_proposed_fails():
    rep = _gate().analyze("x = 1\n", "   \n")
    assert rep.ok is False
    assert any("empty" in e for e in rep.errors)


@pytest.mark.parametrize(
    "payload",
    [
        "eval(user_input)",
        "x = Function('return 1')",
        "require('child_process')",
        "import subprocess",
        "os.system('ls')",
        "os.popen('id')",
        "pickle.loads(blob)",
        "rm -rf /tmp/x",
        "cursor.execute('DROP TABLE users')",
    ],
)
def test_analyze_blocked_patterns(payload):
    rep = _gate().analyze("", f"x = 1\n{payload}\n")
    assert rep.ok is False
    assert any("dangerous pattern" in e for e in rep.errors)


def test_analyze_unbalanced_brackets_warn():
    rep = _gate().analyze("", "def f(:\n    pass\n")
    assert rep.ok is True  # warning only, not an error
    assert any("unbalanced" in w for w in rep.warnings)


def test_analyze_todo_warns():
    rep = _gate().analyze("", "x = 1  # TODO: fix\n")
    assert rep.ok is True
    assert any("TODO" in w for w in rep.warnings)


def test_analyze_never_raises():
    rep = _gate().analyze(None, None)  # type: ignore[arg-type]
    assert isinstance(rep.ok, bool)


def test_history_bounded():
    gate = _gate()
    for _ in range(60):
        gate.analyze("", "x = 1\n")
    assert len(gate.history) == 50


def test_apply_needs_clean_report(tmp_path):
    gate = _gate()
    rep = gate.analyze("", "   ")  # fails: empty
    res = gate.apply("x = 1\n", rep, tmp_path / "out.py", confirmed=True)
    assert res["ok"] is False
    assert not (tmp_path / "out.py").exists()


def test_apply_needs_confirmation(tmp_path):
    gate = _gate()
    rep = gate.analyze("", "x = 1\n")
    res = gate.apply("x = 1\n", rep, tmp_path / "out.py", confirmed=False)
    assert res["ok"] is False
    assert "HITL" in res["reason"]
    assert not (tmp_path / "out.py").exists()


def test_apply_needs_report(tmp_path):
    res = _gate().apply("x = 1\n", None, tmp_path / "out.py", confirmed=True)
    assert res["ok"] is False


def test_apply_writes_with_report_and_confirmation(tmp_path):
    gate = _gate()
    rep = gate.analyze("x = 0\n", "x = 1\n")
    target = tmp_path / "sub" / "out.py"
    res = gate.apply("x = 1\n", rep, target, confirmed=True)
    assert res["ok"] is True
    assert res["report_id"] == rep.id
    assert target.read_text() == "x = 1\n"


def test_apply_blocked_code_never_writes(tmp_path):
    gate = _gate()
    evil = "import subprocess\nsubprocess.run(['rm','-rf','/'])\n"
    rep = gate.analyze("", evil)
    assert rep.ok is False
    res = gate.apply(evil, rep, tmp_path / "evil.py", confirmed=True)
    assert res["ok"] is False
    assert not (tmp_path / "evil.py").exists()
