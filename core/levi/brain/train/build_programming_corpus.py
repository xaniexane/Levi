"""Build the programming-proficiency corpus for LEVI's native brain.

Chauncey 2026-09-29: LEVI must be PROFICIENT in programming "like the law" --
write, debug, explain, and apply it, not just recite lessons. The source of
truth is HIS 14-lesson programming course (originals-first law): every record
derives from
  /home/hatch/workspace/your_files/programming-full-course/build/content.py
and the verified outputs in outputs.json. Nothing invented, nothing from a
generic Python course.

Deterministic: fixed lesson order, index-based rotation (no sampling), all
solutions RUN at build time via subprocess with fixed inputs, captured stdout
embedded. Rerunning this file produces byte-identical corpus output. The
manifest carries built_utc (provenance only, never inside a record).

Record shape: {"text", "kind", "source", "topic", "lesson_n"}.
"User: ...\\nLEVI: ..." turn format matches the curriculum/dialogue corpora.

Five kinds per lesson:
  concept     - explain the lesson's core idea in plain words (extractive)
  write-code  - spec -> solution, written AND run at build time
  debug       - broken -> fixed, one plausible bug; broken genuinely fails,
                fixed compiles and runs
  read-code   - what does this snippet do / print, with verified output
  lesson      - condensed "teach the lesson" record

Usage: python3 build_programming_corpus.py [--out corpus_programming.jsonl]
"""

from __future__ import annotations

import argparse
import datetime
import json
import keyword
import re
import subprocess
import sys
import tempfile
from pathlib import Path

COURSE_BUILD = Path(__file__).resolve().parent / "course_data"
sys.path.insert(0, str(COURSE_BUILD))
import content as course_content  # noqa: E402  (pure data, no side effects)

OUTPUTS: dict[str, str] = json.loads((COURSE_BUILD / "outputs.json").read_text())

HERE = Path(__file__).resolve().parent
OUT = HERE / "corpus_programming.jsonl"
MANIFEST = HERE / "corpus_programming_manifest.json"

SEED = 20260929
GENERATOR_VERSION = "2026-09-29-v1"
SOURCE = "programming-course-v1"

USER = "User: "
LEVI = "LEVI: "

KINDS = ("concept", "write-code", "debug", "read-code", "lesson")

SLUGS = {
    1: "variables",
    2: "decisions-repetition",
    3: "functions",
    4: "lists-tuples",
    5: "dictionaries",
    6: "strings",
    7: "files",
    8: "errors-debugging",
    9: "modules-pip",
    10: "comprehensions",
    11: "classes",
    12: "working-with-data",
    13: "automation",
    14: "capstone",
}

# Snippets with deterministic, verified outputs (keyed L{n}:{code_id}).
# Excluded: l9e1 (random.choice + date.today -> volatile), setup3/setup4/cap2/cap5
# (shell commentary, no captured output).
READ_SNIPPETS = {
    1: ["l1e1", "l1e2"], 2: ["l2e1", "l2e2", "l2e3"], 3: ["l3e1", "l3e2"],
    4: ["l4e1", "l4e2"], 5: ["l5e1", "l5e2"], 6: ["l6e1", "l6e2"],
    7: ["l7e1", "l7e2"], 8: ["l8e1", "l8e2"], 9: ["l9e2"],
    10: ["l10e1", "l10e2"], 11: ["l11e1"], 12: ["l12e1", "l12e2"],
    13: ["l13e1"], 14: ["cap3b"],
}
# Snippets whose fixed half can be executed standalone at build time.
# l8e1's fixed half is the lesson's own correction (print(total), not the crash).
DEBUG_SNIPPETS = {
    1: ["l1e1", "l1e2"], 2: ["l2e1", "l2e2", "l2e3"], 3: ["l3e1", "l3e2"],
    4: ["l4e1", "l4e2"], 5: ["l5e1", "l5e2"], 6: ["l6e1", "l6e2"],
    7: ["l7e1", "l7e2"], 8: ["l8e1", "l8e2"], 9: ["l9e2"],
    10: ["l10e1", "l10e2"], 11: ["l11e1"], 12: ["l12e1", "l12e2"],
    13: ["l13e1"], 14: ["cap3a-adapted"],
}


def rec(text: str, kind: str, lesson_n: int) -> dict:
    return {
        "text": text,
        "kind": kind,
        "source": SOURCE,
        "topic": SLUGS[lesson_n],
        "lesson_n": lesson_n,
    }


# ------------------------------------------------------------ prose helpers

def clean(s: str) -> str:
    s = s.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", s).strip()


def shorten(s: str, limit: int = 180) -> str:
    s = clean(s)
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0]
    return cut + "..."


def norm_output(s: str) -> str:
    """Normalize volatile paths in verified outputs (L8:l8e1 traceback)."""
    return re.sub(r"/tmp/course-verify-[A-Za-z0-9]+/main\.py", "main.py", s)


def lesson_by_n(n: int) -> dict:
    for lesson in course_content.LESSONS:
        if lesson["n"] == n:
            return lesson
    raise KeyError(f"lesson {n} missing from course content")


def code_block(lesson: dict, code_id: str) -> dict:
    for kind, blk in lesson["blocks"]:
        if kind == "code" and blk.get("id") == code_id:
            return blk
    raise KeyError(f"code block {code_id} missing in lesson {lesson['n']}")


def following_prose(lesson: dict, code_id: str) -> str | None:
    seen = False
    for kind, blk in lesson["blocks"]:
        if kind == "code" and blk.get("id") == code_id:
            seen = True
            continue
        if seen and kind == "p":
            return blk
    return None


# ------------------------------------------------------- build-time runner

GREET_PY = 'def hello(name):\n    return f"Hello, {name}!"\n'
INVOICES_CSV = (
    "invoice_id,client,amount,paid\n"
    "INV-1042,Ava,400,no\n"
    "INV-1043,Ben,150,yes\n"
    "INV-1044,Cy,275,no\n"
)


def prep_sandbox(d: Path, pre_code: str | None = None) -> None:
    (d / "greet.py").write_text(GREET_PY)
    (d / "invoices.csv").write_text(INVOICES_CSV)
    if pre_code:
        run_python(pre_code, cwd=d)


def run_python(
    code: str,
    stdin: str | None = None,
    cwd: Path | None = None,
    argv: list[str] | None = None,
    timeout: int = 15,
) -> tuple[int, str, str]:
    """Run code in a subprocess. Returns (returncode, stdout, stderr).

    When cwd is given the script is written inside it, so sibling imports
    (greet, helpers, data files) resolve the way a real run would.
    """
    with tempfile.TemporaryDirectory() as td:
        workdir = Path(cwd) if cwd else Path(td)
        script = workdir / "main.py"
        script.write_text(code)
        proc = subprocess.run(
            [sys.executable, str(script)] + (argv or []),
            input=stdin,
            # Never inherit a live stdin: without explicit input the child
            # gets EOF immediately instead of blocking forever on input().
            stdin=None if stdin is not None else subprocess.DEVNULL,
            capture_output=True,
            text=True,
            cwd=str(workdir),
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr


def run_in_sandbox(code: str, snippet_key: str, stdin=None, argv=None) -> str:
    """Run lesson code in a sandbox dir pre-staged with course fixtures."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        pre = None
        if snippet_key == "L7:l7e2":
            # l7e2 reads what l7e1 wrote; reproduce the course's sequence.
            l7 = lesson_by_n(7)
            pre = code_block(l7, "l7e1")["code"]
        prep_sandbox(d, pre)
        rc, out, err = run_python(code, stdin=stdin, cwd=d, argv=argv)
        if rc != 0:
            raise RuntimeError(f"sandbox run failed for {snippet_key}:\n{err}")
        return out


def run_solution(
    code: str,
    stdin: str | None = None,
    argv: list[str] | None = None,
    files: dict[str, str] | None = None,
) -> str:
    """Run a write-code solution in an isolated dir; return stdout."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        for name, body in (files or {}).items():
            (d / name).write_text(body)
        rc, out, err = run_python(code, stdin=stdin, cwd=d, argv=argv)
        if rc != 0:
            raise RuntimeError(f"solution run failed:\n{err}")
        return out


# ------------------------------------------------------------- concept

CONCEPT_USERS = [
    "explain {title}",
    "what is {title} about",
    "teach me {title}",
    "in plain words, what is {title}",
    "explain {title} like I'm new to code",
    "what's the big idea behind {title}",
    "break down {title} for me",
    "I don't get {title} — explain it",
    "what does lesson {n} on {title} teach",
    "describe {title} in plain English",
    "give me the plain-words version of {title}",
    "{title} — what is it really about",
]


def gen_concept(lesson: dict) -> list[dict]:
    n, title = lesson["n"], lesson["title"]
    moves = [shorten(blk) for kind, blk in lesson["blocks"] if kind == "p"]
    body = (
        f"The core idea: {clean(lesson['idea'])}\n\n"
        "Key moves:\n" + "\n".join(f"- {m}" for m in moves)
    )
    return [
        rec(f"{USER}{u.format(title=title, n=n)}\n{LEVI}{body}", "concept", n)
        for u in CONCEPT_USERS
    ]


# ---------------------------------------------------------- write-code

# Solutions are authored here, RUN at build time, stdout embedded.
# Every solution is deterministic: fixed inputs, no randomness, no
# timestamps or memory addresses in printed output.
SOLUTIONS: dict[str, dict] = {
    "L1": {
        "task": "Ask the user for two whole numbers and print their sum.",
        "hint": 'input() always returns text, even when the user types digits. int() turns text like "42" into the number 42. You\'ll need it twice.',
        "code": 'a = int(input("First number: "))\nb = int(input("Second number: "))\nprint(a + b)',
        "stdin": "7\n5\n",
    },
    "L2": {
        "task": 'Print the numbers 1 to 20, but print the word "even" instead of each even number.',
        "hint": "range(1, 21) gives 1..20. n % 2 is the remainder after dividing by 2 — it equals 0 exactly when n is even.",
        "code": "for n in range(1, 21):\n    if n % 2 == 0:\n        print(\"even\")\n    else:\n        print(n)",
    },
    "L3": {
        "task": "Write total(numbers) — a function that takes a list of numbers and returns their sum.",
        "hint": "Start with t = 0. Loop over the list, add each number to t. Return t — after the loop ends, so check your indentation.",
        "code": "def total(numbers):\n    t = 0\n    for n in numbers:\n        t = t + n\n    return t\n\nprint(total([3, 7, 10]))\nprint(total([]))",
    },
    "L4": {
        "task": "Reverse a list without using .reverse() or reversed().",
        "hint": "Slicing takes an optional step: items[start:stop:step]. A step of -1 walks backwards.",
        "code": 'items = ["a", "b", "c", "d"]\nprint(items[::-1])',
    },
    "L5": {
        "task": "Count how many times each word appears in a sentence, and print the counts.",
        "hint": 'Split the sentence into words first. Then: counts[word] = counts.get(word, 0) + 1 — read it as "whatever was there before (or 0), plus one".',
        "code": 'sentence = "the cat sat and the cat slept"\ncounts = {}\nfor word in sentence.split():\n    counts[word] = counts.get(word, 0) + 1\nprint(counts)',
    },
    "L6": {
        "task": 'Turn the string "5550100199" into "555-010-0199".',
        "hint": "Slice it into three pieces — [0:3], [3:6], [6:] — then glue with an f-string and two dashes.",
        "code": 'digits = "5550100199"\nphone = f"{digits[0:3]}-{digits[3:6]}-{digits[6:]}"\nprint(phone)',
    },
    "L7": {
        "task": "Write a tiny log: every time the script runs, append the current date and time on its own line to log.txt.",
        "hint": "from datetime import datetime gives you datetime.now(). Open log.txt in append mode and write str(datetime.now()) plus a newline.",
        "code": 'from datetime import datetime\n\nwith open("log.txt", "a") as f:\n    f.write(str(datetime.now()) + "\\n")\nprint("logged to log.txt")',
    },
    "L8": {
        "task": 'This crashes. Fix it so it prints a friendly fallback instead:\nprices = {"cut": 25}\nprint(prices["color"])',
        "hint": 'The key "color" was never put in the drawer. Either ask politely with .get() and a default, or check membership first with: if "color" in prices.',
        "code": 'prices = {"cut": 25}\nprint(prices.get("color", "we don\'t offer that service"))',
    },
    "L9": {
        "task": "Split any program you've written into two files: the logic in helpers.py, the running part in main.py.",
        "hint": 'Move the defs into helpers.py, then in main.py: import helpers. Guard the running part with: if __name__ == "__main__": — that line means "only run this when the file is executed directly".',
        "files": {
            "helpers.py": 'def shout(name):\n    return f"Hello, {name.upper()}!"\n',
            "main.py": 'import helpers\n\nif __name__ == "__main__":\n    print(helpers.shout("Chauncey"))\n',
        },
    },
    "L10": {
        "task": 'From pairs = [("a", 1), ("b", 2)] build the dict {"a": 1, "b": 2} using a dict comprehension.',
        "hint": "Same shape as the labels example: {k: v for k, v in pairs} — the loop unpacks each tuple straight into k and v.",
        "code": 'pairs = [("a", 1), ("b", 2)]\nd = {k: v for k, v in pairs}\nprint(d)',
    },
    "L11": {
        "task": 'Add a chase_message() method to Invoice that returns: "Hi {client}, invoice {id} for ${amount} is due."',
        "hint": "Methods take self first and read self.client, self.invoice_id, self.amount. It's one return line with an f-string.",
        "code": 'class Invoice:\n    def __init__(self, invoice_id, client, amount):\n        self.invoice_id = invoice_id\n        self.client = client\n        self.amount = amount\n\n    def chase_message(self):\n        return f"Hi {self.client}, invoice {self.invoice_id} for ${self.amount} is due."\n\ninv = Invoice("INV-1042", "Ava", 400)\nprint(inv.chase_message())',
    },
    "L12": {
        "task": "Write only the rows with amount over 100 to expensive.csv, with the same header.",
        "hint": "csv.DictWriter needs fieldnames — grab them from the reader: reader.fieldnames. Remember writer.writeheader() before the rows, and compare with float(...).",
        "code": 'import csv\n\nrows = [\n    {"client": "Ava", "amount": "400"},\n    {"client": "Ben", "amount": "150"},\n    {"client": "Cy", "amount": "90"},\n]\nwith open("sales.csv", "w", newline="") as f:\n    writer = csv.DictWriter(f, fieldnames=["client", "amount"])\n    writer.writeheader()\n    writer.writerows(rows)\n\nwith open("sales.csv", newline="") as f:\n    reader = csv.DictReader(f)\n    big = [r for r in reader if float(r["amount"]) > 100]\n\nwith open("expensive.csv", "w", newline="") as f:\n    writer = csv.DictWriter(f, fieldnames=reader.fieldnames)\n    writer.writeheader()\n    writer.writerows(big)\n\nprint(open("expensive.csv").read())',
    },
    "L13": {
        "task": "Add a --dry-run flag: when present, the script prints what it WOULD do instead of doing it.",
        "hint": 'parser.add_argument("--dry-run", action="store_true") — no value needed, its presence sets args.dry_run to True. Then: if args.dry_run: print(...) else: ...',
        "code": 'import argparse\n\nparser = argparse.ArgumentParser(description="Chase overdue invoices.")\nparser.add_argument("--dry-run", action="store_true")\nargs = parser.parse_args()\n\nif args.dry_run:\n    print("DRY RUN: would send 3 reminders")\nelse:\n    print("sending 3 reminders...")',
        "argv_variants": [[], ["--dry-run"]],
    },
    # L14 has no "try" exercise: derive from the capstone's own ShoutOut
    # service (cap3a), made self-contained so it runs standalone.
    "L14": {
        "task": "Write a service class like the capstone's ShoutOut: a name attribute and a run_once() method that returns a small result dict.",
        "hint": "Follow the capstone shape — class ShoutOut with name = \"shoutout\" and run_once returning {\"sent\": 1, \"message\": \"still here, still building\"}. Then make one and call run_once().",
        "code": 'class ShoutOut:\n    name = "shoutout"\n\n    def run_once(self):\n        return {"sent": 1, "message": "still here, still building"}\n\nsvc = ShoutOut()\nprint(svc.name)\nprint(svc.run_once())',
    },
}

WRITECODE_USERS = [
    "write a program that {task} (hint: {hint})",
    "show me a script that {task}",
    "solve this exercise: {task}",
    "code it: {task} — hint: {hint}",
]


def gen_write_code(lesson: dict) -> list[dict]:
    n = lesson["n"]
    spec = SOLUTIONS[f"L{n}"]
    if "files" in spec:
        # L9: two-file solution; run main.py from the dir holding helpers.py.
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for fname, fbody in spec["files"].items():
                (d / fname).write_text(fbody)
            proc = subprocess.run(
                [sys.executable, str(d / "main.py")],
                capture_output=True,
                text=True,
                cwd=str(d),
                timeout=15,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"L9 solution failed:\n{proc.stderr}")
            out = proc.stdout
        shown = "\n\n".join(
            f"{fname}:\n```python\n{spec['files'][fname].rstrip()}\n```"
            for fname in ("helpers.py", "main.py")
        )
        body = f"{shown}\n\nOutput:\n{out}"
    elif "argv_variants" in spec:
        outs = []
        for argv in spec["argv_variants"]:
            outs.append(run_solution(spec["code"], argv=argv))
        shown = f"```python\n{spec['code']}\n```"
        runs = "\n\n".join(
            f"Run with `{' '.join(argv) if argv else '(no flags)'}`:\n{o.rstrip()}"
            for argv, o in zip(spec["argv_variants"], outs)
        )
        body = f"{shown}\n\n{runs}"
    else:
        out = run_solution(
            spec["code"], stdin=spec.get("stdin"), argv=spec.get("argv")
        )
        body = f"```python\n{spec['code']}\n```\n\nOutput:\n{out}"
    return [
        rec(
            f"{USER}{u.format(task=spec['task'], hint=spec['hint'])}\n{LEVI}{body}",
            "write-code",
            n,
        )
        for u in WRITECODE_USERS
    ]


# --------------------------------------------------------------- debug

BUILTIN_NAMES = {
    "print", "len", "range", "int", "str", "float", "bool", "type", "list",
    "dict", "set", "tuple", "open", "input", "enumerate", "isinstance",
    "Exception", "ValueError", "KeyError", "NameError", "AttributeError",
    "round", "min", "max", "sum", "abs", "sorted", "zip", "map", "filter",
    "any", "all", "repr", "super", "object", "self", "cls",
}
SKIP_IDENTS = BUILTIN_NAMES | set(keyword.kwlist) | {"__name__"}


def mask_strings(code: str) -> str:
    """Replace string-literal contents with spaces (positions preserved)."""
    out = list(code)
    i = 0
    while i < len(code):
        ch = code[i]
        if ch in ("'", '"'):
            quote = ch
            triple = code[i : i + 3] == quote * 3
            qlen = 3 if triple else 1
            j = i + qlen
            while j < len(code):
                if triple and code[j : j + 3] == quote * 3:
                    j += 3
                    break
                if not triple and code[j] == quote:
                    j += 1
                    break
                if code[j] == "\\":
                    j += 2
                    continue
                j += 1
            for k in range(i, min(j, len(code))):
                if out[k] not in ("\n",):
                    out[k] = " "
            i = j
        else:
            i += 1
    return "".join(out)


def bug_typo(code: str):
    masked = mask_strings(code)
    counts: dict[str, int] = {}
    for m in re.finditer(r"[A-Za-z_][A-Za-z0-9_]*", masked):
        name = m.group(0)
        if name in SKIP_IDENTS or name.startswith("__"):
            continue
        counts[name] = counts.get(name, 0) + 1
    for name, cnt in counts.items():
        if cnt < 2:
            continue
        typo = name[0] + name[2] + name[1] + name[3:] if len(name) >= 4 else name + "x"
        if typo == name:
            # swap of identical adjacent chars is a no-op; drop instead
            typo = name[:-1]
        occ = [m for m in re.finditer(rf"\b{re.escape(name)}\b", masked)]
        last = occ[-1]
        buggy = code[: last.start()] + typo + code[last.end() :]
        return (
            buggy,
            "Typo'd variable name",
            f"a misspelled name — the code says `{typo}` but only `{name}` "
            "was ever defined, so Python raises NameError the moment it runs.",
        )
    return None


def bug_colon(code: str):
    lines = code.split("\n")
    for i, line in enumerate(lines):
        if re.match(r"\s*(if|elif|else|for|while|def|class|try|except|finally|with)\b.*:$", line):
            lines[i] = line[:-1]
            return (
                "\n".join(lines),
                "Missing colon",
                "a missing colon — a decision, loop, or definition header must "
                "end with `:`. Without it the file won't even parse (SyntaxError).",
            )
    return None


def bug_eq(code: str):
    """First == outside string literals becomes =."""
    lines = code.split("\n")
    for i, line in enumerate(lines):
        masked = mask_strings(line)
        idx = masked.find("==")
        if idx != -1 and not re.search(r"[!<>=]==", masked[:idx][-1:] + "=="):
            # avoid === / !== style; plain == only
            lines[i] = line[:idx] + "=" + line[idx + 2 :]
            return (
                "\n".join(lines),
                "Assignment where a comparison belongs",
                "`=` stores a value, `==` asks a question. Using `=` inside "
                "the condition is a SyntaxError — the question never gets asked.",
            )
    return None


def bug_indent(code: str):
    lines = code.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("    ") and line.strip():
            lines[i] = line[4:]
            return (
                "\n".join(lines),
                "Bad indentation",
                "broken indentation — the block no longer lines up, so Python "
                "can't tell what belongs inside it (IndentationError).",
            )
    return None


def bug_method(code: str):
    masked = mask_strings(code)
    for m in re.finditer(r"\.([A-Za-z_][A-Za-z0-9_]*)\(", masked):
        name = m.group(1)
        if name.startswith("__"):
            continue
        bad = name[0] + name[2:] if len(name) > 2 else name + "x"
        s, e = m.start(1), m.end(1)
        buggy = code[:s] + bad + code[e:]
        return (
            buggy,
            "Wrong method name",
            f"a misspelled method — the object has no attribute `{bad}`, so "
            "the call raises AttributeError at runtime.",
        )
    return None


def bug_paren(code: str):
    lines = code.split("\n")
    for i, line in enumerate(lines):
        masked = mask_strings(line)
        if "(" in masked and ")" in masked:
            idx = masked.rfind(")")
            lines[i] = line[:idx] + line[idx + 1 :]
            return (
                "\n".join(lines),
                "Unbalanced parenthesis",
                "an unbalanced parenthesis — the line never closes, so the "
                "file won't parse (SyntaxError).",
            )
    return None


BUGS = (bug_typo, bug_colon, bug_eq, bug_indent, bug_method, bug_paren)

DEBUG_USERS = [
    "what's wrong with this code:",
    "this code is broken — what's the bug:",
    "find the bug in this code:",
    "why does this code fail:",
    "debug this for me:",
    "spot the bug in this snippet:",
]


def broken_fails(buggy: str, key: str) -> bool:
    """The broken half must genuinely fail: SyntaxError at compile time,
    or an exception when executed."""
    try:
        compile(buggy, "<broken>", "exec")
    except (SyntaxError, IndentationError):
        return True
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        prep_sandbox(d)
        # Snippets that call input() would block on inherited stdin forever;
        # feed a dummy line so they fail fast on the bug instead of hanging.
        stdin = "test\n" if "input(" in mask_strings(buggy) else None
        rc, _, _ = run_python(buggy, cwd=d, stdin=stdin)
        return rc != 0


def fixed_code_for(lesson_n: int, code_id: str) -> tuple[str, str]:
    """(fixed_code, expected_output). Runs the fixed half in a sandbox."""
    if code_id == "cap3a-adapted":
        code = SOLUTIONS["L14"]["code"]
        out = run_solution(code)
        return code, out
    lesson = lesson_by_n(lesson_n)
    if code_id == "l8e1":
        # The lesson's own correction: the crash fixed, not the crash.
        code = "total = 10 + 5\nprint(total)"
        out = run_in_sandbox(code, f"L{lesson_n}:{code_id}")
        assert out == "15\n", f"l8e1 fixed output drifted: {out!r}"
        return code, out
    blk = code_block(lesson, code_id)
    code = blk["code"]
    stdin = blk.get("stdin")
    stdin = (stdin + "\n") if isinstance(stdin, str) else None
    argv = ["--days", "7"] if code_id == "l13e1" else None
    key = f"L{lesson_n}:{code_id}"
    out = run_in_sandbox(code, key, stdin=stdin, argv=argv)
    expected = norm_output(OUTPUTS[key])
    if out != expected:
        raise RuntimeError(
            f"build-time re-run of {key} disagrees with outputs.json:\n"
            f"got      {out!r}\nexpected {expected!r}"
        )
    return code, out


def gen_debug(lesson: dict) -> list[dict]:
    n = lesson["n"]
    snippet_ids = DEBUG_SNIPPETS[n]
    out: list[dict] = []
    for i, user_tmpl in enumerate(DEBUG_USERS):
        snippet_id = snippet_ids[i % len(snippet_ids)]
        fixed, fixed_out = fixed_code_for(n, snippet_id)
        buggy = None
        for b in range(len(BUGS)):
            maker = BUGS[(i + b) % len(BUGS)]
            res = maker(fixed)
            if res is None:
                continue
            cand, name, explain = res
            if broken_fails(cand, f"L{n}:{snippet_id}"):
                buggy = (cand, name, explain)
                break
        if buggy is None:
            raise RuntimeError(
                f"no applicable bug for L{n}:{snippet_id} — build refuses "
                "to emit an unverified debug record"
            )
        cand, name, explain = buggy
        body = (
            f"Bug: {name}. {explain}\n\n"
            "Fixed:\n"
            f"```python\n{fixed}\n```\n\n"
            f"Output:\n{fixed_out}"
        )
        out.append(rec(f"{USER}{user_tmpl}\n{cand}\n{LEVI}{body}", "debug", n))
    return out


# ------------------------------------------------------------ read-code

READCODE_USERS = [
    "what does this code do:",
    "what does this code print:",
    "walk me through this snippet:",
]


def gen_read_code(lesson: dict) -> list[dict]:
    n, title = lesson["n"], lesson["title"]
    out: list[dict] = []
    for code_id in READ_SNIPPETS[n]:
        blk = code_block(lesson, code_id)
        key = f"L{n}:{code_id}"
        printed = norm_output(OUTPUTS[key])
        prose = following_prose(lesson, code_id)
        grounding = (
            shorten(prose, 160) if prose else shorten(lesson["idea"], 160)
        )
        body = (
            f"{clean(blk.get('title', title))}. {grounding}\n\n"
            f"```python\n{blk['code']}\n```\n\n"
            f"Output:\n{printed}"
        )
        for u in READCODE_USERS:
            out.append(
                rec(
                    f"{USER}{u}\n```python\n{blk['code']}\n```\n{LEVI}{body}",
                    "read-code",
                    n,
                )
            )
    return out


# --------------------------------------------------------------- lesson

LESSON_USERS = [
    "teach lesson {n}: {title}",
    "walk me through lesson {n}",
    "summarize lesson {n}: {title}",
    "give me lesson {n} in plain words",
    "what do I learn in lesson {n}?",
]


def gen_lesson(lesson: dict) -> list[dict]:
    n, title = lesson["n"], lesson["title"]
    moves = [shorten(blk) for kind, blk in lesson["blocks"] if kind == "p"]
    body = (
        f"Lesson {n}: {title} — {clean(lesson.get('subtitle', ''))}\n"
        f"Core idea: {clean(lesson['idea'])}\n\n"
        "Key moves:\n" + "\n".join(f"- {m}" for m in moves)
    )
    return [
        rec(f"{USER}{u.format(n=n, title=title)}\n{LEVI}{body}", "lesson", n)
        for u in LESSON_USERS
    ]


# ----------------------------------------------------------------- main

def build() -> list[dict]:
    records: list[dict] = []
    for n in range(1, 15):
        lesson = lesson_by_n(n)
        records.extend(gen_concept(lesson))
        records.extend(gen_write_code(lesson))
        records.extend(gen_debug(lesson))
        records.extend(gen_read_code(lesson))
        records.extend(gen_lesson(lesson))
    return records


def prove_code(records: list[dict]) -> None:
    """Build-time proof: every ```python fence in a LEVI answer of a
    code-carrying kind must compile. Fails loudly otherwise."""
    fence_re = re.compile(r"```python\n(.*?)```", re.DOTALL)
    checked = 0
    for r in records:
        if r["kind"] not in ("write-code", "debug", "read-code"):
            continue
        answer = r["text"].split("\nLEVI: ", 1)[1]
        for m in fence_re.finditer(answer):
            checked += 1
            try:
                compile(m.group(1), "<record>", "exec")
            except SyntaxError as exc:
                raise RuntimeError(
                    f"record failed compile proof ({r['kind']}, "
                    f"lesson {r['lesson_n']}): {exc}\n{m.group(1)[:300]}"
                )
    if checked == 0:
        raise RuntimeError("compile proof checked zero fences — harness broken")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    records = build()
    prove_code(records)

    out_path = Path(args.out)
    with open(out_path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    counts = {k: sum(1 for r in records if r["kind"] == k) for k in KINDS}
    total_chars = sum(len(r["text"]) for r in records)
    manifest = {
        "generator": "build_programming_corpus.py",
        "version": GENERATOR_VERSION,
        "seed": SEED,
        "built_utc": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "directive": (
            "Chauncey 2026-09-29: LEVI proficient in programming as in law — "
            "writes, debugs, explains, applies; source: his 14-lesson course"
        ),
        "sections": counts,
        "sources_per_section": {k: [SOURCE] for k in KINDS},
        "total_records": len(records),
        "total_chars": total_chars,
        "record_shape": ["text", "kind", "source", "topic", "lesson_n"],
        "corpus_file": out_path.name,
    }
    man_path = out_path.with_name(out_path.stem + "_manifest.json")
    with open(man_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"wrote {out_path} ({len(records)} records)")
    for k in KINDS:
        print(f"  {k}: {counts[k]}")
    print(f"manifest -> {man_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
