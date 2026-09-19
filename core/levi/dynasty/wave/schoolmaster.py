# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Schoolmaster — the wave's infinite-learning agent.

Owns "infinite learning". Builds course tracks with the tutoring
layer woven in from lesson one — Socratic interrogation, Feynman
drills, spaced repetition — and NOT certifiable: no degrees, no
certificates, ever. The knowledge itself, nothing else.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from levi.dynasty.dna import AgentError, DynastyAgent, scrub_text

__all__ = ["Schoolmaster"]

_MAX_TOPIC_LEN = 128
_MAX_QUESTION_LEN = 512
_MAX_ESSENCE = 8
_MAX_ESSENCE_WORD_LEN = 32
_MAX_EXPLANATION_WORDS = 4000
_PASS_ACCURACY = 0.5
_INITIAL_DEBT = 2.0
_INTEREST = 0.1

_TRACKS: Dict[str, Dict[str, Any]] = {
    "seeded randomness": {
        "blurb": (
            "Why the same seed always deals the same game: determinism "
            "you can hold in your hand."
        ),
        "sections": [
            {
                "title": "What a seed is",
                "points": [
                    "A seed is the starting state of a deterministic generator.",
                    "The generator is an algorithm, not a coin: same state in, same numbers out.",
                    "Knowing the seed means knowing the whole future sequence.",
                ],
            },
            {
                "title": "Determinism and reproducibility",
                "points": [
                    "Re-running with the same seed replays every roll exactly.",
                    "Player names join the seed so swapped players swap fates.",
                    "Reproducibility is what turns a game into an experiment.",
                ],
            },
            {
                "title": "Why it matters",
                "points": [
                    "Fair automated games: anyone can re-deal the match and check it.",
                    "Reproducible science: same seed, same simulation, same paper.",
                    "Debugging luck: a 'random' bug you can replay is a bug you can fix.",
                ],
            },
        ],
    },
}


def _home() -> Path:
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".cards-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, sort_keys=True, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)


def _check_topic(topic: Any) -> str:
    if not isinstance(topic, str) or not topic.strip():
        raise AgentError("topic must be a non-empty string")
    clean = scrub_text(topic.strip())
    if len(clean) > _MAX_TOPIC_LEN:
        raise AgentError(f"topic too long (>{_MAX_TOPIC_LEN} chars)")
    return clean


def _check_essence(essence: Any) -> List[str]:
    if not isinstance(essence, list) or not essence:
        raise AgentError("essence needs at least one keyword")
    if len(essence) > _MAX_ESSENCE:
        raise AgentError(f"essence holds at most {_MAX_ESSENCE} keywords")
    out = []
    for word in essence:
        if not isinstance(word, str) or not word.strip():
            raise AgentError("essence keywords must be non-empty strings")
        clean = scrub_text(word.strip().lower())
        if len(clean) > _MAX_ESSENCE_WORD_LEN:
            raise AgentError("essence keyword too long")
        out.append(clean)
    return out


class Schoolmaster(DynastyAgent):
    """Teaches the track, keeps the debt ledger, never certifies."""

    agent_id = "schoolmaster"
    display_name = "Schoolmaster"
    owns = "infinite learning"
    first_milestone = "first course track + tutoring"
    proficiency = {"learning": 10, "tutoring": 9, "general": 6}
    specialties = [
        "course tracks of university-grade depth",
        "Socratic interrogation and Feynman drills",
        "spaced repetition that settles by explanation",
    ]
    attributes = [
        {
            "name": "compression ledger",
            "assertion": (
                "every review card is a debt settled by explanation "
                "compression, not by recall probability: an accurate "
                "explanation that cannot get shorter without lying pays "
                "more than a long accurate one, a short wrong one pays "
                "nothing and accrues interest, and a card retires when its "
                "explanation is incompressible."
            ),
        }
    ]

    def __init__(self, home: Optional[Path] = None) -> None:
        super().__init__(home)
        self._cards_path = (
            (home or _home()) / "dynasty" / "agents" / self.agent_id / "cards.json"
        )
        self._cards_lock = threading.Lock()
        # PURGE-1: the shared receipt minter is not thread-safe (concurrent
        # minters can duplicate sequence numbers). Serialize task sealing
        # per agent instance until the DNA owns a lock of its own.
        self._task_lock = threading.Lock()

    def do_task(
        self,
        kind: str,
        payload: Dict[str, Any],
        task: str = "",
        verify: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        with self._task_lock:
            return super().do_task(kind, payload, task=task, verify=verify)

    # -- card state ----------------------------------------------------
    def _read_cards(self) -> Dict[str, Any]:
        if not self._cards_path.exists():
            return {"cards": {}, "seq": 0}
        try:
            data = json.loads(self._cards_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise AgentError(f"card ledger unreadable: {exc}") from exc
        if not isinstance(data, dict):
            raise AgentError("card ledger corrupt: not a dict")
        data.setdefault("cards", {})
        data.setdefault("seq", 0)
        return data

    def _write_cards(self, data: Dict[str, Any]) -> None:
        _atomic_write_json(self._cards_path, data)

    # -- teaching ------------------------------------------------------
    def teach(self, topic: str) -> Dict[str, Any]:
        """Build the lesson outline for a topic. Never a certificate."""
        clean = _check_topic(topic)
        track = _TRACKS.get(clean.lower())
        if track is None:
            sections = [
                {
                    "title": f"{clean}: first principles",
                    "points": [
                        f"Name the pattern at the heart of {clean}, not the textbook around it.",
                        f"Ask what {clean} must be true of, before asking what it is.",
                        f"One concrete example of {clean} you can point at.",
                    ],
                },
                {
                    "title": f"{clean}: the mechanism",
                    "points": [
                        f"How {clean} works, step by step, with nothing skipped.",
                        f"What breaks {clean}, and what that breakage teaches.",
                        f"Where {clean} shows up when nobody invited it.",
                    ],
                },
                {
                    "title": f"{clean}: make it yours",
                    "points": [
                        f"Explain {clean} in your own words until it gets shorter.",
                        f"Teach {clean} to someone who never heard of it.",
                        f"Find where {clean} was hiding in your own work.",
                    ],
                },
            ]
            blurb = f"A first track on {clean}: the floor, not the ceiling."
        else:
            sections = track["sections"]
            blurb = track["blurb"]
        outline = {
            "topic": clean,
            "blurb": blurb,
            "sections": sections,
            "methods": ["socratic", "feynman", "spaced-repetition"],
            "certifies": False,
        }
        self.note(f"taught track outline: {clean}")
        return outline

    def issue_card(
        self, topic: str, question: str, essence: List[str]
    ) -> Dict[str, Any]:
        """Issue one spaced-repetition card carrying a knowledge debt."""
        clean_topic = _check_topic(topic)
        if not isinstance(question, str) or not question.strip():
            raise AgentError("card needs a non-empty question")
        clean_q = scrub_text(question.strip())
        if len(clean_q) > _MAX_QUESTION_LEN:
            raise AgentError(f"question too long (>{_MAX_QUESTION_LEN} chars)")
        clean_essence = _check_essence(essence)
        with self._cards_lock:
            data = self._read_cards()
            data["seq"] += 1
            card_id = f"card-{data['seq']:04d}"
            card = {
                "card_id": card_id,
                "topic": clean_topic,
                "question": clean_q,
                "essence": clean_essence,
                "debt": _INITIAL_DEBT,
                "best_len": None,
                "interval_days": 1.0,
                "reviews": 0,
                "retired": False,
                "issued_at": _utc_now(),
            }
            data["cards"][card_id] = card
            self._write_cards(data)
        self.note(f"issued card {card_id} on {clean_topic}")
        return dict(card)

    def settle(self, card_id: str, explanation: str) -> Dict[str, Any]:
        """Pay a card's debt with an explanation.

        Accurate compression pays down the debt and stretches the
        interval; a short wrong explanation accrues interest instead.
        """
        if not isinstance(card_id, str) or not card_id:
            raise AgentError("settle needs a card id")
        if not isinstance(explanation, str) or not explanation.strip():
            raise AgentError("settle needs a non-empty explanation")
        text = scrub_text(explanation.strip())
        words = text.split()
        if len(words) > _MAX_EXPLANATION_WORDS:
            raise AgentError("explanation too long")
        with self._cards_lock:
            data = self._read_cards()
            card = data["cards"].get(card_id)
            if card is None:
                raise AgentError(f"unknown card: {card_id!r}")
            if card["retired"]:
                raise AgentError(f"card {card_id} retired — its debt is settled")
            lowered = text.lower()
            hits = sum(1 for kw in card["essence"] if kw in lowered)
            accuracy = hits / len(card["essence"])
            n = len(words)
            card["reviews"] += 1
            if accuracy < _PASS_ACCURACY:
                card["debt"] = round(card["debt"] + _INTEREST, 4)
                verdict = "rejected"
                payment = 0.0
            else:
                if card["best_len"] is None or n < card["best_len"]:
                    compression = (card["best_len"] or n) / n if n else 1.0
                    payment = 0.5 * compression * accuracy
                    card["best_len"] = n
                else:
                    payment = 0.05 * accuracy
                card["debt"] = round(max(0.0, card["debt"] - payment), 4)
                card["interval_days"] = round(1.0 + 12.0 * payment, 1)
                verdict = "retired" if card["debt"] == 0 else "settled"
                card["retired"] = verdict == "retired"
            self._write_cards(data)
            result = {
                "card_id": card_id,
                "verdict": verdict,
                "debt": card["debt"],
                "interval_days": card["interval_days"],
                "accuracy": round(accuracy, 3),
                "words": n,
                "reviews": card["reviews"],
                "retired": card["retired"],
            }
        self.note(f"card {card_id} {verdict}: debt={card['debt']}")
        return result

    def list_cards(self) -> List[Dict[str, Any]]:
        """Every card and its current debt."""
        with self._cards_lock:
            cards = self._read_cards()["cards"]
        return [dict(c) for c in cards.values()]

    # -- domain dispatch ----------------------------------------------
    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        shape = task.get("shape", "echo")
        if shape == "teach":
            return self.teach(task.get("topic", ""))
        if shape == "issue_card":
            return self.issue_card(
                task.get("topic", ""),
                task.get("question", ""),
                task.get("essence", []),
            )
        if shape == "settle":
            return self.settle(task.get("card_id", ""), task.get("explanation", ""))
        if shape == "cards":
            return {"cards": self.list_cards()}
        return super().handle(task)

    # -- first green task ----------------------------------------------
    def first_task(self) -> Dict[str, Any]:
        outline = self.teach("seeded randomness")
        card = self.issue_card(
            "seeded randomness",
            (
                "In your own words: why does the same seed always produce "
                "the same sequence of dice rolls?"
            ),
            ["seed", "state", "deterministic", "sequence", "algorithm"],
        )
        return self.do_task(
            "wave.first_task",
            {
                "outline": outline,
                "card": {
                    "card_id": card["card_id"],
                    "question": card["question"],
                    "debt": card["debt"],
                },
                "certifies": False,
            },
            task="schoolmaster:first",
        )
