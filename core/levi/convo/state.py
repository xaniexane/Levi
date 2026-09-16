"""DialogueState: the living shape of a conversation.

A conversation is not a list of turns. It is a body the organism can feel:
threads (topics) with salience that decays when unmentioned and *reignites*
on callback ("back to the server thing" should work), entities with
lightweight coreference ("it", "that one"), open loops LEVI owes the user
(questions asked, promises made), and session facts for the contradiction
sense.

All extraction is stdlib heuristics, precision over recall: the state would
rather miss a subtle link than hallucinate one. Deterministic — no
randomness anywhere.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

# Salience dynamics ------------------------------------------------------------
_THREAD_DECAY = 0.85      # per turn when unmentioned
_ENTITY_DECAY = 0.90
_THREAD_BOOST = 0.45      # added on mention
_THREAD_JACCARD = 0.30    # keyword overlap to join an existing thread
_HISTORY_CAP = 40         # salience samples kept per thread (sparkline)
_ENTITY_RECENCY = 6       # turns within which a pronoun may resolve
_FACT_CAP = 60

_BOT_SPEAKERS = {"levi", "assistant", "bot"}

_CALLBACK_RE = re.compile(
    r"\b(back to|anyway,?\s+(?:about|regarding)|returning to|as for|"
    r"speaking of|regarding|re:|on the .*? front)\b",
    re.IGNORECASE,
)
_PROMISE_RE = re.compile(
    r"\b(i'll|i will|let me|i'm going to|gonna)\s+"
    r"(check|look into|verify|confirm|find out|test|run|send|get back|"
    r"handle|take care of|dig into)[^.?!]{0,80}",
    re.IGNORECASE,
)
_ENTITY_RE = re.compile(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,2})\b")
_PRONOUN_RE = re.compile(
    r"\b(it|this|that|these|those|they|them|that one|this one)\b", re.IGNORECASE
)
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]")
_CLAIM_HINT_RE = re.compile(
    r"\b(is|are|was|were|be|been|can|cannot|can't|won't|will|does|doesn't|"
    r"do|don't|has|have|had|runs|uses)\b",
    re.IGNORECASE,
)

_ENTITY_STOP = frozenset(
    "I It This That The A An And But Or So If When What How Why Who "
    "You We They He She My Your Our Its Their "
    # sentence-initial capitalized common words: never entities
    "Can Do Does Is Are Was Were Will Would Could Should May Might Must "
    "Where Which There Here Thanks Thank Yes No Okay Ok Please Now Then "
    "Also Still Even Just Very Really "
    # capitalized prepositions / conjunctions / determiners: never entities
    "Got For From With Without About After Before During Between Into Over "
    "Under Against Among Through Despite Towards Upon Within "
    "All Any Both Each Few More Most Other Some Such Only Own Same Too".split()
)
_LOOP_CLOSE_OVERLAP = 0.5
_LOCAL_STOP = frozenset(
    "a an the and or but so if of to in on for with is are was were be been "
    "it its this that these those they them we you he she my your our their "
    "do does did not no yes what when where why how which who will would can "
    "could should shall may might must just very really quite also too than "
    "then there here as at by from into over under about after before up out "
    "off back get got going gonna let im ive dont cant wont isnt arent "
    "like okay ok hey hi hello".split()
)


def _tokenize_fallback(text: str) -> List[str]:
    """Tiny local tokenizer (lowercase, alpha-only). Retrieval's is preferred."""
    return re.findall(r"[a-z]{2,}", text.lower())


def _tokenize(text: str) -> List[str]:
    try:
        from levi.memory.retrieval import tokenize as _rt  # type: ignore

        return list(_rt(text))
    except Exception:
        return _tokenize_fallback(text)


def _content_words(text: str) -> List[str]:
    return [w for w in _tokenize(text) if w not in _LOCAL_STOP and len(w) > 2]


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENTENCE_RE.findall(text) if s.strip()]


class DialogueState:
    """Living conversational state. Call :meth:`update` once per turn."""

    def __init__(self) -> None:
        self.turns: List[Dict[str, str]] = []          # {speaker, text}
        self.threads: Dict[str, Dict] = {}            # name -> thread record
        self.entities: Dict[str, Dict] = {}           # name -> entity record
        self.loops: List[Dict] = []                   # open loops
        self.facts: List[Dict] = []                   # session facts
        self.last_resolution: Optional[Tuple[str, str, int]] = None
        self.turn_count: int = 0

    # -- internal helpers ----------------------------------------------------
    def _decay(self) -> None:
        for t in self.threads.values():
            t["salience"] *= _THREAD_DECAY
            t["history"].append(round(t["salience"], 3))
            if len(t["history"]) > _HISTORY_CAP:
                t["history"] = t["history"][-_HISTORY_CAP:]
            t.pop("reignited", None)
        for e in self.entities.values():
            e["salience"] *= _ENTITY_DECAY

    def _match_thread(self, kwset: set) -> Optional[str]:
        best, best_j = None, 0.0
        for name, t in self.threads.items():
            keys = set(t["keywords"].keys())
            if not keys or not kwset:
                continue
            j = len(keys & kwset) / len(keys | kwset)
            if j >= _THREAD_JACCARD and j > best_j:
                best, best_j = name, j
        return best

    def _thread_name(self, keywords: Counter) -> str:
        top = [w for w, _ in keywords.most_common(3)]
        return " ".join(top) if top else "untitled"

    # -- public API ----------------------------------------------------------
    def update(self, speaker: str, text: str) -> Dict:
        """Ingest one turn. Returns a dict of what changed (for tests/debug)."""
        text = (text or "").strip()
        turn = self.turn_count
        self.turn_count += 1
        self.turns.append({"speaker": speaker, "text": text})
        changed: Dict[str, object] = {"turn": turn}

        self._decay()
        kws = Counter(_content_words(text))
        kwset = set(kws)

        # 1. threads ---------------------------------------------------------
        callback = _CALLBACK_RE.search(text)
        if callback and kwset:
            # Try to match the thread named after the callback phrase.
            rest = _content_words(text[callback.end():])
            target = self._match_thread(set(rest)) if rest else None
            if target is None:
                # Fall back: any thread sharing a word with the remainder.
                for name, t in self.threads.items():
                    if set(t["keywords"]) & set(rest):
                        target = name
                        break
            if target is None:
                target = self._match_thread(kwset)
            if target:
                t = self.threads[target]
                t["salience"] = 1.0
                t["mentions"] += 1
                t["last_turn"] = turn
                t["keywords"].update(kws)
                t["reignited"] = True
                changed["reignited"] = target
            else:
                changed["thread"] = self._new_thread(kws, turn)
        elif kwset:
            name = self._match_thread(kwset)
            if name:
                t = self.threads[name]
                t["salience"] = min(1.0, t["salience"] + _THREAD_BOOST)
                t["mentions"] += 1
                t["last_turn"] = turn
                t["keywords"].update(kws)
                changed["thread"] = name
            else:
                changed["thread"] = self._new_thread(kws, turn)

        # 2. entities ---------------------------------------------------------
        # Precision over recall: strip leading stopwords ("The Nginx" -> "Nginx"),
        # drop sentence-initial common words ("Can", "Thanks"), keep the rest.
        for m in _ENTITY_RE.finditer(text):
            parts = [p for p in m.group(1).split() if p not in _ENTITY_STOP]
            if not parts:
                continue
            name = " ".join(parts)
            if len(name) < 2:
                continue
            e = self.entities.get(name)
            if e:
                e["salience"] = min(1.0, e["salience"] + 0.5)
                e["last_turn"] = turn
                e["mentions"] += 1
            else:
                self.entities[name] = {
                    "name": name, "salience": 1.0, "last_turn": turn,
                    "mentions": 1,
                }
            changed.setdefault("entities", []).append(name)

        # 3. pronoun resolution ------------------------------------------------
        pm = _PRONOUN_RE.search(text)
        if pm:
            resolved = self._resolve_pronoun(turn)
            if resolved:
                self.last_resolution = (pm.group(1).lower(), resolved, turn)
                changed["resolved"] = {"pronoun": pm.group(1).lower(),
                                       "entity": resolved}

        # 4. open loops ---------------------------------------------------------
        if speaker.lower() in _BOT_SPEAKERS:
            for m in _PROMISE_RE.finditer(text):
                # Loop keywords exclude the promise verb itself ("check" is
                # scaffolding; "drive space" is the substance).
                verb = m.group(2).lower()
                verb_stem = (_content_words(verb) or [verb])[0]
                kws = [w for w in _content_words(m.group(0)) if w != verb_stem]
                self.loops.append({
                    "kind": "promise", "text": m.group(0).strip(),
                    "keywords": kws,
                    "opened_turn": turn, "status": "open",
                })
                changed.setdefault("loops_opened", []).append(m.group(0).strip())
            if text.rstrip().endswith("?") and len(text) > 12:
                self.loops.append({
                    "kind": "question", "text": text.strip()[:120],
                    "keywords": _content_words(text),
                    "opened_turn": turn, "status": "open",
                })
                changed.setdefault("loops_opened", []).append("question")
        # close loops whose substance reappears
        for loop in self.loops:
            if loop["status"] != "open" or not loop["keywords"]:
                continue
            overlap = len(set(loop["keywords"]) & kwset) / len(loop["keywords"])
            if overlap >= _LOOP_CLOSE_OVERLAP and turn > loop["opened_turn"]:
                loop["status"] = "closed"
                loop["closed_turn"] = turn
                changed.setdefault("loops_closed", []).append(loop["text"])

        # 5. session facts -------------------------------------------------------
        if speaker.lower() in _BOT_SPEAKERS:
            for s in _sentences(text):
                if _CLAIM_HINT_RE.search(s):
                    self.facts.append({"text": s.strip(), "turn": turn})
        if len(self.facts) > _FACT_CAP:
            self.facts = self.facts[-_FACT_CAP:]

        return changed

    def _new_thread(self, kws: Counter, turn: int) -> str:
        name = self._thread_name(kws)
        # avoid key collision with a distinct-but-same-named thread
        base, i = name, 2
        while name in self.threads:
            name = f"{base} {i}"
            i += 1
        self.threads[name] = {
            "name": name, "keywords": Counter(kws), "salience": 1.0,
            "last_turn": turn, "mentions": 1, "history": [1.0],
        }
        return name

    def _resolve_pronoun(self, turn: int) -> Optional[str]:
        cands = [e for e in self.entities.values()
                 if turn - e["last_turn"] <= _ENTITY_RECENCY]
        if not cands:
            return None
        cands.sort(key=lambda e: (e["salience"], e["last_turn"]), reverse=True)
        return cands[0]["name"]

    # -- views -----------------------------------------------------------------
    def live_threads(self, min_salience: float = 0.15) -> List[Dict]:
        return sorted(
            (t for t in self.threads.values() if t["salience"] >= min_salience),
            key=lambda t: t["salience"], reverse=True,
        )

    def live_entities(self, min_salience: float = 0.15) -> List[Dict]:
        return sorted(
            (e for e in self.entities.values() if e["salience"] >= min_salience),
            key=lambda e: (e["salience"], e["last_turn"]), reverse=True,
        )

    def open_loops(self) -> List[Dict]:
        return [l for l in self.loops if l["status"] == "open"]

    # -- persistence -------------------------------------------------------------
    def to_dict(self) -> Dict:
        return {
            "turn_count": self.turn_count,
            "turns": self.turns,
            "threads": {n: {**t, "keywords": dict(t["keywords"])}
                        for n, t in self.threads.items()},
            "entities": self.entities,
            "loops": self.loops,
            "facts": self.facts,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DialogueState":
        s = cls()
        s.turn_count = int(data.get("turn_count", 0))
        s.turns = list(data.get("turns", []))
        for n, t in data.get("threads", {}).items():
            t = dict(t)
            t["keywords"] = Counter(t.get("keywords", {}))
            t.setdefault("history", [t.get("salience", 0.0)])
            s.threads[n] = t
        s.entities = dict(data.get("entities", {}))
        s.loops = list(data.get("loops", []))
        s.facts = list(data.get("facts", []))
        return s
