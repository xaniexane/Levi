#!/usr/bin/env python3
"""Proof gate for the void-mind v1 mockup (web/mockups/void-mind-v1.html).

Laws checked:
  L1 local-first      - zero external network references (no CDN, fonts, fetch targets)
  L2 signature gold   - uses #C4A35A; the drifted #e2a63d must be absent
  L3 no free-core     - "free core" / "free tier" language forbidden anywhere
  L4 honest mock      - every demo surface is labeled MOCKUP / mock
  L5 real registers   - all 14 registers from levi.persona.levi.all_variants() present
  L6 self-contained   - single file; no <link> or <script src> pulling remote assets
  L7 js parses        - inline script must pass node --check
"""
import re
import subprocess
import sys
from pathlib import Path

HTML = Path(__file__).resolve().parent / "void-mind-v1.html"
FAIL = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(name)


def main():
    text = HTML.read_text(encoding="utf-8")
    low = text.lower()

    # L1: no external network references
    ext = re.findall(r'https?://|src="//|href="//|url\(\s*["\']?https?://', text, re.I)
    check("L1 local-first: zero external URLs", not ext, f"found {ext[:3]}")

    # L6: no remote link/script tags
    remote_tags = re.findall(r'<(?:link|script)[^>]*(?:href|src)\s*=\s*["\']https?://', text, re.I)
    check("L6 self-contained: no remote link/script", not remote_tags, f"found {remote_tags[:2]}")

    # L2: signature gold only
    check("L2a signature gold #C4A35A present", "#c4a35a" in low)
    check("L2b drifted #e2a63d absent", "#e2a63d" not in low, "accent drift present")

    # L3: no free-core language
    bad = [p for p in ("free core", "free tier", "free-core") if p in low]
    check("L3 no free-core language", not bad, f"found {bad}")

    # L4: honest mock labeling
    check("L4a MOCKUP banner present", "mockup" in low)
    check("L4b demo controls labeled mock", "mock controls" in low)

    # L5: all 14 real register ids
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "core"))
    from levi.persona.levi import all_variants
    ids = [v.id for v in all_variants()]
    missing = [i for i in ids if i not in text]
    check(f"L5 all {len(ids)} register ids present", not missing, f"missing {missing}")

    # L7: inline JS parses
    m = re.search(r"<script>(.*?)</script>", text, re.S)
    if not m:
        check("L7 inline script found", False)
    else:
        p = Path("/tmp/void_mind_v1_check.js")
        p.write_text(m.group(1), encoding="utf-8")
        r = subprocess.run(["node", "--check", str(p)], capture_output=True, text=True)
        check("L7 inline JS parses (node --check)", r.returncode == 0, r.stderr.strip()[:200])

    print()
    if FAIL:
        print(f"GATE FAILED: {len(FAIL)} law(s) broken: {FAIL}")
        return 1
    print("GATE PASSED: all 7 laws hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
