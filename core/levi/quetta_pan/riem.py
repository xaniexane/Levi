"""RIEM — Recursion Inverse Echo Mapping: dream-compression intelligence.

Composted failure lessons (and recorded successes) are mapped forward
into the genome: persistent learned patterns of the form
"mutation <rule> in context <context> fails/succeeds". The genome is
consulted BEFORE Quetta-Pan generates projections — that is the loop
closing: yesterday's compost steers tomorrow's traversal.

Canon: "RIEM dream-compression intelligence" (LEXICON.md:783-785);
compost -> genome is the dream being compressed into inheritable pattern.

Consult policy (deterministic, documented):
- "suppress": >= 2 attempts and failure rate >= 2/3 in this context.
  The suggestion is withheld, with the reason stated.
- "boost": >= 1 success and zero failures. The suggestion is marked
  genome-trusted.
- "unknown": everything else. Suggested normally.

The genome is JSON, capped per rule (lessons list keeps the 20 most
recent). Nothing is deleted; patterns only accumulate evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

MAX_LESSONS_PER_RULE = 20

SUPPRESS_MIN_ATTEMPTS = 2
SUPPRESS_FAILURE_RATE = 2.0 / 3.0


def context_key_for(path: Path | str) -> str:
    """Coarse context key: language family of the file under mutation."""
    suffix = Path(path).suffix.lower()
    if suffix == ".py":
        return "py"
    if suffix in (".js", ".ts", ".jsx", ".tsx"):
        return "js-ts"
    if suffix == ".sql":
        return "sql"
    return suffix.lstrip(".") or "unknown"


class RiemGenome:
    """Persistent mutation-pattern store, consulted before generation."""

    def __init__(self, store_path: Path | str):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Any] = {"patterns": {}}
        self._load()

    # ---- persistence ----------------------------------------------------

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        try:
            raw = json.loads(self.store_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return  # corrupt store: start empty, never crash the run
        if isinstance(raw, dict) and isinstance(raw.get("patterns"), dict):
            self._data = raw

    def _save(self) -> None:
        tmp = self.store_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        tmp.replace(self.store_path)

    # ---- learning -------------------------------------------------------

    def _slot(self, rule_id: str, context: str) -> Dict[str, Any]:
        patterns = self._data["patterns"]
        ctx = patterns.setdefault(context, {})
        slot = ctx.setdefault(
            rule_id,
            {"attempts": 0, "successes": 0, "failures": 0, "lessons": []},
        )
        return slot

    def learn(
        self, rule_id: str, context: str, success: bool, lesson: str = ""
    ) -> Dict[str, Any]:
        """Fold one outcome into the genome. Returns the updated slot."""
        slot = self._slot(rule_id, context)
        slot["attempts"] += 1
        if success:
            slot["successes"] += 1
        else:
            slot["failures"] += 1
        if lesson:
            lessons = slot.setdefault("lessons", [])
            lessons.append(lesson)
            del lessons[:-MAX_LESSONS_PER_RULE]
        self._save()
        return dict(slot)

    def learn_compost_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Fold a REIM compost entry (a failure) into the genome."""
        return self.learn(
            rule_id=str(entry.get("rule_id", "unknown")),
            context=str(entry.get("context", "unknown")),
            success=False,
            lesson=str(entry.get("inverse_lesson", "")),
        )

    def record_success(
        self, rule_id: str, context: str, note: str = ""
    ) -> Dict[str, Any]:
        return self.learn(rule_id, context, True, note)

    # ---- consultation ---------------------------------------------------

    def stats(self, rule_id: str, context: str) -> Dict[str, Any]:
        slot = self._slot(rule_id, context)
        return {
            "attempts": slot["attempts"],
            "successes": slot["successes"],
            "failures": slot["failures"],
        }

    def consult(self, rule_id: str, context: str) -> str:
        """Pre-generation verdict: 'suppress' | 'boost' | 'unknown'."""
        slot = self._slot(rule_id, context)
        attempts = slot["attempts"]
        failures = slot["failures"]
        successes = slot["successes"]
        if attempts >= SUPPRESS_MIN_ATTEMPTS:
            if failures / attempts >= SUPPRESS_FAILURE_RATE:
                return "suppress"
        if successes >= 1 and failures == 0:
            return "boost"
        return "unknown"

    def suppression_reason(self, rule_id: str, context: str) -> str:
        slot = self._slot(rule_id, context)
        return (
            f"genome: {rule_id} failed {slot['failures']}/"
            f"{slot['attempts']} in context {context}; withheld"
        )

    def patterns(self) -> Dict[str, Any]:
        return {k: dict(v) for k, v in self._data["patterns"].items()}

    def known_rules(self, context: str) -> List[str]:
        return list(self._data["patterns"].get(context, {}).keys())
