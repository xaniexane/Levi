"""Law-guard-prove tests for the programming course's teachable academy layer.

Laws: 14 lessons in order with unique stable ids; core ideas, examples,
captured outputs, and exercises preserved verbatim from Chauncey's
course source; builder deterministic; CLI surfaces serve the course.
"""

import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

from levi.academy.lessons.programming import (
    format_lesson,
    get_lesson,
    load_lessons,
    next_lesson,
    search,
    syllabus,
)

PKG = Path("core/levi/academy/lessons/programming")


def test_fourteen_lessons_in_order_unique_ids():
    lessons = load_lessons()
    assert [l["n"] for l in lessons] == list(range(1, 15))
    ids = [l["id"] for l in lessons]
    assert len(set(ids)) == 14
    assert all(i and i == i.lower() for i in ids)
    assert [n for n, _i, _t in syllabus()] == list(range(1, 15))


def test_expected_lesson_titles():
    assert [t for _n, _i, t in syllabus()] == [
        "Variables",
        "Decisions & repetition",
        "Functions",
        "Lists & tuples",
        "Dictionaries",
        "Strings in depth",
        "Files & persistence",
        "Errors, exceptions & debugging",
        "Modules, packages & pip",
        "Comprehensions & iteration",
        "Classes",
        "Working with data",
        "Automation",
        "Capstone",
    ]


def test_core_ideas_preserved():
    lessons = load_lessons()
    assert all(l["idea"].strip() for l in lessons)
    assert lessons[0]["idea"].startswith("Every program is input")
    assert "capstone" in lessons[13]["idea"].lower() or "DDD" in lessons[13]["idea"]


def test_examples_present_with_stable_ids():
    lessons = load_lessons()
    code_ids = [e["id"] for l in lessons for e in l["examples"]]
    assert len(code_ids) == 31
    assert len(set(code_ids)) == 31  # stable + unique
    for l in lessons:
        assert l["examples"], f"lesson {l['n']} has no examples"
        for e in l["examples"]:
            assert e["title"].strip() and e["code"].strip()
            assert e["kind"] in ("python", "shell")


def test_python_examples_compile():
    for l in load_lessons():
        for e in l["examples"]:
            if e["kind"] == "python":
                compile(e["code"], f"<lesson{l['n']}:{e['id']}>", "exec")


def test_captured_outputs_where_expected():
    lessons = load_lessons()
    with_out = [e for l in lessons for e in l["examples"] if e["output"] is not None]
    without = [e for l in lessons for e in l["examples"] if e["output"] is None]
    assert len(with_out) == 26  # the 26 verified snippets
    assert all(e["output"].strip() for e in with_out)
    # the 5 without: 4 shell snippets + cap3a (marked skip_run in source)
    assert len(without) == 5
    assert sum(1 for e in without if e["kind"] == "shell") == 4
    assert {e["id"] for e in without} == {"setup3", "setup4", "cap2", "cap3a", "cap5"}
    # spot-check a captured output survived verbatim
    l1e1 = next(e for e in with_out if e["id"] == "l1e1")
    assert "Chauncey <class 'str'>" in l1e1["output"]


def test_exercises_preserved_with_hints():
    lessons = load_lessons()
    total = sum(len(l["exercises"]) for l in lessons)
    assert total == 18
    for l in lessons[:13]:
        trys = [e for e in l["exercises"] if e["kind"] == "try"]
        assert len(trys) == 1, f"lesson {l['n']} should keep its one your-try"
        assert trys[0]["task"].strip() and trys[0]["hint"].strip()
    cap = lessons[13]["exercises"]
    assert [e["kind"] for e in cap] == ["capstone"] * 5
    assert cap[0]["task"].startswith("Exercise 1")


def test_loader_by_number_slug_and_title():
    assert get_lesson(1)["id"] == "variables"
    assert get_lesson("functions")["n"] == 3
    assert get_lesson("14")["title"] == "Capstone"
    assert get_lesson("Dictionaries")["n"] == 5
    with pytest.raises(KeyError):
        get_lesson("nope")


def test_next_lesson_walks_the_course():
    assert next_lesson()["n"] == 1
    seen = []
    cur = next_lesson()
    while cur is not None:
        seen.append(cur["n"])
        cur = next_lesson(cur["n"])
    assert seen == list(range(1, 15))
    assert next_lesson(14) is None
    assert next_lesson("automation")["n"] == 14


def test_search_finds_lessons():
    hits = [l["n"] for l in search("dict")]
    assert hits[0] == 5  # the dictionaries lesson ranks first
    assert 11 in [l["n"] for l in search("class")]
    assert search("zzz-no-such-thing") == []


def test_format_lesson_teaches():
    out = format_lesson(get_lesson(2))
    assert "Lesson 2/14" in out
    assert "Core idea:" in out
    assert "for name in names" in out
    assert "Your try:" in out
    assert "Hint:" in out


def test_builder_deterministic(tmp_path):
    built = tmp_path / "lessons.json"
    r = subprocess.run(
        [sys.executable, str(PKG / "build_programming_lessons.py"),
         "--out", str(built), "--manifest", str(tmp_path / "m.json")],
        capture_output=True, text=True, cwd=Path.cwd(),
    )
    assert r.returncode == 0, r.stderr
    assert built.read_bytes() == (PKG / "lessons.json").read_bytes()


def test_manifest_provenance():
    m = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
    assert m["total_lessons"] == 14
    assert m["total_examples"] == 31
    assert m["total_exercises"] == 18
    assert m["examples_with_output"] == 26
    assert len(m["source"]["content_sha256"]) == 64


def test_module_cli_syllabus_and_lesson(monkeypatch, tmp_path, capsys):
    from levi.academy.__main__ import main

    monkeypatch.setenv("HOME", str(tmp_path))
    assert main(["programming"]) == 0
    assert "14 lessons" in capsys.readouterr().out
    assert main(["programming", "lesson", "3"]) == 0
    assert "Functions" in capsys.readouterr().out


def test_module_cli_unknown_lesson_fails_closed(monkeypatch, tmp_path, capsys):
    from levi.academy.__main__ import main

    monkeypatch.setenv("HOME", str(tmp_path))
    assert main(["programming", "lesson", "99"]) == 2
    assert main(["programming", "bogus"]) == 2


def test_main_cli_programming_action(capsys):
    from levi.cli.main import cmd_academy

    args = types.SimpleNamespace(
        academy_action="programming", programming_args=["syllabus"]
    )
    assert cmd_academy(args) == 0
    assert "Variables" in capsys.readouterr().out

    args = types.SimpleNamespace(
        academy_action="programming",
        programming_args=["next", "--after", "13"],
    )
    assert cmd_academy(args) == 0
    assert "Capstone" in capsys.readouterr().out
