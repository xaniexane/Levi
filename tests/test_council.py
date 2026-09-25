"""Hermetic tests for the LEVI-native code council.

No network, no keys, no user HOME writes (HOME is redirected to
tmp_path). The native brain is mocked where needed; the real
rules-engine mind runs directly (stdlib-only, deterministic).
"""

import json
import textwrap

import pytest

from levi.council import (
    NativeBrainMind,
    RulesEngineMind,
    SpecialistsMind,
    detect_seats,
    mind_for,
    mutation_sample,
    parse_checklist,
    run_council,
    run_properties,
    static_gates,
    synthesize_scaffold,
)
from levi.council import test_first_check as _test_first_check  # not collected
from levi.council.cli import main as council_main
from levi.council.minds import MindResult, ReviewResult

FIB = textwrap.dedent(
    """\
    def fib(n):
        if n < 0:
            raise ValueError("n must be non-negative")
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return a
    """
)

FIB_TESTS = textwrap.dedent(
    """\
    import candidate

    def test_fib_zero():
        assert candidate.fib(0) == 0

    def test_fib_ten():
        assert candidate.fib(10) == 55

    def test_fib_negative_raises():
        try:
            candidate.fib(-1)
        except ValueError:
            return
        raise AssertionError("expected ValueError")
    """
)

FIB_PROPS = textwrap.dedent(
    """\
    import candidate

    def prop_fib_nonneg(rng):
        n = rng.randrange(0, 60)
        assert candidate.fib(n) >= 0

    def prop_fib_recurrence(rng):
        n = rng.randrange(2, 40)
        assert candidate.fib(n) == candidate.fib(n - 1) + candidate.fib(n - 2)
    """
)

GLOWING_REVIEW = (
    "SECURITY: PASS - no issues\n"
    "ERROR_HANDLING: PASS - thorough\n"
    "EDGE_CASES: PASS - covered\n"
    "Excellent candidate."
)

HARSH_REVIEW = (
    "SECURITY: FAIL - sloppy\n"
    "ERROR_HANDLING: FAIL - missing\n"
    "EDGE_CASES: FAIL - untested\n"
    "Terrible candidate."
)


class FakeMind:
    """Deterministic stand-in for a LEVI mind."""

    def __init__(
        self,
        seat,
        code,
        review_text=GLOWING_REVIEW,
        model="fake-mind",
        ok=True,
        error="",
    ):
        self.seat = seat
        self._code = code
        self._review_text = review_text
        self._model = model
        self._ok = ok
        self._error = error

    def generate(self, task, tests_hint=""):
        return MindResult(
            ok=self._ok,
            text=self._code,
            seat=self.seat,
            model=self._model,
            error=self._error,
        )

    def review(self, task, code, test_summary):
        return ReviewResult(ok=True, text=self._review_text, seat=self.seat)


@pytest.fixture
def home_tmp(monkeypatch, tmp_path):
    """Redirect HOME so council scratch never touches the user home."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def brain_off(monkeypatch):
    """Force the native brain to report unavailable."""
    import levi.council.minds as minds

    monkeypatch.setattr(minds, "brain_available", lambda: (False, "mock: no brain"))


@pytest.fixture
def brain_on(monkeypatch):
    """Force the native brain to report available (no real generation)."""
    import levi.council.minds as minds

    monkeypatch.setattr(minds, "brain_available", lambda: (True, "mock: brain ready"))


# -- seat detection --------------------------------------------------------


def test_rules_engine_always_available():
    seats = {s.id: s for s in detect_seats()}
    assert set(seats) == {"native-brain", "rules-engine", "specialists"}
    assert seats["rules-engine"].available


def test_native_brain_skips_gracefully_without_weights(brain_off):
    seats = {s.id: s for s in detect_seats()}
    assert not seats["native-brain"].available
    assert "skipped" in seats["native-brain"].note
    assert "not an error" in seats["native-brain"].note


def test_specialists_skip_without_brain_voice(brain_off):
    seats = {s.id: s for s in detect_seats()}
    assert not seats["specialists"].available
    assert "voice" in seats["specialists"].note


def test_all_seats_available_with_brain(brain_on):
    seats = {s.id: s for s in detect_seats()}
    assert all(s.available for s in seats.values())


def test_mind_for_unknown_seat():
    with pytest.raises(ValueError):
        mind_for("claude")


def test_no_external_seats_remain():
    import levi.council.seats as seats_mod

    assert not hasattr(seats_mod, "SEAT_CLAUDE")
    assert not hasattr(seats_mod, "SEAT_GROK")
    assert not hasattr(seats_mod, "SEAT_COPILOT")
    assert not hasattr(seats_mod, "SEAT_EMERGENT")
    assert "providers" not in dir(seats_mod)


# -- minds -----------------------------------------------------------------


def test_scaffold_matches_test_api():
    code = synthesize_scaffold("write fib", FIB_TESTS)
    compile(code, "<scaffold>", "exec")
    assert "def fib(arg0):" in code
    assert "NotImplementedError" in code
    assert "symbolic mind" in code


def test_scaffold_empty_tests():
    code = synthesize_scaffold("task", "x = 1\n")
    compile(code, "<scaffold>", "exec")


def test_rules_engine_review_flags_eval():
    mind = RulesEngineMind()
    res = mind.review("t", "def f():\n    return eval('1+1')\n", "1 passed, 0 failed")
    assert res.ok
    checklist = parse_checklist(res.text)
    assert checklist["SECURITY"]["verdict"] == "FAIL"
    assert "eval" in checklist["SECURITY"]["note"]


def test_rules_engine_review_passes_clean():
    mind = RulesEngineMind()
    res = mind.review("t", FIB, "3 passed, 0 failed")
    checklist = parse_checklist(res.text)
    assert checklist["SECURITY"]["verdict"] == "PASS"
    assert checklist["ERROR_HANDLING"]["verdict"] == "PASS"
    assert checklist["EDGE_CASES"]["verdict"] == "UNKNOWN"


def test_rules_engine_review_flags_no_error_handling():
    mind = RulesEngineMind()
    res = mind.review("t", "def f(x):\n    return x\n", "1 passed, 0 failed")
    checklist = parse_checklist(res.text)
    assert checklist["ERROR_HANDLING"]["verdict"] == "FAIL"


def test_specialists_drafting_selects_coding():
    mind = SpecialistsMind()
    spec = mind._drafting_specialist("write a fib function in code", FIB_TESTS)
    assert spec.id == "coding"


def test_specialists_generate_skips_without_brain(brain_off):
    mind = SpecialistsMind()
    res = mind.generate("write fib", FIB_TESTS)
    assert not res.ok


def test_native_brain_generate_skips_without_weights(brain_off):
    mind = NativeBrainMind()
    res = mind.generate("write fib", FIB_TESTS)
    assert not res.ok
    assert "mock: no brain" in res.error


# -- techniques (unchanged layer) ------------------------------------------


def test_test_first_flags_no_tests():
    r = _test_first_check("x = 1\n")
    assert r.status == "fail"
    assert "no test_" in r.evidence


def test_test_first_passes():
    r = _test_first_check(FIB_TESTS)
    assert r.status == "pass"
    assert len(r.details["found"]) == 3


def test_static_gate_syntax_failure():
    r = static_gates("def broken(:\n")
    assert r.status == "fail"


def test_static_gate_complexity_cap():
    body = "\n".join(f"    if x == {i}:\n        y = {i}" for i in range(12))
    code = f"def big(x):\n    y = 0\n{body}\n    return y\n"
    r = static_gates(code, max_complexity=10)
    assert r.status == "fail"
    assert "complexity" in r.evidence


def test_static_gate_passes_clean():
    assert static_gates(FIB).status == "pass"


def test_property_checks_pass(home_tmp):
    r = run_properties(FIB, FIB_PROPS, trials=10, timeout=20, run_id="t", seat="s")
    assert r.status == "pass"


def test_property_checks_fail(home_tmp):
    bad = "import candidate\ndef prop_bad(rng):\n    assert candidate.fib(10) == 999\n"
    r = run_properties(FIB, bad, trials=5, timeout=20, run_id="t", seat="s")
    assert r.status == "fail"
    assert "prop_bad" in r.evidence


def test_property_checks_skip_without_file(home_tmp):
    assert run_properties(FIB, None, run_id="t", seat="s").status == "skip"


SIGN = textwrap.dedent(
    """\
    def sign(x):
        if x > 0:
            return 1
        if x < 0:
            return -1
        return 0
    """
)

SIGN_TESTS = textwrap.dedent(
    """\
    import candidate

    def test_pos():
        assert candidate.sign(5) == 1

    def test_neg():
        assert candidate.sign(-3) == -1

    def test_zero():
        assert candidate.sign(0) == 0
    """
)


def test_mutation_kill_rate_high(home_tmp):
    r = mutation_sample(
        SIGN,
        SIGN_TESTS,
        ["test_pos", "test_neg", "test_zero"],
        timeout=20,
        max_mutants=12,
        run_id="t",
        seat="s",
    )
    assert r.status == "pass"
    assert r.details["kill_rate"] >= 0.8


def test_mutation_weak_suite_is_advisory(home_tmp):
    weak = "import candidate\ndef test_pos():\n    assert candidate.sign(5) == 1\n"
    r = mutation_sample(
        SIGN, weak, ["test_pos"], timeout=20, max_mutants=12, run_id="t", seat="s"
    )
    assert r.status == "pass"
    assert r.details["weak_tests"]


def test_checklist_parsing():
    c = parse_checklist("SECURITY: FAIL - injection risk\nERROR_HANDLING: PASS - ok\n")
    assert c["SECURITY"]["verdict"] == "FAIL"
    assert c["ERROR_HANDLING"]["verdict"] == "PASS"
    assert c["EDGE_CASES"]["verdict"] == "UNKNOWN"


def test_sandbox_scrubs_env(home_tmp, monkeypatch):
    monkeypatch.setenv("LEVI_TEST_COUNCIL_SECRET", "zzz")
    tests = (
        "import os\ndef test_hidden():\n"
        "    assert 'LEVI_TEST_COUNCIL_SECRET' not in os.environ\n"
    )
    result = run_council(
        "t",
        tests,
        seats=["rules-engine"],
        minds={"rules-engine": FakeMind("rules-engine", "x = 1\n")},
        timeout=20,
    )
    cand = result["receipt"]["candidates"][0]
    assert cand["tests"]["pass_rate"] == 1.0


# -- pipeline --------------------------------------------------------------


def test_failing_candidates_excluded_from_review(home_tmp, brain_on):
    minds = {
        "native-brain": FakeMind(
            "native-brain", FIB, GLOWING_REVIEW, model="levi-brain (native, tiny-gpt)"
        ),
        "rules-engine": FakeMind("rules-engine", "def broken(:\n", GLOWING_REVIEW),
    }
    result = run_council(
        "t", FIB_TESTS, seats=["native-brain", "rules-engine"], minds=minds, timeout=20
    )
    receipt = result["receipt"]
    by_seat = {c["seat"]: c for c in receipt["candidates"]}
    assert by_seat["rules-engine"]["gated"] == "static"
    assert by_seat["rules-engine"]["reviews"] == []
    assert receipt["ranked_seats"] == ["native-brain"]
    assert receipt["winner"] == "native-brain"
    assert receipt["winner_model"] == "levi-brain (native, tiny-gpt)"


def test_tests_beat_opinions(home_tmp, brain_on):
    bad_fib = "def fib(n):\n    return 0\n"  # only test_fib_zero passes
    minds = {
        "native-brain": FakeMind("native-brain", FIB, HARSH_REVIEW),
        "specialists": FakeMind(
            "specialists",
            bad_fib,
            GLOWING_REVIEW,
            model="specialists/coding via levi-brain (native)",
        ),
    }
    result = run_council(
        "t", FIB_TESTS, seats=["native-brain", "specialists"], minds=minds, timeout=20
    )
    receipt = result["receipt"]
    by_seat = {c["seat"]: c for c in receipt["candidates"]}
    assert by_seat["native-brain"]["tests"]["pass_rate"] == 1.0
    assert by_seat["specialists"]["tests"]["pass_rate"] < 1.0
    assert receipt["winner"] == "native-brain"


def test_unavailable_seat_sits_out(home_tmp, brain_off):
    result = run_council("t", FIB_TESTS, seats=["native-brain"], timeout=20)
    receipt = result["receipt"]
    assert receipt["seated"] == []
    assert receipt["candidates"] == []
    assert receipt["winner"] is None
    assert any("sat out" in n for n in receipt["notes"])


def test_rules_engine_scaffold_flows_honestly(home_tmp):
    result = run_council("t", FIB_TESTS, seats=["rules-engine"], timeout=20)
    receipt = result["receipt"]
    cand = receipt["candidates"][0]
    assert cand["model"] == "rules-engine (symbolic, deterministic)"
    assert cand["gated"] == "tests"  # scaffold raises NotImplementedError
    assert cand["reviews"] == []
    assert receipt["winner"] is None
    assert any("LEVI-native" in n for n in receipt["notes"])


def test_unknown_seats_noted(home_tmp):
    result = run_council(
        "t",
        FIB_TESTS,
        seats=["rules-engine", "nope"],
        minds={"rules-engine": FakeMind("rules-engine", FIB)},
        timeout=20,
    )
    assert any("nope" in n for n in result["receipt"]["notes"])


def test_no_keys_needed(home_tmp, monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "XAI_API_KEY", "GITHUB_TOKEN", "COPILOT_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    result = run_council(
        "t",
        FIB_TESTS,
        seats=["rules-engine"],
        minds={"rules-engine": FakeMind("rules-engine", FIB)},
        timeout=20,
    )
    blob = json.dumps(result["receipt"])
    assert "API_KEY" not in blob and "TOKEN" not in blob
    assert result["receipt"]["winner"] == "rules-engine"


# -- CLI -------------------------------------------------------------------


def test_cli_seats(home_tmp, capsys, brain_off):
    assert council_main(["seats"]) == 0
    out = capsys.readouterr().out
    assert "native-brain" in out
    assert "rules-engine" in out
    assert "specialists" in out
    assert "skipped" in out
    assert "API_KEY" not in out


def test_cli_build_rules_engine_only(home_tmp, capsys, tmp_path):
    tests_file = tmp_path / "t.py"
    tests_file.write_text(FIB_TESTS)
    assert (
        council_main(
            [
                "build",
                "--task",
                "fib",
                "--tests",
                str(tests_file),
                "--seats",
                "rules-engine",
            ]
        )
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["seated"] == ["rules-engine"]
    assert receipt["candidates"][0]["gated"] == "tests"
    assert receipt["winner"] is None
