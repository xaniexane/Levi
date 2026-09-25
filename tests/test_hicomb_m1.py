"""Hicomb M1 (Phase-0 skeleton) tests — run from zero, hermetic, offline.

Covers: buffer engine, highlighting, search, tabs/session, command bar
(proposer + verifier twins), snippets, themes, journal, economy, dock.
"""

import copy
import json

import pytest

from levi.hicomb import (
    PLATFORM_CUT,
    Buffer,
    BufferError,
    CommandBar,
    CommandRegistry,
    CommandVerdict,
    CommandVerifier,
    DockReport,
    EditJournal,
    FileVerdict,
    OwnerGateRequired,
    Session,
    ThemeError,
    builders_available,
    collect_entry_fee,
    customize,
    default_registry,
    detect_language,
    dispatch,
    dock_builders,
    expand,
    export_theme,
    file_tree,
    find_all,
    get_theme,
    highlight,
    list_themes,
    marketplace_royalty,
    project_replace,
    project_search,
    replace_all,
    row_for,
    theme_from_json,
    tokenize,
    validate_theme,
)
from levi.hicomb import bracket_pairs as _bracket_pairs
from levi.hicomb import dock as _dock
from levi.hicomb import journal as _journal_mod
from levi.hicomb import snippets as _snippets
from levi.hicomb.tabs import SessionError


# ------------------------------------------------------------------ buffer
def test_buffer_open_edit_save_roundtrip(tmp_path):
    p = tmp_path / "a.py"
    p.write_text("x = 1\n", encoding="utf-8")
    buf = Buffer.open(str(p))
    assert buf.line_count == 2  # trailing newline -> empty last line
    assert not buf.dirty
    buf.insert(0, 5, "\nprint(x)")
    assert buf.dirty
    assert "print(x)" in buf.get_text()
    buf.save()
    assert not buf.dirty
    assert "print(x)" in p.read_text(encoding="utf-8")


def test_buffer_crlf_preserved(tmp_path):
    p = tmp_path / "w.txt"
    p.write_bytes(b"a\r\nb\r\n")
    buf = Buffer.open(str(p))
    assert buf.newline == "\r\n"
    out = tmp_path / "w2.txt"
    buf.save(str(out))
    assert out.read_bytes() == b"a\r\nb\r\n"


def test_buffer_refuses_binary(tmp_path):
    p = tmp_path / "b.bin"
    p.write_bytes(b"\x00\x01\x02binary")
    with pytest.raises(BufferError):
        Buffer.open(str(p))


def test_buffer_delete_multiline_and_undo():
    buf = Buffer("one\ntwo\nthree\nfour")
    removed = buf.delete(0, 2, 2, 3)  # "e\ntwo\nthr"
    assert removed == "e\ntwo\nthr"
    assert buf.get_text() == "onee\nfour"
    assert buf.undo()
    assert buf.get_text() == "one\ntwo\nthree\nfour"
    assert buf.redo()
    assert buf.get_text() == "onee\nfour"


def test_buffer_undo_redo_chains():
    buf = Buffer("ab")
    buf.insert(0, 2, "cd")
    buf.insert(0, 0, ">>")
    assert buf.get_text() == ">>abcd"
    assert buf.undo() and buf.undo()
    assert buf.get_text() == "ab"
    assert not buf.undo()
    assert buf.redo() and buf.redo()
    assert buf.get_text() == ">>abcd"
    # new edit clears redo
    buf.undo()
    buf.insert(0, 0, "!")
    assert not buf.can_redo
    assert buf.get_text() == "!abcd"


def test_buffer_replace_range_is_one_undo_step():
    buf = Buffer("hello world")
    buf.replace_range(0, 6, 0, 11, "there")
    assert buf.get_text() == "hello there"
    buf.undo()
    assert buf.get_text() == "hello world"


def test_buffer_out_of_range_raises():
    buf = Buffer("x")
    with pytest.raises(BufferError):
        buf.insert(5, 0, "y")
    with pytest.raises(BufferError):
        buf.delete(0, 0, 0, 9)
    with pytest.raises(BufferError):
        buf.line(3)


def test_buffer_large_flag_and_window():
    buf = Buffer("\n".join(f"l{i}" for i in range(20001)))
    assert buf.is_large
    assert buf.lines(19999, 20001) == ["l19999", "l20000"]
    small = Buffer("a\nb")
    assert not small.is_large


def test_buffer_save_needs_path():
    with pytest.raises(BufferError):
        Buffer("x").save()


# --------------------------------------------------------------- highlight
def test_python_highlight_basics():
    toks = tokenize(["def foo(x):  # hi", '    return "s" + 42'], "python")[0]
    kinds = {t.kind for t in toks}
    assert {"keyword", "function", "comment"} <= kinds
    line2 = tokenize(['    return "s" + 42'], "python")[0]
    kinds2 = {t.kind for t in line2}
    assert {"keyword", "string", "number"} <= kinds2


def test_python_triple_string_spans_lines():
    toks = tokenize(['x = """start', "middle", 'end""" + y'], "python")
    assert toks[0][-1].kind == "string"
    assert all(t.kind == "string" for t in toks[1])
    assert toks[2][0].kind == "string"
    # y after the closing quotes is plain text, not string
    assert toks[2][-1].kind == "text"


def test_python_decorator():
    toks = tokenize(["@dataclass", "class A:  # c"], "python")[0]
    assert toks[0].kind == "decorator"


def test_js_block_comment_spans_lines():
    toks = tokenize(["/* open", "still", "close */ var x = 1;"], "javascript")
    assert toks[0][-1].kind == "comment"
    assert all(t.kind == "comment" for t in toks[1])
    kinds = {t.kind for t in toks[2]}
    assert "comment" in kinds and "keyword" in kinds


def test_html_tags_and_attrs():
    toks = tokenize(['<a href="u" class=x>hi</a>'], "html")[0]
    kinds = {t.kind for t in toks}
    assert {"tag", "attr", "string"} <= kinds


def test_html_comment():
    toks = tokenize(["<!-- hi -->"], "html")[0]
    assert toks[0].kind == "comment"


def test_css_property_is_attr():
    toks = tokenize(["  color: red;"], "css")[0]
    by_kind = {t.kind: t.text_of("  color: red;") for t in toks}
    assert by_kind.get("attr") == "color"


def test_shell_variable_and_comment():
    toks = tokenize(['echo "hi $HOME" # done'], "shell")[0]
    kinds = {t.kind for t in toks}
    assert {"string", "comment"} <= kinds
    toks2 = tokenize(["echo $HOME"], "shell")[0]
    assert any(t.kind == "variable" for t in toks2)


def test_markdown_heading_bold_code_link():
    toks = tokenize(["# Title", "**b** and `c` and [t](u)"], "markdown")
    assert toks[0][0].kind == "heading"
    kinds = {t.kind for t in toks[1]}
    assert {"bold", "code", "link"} <= kinds


def test_markdown_fence():
    toks = tokenize(["```py", "x = 1", "```"], "markdown")
    assert all(t[0].kind == "code" for t in toks)


def test_highlight_is_deterministic():
    lines = ['def f(a, b="x"):  # c', "    return a + 1"]
    a = tokenize(lines, "python")
    b = tokenize(lines, "python")
    assert [(t.kind, t.start, t.end) for lt in a for t in lt] == [
        (t.kind, t.start, t.end) for lt in b for t in lt
    ]


def test_highlight_window_matches_full_slice():
    lines = [f"# c{i}" if i % 3 else f"x_{i} = {i}" for i in range(60)]
    full = tokenize(lines, "python")
    windowed = highlight(lines, "python", start=20, end=30)
    assert [[(t.kind, t.start, t.end) for t in lt] for lt in windowed] == [
        [(t.kind, t.start, t.end) for t in lt] for lt in full[20:30]
    ]


def test_highlight_window_mid_block_comment():
    lines = ["/* a", "b", "c */", "var x = 1;"]
    toks = highlight(lines, "javascript", start=3, end=4)
    assert any(t.kind == "keyword" for t in toks[0])


def test_detect_language():
    assert detect_language("a.py") == "python"
    assert detect_language("B.TSX") == "typescript"
    assert detect_language("x.md") == "markdown"
    assert detect_language("run.sh") == "shell"
    assert detect_language("weird.zzz") == "plain"


# ------------------------------------------------------------------ search
def test_find_all_defaults_case_insensitive():
    hits = find_all(["Hello hello HELLO"], "hello")
    assert len(hits) == 3
    hits_cs = find_all(["Hello hello"], "hello", case_sensitive=True)
    assert len(hits_cs) == 1


def test_find_regex_and_whole_word():
    hits = find_all(["foo1 foo22"], r"foo\d+", regex=True)
    assert len(hits) == 2
    hits = find_all(["foobar foo"], "foo", whole_word=True)
    assert len(hits) == 1 and hits[0].start == 7


def test_find_empty_pattern_raises():
    with pytest.raises(ValueError):
        find_all(["x"], "")


def test_replace_all_is_single_undo():
    buf = Buffer("a a a")
    n = replace_all(buf, "a", "b")
    assert n == 3 and buf.get_text() == "b b b"
    buf.undo()
    assert buf.get_text() == "a a a"


def test_replace_regex_groups():
    buf = Buffer("2026-09-21")
    n = replace_all(buf, r"(\d+)-(\d+)-(\d+)", r"\3/\2/\1", regex=True)
    assert n == 1 and buf.get_text() == "21/09/2026"


def test_project_search_skips_git_and_binary(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x").write_text("needle")
    (tmp_path / "bin.dat").write_bytes(b"\x00needle")
    (tmp_path / "ok.txt").write_text("a needle here")
    hits = project_search(str(tmp_path), "needle")
    assert [h.path for h in hits] == [str(tmp_path / "ok.txt")]
    assert hits[0].matches[0].line == 0


def test_project_replace_ternary(tmp_path):
    (tmp_path / "a.txt").write_text("x x")
    (tmp_path / "b.txt").write_text("nope")
    big = "y " * 60  # 60 hits > REVIEW_THRESHOLD
    (tmp_path / "c.txt").write_text(big)
    (tmp_path / "d.bin").write_bytes(b"\x00y")
    v = project_replace(str(tmp_path), "x", "z")
    assert v[str(tmp_path / "a.txt")] is FileVerdict.REPLACED
    assert (tmp_path / "a.txt").read_text() == "z z"
    v2 = project_replace(str(tmp_path), "y", "z")
    assert v2[str(tmp_path / "c.txt")] is FileVerdict.REVIEW_NEEDED
    assert "y" in (tmp_path / "c.txt").read_text()  # untouched
    assert v2[str(tmp_path / "d.bin")] is FileVerdict.SKIPPED
    v3 = project_replace(str(tmp_path), "zzz-nope", "q")
    assert v3[str(tmp_path / "b.txt")] is FileVerdict.CLEAN


# -------------------------------------------------------------------- tabs
def test_session_tabs_open_reuse_close(tmp_path):
    p = tmp_path / "f.py"
    p.write_text("1")
    s = Session()
    t1 = s.open_tab(str(p))
    t2 = s.open_tab(str(p))
    assert t1 is t2 and len(s.tabs) == 1
    s.open_tab()  # untitled
    assert len(s.tabs) == 2
    assert s.switch_tab(0) is t1
    s.close_tab(1)
    assert len(s.tabs) == 1


def test_session_refuses_dirty_close(tmp_path):
    s = Session()
    s.open_tab()
    s.active.buffer.insert(0, 0, "dirty")
    with pytest.raises(SessionError):
        s.close_tab()
    s.close_tab(force=True)
    assert s.tabs == []


def test_session_save_active(tmp_path):
    s = Session()
    s.open_tab()
    s.active.buffer.insert(0, 0, "hi")
    out = tmp_path / "note.txt"
    saved = s.save_active(str(out))
    assert saved == str(out) and out.read_text() == "hi"


def test_open_folder_detects_git(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    s = Session()
    info = s.open_folder(str(tmp_path))
    assert info["is_repo"] and info["vcs"] == "git" and info["branch"] == "main"
    s2 = Session()
    plain = tmp_path / "plain"
    plain.mkdir()
    info3 = s2.open_folder(str(plain))
    assert not info3["is_repo"]


def test_file_tree_skips_vcs(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "h").write_text("x")
    (tmp_path / "a.txt").write_text("x")
    tree = file_tree(str(tmp_path))
    names = [c["name"] for c in tree["children"]]
    assert "a.txt" in names and ".git" not in names


def test_session_state_roundtrip(tmp_path):
    p1 = tmp_path / "one.py"
    p2 = tmp_path / "two.py"
    p1.write_text("1")
    p2.write_text("2")
    s = Session()
    s.open_folder(str(tmp_path))
    s.open_tab(str(p1))
    s.open_tab(str(p2))
    state_path = tmp_path / "state.json"
    s.save_state(str(state_path))
    s2 = Session.load_state(str(state_path))
    assert [t.path for t in s2.tabs] == [str(p1), str(p2)]
    assert s2.folder == str(tmp_path)
    assert s2.active.path == str(p2)


def test_session_load_skips_missing_files(tmp_path):
    state_path = tmp_path / "s.json"
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "folder": None,
                "tabs": [str(tmp_path / "gone.py")],
                "active": 0,
            }
        )
    )
    s = Session.load_state(str(state_path))
    assert s.tabs == [] and s.active is None


def test_recent_files_mru(tmp_path):
    s = Session()
    paths = []
    for name in ("a.py", "b.py", "c.py"):
        p = tmp_path / name
        p.write_text("x")
        paths.append(str(p))
        s.open_tab(str(p))
    recent = s.recent_files()
    assert recent[-1] == paths[-1]  # active tab last


# ---------------------------------------------------------------- commands
def test_command_bar_proposes_ranked():
    reg = default_registry()
    bar = CommandBar(reg)
    top = bar.propose("save")
    ids = [c.id for c, _ in top]
    assert "file.save" in ids and "file.save_all" in ids
    # exact-ish query ranks the file.save command first
    assert bar.propose("save file")[0][0].id == "file.save"
    assert bar.propose("zzz-no-such-thing") == []


def test_verifier_ternary():
    reg = default_registry()
    v = CommandVerifier(reg)
    assert v.verify("file.save", {}) is CommandVerdict.EXECUTED
    assert v.verify("nope.nope", {}) is CommandVerdict.UNKNOWN_COMMAND
    assert v.verify("file.open", {}) is CommandVerdict.ARGS_REVIEW  # missing path
    assert (
        v.verify("file.open", {"path": "x", "bogus": 1}) is CommandVerdict.ARGS_REVIEW
    )


def test_dispatch_runs_and_reports(tmp_path):
    p = tmp_path / "d.py"
    p.write_text("old old")
    s = Session()
    reg = default_registry()
    verdict, msg = dispatch(s, reg, "file.open", {"path": str(p)})
    assert verdict is CommandVerdict.EXECUTED and "d.py" in msg
    verdict, msg = dispatch(s, reg, "edit.find", {"pattern": "old"})
    assert verdict is CommandVerdict.EXECUTED and "2 hit(s)" in msg
    verdict, msg = dispatch(
        s, reg, "edit.replace", {"pattern": "old", "replacement": "new"}
    )
    assert verdict is CommandVerdict.EXECUTED and "2 hit(s)" in msg
    assert s.active.buffer.get_text() == "new new"


def test_dispatch_unknown_and_missing_args():
    s = Session()
    reg = default_registry()
    v, msg = dispatch(s, reg, "nope.cmd", {})
    assert v is CommandVerdict.UNKNOWN_COMMAND
    v, msg = dispatch(s, reg, "edit.goto", {})
    assert v is CommandVerdict.ARGS_REVIEW and "line" in msg


def test_dispatch_failing_command_fails_safe():
    s = Session()  # no active tab -> edit.goto raises inside run
    reg = CommandRegistry()
    from levi.hicomb.commands import Command

    reg.register(
        Command(
            id="boom.x",
            title="Boom",
            touch_label="Boom",
            run=lambda sess, args: 1 / 0,
        )
    )
    v, msg = dispatch(s, reg, "boom.x", {})
    assert v is CommandVerdict.ARGS_REVIEW and "failed safely" in msg


def test_dispatch_goto_and_snapshot(tmp_path):
    s = Session()
    reg = default_registry()
    p = tmp_path / "g.py"
    p.write_text("l1\nl2 target\nl3")
    dispatch(s, reg, "file.open", {"path": str(p)})
    v, msg = dispatch(s, reg, "edit.goto", {"line": 2})
    assert v is CommandVerdict.EXECUTED and "l2 target" in msg
    snap = tmp_path / "snap.json"
    v, msg = dispatch(s, reg, "session.snapshot", {"path": str(snap)})
    assert v is CommandVerdict.EXECUTED and snap.exists()


def test_dispatch_snippets_row_and_theme():
    s = Session()
    reg = default_registry()
    v, msg = dispatch(s, reg, "snippets.row", {"language": "python"})
    assert v is CommandVerdict.EXECUTED and "def" in msg
    v, msg = dispatch(s, reg, "theme.set", {"name": "void"})
    assert v is CommandVerdict.EXECUTED


# ---------------------------------------------------------------- snippets
def test_snippet_row_and_expand():
    row = row_for("python")
    assert "def" in row and "(" in row
    row.append("MUT")
    assert "MUT" not in row_for("python")  # copies, not aliases
    body = expand("python", "def")
    assert body and "${1:name}" in body
    assert expand("python", "nope") is None
    assert row_for("unknown-lang") == row_for("python")  # sane fallback


def test_bracket_pairs():
    pairs = _bracket_pairs()
    assert pairs["("] == ")" and pairs["{"] == "}"
    pairs["("] = "X"
    assert _bracket_pairs()["("] == ")"


# ------------------------------------------------------------------ themes
def test_builtin_themes_validate():
    for name in list_themes():
        theme = get_theme(name)
        assert theme.name == name
        assert len(theme.surfaces) == 7  # every editor surface
        assert theme.color_for("keyword").startswith("#")


def test_theme_rejects_injection():
    good = json.loads(get_theme("void").to_json())
    for evil_value in (
        "<script>alert(1)</script>",
        "javascript:alert(1)",
        "red; expression(alert(1))",
        "{{constructor}}",
    ):
        data = copy.deepcopy(good)
        data["name"] = evil_value
        with pytest.raises(ThemeError):
            validate_theme(data)
    data = copy.deepcopy(good)
    data["font_family"] = "x</style><script>"
    with pytest.raises(ThemeError):
        validate_theme(data)


def test_theme_rejects_bad_shapes():
    good = json.loads(get_theme("void").to_json())

    data = copy.deepcopy(good)
    data["ui"]["background"] = "red"
    with pytest.raises(ThemeError):
        validate_theme(data)
    data = copy.deepcopy(good)
    data["ui"]["nope"] = "#ffffff"
    with pytest.raises(ThemeError):
        validate_theme(data)
    data = copy.deepcopy(good)
    del data["ui"]["text"]
    with pytest.raises(ThemeError):
        validate_theme(data)
    data = copy.deepcopy(good)
    data["font_scale"] = 99
    with pytest.raises(ThemeError):
        validate_theme(data)
    with pytest.raises(ThemeError):
        get_theme("no-such-theme")


def test_customize_remix_and_roundtrip():
    mine = customize(
        "void",
        "chauncey-void",
        {
            "ui": {"accent": "#ff00ff"},
            "syntax": {"keyword": "#00ff00"},
            "font_scale": 1.25,
        },
    )
    assert mine.name == "chauncey-void"
    assert mine.ui["accent"] == "#ff00ff"
    assert mine.syntax["keyword"] == "#00ff00"
    assert mine.font_scale == 1.25
    # base theme untouched
    assert get_theme("void").ui["accent"] != "#ff00ff"
    # export -> import roundtrip
    back = theme_from_json(export_theme(mine))
    assert back == mine
    # injection via override dies at validation
    with pytest.raises(ThemeError):
        customize("void", "evil2", {"ui": {"accent": "<img src=x>"}})


# ------------------------------------------------------------------ journal
def test_journal_append_recall(tmp_path):
    j = EditJournal(str(tmp_path))
    j.append("edit", "a.py", "fixed off-by-one in parser")
    j.append("save", "a.py")
    j.append("edit", "b.py", "fixed off-by-one in lexer")
    assert j.count() == 3
    hits = j.recall("off-by-one")
    assert len(hits) == 2
    assert j.recall("parser")[0].path == "a.py"
    assert j.recall("zzz") == []


def test_journal_skips_corrupt_lines(tmp_path):
    j = EditJournal(str(tmp_path))
    j.append("edit", "a.py", "ok")
    with open(j.path, "a", encoding="utf-8") as fh:
        fh.write("NOT JSON{{{\n")
    j.append("save", "a.py")
    assert j.count() == 2


def test_journal_rotates(tmp_path, monkeypatch):
    monkeypatch.setattr(_journal_mod, "MAX_ENTRIES", 5)
    j = EditJournal(str(tmp_path))
    for i in range(8):
        j.append("edit", f"f{i}.py", f"change {i}")
    assert j.count() == 5
    assert j.entries()[0].path == "f3.py"


# ------------------------------------------------------------------ economy
def test_economy_cut_and_gates():
    assert PLATFORM_CUT == 0.12
    assert marketplace_royalty(100.0) == 12.0
    from levi.hicomb.economy import builder_take

    assert builder_take(100.0) == 88.0
    with pytest.raises(ValueError):
        marketplace_royalty(-1)
    with pytest.raises(OwnerGateRequired):
        collect_entry_fee()  # price is Chauncey's call


# --------------------------------------------------------------------- dock
def test_builders_available_is_bool():
    assert isinstance(builders_available(), bool)


def test_dock_builders_never_raises():
    s = Session()
    reg = default_registry()
    report = dock_builders(s, reg)
    assert isinstance(report, DockReport)
    if report.available and report.attached:
        assert "builders" in s.extensions
        assert "builders.scaffold" in report.commands_registered
        v, _ = dispatch(s, reg, "builders.scaffold", {})
        assert v is CommandVerdict.ARGS_REVIEW  # prompt required
    else:
        assert not report.attached  # honest about sibling flux


def test_project_model_hook_is_honest_stub():
    assert _dock.project_model(Session()) is None


# ------------------------------------------------------- offline / hygiene
def test_no_network_imports_in_hicomb():
    import pathlib

    pkg = pathlib.Path(_snippets.__file__).parent
    banned = ("import socket", "import urllib", "import http", "import requests")
    for py in pkg.glob("*.py"):
        src = py.read_text(encoding="utf-8")
        for bad in banned:
            assert bad not in src, f"{py.name} contains {bad!r}"


def test_package_exports():
    import levi.hicomb as h

    for name in (
        "Buffer",
        "Session",
        "CommandBar",
        "Theme",
        "EditJournal",
        "PLATFORM_CUT",
        "dock_builders",
    ):
        assert name in h.__all__ and hasattr(h, name)
