"""Phase 0 separation audit — the binding gate, enforced in code.

Echoverse (SFW) and Plaiground (adult) are NEVER merged. These tests
prove it two ways, per the production plan:

  1. Import every Echoverse module with the adult gate OFF and prove no
     adult path is touched (static prover/verifier audit + runtime
     audit with an import spy).
  2. Prove the gate/bounds modules have no SFW-side bypass: the gate
     stays closed under every trick, and no Echoverse API can open it.

Hermetic: tmp home dirs only, never the real ``~/.levi``. No network.
No explicit content anywhere.
"""

import ast
import json
import os
import stat
import sys
from pathlib import Path

import pytest

from levi.echoverse import entry, separation, themes
from levi.plaiground import gate


@pytest.fixture()
def home(tmp_path):
    return tmp_path


@pytest.fixture()
def clean_env(monkeypatch):
    for var in (
        "PLAIGROUND_ENABLED",
        "PLAIGROUND_ADULT",
        "LEVI_ADULT",
        "LEVI_ADULT_MODE",
        "LEVI_MINOR",
        "LEVI_MINOR_MODE",
        "PLAIGROUND_MINOR",
    ):
        monkeypatch.delenv(var, raising=False)


def _pkg_dir() -> Path:
    return Path(separation.__file__).parent


# ---------------------------------------------------------------------------
# 1a. Static audit — the whole Echoverse package is CLEAN.
# ---------------------------------------------------------------------------


def test_full_static_audit_is_clean():
    report = separation.full_static_audit()
    assert report["verdict"] == "clean", report["findings"]
    assert report["findings"] == []
    assert report["agreed"] is True
    assert report["files_scanned"] >= 3  # __init__, entry, themes (+harness)


def test_harness_exclusion_is_exactly_the_harness():
    # The audit harness (separation.py) is excluded from its own static
    # walk because it must READ gate state to do its job. The exclusion
    # must be exactly the harness — nothing else may hide behind it.
    assert separation.HARNESS_EXCLUDE == frozenset({"separation.py"})
    report = separation.full_static_audit()
    assert report["harness_excluded"] == ["separation.py"]


def test_harness_can_read_the_lock_but_never_turn_the_key():
    # separation.py may reference verify_adult / GateLockedError (boundary
    # reads inside runtime_audit). It must NEVER reference any enabling
    # adult entry — the harness reads the lock, never turns the key.
    tree = ast.parse(Path(separation.__file__).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    for forbidden in (
        "enable_adult_mode",
        "disable_adult_mode",
        "set_pin",
        "change_pin",
        "verify_pin",
    ):
        assert forbidden not in names, forbidden
    # And no Echoverse product module may import from plaiground, or call
    # (or import) an adult entry name — checked at the AST level, which is
    # what the audit itself enforces. (Docstrings may NAME the law; only
    # code contact counts.)
    for mod in (entry, themes):
        tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("levi.plaiground"), alias.name
            elif isinstance(node, ast.ImportFrom) and not node.level:
                modname = node.module or ""
                assert not modname.startswith("levi.plaiground"), modname
                for alias in node.names:
                    assert alias.name not in separation.ADULT_ENTRY_NAMES
            elif isinstance(node, ast.Call):
                func = node.func
                cname = None
                if isinstance(func, ast.Name):
                    cname = func.id
                elif isinstance(func, ast.Attribute):
                    cname = func.attr
                assert cname not in separation.ADULT_ENTRY_NAMES, cname


def test_no_echoverse_product_module_imports_plaiground():
    for mod in (entry, themes):
        tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("levi.plaiground"), alias.name
            elif isinstance(node, ast.ImportFrom) and not node.level:
                assert (node.module or "") != "levi.plaiground"
                assert not (node.module or "").startswith("levi.plaiground.")


# ---------------------------------------------------------------------------
# 1b. Ternary verdicts — proven on synthetic packages.
# ---------------------------------------------------------------------------


def _write_pkg(tmp_path: Path, files: dict) -> Path:
    pkg = tmp_path / "fakepkg"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    for name, body in files.items():
        (pkg / name).write_text(body, encoding="utf-8")
    return pkg


def test_verdict_clean_on_clean_package(tmp_path):
    pkg = _write_pkg(tmp_path, {"mod.py": "X = 1\n"})
    report = separation.prover_audit(package_dir=pkg)
    assert report.verdict is separation.Verdict.CLEAN


def test_verdict_violation_on_adult_import(tmp_path):
    pkg = _write_pkg(tmp_path, {"mod.py": "from levi.plaiground import afterdark\n"})
    report = separation.prover_audit(package_dir=pkg)
    assert report.verdict is separation.Verdict.VIOLATION
    assert report.findings[0].target == "levi.plaiground"


def test_verdict_violation_on_gated_engine_import(tmp_path):
    # The seven shared engines are gate-required today: importing one
    # from Echoverse-shaped code is a violation until they grow SFW cores.
    for engine in sorted(separation.GATE_REQUIRED_ENGINES):
        slug = engine.replace(".", "_")
        pkg = _write_pkg(tmp_path / slug, {"mod.py": "import %s\n" % engine})
        report = separation.prover_audit(package_dir=pkg)
        assert report.verdict is separation.Verdict.VIOLATION, engine


def test_verdict_violation_on_adult_call_name(tmp_path):
    pkg = _write_pkg(
        tmp_path, {"mod.py": "def f(g):\n    return g.enable_adult_mode('x')\n"}
    )
    report = separation.prover_audit(package_dir=pkg)
    assert report.verdict is separation.Verdict.VIOLATION


def test_verdict_inconclusive_on_dynamic_import(tmp_path):
    pkg = _write_pkg(
        tmp_path,
        {
            "mod.py": "import importlib\n\ndef f(n):\n    return importlib.import_module(n)\n"
        },
    )
    report = separation.prover_audit(package_dir=pkg)
    assert report.verdict is separation.Verdict.INCONCLUSIVE


def test_prover_verifier_agree_on_synthetic_packages(tmp_path):
    cases = {
        "clean": {"mod.py": "X = 1\n"},
        "violation": {"mod.py": "import levi.plaiground.gate\n"},
        "inconclusive": {"mod.py": "x = eval('1')\n"},
    }
    for name, files in cases.items():
        pkg = _write_pkg(tmp_path / name, files)
        prover = separation.prover_audit(package_dir=pkg)
        verifier = separation.verifier_audit(package_dir=pkg)
        assert separation.cross_check(prover, verifier) is True, name
        full = separation.full_static_audit(package_dir=pkg)
        assert full["verdict"] == prover.verdict.value, name


def test_cross_check_rejects_disagreement():
    a = separation.AuditReport(verdict=separation.Verdict.CLEAN)
    b = separation.AuditReport(verdict=separation.Verdict.VIOLATION)
    assert separation.cross_check(a, b) is False
    c = separation.AuditReport(
        verdict=separation.Verdict.CLEAN,
        findings=[separation.Finding("m.py", 1, "import", "x")],
    )
    assert separation.cross_check(a, c) is False


# ---------------------------------------------------------------------------
# 1c. Runtime audit — gate OFF, entry points touch no adult path.
# ---------------------------------------------------------------------------


def _echoverse_entries(home):
    session = entry.open_session(home, session_id="audit1")
    entry.log_line(session, "a clean line in the ledger")
    entry.close_session(session)
    themes.save_theme(home, "audit", {"mood": "dawn", "layout": "airy"})
    return {
        "status": entry.zone_status(home),
        "ledger": entry.read_ledger(home, "audit1"),
        "chain_ok": session.verify_chain(),
        "themes": themes.list_themes(home),
    }


def test_runtime_audit_passes_with_gate_off(home, clean_env):
    assert gate.verify_adult(home) is False  # gate provably OFF first
    report = separation.runtime_audit({"smoke": _echoverse_entries}, home)
    assert report.gate_was_off is True
    assert report.adult_imports == []
    assert report.failures == [], report.failures
    assert report.passed is True
    assert report.entry_results["smoke"]["chain_ok"] is True
    assert report.entry_results["smoke"]["status"]["sfw_only"] is True


def test_runtime_audit_detects_adult_import(home, clean_env):
    def bad(_home):
        import levi.plaiground.afterdark  # noqa: F401  (simulated violation)

        return None

    # The audit harness evicts and restores levi.plaiground itself so the
    # import spy sees exactly what the entry point imports.
    report = separation.runtime_audit({"bad": bad}, home)
    assert report.passed is False
    assert "levi.plaiground.afterdark" in report.adult_imports
    assert any("adult-surface module imported" in f for f in report.failures)


def test_runtime_audit_detects_gate_locked_error(home, clean_env):
    def gated(_home):
        raise gate.GateLockedError("simulated adult-gated call")

    report = separation.runtime_audit({"gated": gated}, home)
    assert report.passed is False
    assert any("adult-gated path" in f for f in report.failures)


# ---------------------------------------------------------------------------
# 1d. Import every Echoverse module with the gate off — no adult contact.
# ---------------------------------------------------------------------------


def test_import_all_echoverse_modules_gate_off(home, clean_env, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pytest"])
    before = set(sys.modules)
    import importlib

    for name in (
        "levi.echoverse",
        "levi.echoverse.separation",
        "levi.echoverse.entry",
        "levi.echoverse.themes",
    ):
        importlib.import_module(name)
    assert gate.verify_adult(home) is False
    new_mods = set(sys.modules) - before
    for mod in new_mods:
        assert mod not in separation.ADULT_SURFACE, mod
        assert mod not in separation.GATE_REQUIRED_ENGINES, mod


# ---------------------------------------------------------------------------
# 2. The gate/bounds have no SFW-side bypass.
# ---------------------------------------------------------------------------


def test_gate_off_by_default(home, clean_env):
    assert gate.verify_adult(home) is False
    with pytest.raises(gate.GateLockedError):
        gate.require_adult(home)


@pytest.mark.parametrize(
    "var", ["PLAIGROUND_ENABLED", "LEVI_ADULT", "PLAIGROUND_ADULT"]
)
def test_env_var_tricks_fail(home, clean_env, monkeypatch, var):
    monkeypatch.setenv(var, "1")
    assert gate.verify_adult(home) is False


def test_handwritten_record_cannot_enable(home, clean_env):
    gate.gate_dir(home).mkdir(parents=True, exist_ok=True)
    fake = gate.gate_file(home)
    fake.write_text(json.dumps({"enabled": True}), encoding="utf-8")
    os.chmod(fake, 0o600)
    assert gate.verify_adult(home) is False


def test_enable_without_pin_refused(home, clean_env):
    with pytest.raises(gate.PinError):
        gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, "0000", home)
    assert gate.verify_adult(home) is False


def test_minor_indicator_blocks_enable(home, clean_env, monkeypatch):
    gate.set_pin("1234", home)
    monkeypatch.setenv("LEVI_MINOR", "1")
    with pytest.raises(gate.MinorIndicatorError):
        gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, "1234", home)
    assert gate.verify_adult(home) is False


def test_no_echoverse_api_can_open_the_gate(home, clean_env):
    # The full public surface of the Echoverse package, exercised: none
    # of it may result in the gate opening.
    entry.zone_status(home)
    session = entry.open_session(home, session_id="gateprobe")
    entry.log_line(session, "probing")
    entry.close_session(session)
    themes.save_theme(home, "probe", {"mood": "calm"})
    assert gate.verify_adult(home) is False
    assert gate.gate_file(home).is_file() is False


# ---------------------------------------------------------------------------
# Entry + themes behavior (the surface the audit protects).
# ---------------------------------------------------------------------------


def test_session_ledger_and_witness(home):
    session = entry.open_session(home, session_id="s1")
    entry.log_line(session, "first beat")
    entry.log_line(session, "second beat")
    assert session.verify_chain() is True
    ledger = entry.read_ledger(home, "s1")
    assert [e["line"] for e in ledger] == ["first beat", "second beat"]
    entry.close_session(session)
    # Tampering breaks the witness chain.
    path = entry.zone_dir(home) / "sessions" / "s1" / "ledger.jsonl"
    path.write_text('{"at": "x", "line": "forged"}\n', encoding="utf-8")
    assert session.verify_chain() is False


def test_session_records_are_owner_only(home):
    session = entry.open_session(home, session_id="perm")
    entry.log_line(session, "private")
    for p in (
        entry.zone_dir(home) / "sessions" / "perm" / "ledger.jsonl",
        entry.zone_dir(home) / "sessions" / "perm" / "witness.txt",
    ):
        assert stat.S_IMODE(p.stat().st_mode) == 0o600


def test_theme_injection_rejected():
    for evil in (
        "<script>alert(1)</script>",
        "javascript:alert(1)",
        '"><img src=x onerror=alert(1)>',
        "{{7*7}}",
    ):
        with pytest.raises(themes.ThemeError):
            themes.validate_theme({"mood": "calm", "background": evil})
    with pytest.raises(themes.ThemeError):
        themes.validate_theme({"background": "red"})  # not a hex color
    with pytest.raises(themes.ThemeError):
        themes.validate_theme({"nope": "#fff"})  # unknown slot


def test_theme_inherit_and_roundtrip(home):
    clean = themes.validate_theme({"background": "inherit", "mood": "noir"})
    assert clean == {"background": "inherit", "mood": "noir"}
    themes.save_theme(home, "mine", {"mood": "dawn"})
    assert themes.list_themes(home)["mine"] == {"mood": "dawn"}
    assert themes.active_theme(home)["mood"] == "calm"  # default, no 'active'
    with pytest.raises(themes.ThemeError):
        themes.save_theme(home, "../escape", {"mood": "calm"})
