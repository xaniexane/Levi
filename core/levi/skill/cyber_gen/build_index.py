#!/usr/bin/env python3
"""Build (or rebuild) the cyber playbook manifest: cyber_index.jsonl.gz.

Usage:
    python3 build_index.py [--check]

--check verifies the manifest against the files on disk without rewriting.
Exit codes: 0 ok, 1 mismatch/error.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from levi.skill import cyber_skills  # noqa: E402


def build() -> int:
    skills = []
    files = sorted(cyber_skills.PLAYBOOK_DIR.glob("*.md"))
    for path in files:
        skill = cyber_skills._skill_from_file(path)
        if skill is None:
            print(f"SKIP (invalid): {path.name}", file=sys.stderr)
            continue
        skills.append(skill)
    cyber_skills._write_manifest(skills)
    print(f"manifest: {len(skills)} entries from {len(files)} files")
    return 0 if len(skills) == len(files) else 1


def check() -> int:
    mp = cyber_skills._manifest_path()
    if not mp.is_file():
        print("manifest missing")
        return 1
    with gzip.open(mp, "rt", encoding="utf-8") as fh:
        header = json.loads(fh.readline())
        entries = [json.loads(line) for line in fh if line.strip()]
    files = sorted(cyber_skills.PLAYBOOK_DIR.glob("*.md"))
    file_ids = {"cyber_" + p.stem.replace("-", "_") for p in files}
    manifest_ids = {e["skill_id"] for e in entries}
    ok = (
        header.get("manifest") == cyber_skills.MANIFEST_VERSION
        and header.get("count") == len(files)
        and len(manifest_ids) == len(entries)
        and manifest_ids == file_ids
    )
    print(
        f"manifest v{header.get('manifest')} count={header.get('count')} "
        f"files={len(files)} match={ok}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(check() if "--check" in sys.argv[1:] else build())
