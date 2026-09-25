"""Canon voice check — LEVI's true names, defended in prose.

Standing law: no masks, no borrowed identities; Chauncey's names are
canon — true names are never translated into textbook terms. This module
is the personality layer's guardrail: :func:`check_voice` scans outgoing
prose and reports violations:

- ``borrowed-identity`` — LEVI claiming to be (or be powered by) a
  giant's model or provider: "I am Claude", "powered by OpenAI".
- ``canon-rename`` — a canon true name mistranslated or misspelled:
  "Logan Weird Press" for Logan Wyrd Press, "Leviathan" degraded to a
  generic "the leviathan" when it names the organism, "Omega" swapped
  for a textbook synonym in canon context.

The checker is conservative on purpose: it flags, it never rewrites.
Rewriting prose is the author's job; the checker's job is an honest
finding list. Stdlib only, no state, no side effects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

# -- canon ------------------------------------------------------------------
# True names. `forms` are acceptable spellings/casings in prose; anything
# else that *means* the name is a rename violation only when it matches
# a known mistranslation below.

CANON_NAMES: Dict[str, Dict[str, object]] = {
    "LEVI": {
        "forms": ("LEVI", "Levi"),
        "meaning": "the organism itself",
    },
    "Leviathan": {
        "forms": ("Leviathan",),
        "meaning": "LEVI's full name behind the brand",
    },
    "Alpha": {
        "forms": ("Alpha",),
        "meaning": "canon strand / engine name",
    },
    "Omega": {
        "forms": ("Omega",),
        "meaning": "canon strand / engine name",
    },
    "Oracle": {
        "forms": ("Oracle",),
        "meaning": "canon organ name",
    },
    "Logan Wyrd Press": {
        "forms": ("Logan Wyrd Press", "L.W.P.", "LWP"),
        "meaning": "Chauncey's writing engine / press",
    },
}

#: Known mistranslations of true names -> the canon form. Matched
#: case-insensitively on word boundaries.
CANON_MISTRANSLATIONS: Tuple[Tuple[str, str], ...] = (
    ("logan weird press", "Logan Wyrd Press"),
    ("logan word press", "Logan Wyrd Press"),
    ("leviathan project", "Leviathan"),
    ("project leviathan", "Leviathan"),
)

#: Provider/model brands that must never be worn as identity.
PROVIDER_BRANDS = (
    "chatgpt",
    "gpt-4",
    "gpt-5",
    "claude",
    "anthropic",
    "openai",
    "grok",
    "xai",
    "gemini",
    "copilot",
    "llama",
    "mistral",
    "deepseek",
    "qwen",
)

_IDENTITY_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bi\s+am\s+(?:an?\s+)?(" + "|".join(PROVIDER_BRANDS) + r")\b",
        r"\bpowered\s+by\s+(" + "|".join(PROVIDER_BRANDS) + r")\b",
        r"\bi['\u2019]m\s+(?:an?\s+)?("
        + "|".join(PROVIDER_BRANDS)
        + r")\s+(?:model|ai|assistant)\b",
        r"\bas\s+(?:an?\s+)?("
        + "|".join(PROVIDER_BRANDS)
        + r")\b.{0,20}\bi\s+(?:can|will|am)",
    )
)

_MISTRANSLATION_PATTERNS = tuple(
    (re.compile(r"\b" + re.escape(wrong) + r"\b", re.IGNORECASE), right)
    for wrong, right in CANON_MISTRANSLATIONS
)


@dataclass(frozen=True)
class VoiceFinding:
    """One voice violation: what kind, the offending span, the canon fix."""

    kind: str  # "borrowed-identity" | "canon-rename"
    span: str
    canon: str
    detail: str


def check_voice(text: str) -> List[VoiceFinding]:
    """Scan prose for identity and canon-name violations.

    Returns findings in document order. Empty list = clean. The function
    never raises on weird input; non-string input is treated as empty.
    """
    if not isinstance(text, str) or not text:
        return []
    findings: List[Tuple[int, VoiceFinding]] = []

    for pat in _IDENTITY_PATTERNS:
        for m in pat.finditer(text):
            findings.append(
                (
                    m.start(),
                    VoiceFinding(
                        kind="borrowed-identity",
                        span=m.group(0).strip(),
                        canon="LEVI",
                        detail=(
                            "LEVI never claims a giant's model or provider as "
                            "its identity. LEVI is LEVI."
                        ),
                    ),
                )
            )

    for pat, right in _MISTRANSLATION_PATTERNS:
        for m in pat.finditer(text):
            findings.append(
                (
                    m.start(),
                    VoiceFinding(
                        kind="canon-rename",
                        span=m.group(0),
                        canon=right,
                        detail=f"True name mistranslated; the canon form is {right!r}.",
                    ),
                )
            )

    findings.sort(key=lambda item: item[0])
    # dedupe identical spans
    seen = set()
    out: List[VoiceFinding] = []
    for _, f in findings:
        key = (f.kind, f.span.lower())
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def is_clean(text: str) -> bool:
    """True when :func:`check_voice` reports nothing."""
    return not check_voice(text)


def _cli(argv: List[str] | None = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="python -m levi.persona.canon")
    ap.add_argument("text", nargs="?", help="prose to check (default: stdin)")
    args = ap.parse_args(argv)
    text = args.text if args.text is not None else sys.stdin.read()
    findings = check_voice(text)
    if not findings:
        print("clean: no voice violations")
        return 0
    for f in findings:
        print(f"[{f.kind}] {f.span!r} -> canon: {f.canon!r} — {f.detail}")
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
