"""Law -> guard -> prove for the programming-proficiency corpus.

Laws:
  L1 determinism: the generator is seeded and fixed-order; two runs are
     byte-identical.
  L2 record shape: every line parses and carries text/kind/source/topic/
     lesson_n; the User/LEVI turn format holds; source is constant.
  L3 lesson coverage: exactly lessons 1..14; every lesson has >=1 record of
     each of the 5 kinds; lesson order preserved in file order.
  L4 code proof: every ```python fence in a LEVI answer of a code-carrying
     kind compiles; every debug record's broken block genuinely fails
     (compile error or a raised exception on execution).
  L5 manifest honesty: total_records == jsonl line count; section counts sum
     to the total; per-kind counts match the file; total_chars matches.
  L6 wiring: train_bpev3.py defines PROGRAMMING -> corpus_programming.jsonl,
     includes it in the corpus loop, and carries the 3 programming
     qualitative prompts (source-text check; torch is never imported).
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TRAIN_DIR = REPO / "core" / "levi" / "brain" / "train"
BUILDER = TRAIN_DIR / "build_programming_corpus.py"
CORPUS = TRAIN_DIR / "corpus_programming.jsonl"
MANIFEST = TRAIN_DIR / "corpus_programming_manifest.json"
TRAINER = TRAIN_DIR / "train_bpev3.py"

SOURCE = "programming-course-v1"
KINDS = ("concept", "write-code", "debug", "read-code", "lesson")
CODE_KINDS = ("write-code", "debug", "read-code")
FENCE_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)

NEW_PROMPTS = [
    r"User: write a function that doubles a number\nLEVI:",
    r"User: what does this print: for i in range(3): print(i)\nLEVI:",
    r"User: fix this code: pirnt('hi')\nLEVI:",
]


def load_records(path=CORPUS):
    recs = []
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            recs.append((i, json.loads(line)))
    return recs


# ------------------------------------------------------- L1 determinism

def test_determinism_byte_identical(tmp_path):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    for out in (a, b):
        proc = subprocess.run(
            [sys.executable, str(BUILDER), "--out", str(out)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert proc.returncode == 0, f"builder failed:\n{proc.stderr}"
    assert a.read_bytes() == b.read_bytes(), "two runs differ — not deterministic"


# ------------------------------------------------------------- L2 shape

def test_record_shape():
    recs = load_records()
    assert recs, "corpus is empty"
    for lineno, r in recs:
        assert set(r.keys()) == {"text", "kind", "source", "topic", "lesson_n"}, (
            f"line {lineno}: bad keys {sorted(r.keys())}"
        )
        assert isinstance(r["text"], str) and r["text"].startswith("User: "), (
            f"line {lineno}: text must start with 'User: '"
        )
        assert "\nLEVI: " in r["text"] or r["text"].endswith("\nLEVI:"), (
            f"line {lineno}: missing LEVI turn"
        )
        assert r["source"] == SOURCE, f"line {lineno}: wrong source {r['source']!r}"
        assert r["kind"] in KINDS, f"line {lineno}: bad kind {r['kind']!r}"
        assert isinstance(r["lesson_n"], int) and 1 <= r["lesson_n"] <= 14, (
            f"line {lineno}: bad lesson_n {r['lesson_n']!r}"
        )


# ---------------------------------------------------------- L3 coverage

def test_lesson_coverage_and_order():
    recs = load_records()
    by_lesson: dict[int, set[str]] = {}
    first_seen: list[int] = []
    for _, r in recs:
        n = r["lesson_n"]
        by_lesson.setdefault(n, set()).add(r["kind"])
        if n not in first_seen:
            first_seen.append(n)
    assert set(by_lesson) == set(range(1, 15)), (
        f"lessons covered: {sorted(by_lesson)}"
    )
    for n in range(1, 15):
        missing = set(KINDS) - by_lesson[n]
        assert not missing, f"lesson {n} missing kinds: {sorted(missing)}"
    assert first_seen == list(range(1, 15)), (
        f"lesson order not preserved: {first_seen}"
    )


# ---------------------------------------------------------- L4 code proof

def test_all_good_code_compiles():
    recs = load_records()
    checked = 0
    for lineno, r in recs:
        if r["kind"] not in CODE_KINDS:
            continue
        answer = r["text"].split("\nLEVI: ", 1)[1]
        for m in FENCE_RE.finditer(answer):
            checked += 1
            try:
                compile(m.group(1), f"<line {lineno}>", "exec")
            except SyntaxError as exc:
                pytest.fail(
                    f"line {lineno} ({r['kind']}, lesson {r['lesson_n']}): "
                    f"good code failed compile: {exc}"
                )
    assert checked > 0, "no python fences found — proof harness broken"


def test_debug_broken_halves_genuinely_fail(tmp_path):
    recs = [r for _, r in load_records() if r["kind"] == "debug"]
    assert recs, "no debug records — proof harness broken"
    checked = 0
    for r in recs:
        user_part, _ = r["text"].split("\nLEVI:", 1)
        tmpl_end = user_part.index("\n", len("User: "))
        buggy = user_part[tmpl_end + 1 :]
        assert buggy.strip(), "empty broken block"
        assert "```python" not in buggy, "broken code must not sit in a python fence"
        checked += 1
        try:
            compile(buggy, "<broken>", "exec")
        except (SyntaxError, IndentationError):
            continue  # fails at parse time: genuinely broken
        # Compiles: must raise when executed.
        script = tmp_path / f"broken_{checked}.py"
        script.write_text(buggy)
        proc = subprocess.run(
            [sys.executable, str(script)],
            input="test\n",
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            timeout=20,
        )
        assert proc.returncode != 0, (
            f"lesson {r['lesson_n']}: broken half ran clean — not a real bug:\n"
            f"{buggy[:400]}"
        )
    assert checked == len(recs)


# ---------------------------------------------------------- L5 manifest

def test_manifest_honest():
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for key in (
        "generator", "version", "seed", "built_utc", "directive",
        "sections", "total_records", "total_chars", "record_shape",
        "sources_per_section",
    ):
        assert key in man, f"manifest missing {key!r}"
    recs = load_records()
    assert man["total_records"] == len(recs), (
        f"manifest total {man['total_records']} != file lines {len(recs)}"
    )
    assert sum(man["sections"].values()) == man["total_records"]
    for kind in KINDS:
        file_count = sum(1 for _, r in recs if r["kind"] == kind)
        assert man["sections"][kind] == file_count, (
            f"manifest {kind}={man['sections'][kind]} != file {file_count}"
        )
        assert man["sources_per_section"][kind] == [SOURCE]
    assert man["total_chars"] == sum(len(r["text"]) for _, r in recs)
    assert man["record_shape"] == ["text", "kind", "source", "topic", "lesson_n"]
    assert "Chauncey 2026-09-29" in man["directive"]


# ------------------------------------------------------------- L6 wiring

def test_trainer_wired():
    src = TRAINER.read_text(encoding="utf-8")
    m = re.search(r'^PROGRAMMING\s*=\s*(.+)$', src, re.M)
    assert m, "PROGRAMMING not defined in train_bpev3.py"
    assert "corpus_programming.jsonl" in m.group(1), (
        f"PROGRAMMING points elsewhere: {m.group(1)}"
    )
    assert re.search(
        r"for path in \(CURRICULUM,\s*PROGRAMMING,\s*DIALOGUE\):", src
    ), "corpus loop does not include PROGRAMMING"
    # HEAD's trainer has no diag machinery (the "no usable texts in" message
    # lives only in a sibling's uncommitted rewrite); prove PROGRAMMING is
    # actually consumed by load_sequences instead.
    body = src.split("def load_sequences")[1]
    assert "PROGRAMMING" in body, "load_sequences never references PROGRAMMING"
    for p in NEW_PROMPTS:
        assert p in src, f"qualitative prompt missing: {p!r}"
