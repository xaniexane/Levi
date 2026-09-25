"""Tests for levi.cybrus.sealpass — the signature seal pass (hermetic).

Law → guard → prove: the laws live in the module docstring, the guards
in the code, and THESE tests are the honestly-named proof gate —
invariant demonstrations, never "formally proven".
"""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from levi.cybrus.sealpass import (
    ITERATIONS,
    ORIGINALS,
    GuardError,
    ImprovementProposal,
    LedgerTamperError,
    SealLedger,
    SealPass,
    SealScore,
    _score_factors,
)

REPO = Path(__file__).resolve().parents[1]
CORE = str(REPO / "core")
if CORE not in sys.path:
    sys.path.insert(0, CORE)

CLEAN_MODULE = '''"""A clean fixture module: nothing for heuristics to find."""


def add(a, b):
    """Add two numbers."""
    return a + b
'''

FORMAT_MODULE = '''"""Fixture with a .format() call: advisory-only finding, no auto-fix."""


def greet(name):
    return "hello {}".format(name)
'''

BARE_EXCEPT_MODULE = '''"""Fixture with a bare except: Quetta-Pan has a safe fix for this."""


def risky(x):
    try:
        return int(x)
    except:
        return 0
'''

BROKEN_MODULE = "def broken(:\n"

TEST_MOD = '''from mod import risky


def test_risky_int():
    assert risky("3") == 3


def test_risky_fallback():
    assert risky("nope") == 0
'''


def _fixture(tmp_path, module_text=FORMAT_MODULE, name="mod.py"):
    (tmp_path / name).write_text(module_text, encoding="utf-8")
    return tmp_path / name


def _pass(tmp_path, **kwargs):
    kwargs.setdefault("repo_root", tmp_path)
    kwargs.setdefault("ledger_dir", tmp_path / "sealpass")
    kwargs.setdefault("test_map", {})
    return SealPass(**kwargs)


# ---------------------------------------------------------------------------
# Stage ordering + iteration counting
# ---------------------------------------------------------------------------


def test_five_iterations_are_counted(tmp_path):
    target = _fixture(tmp_path, CLEAN_MODULE)
    sp = _pass(tmp_path)
    report = sp.run([target], iterations=ITERATIONS)
    assert report["iterations"] == 5
    entries = sp.ledger.stages()
    iters = sorted({e["iteration"] for e in entries if e["iteration"] > 0})
    assert iters == [1, 2, 3, 4, 5]


def test_stage_ordering_per_iteration(tmp_path):
    target = _fixture(tmp_path)
    sp = _pass(tmp_path)
    sp.run([target], iterations=1)
    entries = sp.ledger.stages()
    it1 = [e for e in entries if e["iteration"] == 1]
    order = [e["stage"] for e in it1]
    canonical = ["kfx2", "demandpulse", "echo", "mandella", "reim", "riem", "quetta-pan"]
    positions = []
    for stage in canonical:
        assert stage in order, f"stage {stage} missing from ledger"
        positions.append(order.index(stage))
    assert positions == sorted(positions), "stages ran out of order"


# ---------------------------------------------------------------------------
# Ledger integrity: tamper fails closed
# ---------------------------------------------------------------------------


def test_ledger_tamper_fails_closed(tmp_path):
    target = _fixture(tmp_path)
    sp = _pass(tmp_path)
    sp.run([target], iterations=1)
    assert sp.ledger.verify() > 0
    # Tamper with one line: flip a byte in the middle entry.
    lines = sp.ledger.path.read_text(encoding="utf-8").splitlines()
    mid = len(lines) // 2
    entry = json.loads(lines[mid])
    entry["payload"]["detail"] = "forged detail"
    lines[mid] = json.dumps(entry, sort_keys=True)
    sp.ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(LedgerTamperError):
        sp.ledger.verify()


def test_ledger_missing_key_fails_closed(tmp_path):
    target = _fixture(tmp_path)
    sp = _pass(tmp_path)
    sp.run([target], iterations=1)
    (sp.ledger.dir / "ledger.key").unlink()
    with pytest.raises(LedgerTamperError):
        sp.ledger.verify()


def test_no_cancellation_append_only(tmp_path):
    ledger = SealLedger(tmp_path / "seal")
    assert not hasattr(ledger, "delete")
    assert not hasattr(ledger, "remove")
    ledger.append("kfx2", "t", 1, "-", {"ok": True})
    ledger.append("demandpulse", "t", 1, "-", {"ok": True})
    assert ledger.verify() == 2
    # Prior seals stay valid after later appends: nothing was cancelled.
    ledger.append("echo", "t", 1, "-", {"ok": True})
    assert ledger.verify() == 3


def test_owner_only_permissions(tmp_path):
    ledger = SealLedger(tmp_path / "seal")
    ledger.append("kfx2", "t", 1, "-", {"ok": True})
    mode = lambda p: stat.S_IMODE(os.stat(p).st_mode)  # noqa: E731
    assert mode(ledger.dir) == 0o700
    assert mode(ledger.path) == 0o600
    assert mode(ledger.dir / "ledger.key") == 0o600


# ---------------------------------------------------------------------------
# Convergence: zero improvements recorded honestly
# ---------------------------------------------------------------------------


def test_convergence_with_zero_improvements(tmp_path):
    target = _fixture(tmp_path, CLEAN_MODULE)
    sp = _pass(tmp_path)
    report = sp.run([target], iterations=5)
    assert report["applied"] == 0
    assert report["proposals"] == 0
    assert len(report["converged_iterations"]) == 5
    stages = [e["stage"] for e in sp.ledger.stages()]
    assert stages.count("convergence") == 5


def test_advisory_only_never_inflated(tmp_path):
    """PY_FSTRING fires but has no auto-fix: proposals exist, nothing applies."""
    target = _fixture(tmp_path, FORMAT_MODULE)
    sp = _pass(tmp_path)
    report = sp.run([target], iterations=1)
    assert report["proposals"] >= 1
    assert report["applied"] == 0
    assert len(report["converged_iterations"]) == 1


# ---------------------------------------------------------------------------
# Echo: originals-first rejects anti-original proposals
# ---------------------------------------------------------------------------


def _anti_original_proposal(target):
    return ImprovementProposal(
        id="anti-it1-X-00000000",
        target=str(target),
        iteration=1,
        rule_id="X",
        title="remove a public function",
        desc="synthetic anti-original",
        severity="warning",
        basis="test",
        context="py",
        approved=True,
        touches={"removed_public_defs": ["doomed_public_fn"]},
    )


def test_echo_rejects_anti_original(tmp_path):
    target = _fixture(tmp_path)
    sp = _pass(tmp_path)
    proposal = _anti_original_proposal(target)
    sp.stage_echo(target, 1, [proposal])
    assert proposal.approved is False
    assert proposal.rejection_stage == "echo"
    assert "no-cancellation" in proposal.rejection_reason


def test_compost_receives_failures(tmp_path):
    target = _fixture(tmp_path)
    sp = _pass(tmp_path)
    proposal = _anti_original_proposal(target)
    sp.stage_echo(target, 1, [proposal])
    result = sp.stage_reim(target, 1, [proposal])
    assert result.payload["composted"] == [proposal.id]
    compost_path = sp.ledger.dir / ".quetta_compost.jsonl"
    assert compost_path.exists()
    text = compost_path.read_text(encoding="utf-8")
    assert proposal.id in text
    assert "no-cancellation" in text


def test_genome_records_steering(tmp_path):
    target = _fixture(tmp_path)
    sp = _pass(tmp_path)
    proposal = _anti_original_proposal(target)
    sp.stage_echo(target, 1, [proposal])
    sp.stage_reim(target, 1, [proposal])
    sp.stage_riem(target, 1, [proposal])
    stats = sp.engine.genome.stats("X", "py")
    assert stats["attempts"] >= 1
    assert stats["failures"] >= 1


# ---------------------------------------------------------------------------
# DemandPulse: basis required, deterministic
# ---------------------------------------------------------------------------


def test_demandpulse_requires_basis(tmp_path):
    factors = _score_factors(
        ImprovementProposal(
            id="p", target="t", iteration=1, rule_id="R", title="t",
            desc="d", severity="info", basis="b", context="py",
        ),
        diff_lines=0,
        test_files=[],
    )
    name = next(iter(factors))
    value, _ = factors[name]
    factors[name] = (value, "   ")
    with pytest.raises(GuardError):
        SealScore(proposal_id="p", factors=factors)


def test_demandpulse_deterministic(tmp_path):
    target = _fixture(tmp_path, FORMAT_MODULE)
    sp = _pass(tmp_path)
    _, proposals = sp.stage_kfx2(target, 1)
    assert proposals, "expected at least one heuristic proposal"
    sp.stage_demandpulse(target, 1, proposals)
    first = {p.id: (p.score.composite, p.score.tier) for p in proposals}
    # Re-score fresh: identical inputs give identical outputs.
    sp2 = _pass(tmp_path / "second")
    _, proposals2 = sp2.stage_kfx2(target, 1)
    sp2.stage_demandpulse(target, 1, proposals2)
    second = {p.id: (p.score.composite, p.score.tier) for p in proposals2}
    assert first == second


# ---------------------------------------------------------------------------
# Guards: unparseable target fails closed but the pass moves on
# ---------------------------------------------------------------------------


def test_guard_unparseable_target_moves_on(tmp_path):
    bad = _fixture(tmp_path, BROKEN_MODULE, name="bad.py")
    good = _fixture(tmp_path, CLEAN_MODULE, name="good.py")
    sp = _pass(tmp_path)
    report = sp.run([bad, good], iterations=1)
    guards = [
        e for e in sp.ledger.stages()
        if e["stage"] == "guard" and e["target"].endswith("bad.py")
    ]
    assert guards, "guard firing was not sealed"
    assert "does not parse" in guards[0]["payload"]["detail"]
    # Forward-motion: the good target still got its full pass.
    good_stages = {
        e["stage"] for e in sp.ledger.stages() if e["target"].endswith("good.py")
    }
    assert "quetta-pan" in good_stages
    assert report["ledger_entries"] > 0


def test_originals_registry_nonempty():
    assert len(ORIGINALS) >= 3
    assert {o["id"] for o in ORIGINALS} >= {
        "no-cancellation",
        "stdlib-core",
        "dynasty-sealed",
    }


# ---------------------------------------------------------------------------
# Quetta-Pan apply path: bare except gets the safe fix, tests stay green
# ---------------------------------------------------------------------------


def test_apply_path_end_to_end(tmp_path):
    target = _fixture(tmp_path, BARE_EXCEPT_MODULE)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_mod.py").write_text(TEST_MOD, encoding="utf-8")
    sp = _pass(tmp_path, test_map={"mod.py": ["test_mod.py"]})
    report = sp.run([target], iterations=1)
    assert report["applied"] == 1
    text = target.read_text(encoding="utf-8")
    assert "except Exception:" in text
    # Tests stayed green after application: the file still imports and works.
    assert "except:" not in text.replace("except Exception:", "")
    apps = [
        e for e in sp.ledger.stages() if e["stage"] == "quetta-pan-application"
    ]
    assert apps and all(e["payload"]["ok"] for e in apps)
    stats = sp.engine.genome.stats("PY_BARE_EXCEPT", "py")
    assert stats["successes"] >= 1
    # Iteration 2 converges: the fix is already applied, nothing left.
    report2 = sp.run([target], iterations=1)
    assert report2["applied"] == 0
