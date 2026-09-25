"""QuettaPanDaVinci — the Quetta-Pan brain, rebuilt.

PROVENANCE (honest): this file is a RECONSTRUCTION, not a verbatim
recovery. What survived from Chauncey's paste (chat 74, "LLM Studio
Project Generation", 2026-07-17, `core/quetta_pan_brain.py`) is only the
shape, recorded in the sweep notes:
  - MD5 phase hash -> state 1-13
  - coherence 0.96-1.0
  - detect_mutations -> "Ternary Inversion +22%" / "Entropy Lock" /
    "Harmony Refactor"
The class name, the MD5->state mapping, the coherence range, the three
mutation names, and the "+22%" figure are his. Everything else —
detector internals, method signatures beyond detect_mutations, the
meaning of "state" — is my faithful reconstruction of that shape, and
is marked RECONSTRUCTED below. The "+22%" is his claimed gain for
Ternary Inversion, NOT a measured result.

What the reconstruction means by the pieces:
- phase_hash: md5(source) — the code's fingerprint; the brain's "phase".
- state (1-13): the phase hash folded into Chauncey's 13 logic states
  (his ternary engine lineage: 13 states, cf. QID shell/form/state).
- coherence (0.96-1.0): deterministic pseudo-measure of how "settled"
  the source reads — derived from the hash, a stable property of the
  input, not a live measurement.
- detect_mutations: three reconstructed detectors returning the named
  mutations with spans and proposed rewrites.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List

# His figure for Ternary Inversion. Claimed, not measured — carried as
# his words, never presented as a benchmark result.
CLAIMED_TERNARY_GAIN = "+22%"


class QuettaPanDaVinci:
    """Reconstructed Quetta-Pan brain: phase-hashed mutation detection."""

    def __init__(self, source: str):
        self.source = source
        self.phase_hash = hashlib.md5(source.encode("utf-8")).hexdigest()
        # RECONSTRUCTED mapping: hash folded into states 1-13.
        self.state = (int(self.phase_hash, 16) % 13) + 1
        # RECONSTRUCTED mapping: hash folded into coherence 0.96-1.0.
        self.coherence = 0.96 + (int(self.phase_hash[:8], 16) % 401) / 10000.0

    # ---- reconstructed detectors --------------------------------------

    def _detect_ternary_inversion(self, content: str) -> List[Dict[str, Any]]:
        """RECONSTRUCTED detector for his 'Ternary Inversion' mutation:
        Python ternary ``a if cond else b`` spots where inverting the
        condition and swapping the branches reads cleaner. His claimed
        gain (+22%) is attached as claimed, not measured."""
        found = []
        for lineno, line in enumerate(content.splitlines(), 1):
            # conservative: single ternary per line, no nesting
            match = re.search(
                r"(?P<true>[A-Za-z0-9_'\".()\[\] ]+?)\s+if\s+"
                r"(?P<cond>[A-Za-z0-9_'\".()\[\] ]+?)\s+else\s+"
                r"(?P<false>[A-Za-z0-9_'\".()\[\] ]+)",
                line,
            )
            if not match or "if" in match.group("cond"):
                continue
            true_v = match.group("true").strip()
            cond = match.group("cond").strip()
            false_v = match.group("false").strip()
            found.append(
                {
                    "name": "Ternary Inversion",
                    "kind": "performance",
                    "claimed_gain": CLAIMED_TERNARY_GAIN,
                    "gain_note": "claimed by Chauncey (chat 74), not measured",
                    "line": lineno,
                    "detail": (
                        f"ternary '{true_v} if {cond} else {false_v}' — "
                        f"consider inverted form '{false_v} if not ({cond}) "
                        f"else {true_v}' where the negative branch dominates"
                    ),
                    "provenance": "reconstructed-detector",
                }
            )
        return found

    def _detect_entropy_lock(self, content: str, suffix: str) -> List[Dict[str, Any]]:
        """RECONSTRUCTED detector for his 'Entropy Lock' mutation:
        disorder spots (unhandled throws, untyped holes, stray debug)
        to lock down. Names his; the spot list is reconstructed."""
        spots = []
        checks = [
            ("except:", "bare except — locks out SystemExit/KeyboardInterrupt"),
            ("as any", "TypeScript 'any' — type-system hole"),
            (": any", "TypeScript 'any' annotation — type-system hole"),
            ("console.log(", "stray console.log — debug entropy"),
            ("debugger;", "stray debugger — execution entropy"),
            ("TODO", "open TODO — unresolved entropy"),
            ("FIXME", "open FIXME — unresolved entropy"),
        ]
        for lineno, line in enumerate(content.splitlines(), 1):
            for token, why in checks:
                if token == "except:" and suffix != ".py":
                    continue  # bare-except is a Python-only spot
                if token in line:
                    spots.append(
                        {
                            "name": "Entropy Lock",
                            "kind": "security",
                            "line": lineno,
                            "detail": f"{why} at line {lineno}: lock it down",
                            "provenance": "reconstructed-detector",
                        }
                    )
                    break
        return spots

    def _detect_harmony_refactor(self, content: str) -> List[Dict[str, Any]]:
        """RECONSTRUCTED detector for his 'Harmony Refactor' mutation:
        formatting disharmony (tabs, trailing whitespace, >3 blank runs)
        to normalize."""
        found = []
        lines = content.splitlines()
        for lineno, line in enumerate(lines, 1):
            if "\t" in line:
                found.append(
                    {
                        "name": "Harmony Refactor",
                        "kind": "refactor",
                        "line": lineno,
                        "detail": f"tab indentation at line {lineno} — "
                        "normalize to spaces",
                        "provenance": "reconstructed-detector",
                    }
                )
                break
        for lineno, line in enumerate(lines, 1):
            if line != line.rstrip():
                found.append(
                    {
                        "name": "Harmony Refactor",
                        "kind": "refactor",
                        "line": lineno,
                        "detail": f"trailing whitespace at line {lineno}",
                        "provenance": "reconstructed-detector",
                    }
                )
                break
        blank_run = 0
        for lineno, line in enumerate(lines, 1):
            blank_run = blank_run + 1 if not line.strip() else 0
            if blank_run == 4:
                found.append(
                    {
                        "name": "Harmony Refactor",
                        "kind": "refactor",
                        "line": lineno,
                        "detail": "4+ blank-line run — collapse for harmony",
                        "provenance": "reconstructed-detector",
                    }
                )
                break
        return found

    # ---- public ---------------------------------------------------------

    def detect_mutations(
        self, content: str, suffix: str = ".py"
    ) -> List[Dict[str, Any]]:
        """His method name, his three mutation names. Detectors are
        reconstructed; each result carries its provenance."""
        mutations = []
        mutations.extend(self._detect_ternary_inversion(content))
        mutations.extend(self._detect_entropy_lock(content, suffix))
        mutations.extend(self._detect_harmony_refactor(content))
        return mutations

    def phase(self) -> Dict[str, Any]:
        """Brain state snapshot: hash, state 1-13, coherence 0.96-1.0."""
        return {
            "phase_hash": self.phase_hash,
            "state": self.state,
            "coherence": round(self.coherence, 4),
        }
