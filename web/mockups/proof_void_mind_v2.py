#!/usr/bin/env python3
"""Proof gate for the void-mind v2 real build (replaces the mockup).

Gates the UI invariants Chauncey approved. Every law must hold or the
build does not ship:

- L1: zero external requests — the app phones home to nothing.
- L2: all 14 registers come live from levi.persona.levi.all_variants().
- L3: signature gold #C4A35A present; the drifted #e2a63d absent.
- L4: no mock/placeholder language anywhere in the shipped UI.
- L5: no "free core" / "free tier" language anywhere.
- L6: the API builders return real shapes (health, registers, growth,
  model) — no hard-coded stage names, no invented counts.
- L7: the inline script parses clean under node --check.
- L8: the hash chain is a real chain — ticks link, n increments.

Usage: python3 web/mockups/proof_void_mind_v2.py  (run from repo root)
Exit 0 = all laws hold. Anything else = the build is not shippable.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
HTML = WEB / "index.html"
sys.path.insert(0, str(ROOT / "core"))

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))


def main() -> int:
    html = HTML.read_text(encoding="utf-8")
    low = html.lower()

    # L1: zero external requests.
    check(
        "L1-no-external-urls",
        not re.search(r'https?://|src="//|href="//|\bcdn\b', low),
        "no http(s)://, no protocol-relative, no cdn",
    )
    check(
        "L1-no-fetch-off-origin",
        not re.search(r'fetch\(\s*["\']https?://', html),
        "fetch only hits same-origin /api/*",
    )

    # L2: registers live.
    from levi.persona.levi import all_variants

    variants = all_variants()
    check("L2-fourteen-variants", len(variants) == 14, f"{len(variants)} variants")
    check(
        "L2-app-fetches-registers",
        "/api/registers" in html,
        "index.html builds the ring from /api/registers",
    )
    from levi.serve import void_api

    regs = void_api.build_registers()
    live_ids = {v.id for v in variants}
    api_ids = {r["id"] for r in regs["registers"]}
    check("L2-api-ids-match-live", api_ids == live_ids, "api ids == all_variants() ids")

    # L3: signature gold, no drift.
    check("L3-signature-gold", "#c4a35a" in low, "signature gold present")
    check("L3-no-drift-accent", "#e2a63d" not in low, "drifted accent absent")

    # L4: no mock language.
    check(
        "L4-no-mock",
        not re.search(r"\bmock\w*\b", low),
        "no mock/mockup/placeholder text in the shipped UI",
    )
    check("L4-no-lorem", "lorem" not in low, "no lorem ipsum")

    # L5: no free-core language.
    check(
        "L5-no-free-core",
        not re.search(r"free[ -]core|free[ -]tier|free forever", low),
        "dead doctrine stays dead",
    )

    # L6: API builders return real shapes.
    health = void_api.build_health()
    check("L6-health", health.get("ok") is True, "health ok")
    growth = void_api.build_growth()
    from levi.growth.stages import STAGE_LADDER

    ladder = {name for name, _, _ in STAGE_LADDER}
    check(
        "L6-growth-stage-real",
        growth.get("stage") in ladder,
        f"stage={growth.get('stage')!r} is a real ladder stage",
    )
    check(
        "L6-growth-learnings-int",
        isinstance(growth.get("learnings"), int),
        f"learnings={growth.get('learnings')!r}",
    )
    model = void_api.build_model()
    check(
        "L6-model-honest",
        bool(model.get("resolved")) and "streaming_note" in model,
        "model status states the non-streaming limit plainly",
    )

    # L7: inline script parses.
    m = re.search(r"<script>(.*?)</script>", html, re.S)
    if m:
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(m.group(1))
            js_path = fh.name
        r = subprocess.run(["node", "--check", js_path], capture_output=True, text=True)
        check("L7-js-parses", r.returncode == 0, "node --check clean")
    else:
        check("L7-js-parses", False, "no inline script found")

    # L8: hash chain is a real chain.
    st = void_api.VoidState()
    t1 = st.chain_tick("s", "user", "hello")
    t2 = st.chain_tick("s", "levi", "hi")
    check(
        "L8-chain-links",
        t2["n"] == t1["n"] + 1 and t1["tick"] != t2["tick"],
        f"n {t1['n']}->{t2['n']}, ticks differ",
    )
    expect = void_api._tick(t1["tick"], "s", "levi", "hi")
    check("L8-chain-deterministic", t2["tick"] == expect, "tick recomputes")

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
