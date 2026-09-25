"""REIM — Recursion Echo Inverse Mapping: failure-compost intelligence.

A failed mutation is echoed back (replayed: what was tried, in what
context) and inverse-mapped into compost — a structured failure lesson.
Compost is append-only JSONL; nothing is ever deleted, only learned from.

Canon: "REIM failure-compost intelligence" (LEXICON.md:783-785), one of
Chauncey's unattempted intelligence types; the signature formula runs
Quetta "through Echo, REIM, RIEM, Mandella" (LEXICON.md:709-710).

The "Echo" in the name: the lesson is derived by echoing the attempt
back — replaying tried-what against failed-why — and mapping the failure
to its inverse (what to do instead). Deterministic, no model calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

# Inverse remedies per failure class. The inverse of a failure is the
# concrete thing to do instead — that is the compost's value.
REMEDIES = {
    "parse": (
        "leave the construct untouched and flag it for human review; "
        "do not auto-rewrite code that no longer parses"
    ),
    "test": (
        "revert to the last green shape, shrink the mutation to the "
        "smallest diff that keeps tests green, then re-run the suite"
    ),
    "guard": (
        "the guard itself fired: treat the mutation as unsafe in this "
        "context and require explicit human approval before retrying"
    ),
}

REQUIRED_KEYS = (
    "mutation_id",
    "rule_id",
    "file",
    "context",
    "tried_what",
    "failed_why",
)


def failure_class(failed_why: str) -> str:
    """Classify a failure into parse / test / guard from its reason text."""
    text = failed_why.lower()
    if "parse" in text or "syntax" in text or "balance" in text:
        return "parse"
    if "test" in text or "suite" in text or "command" in text:
        return "test"
    return "guard"


def derive_inverse_lesson(failure: Dict[str, Any]) -> str:
    """Echo the attempt back and map it to its inverse.

    Deterministic: "Tried X on F (context C); it failed because W.
    Inverse lesson: do not <rule> when <context>; instead <remedy>."
    """
    for key in REQUIRED_KEYS:
        if not failure.get(key):
            raise ValueError(f"compost failure missing required key: {key}")
    cls = failure_class(str(failure["failed_why"]))
    remedy = REMEDIES[cls]
    return (
        f"Tried {failure['tried_what']} on {failure['file']} "
        f"(context {failure['context']}); it failed because "
        f"{failure['failed_why']}. Inverse lesson: do not apply "
        f"{failure['rule_id']} in context {failure['context']}; "
        f"instead: {remedy}."
    )


class ReimCompost:
    """Append-only failure-compost store (JSONL, one lesson per line)."""

    def __init__(self, store_path: Path | str):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def compost(self, failure: Dict[str, Any]) -> Dict[str, Any]:
        """Inverse-map a failure into compost. Never drops silently:
        missing keys raise; I/O errors raise. Returns the stored entry."""
        lesson = derive_inverse_lesson(failure)  # validates keys
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "failure_class": failure_class(str(failure["failed_why"])),
            "inverse_lesson": lesson,
        }
        for key in REQUIRED_KEYS:
            entry[key] = failure[key]
        # Preserve any extra caller context (heuristic deltas, diff stats).
        for key, value in failure.items():
            if key not in entry:
                entry[key] = value
        with open(self.store_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        return entry

    def lessons(
        self, rule_id: Optional[str] = None, context: Optional[str] = None
    ) -> Iterator[Dict[str, Any]]:
        """Replay compost, optionally filtered. Read-only."""
        if not self.store_path.exists():
            return
        with open(self.store_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue  # corrupt line: skip, never crash the replay
                if rule_id is not None and entry.get("rule_id") != rule_id:
                    continue
                if context is not None and entry.get("context") != context:
                    continue
                yield entry

    def count(self) -> int:
        return sum(1 for _ in self.lessons())

    def recent(self, n: int = 10) -> List[Dict[str, Any]]:
        entries = list(self.lessons())
        return entries[-n:]
