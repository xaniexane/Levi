"""ScriptTalk — the engine/script split for pattern conversation.

Studied from: ai-si-software-internals-20260916-0005/report.md (sec 1.2).

The mechanism under study: a hard split between a deterministic
conversation *engine* (keyword scan → decomposition rules → reassembly
templates) and editable *scripts* that are plain data. The engine never
changes when the persona changes; swap the script and you swap the mind.
On top: a MEMORY stash that squirrels away salient fragments and
resurfaces them later, and a runtime teaching mode — add a rule by
example while the thing is running.

This is an original, from-scratch implementation for LEVI, and its voice
is LEVI's own. The bundled demo script is a bench companion — a curious
maker's assistant that wants to know what you're building — never a
therapy clone.

Public surface:
- ``ScriptTalk(script)``: the engine; ``respond(text) -> str``.
- ``load_script(path)`` / ``save_script(script, path)``: scripts are
  plain JSON-able dicts, hot-swappable at runtime.
- ``teach(keyword, decomposition, responses, rank=5, remember=False)``:
  runtime rule teaching.
- ``DEMO_SCRIPT``: LEVI's own demo persona (bench companion).
- Deterministic: responses cycle per rule, never random.

Script shape (all plain data)::

    {
      "greetings": [...], "farewells": [...], "fallbacks": [...],
      "quits": ["bye", ...],
      "reflections": {"i": "you", "my": "your", ...},   # pronoun flip
      "presubs": {"cant": "can't", ...},                # pre-substitution
      "keywords": {
        "build": {"rank": 8, "remember": true,
                  "rules": [("* build *", ["So you're building (2) — ..."]),
                            ...]}
      },
      "memory_rules": {"build": ["Earlier you mentioned (2)..."]},
    }

Decomposition patterns use ``*`` wildcards numbered left to right:
``* build *`` captures group 1 = before, group 2 = after. Reassembly
templates reference captures as ``(1)``, ``(2)``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/scripttalk"


def _wild_to_regex(pattern: str) -> "re.Pattern[str]":
    """Turn a ``*``-wildcard decomposition into a regex, numbered groups."""
    parts = pattern.split("*")
    regex = ""
    for i, part in enumerate(parts):
        if part.strip():
            regex += re.escape(part.strip())
        if i < len(parts) - 1:
            regex += r"\s*(.*?)\s*"
    return re.compile(r"^\s*" + regex + r"\s*$", re.IGNORECASE)


def _clean(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[?!.,;:]+$", "", text)
    return re.sub(r"\s+", " ", text).strip()


class ScriptTalk:
    """The engine. Feed it scripts; it does the talking."""

    def __init__(self, script: Dict, name: str = "scripttalk") -> None:
        self.name = name
        self.script: Dict = script
        self.memory: List[Tuple[str, str]] = []  # stashed (keyword, fragment)
        self._counters: Dict[Tuple[str, int], int] = {}  # rule -> next response idx
        self._turns = 0
        self._greeted = False
        self.taught: List[Dict] = []  # rules added at runtime

    # ------------------------------------------------------------------
    # script data I/O — the hot-swap door
    # ------------------------------------------------------------------
    def swap_script(self, script: Dict, name: str = "swapped") -> None:
        self.script = script
        self.name = name
        self.memory = []
        self._counters = {}
        self.taught = []
        self._greeted = False

    @staticmethod
    def load_script(path: "str | Path") -> Dict:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    @staticmethod
    def save_script(script: Dict, path: "str | Path") -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(script, fh, indent=2, sort_keys=True)

    # ------------------------------------------------------------------
    # runtime teaching — add a rule by example
    # ------------------------------------------------------------------
    def teach(
        self,
        keyword: str,
        decomposition: str,
        responses: List[str],
        rank: int = 5,
        remember: bool = False,
    ) -> str:
        kw = keyword.lower()
        kws = self.script.setdefault("keywords", {})
        entry = kws.setdefault(kw, {"rank": rank, "rules": []})
        entry.setdefault("rules", []).append((decomposition, list(responses)))
        entry["rank"] = max(entry.get("rank", rank), rank)
        if remember:
            entry["remember"] = True
        self.taught.append(
            {
                "keyword": kw,
                "decomposition": decomposition,
                "responses": list(responses),
                "rank": rank,
            }
        )
        return f"learned: when you say something like {decomposition!r}, I'll answer from the new rule"

    # ------------------------------------------------------------------
    # engine internals
    # ------------------------------------------------------------------
    def _reflect(self, fragment: str) -> str:
        refl = self.script.get("reflections", {})
        out = []
        for word in fragment.split():
            out.append(refl.get(word.lower(), word))
        return " ".join(out)

    def _presub(self, text: str) -> str:
        for src, dst in self.script.get("presubs", {}).items():
            text = re.sub(
                r"\b" + re.escape(src) + r"\b", dst, text, flags=re.IGNORECASE
            )
        return text

    def _reassemble(self, template: str, groups: Tuple[str, ...]) -> str:
        def sub(m: "re.Match[str]") -> str:
            idx = int(m.group(1)) - 1
            frag = groups[idx] if 0 <= idx < len(groups) else ""
            return self._reflect(frag.strip())

        return re.sub(r"\((\d+)\)", sub, template)

    def _next_response(self, keyword: str, rule_idx: int, responses: List[str]) -> str:
        key = (keyword, rule_idx)
        i = self._counters.get(key, 0)
        self._counters[key] = (i + 1) % len(responses)
        return responses[i]

    def _keywords_ranked(self) -> List[str]:
        kws = self.script.get("keywords", {})
        return sorted(kws, key=lambda k: -kws[k].get("rank", 0))

    # ------------------------------------------------------------------
    # the turn
    # ------------------------------------------------------------------
    def respond(self, text: str) -> str:
        self._turns += 1
        raw = text.strip()
        if not raw:
            return self._fallback("silence")
        low = _clean(self._presub(raw))

        if any(q in low.split() or q in low for q in self.script.get("quits", [])):
            return self._pick(self.script.get("farewells", ["bye"]), "farewell")

        if not self._greeted:
            self._greeted = True
            greets = self.script.get("greetings", [])
            if greets:
                return greets[0]

        # memory resurface: every 4th turn, if anything stashed
        if self.memory and self._turns % 4 == 0:
            kw, frag = self.memory.pop(0)
            templates = self.script.get("memory_rules", {}).get(kw)
            if templates:
                tmpl = templates[self._turns % len(templates)]
                return self._reassemble(tmpl, ("", frag))

        kws = self.script.get("keywords", {})
        for kw in self._keywords_ranked():
            if kw not in low:
                continue
            entry = kws[kw]
            for ri, (decomp, responses) in enumerate(entry.get("rules", [])):
                m = _wild_to_regex(decomp).match(low)
                if not m:
                    continue
                groups = tuple(g or "" for g in m.groups())
                if entry.get("remember"):
                    frag = " ".join(g for g in groups if g).strip()
                    if frag:
                        self.memory.append((kw, self._reflect(frag)))
                tmpl = self._next_response(kw, ri, responses)
                return self._reassemble(tmpl, groups)

        return self._fallback(low)

    def _pick(self, options: List[str], key: str) -> str:
        if not options:
            return "..."
        i = self._counters.get((key, -1), 0)
        self._counters[(key, -1)] = (i + 1) % len(options)
        return options[i]

    def _fallback(self, low: str) -> str:
        fallbacks = self.script.get("fallbacks", ["Say more."])
        return self._pick(fallbacks, "fallback")

    # ------------------------------------------------------------------
    # inspection
    # ------------------------------------------------------------------
    def stashed(self) -> List[Tuple[str, str]]:
        return list(self.memory)

    def keywords(self) -> List[str]:
        return self._keywords_ranked()

    def describe(self) -> str:
        kws = self.script.get("keywords", {})
        n_rules = sum(len(e.get("rules", [])) for e in kws.values())
        return (
            f"{self.name}: {len(kws)} keywords, {n_rules} rules, "
            f"{len(self.memory)} fragments stashed, {len(self.taught)} taught"
        )


# ----------------------------------------------------------------------
# LEVI's own demo script — the bench companion, not a therapist
# ----------------------------------------------------------------------
DEMO_SCRIPT: Dict = {
    "greetings": [
        "LEVI here — bench is warm, tools are out. What are you building today?",
    ],
    "farewells": [
        "Off to the bench, then. Bring me something strange next time.",
        "Later. I'll keep the workbench warm.",
    ],
    "quits": ["bye", "goodbye", "quit", "exit", "later"],
    "fallbacks": [
        "Noted. Unpack that a little — what's the shape of it?",
        "Hmm. Say it like you're explaining it to the workbench.",
        "I'm listening. What's the part that excites you?",
    ],
    "reflections": {
        "i": "you",
        "me": "you",
        "my": "your",
        "mine": "yours",
        "am": "are",
        "you": "I",
        "your": "my",
        "yours": "mine",
    },
    "presubs": {
        "cant": "can't",
        "wont": "won't",
        "dont": "don't",
        "im": "i'm",
        "ive": "i've",
    },
    "memory_rules": {
        "build": [
            "Earlier you mentioned (2). Did it survive contact with reality?",
            "You were building (2) before — where did that land?",
        ],
        "stuck": ["You said you were stuck on (2). Still stuck, or did it crack?"],
    },
    "keywords": {
        "build": {
            "rank": 9,
            "remember": True,
            "rules": [
                (
                    "* build *",
                    [
                        "Building (2) — good. What's the smallest piece that proves it works?",
                        "(2), huh. What does version one look like, the embarrassing one?",
                    ],
                ),
                (
                    "* building *",
                    [
                        "While you're building (2): what's the hard part you're avoiding?",
                    ],
                ),
            ],
        },
        "stuck": {
            "rank": 8,
            "remember": True,
            "rules": [
                (
                    "* stuck *",
                    [
                        "Stuck on (2). Describe the exact wall — sometimes the wall is the map.",
                        "Being stuck on (2) just means you're at the interesting part. What's the last thing you tried?",
                    ],
                ),
            ],
        },
        "idea": {
            "rank": 7,
            "rules": [
                (
                    "* idea *",
                    [
                        "An idea for (2)? Ideas are cheap until they have edges. Give it one edge.",
                        "(2) — I like the shape of that. What's the first thing it breaks?",
                    ],
                ),
            ],
        },
        "hello": {
            "rank": 10,
            "rules": [
                ("*", ["Hey. Bench is warm. What are we making?"]),
            ],
        },
        "name": {
            "rank": 6,
            "rules": [
                ("* name is *", ["(2) — filed away. Names have weight; use it well."]),
                ("* my name *", ["I'll call you what you call yourself. Go on."]),
            ],
        },
        "levi": {
            "rank": 9,
            "rules": [
                ("*", ["That's me — synthetic, not artificial. What are we building?"]),
            ],
        },
    },
}


def demo() -> ScriptTalk:
    """A ScriptTalk running LEVI's own bench-companion script."""
    return ScriptTalk(DEMO_SCRIPT, name="bench-companion")
