"""Build the teachable academy records for Chauncey's programming course.

Source of truth (read-only, never edited here):
  ~/workspace/your_files/programming-full-course/build/content.py  (LESSONS)
  ~/workspace/your_files/programming-full-course/build/outputs.json (captured stdout)

Deterministic: pure extraction, fixed lesson order, no randomness, no
wall-clock in the lesson records. Rerunning produces byte-identical
lessons.json. (The manifest carries built_utc for provenance only.)

Output (next to this file):
  lessons.json   — the 14 structured lessons
  manifest.json  — provenance: source hash, per-lesson counts, directive

Lesson record shape:
  {n, id, title, subtitle, idea, prose[{kind,text}], examples[{id,title,
   kind,code,stdin,args,files,output}], exercises[{kind,task,hint,detail}]}

Prose, code, outputs, tasks and hints are his words verbatim — the
builder extracts, never rewrites pedagogy.

Usage: python3 build_programming_lessons.py [--src ...] [--out ...]
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SRC = (
    Path.home()
    / "workspace"
    / "your_files"
    / "programming-full-course"
    / "build"
    / "content.py"
)
OUT = HERE / "lessons.json"
MANIFEST = HERE / "manifest.json"

GENERATOR_VERSION = "2026-09-29-v1"


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def load_source(src: Path):
    spec = importlib.util.spec_from_file_location("course_content", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    outputs_path = src.parent / "outputs.json"
    outputs = json.loads(outputs_path.read_text(encoding="utf-8"))
    return mod.LESSONS, outputs


def build_lesson(raw: dict, outputs: dict) -> dict:
    n = raw["n"]
    lesson = {
        "n": n,
        "id": slugify(raw["title"]),
        "title": raw["title"],
        "subtitle": raw.get("subtitle", ""),
        "idea": raw.get("idea", ""),
        "prose": [],
        "examples": [],
        "exercises": [],
    }
    capstone_ex = None  # lesson 14: exercises live in h2 sections
    for btype, block in raw["blocks"]:
        if btype in ("p", "note", "h2"):
            lesson["prose"].append({"kind": btype, "text": block})
            if btype == "h2":
                # Only the capstone's "Exercise N — ..." headers are exercises;
                # other h2s (e.g. lesson 8's debugging checklist) are sections.
                if block.strip().lower().startswith("exercise"):
                    capstone_ex = {"kind": "capstone", "task": block, "hint": None, "detail": ""}
                    lesson["exercises"].append(capstone_ex)
                else:
                    capstone_ex = None
            elif capstone_ex is not None and btype in ("p", "note"):
                capstone_ex["detail"] += (block + "\n\n")
        elif btype == "code":
            key = f"L{n}:{block['id']}"
            lesson["examples"].append(
                {
                    "id": block["id"],
                    "title": block["title"],
                    "kind": "shell" if block.get("shell") else "python",
                    "code": block["code"],
                    "stdin": block.get("stdin"),
                    "args": block.get("args"),
                    "files": block.get("files"),
                    "output": outputs.get(key),
                }
            )
        elif btype == "try":
            lesson["exercises"].append(
                {
                    "kind": "try",
                    "task": block["task"],
                    "hint": block["hint"],
                    "detail": None,
                }
            )
        else:
            raise ValueError(f"unknown block type {btype!r} in lesson {n}")
    if capstone_ex is not None:
        capstone_ex["detail"] = capstone_ex["detail"].strip()
    return lesson


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--manifest", default=str(MANIFEST))
    args = ap.parse_args(argv)

    src = Path(args.src)
    raw_lessons, outputs = load_source(src)
    lessons = [build_lesson(raw, outputs) for raw in raw_lessons]

    # Laws, checked before anything is written.
    assert [l["n"] for l in lessons] == list(range(1, 15)), "lessons must be 1..14 in order"
    ids = [l["id"] for l in lessons]
    assert len(set(ids)) == 14, "lesson ids must be unique"
    code_ids = [e["id"] for l in lessons for e in l["examples"]]
    assert len(set(code_ids)) == len(code_ids), "example ids must be unique"
    for l in lessons:
        assert l["idea"].strip(), f"lesson {l['n']} lost its core idea"
        for e in l["examples"]:
            if e["kind"] == "python":
                compile(e["code"], f"<lesson{l['n']}:{e['id']}>", "exec")

    out_path = Path(args.out)
    out_path.write_text(
        json.dumps(lessons, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    manifest = {
        "generator": "build_programming_lessons.py",
        "generator_version": GENERATOR_VERSION,
        "built_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "directive": "Chauncey 2026-09-29: the full programming course lives in "
        "LEVI as teachable academy lessons. PDF remains the readable edition.",
        "source": {
            "content_py": str(src),
            "content_sha256": hashlib.sha256(
                src.read_bytes()
            ).hexdigest(),
            "outputs_json": str(src.parent / "outputs.json"),
        },
        "deterministic": "extractive, fixed lesson order, no randomness; "
        "reruns produce byte-identical lessons.json",
        "lessons": [
            {
                "n": l["n"],
                "id": l["id"],
                "title": l["title"],
                "examples": len(l["examples"]),
                "exercises": len(l["exercises"]),
            }
            for l in lessons
        ],
        "total_lessons": len(lessons),
        "total_examples": sum(len(l["examples"]) for l in lessons),
        "total_exercises": sum(len(l["exercises"]) for l in lessons),
        "examples_with_output": sum(
            1 for l in lessons for e in l["examples"] if e["output"] is not None
        ),
    }
    Path(args.manifest).write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"programming lessons: {len(lessons)} lessons -> {out_path}")
    print(f"manifest -> {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
