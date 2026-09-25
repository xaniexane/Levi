"""Dynasty IP guard — every dynasty file carries the Section 0 block.

Walks ``core/levi/dynasty/`` from the repo root (resolved from this
file's location). Skips ``__pycache__`` directories and ``*.pyc``.
For every ``.py``/``.md`` file, asserts the literal
``SPDX-License-Identifier: LicenseRef-LEVI-Proprietary`` line AND the
literal ``SECTION 0`` marker are present. For every ``.json`` file,
asserts top-level ``"spdx" == "LicenseRef-LEVI-Proprietary"`` and a
``"section_0"`` or ``"notice"`` field exists. Fails naming the
offending path.
"""

from __future__ import annotations

import json
from pathlib import Path

SPDX_LINE = "SPDX-License-Identifier: LicenseRef-LEVI-Proprietary"
SECTION_MARK = "SECTION 0"

ROOT = Path(__file__).resolve().parents[1]
DYNASTY = ROOT / "core" / "levi" / "dynasty"


def _dynasty_files():
    for path in sorted(DYNASTY.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.suffix == ".pyc":
            continue
        yield path


def test_dynasty_ip_guard():
    assert DYNASTY.is_dir(), f"dynasty tree missing: {DYNASTY}"
    checked = 0
    for path in _dynasty_files():
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix in (".py", ".md"):
            text = path.read_text(encoding="utf-8")
            assert SPDX_LINE in text, f"missing SPDX line: {rel}"
            assert SECTION_MARK in text, f"missing SECTION 0 block: {rel}"
            checked += 1
        elif path.suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data.get("spdx") == "LicenseRef-LEVI-Proprietary", (
                f"bad or missing spdx field: {rel}"
            )
            assert "section_0" in data or "notice" in data, (
                f"missing section_0/notice field: {rel}"
            )
            checked += 1
        else:
            # Unknown file types are not covered by the guard's scope;
            # they must not exist silently — the count check below pins
            # the tree to the types this guard knows.
            raise AssertionError(f"unguarded file type in dynasty tree: {rel}")
    assert checked > 0, "guard walked the dynasty tree and found nothing"
