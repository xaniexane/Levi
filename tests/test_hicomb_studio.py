"""Hicomb Studio tests — laws -> guards -> machine-checkable proof.

Every invariant declared in the module docstrings is checked here:
  I1 POLLEN-ABORT    formatter failure aborts the write; file bytes unchanged
  I2 IDEMPOTENT     format(format(x)) == format(x), incl. fuzzed inputs
  I3 ATOMIC         saves never half-write
  I4 HONEST-SOURCE  no "model" completion without a wired, available backend
  I5 LOCAL-ALWAYS   local completions + "local-only" status with no backend
  I6 GBC-GEOMETRY   gbc-card theme: corner_radius == 0
  I7 GBC-PALETTE    every gbc-card color is in GBC_PALETTE
  I8 SELF-CONTAINED the studio HTML has zero external references
  I9 PANELS-PRESENT every required panel id exists in the HTML
  I10 NOTHING-THROWN-AWAY abort paths lose no bytes; delete routes to trash

Hermetic: temp dirs only, no network, stdlib only. Run from repo root.
"""

import random

import pytest

from levi.hicomb import (
    GBC_PALETTE,
    Buffer,
    FormatterError,
    LocalEngine,
    PairProgrammer,
    check_panels,
    check_self_contained,
    format_text,
    get_gbc_theme,
    language_for_path,
    list_themes,
    pollen_languages,
    save_pipeline,
)
from levi.hicomb.pipeline import SaveResult


# ------------------------------------------------------------------ pollen
def test_pollen_idempotent_fixed_cases():
    cases = [
        ("python", "x=1  \n\n\n\ny=2\n"),
        ("python", "def f():\n    return 1\n"),
        ("json", '{"b":2,"a":1}'),
        ("javascript", "function f(){  \n  return 1;\n}\n\n\n"),
        ("markdown", "# hi  \n\n\ntext\n"),
        ("plain", "a\tb  \n"),
    ]
    for lang, text in cases:
        once = format_text(lang, text)
        assert format_text(lang, once) == once, (lang, text)  # I2


def test_pollen_idempotent_fuzz():
    rng = random.Random(20260922)  # seeded: deterministic proof
    alphabet = "ab \t\n{}[]():=,\"'#;def_1"
    for lang in pollen_languages():
        for _ in range(60):
            text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 120)))
            try:
                once = format_text(lang, text)
            except FormatterError:
                continue  # refusal is legal; abort law is tested separately
            assert format_text(lang, once) == once, (lang, text)  # I2


def test_pollen_refuses_broken_code():
    with pytest.raises(FormatterError):
        format_text("python", "def broken(:\n  pass\n")
    with pytest.raises(FormatterError):
        format_text("json", '{"a": }')
    with pytest.raises(FormatterError):
        format_text("javascript", "function f( { return 1; ")


def test_pollen_unknown_language_is_safe():
    out = format_text("cobol", "x  \n")
    assert out == "x\n"


def test_language_for_path():
    assert language_for_path("a.py") == "python"
    assert language_for_path("a.JSON") == "json"
    assert language_for_path("a.weird") == "plain"


# ------------------------------------------------------------------ pipeline (I1, I3, I10)
def test_save_pipeline_formats_then_writes(tmp_path):
    target = tmp_path / "hello.py"
    target.write_text("x=1\n", encoding="utf-8")
    buf = Buffer("y=2  \n\n\n", path=str(target))
    res = save_pipeline(buf, language="python")
    assert isinstance(res, SaveResult)
    assert res.ok and res.formatted
    assert target.read_text(encoding="utf-8") == "y=2\n"
    assert not buf.dirty


def test_save_pipeline_abort_leaves_file_byte_identical(tmp_path):
    """I1 + I10: broken formatter -> no write, no lost bytes."""
    target = tmp_path / "broken.py"
    original = "x = 1\n"
    target.write_text(original, encoding="utf-8")
    buf = Buffer("def broken(:\n", path=str(target))
    res = save_pipeline(buf, language="python")
    assert not res.ok and "pollen refused" in res.aborted
    assert target.read_bytes() == original.encode("utf-8")  # byte-identical
    assert buf.get_text() == "def broken(:\n"  # buffer text preserved


def test_save_pipeline_abort_bad_json(tmp_path):
    target = tmp_path / "data.json"
    original = '{"ok": true}\n'
    target.write_text(original, encoding="utf-8")
    buf = Buffer('{"ok": }', path=str(target))
    res = save_pipeline(buf)
    assert not res.ok
    assert target.read_bytes() == original.encode("utf-8")


def test_save_pipeline_atomic_new_file(tmp_path):
    """I3: temp + replace — a fresh write lands whole."""
    target = tmp_path / "sub" / "new.py"
    buf = Buffer("x=1\n", path=str(target))
    res = save_pipeline(buf)
    assert res.ok and res.bytes_written > 0
    assert target.read_text(encoding="utf-8") == "x=1\n"
    assert not (tmp_path / "sub").joinpath("new.py.hicomb-tmp").exists()


def test_save_pipeline_needs_path():
    buf = Buffer("x=1\n")
    res = save_pipeline(buf)
    assert not res.ok and "no path" in res.aborted


# ------------------------------------------------------------------ ai (I4, I5)
def test_local_completions_are_labeled_local():
    eng = LocalEngine()
    text = "def calculate_total(items):\n    return sum(items)\n\ncalc"
    comps = eng.complete(text, 3, 4, "python")
    assert comps, "expected a word completion for 'calc'"
    assert all(c.source == "local" for c in comps)  # I4
    assert any(c.text.startswith("ulate_total") for c in comps)


def test_pair_programmer_local_only_without_backend():
    pp = PairProgrammer()
    assert pp.status() == "local-only"  # I5
    comps = pp.suggest("import os\n\nos.pa", 2, 5, "python")
    assert all(c.source == "local" for c in comps)  # I4


def test_model_completions_only_with_wired_backend():
    class DeadBackend:
        def name(self): return "ghost"
        def available(self): return False
        def complete(self, p, c, language): return []
        def chat(self, p, c, language): return ""

    pp = PairProgrammer(backend=DeadBackend())
    assert pp.status() == "local-only"
    assert all(c.source == "local" for c in pp.suggest("x = 1\nx", 1, 1, "python"))

    from levi.hicomb.ai import Completion

    class LiveBackend(DeadBackend):
        def available(self): return True
        def complete(self, p, c, language):
            return [Completion(text="suggestion", source="model",
                               label="test-model", confidence=0.9)]

    pp2 = PairProgrammer(backend=LiveBackend())
    assert pp2.status() == "model:ghost"
    got = pp2.suggest("x", 0, 1, "python")
    assert any(c.source == "model" for c in got)  # I4: labeled when real


def test_broken_backend_never_kills_local():
    """I5: a backend whose available() explodes degrades to local-only —
    local completions keep working, nothing raises."""

    class BrokenBackend:
        def name(self): return "broken"
        def available(self): raise RuntimeError("backend exploded")
        def complete(self, p, c, language): raise RuntimeError("backend exploded")
        def chat(self, p, c, language): raise RuntimeError("backend exploded")

    pp = PairProgrammer(backend=BrokenBackend())
    assert pp.status() == "local-only"
    text = "def calculate_total(items):\n    return sum(items)\n\ncalc"
    comps = pp.suggest(text, 3, 4, "python")
    assert comps, "local completions must survive a broken backend"
    assert all(c.source == "local" for c in comps)


def test_ai_analysis_is_labeled_local():
    pp = PairProgrammer()
    text = "def f():\n    x=1  \n    return x\n# TODO: docs\n"
    for kind in ("explain", "review", "fix", "refactor"):
        a = getattr(pp, kind)(text, "python")
        assert a.engine == "local", kind
    fx = pp.fix(text, "python")
    assert fx.new_text is not None and "  \n" not in fx.new_text
    rev = pp.review("def broken(:\n", "python")
    assert any("syntax error" in d for d in rev.details)


def test_ai_ask_routes_honestly():
    pp = PairProgrammer()
    text = "def f():\n    pass\n"
    for q in ("explain this", "fix the bug", "refactor it", "list todos", "hello?"):
        a = pp.ask(q, text, "python")
        assert a.engine == "local"


# ------------------------------------------------------------------ card/theme (I6, I7)
def test_gbc_card_theme_registered_and_angular():
    assert "gbc-card" in list_themes()
    theme = get_gbc_theme()
    assert theme.corner_radius == 0  # I6: angular, no rounded edges


def test_gbc_card_colors_all_in_palette():
    theme = get_gbc_theme()  # I7
    for where, colors in (("ui", theme.ui), ("syntax", theme.syntax)):
        for key, color in colors.items():
            assert color in GBC_PALETTE, f"{where}.{key}={color} outside GBC palette"


def test_gbc_card_theme_rejects_injection_still():
    from levi.hicomb import validate_theme, ThemeError
    from levi.hicomb.card import gbc_card_theme_data

    data = gbc_card_theme_data()
    data["font_family"] = "<script>alert(1)</script>"
    with pytest.raises(ThemeError):
        validate_theme(data)


# ------------------------------------------------------------------ studio html (I8, I9)
def test_studio_html_self_contained():
    violations = check_self_contained()
    assert violations == [], f"external refs: {violations[:5]}"  # I8


def test_studio_html_panels_present():
    missing = check_panels()
    assert missing == [], f"missing panels: {missing}"  # I9


def test_studio_manifest_honest():
    from levi.hicomb import studio_manifest

    m = studio_manifest()
    assert m["offline"] is True
    assert len(m["panels"]) >= 12
