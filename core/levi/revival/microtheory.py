"""Microtheories — contradictory defaults, kept in separate rooms.

Studied from: revival-50-more-20260916-0009/report-part2.md (sec 27);
ai-si-software-internals-20260916-0005/report.md (sec 1.8) — MERGED.

The mechanism under study: assertions live inside named microtheories
— local contexts — so contradictory defaults coexist without exploding.
"Birds fly" and "penguins don't fly" are both true; they just live in
different rooms, and you ask your question in a chosen room. On top:

- **Fast-path reasoners**: a subclass walk and a cached fact lookup
  answer the common questions without search; general backward chaining
  is the fallback when the fast paths miss.
- **Forward + backward + abduction**: derive everything eagerly,
  prove goals lazily, or *assume-and-check* — abduction proposes
  minimal assumption sets inside ephemeral problem stores that vanish
  after the question is answered.
- **Proof explanations**: every derived fact cites its sources —
  which microtheory, which rule, which assumption.

Original, from-scratch implementation for LEVI. Facts are plain tuples
(``("isa", "tweety", "bird")``); pattern elements starting with ``"?"``
are variables. stdlib-only, no network, deterministic.

Public surface:
- ``KnowledgeBase`` — ``mt(name, parents=...)`` to get/create a
  microtheory; ``ask(pattern, mt)``; ``forward(mt)``;
  ``abduce(goal, mt, abducibles)``; ``explain(pattern, mt)``.
- ``Microtheory`` — ``tell(fact)``, ``tell_rule(head, body, name,
  default=False)``, ``problem_store()`` (ephemeral).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

ORIGIN = "levi-revival/microtheory"

Fact = Tuple[Any, ...]
Pattern = Tuple[Any, ...]


def _is_var(x: Any) -> bool:
    return isinstance(x, str) and x.startswith("?")


def _unify(
    pattern: Pattern, fact: Fact, bindings: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    bindings = dict(bindings or {})
    if len(pattern) != len(fact):
        return None
    for p, f in zip(pattern, fact, strict=True):
        if _is_var(p):
            if p in bindings:
                if bindings[p] != f:
                    return None
            else:
                bindings[p] = f
        elif p != f:
            return None
    return bindings


def _subst(pattern: Pattern, bindings: Dict[str, Any]) -> Pattern:
    return tuple(bindings.get(p, p) if _is_var(p) else p for p in pattern)


@dataclass
class Rule:
    head: Pattern
    body: Tuple[Pattern, ...]
    name: str
    default: bool = False
    source_mt: str = ""


@dataclass
class Proof:
    fact: Fact
    sources: List[str] = field(default_factory=list)
    children: List["Proof"] = field(default_factory=list)

    def explanation(self, indent: int = 0) -> List[str]:
        pad = "  " * indent
        lines = [f"{pad}{self.fact}  [{'; '.join(self.sources)}]"]
        for ch in self.children:
            lines.extend(ch.explanation(indent + 1))
        return lines


class Microtheory:
    """One room of assertions. Contradictions live in other rooms."""

    def __init__(self, name: str, parents: Tuple[str, ...] = ()) -> None:
        self.name = name
        self.parents = parents
        self.facts: Set[Fact] = set()
        self.rules: List[Rule] = []
        self._cache: Dict[Pattern, Optional[Proof]] = {}
        self._subclass_cache: Dict[str, Set[str]] = {}

    def tell(self, fact: Fact) -> None:
        self.facts.add(tuple(fact))
        self._cache.clear()
        self._subclass_cache.clear()

    def tell_rule(
        self,
        head: Pattern,
        body: Tuple[Pattern, ...] = (),
        name: str = "rule",
        default: bool = False,
    ) -> Rule:
        rule = Rule(
            tuple(head), tuple(tuple(b) for b in body), name, default, self.name
        )
        self.rules.append(rule)
        self._cache.clear()
        return rule

    def problem_store(self) -> "ProblemStore":
        """An ephemeral scratch room: assumptions live here, then vanish."""
        return ProblemStore(self)


class ProblemStore:
    """Assume-and-check scratch space bound to one microtheory."""

    def __init__(self, mt: Microtheory) -> None:
        self.mt = mt
        self.assumptions: Set[Fact] = set()

    def assume(self, fact: Fact) -> None:
        self.assumptions.add(tuple(fact))

    def __enter__(self) -> "ProblemStore":
        return self

    def __exit__(self, *exc) -> None:
        self.assumptions.clear()


class KnowledgeBase:
    """The house: many rooms, one address book."""

    def __init__(self) -> None:
        self.mts: Dict[str, Microtheory] = {}

    def mt(self, name: str, parents: Tuple[str, ...] = ()) -> Microtheory:
        if name not in self.mts:
            self.mts[name] = Microtheory(name, parents)
        return self.mts[name]

    # ------------------------------------------------------------------
    # visibility: a room sees its own facts plus its parents' (general mts)
    # ------------------------------------------------------------------
    def _chain(self, mt: Microtheory) -> List[Microtheory]:
        seen: List[Microtheory] = []
        stack = [mt]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.append(cur)
            stack.extend(self.mts[p] for p in cur.parents if p in self.mts)
        return seen

    # ------------------------------------------------------------------
    # fast paths
    # ------------------------------------------------------------------
    def subclass_walk(self, entity: str, mt_name: str) -> Set[str]:
        """Fast path: every class ``entity`` belongs to, via isa/subclass."""
        mt = self.mts[mt_name]
        if entity in mt._subclass_cache:
            return set(mt._subclass_cache[entity])
        classes: Set[str] = set()
        frontier = [entity]
        chain = self._chain(mt)
        while frontier:
            cur = frontier.pop()
            for room in chain:
                for pred, a, b in room.facts:
                    if pred == "isa" and a == cur and b not in classes:
                        classes.add(b)
                        frontier.append(b)
                    elif pred == "subclass" and a == cur and b not in classes:
                        classes.add(b)
                        frontier.append(b)
        mt._subclass_cache[entity] = set(classes)
        return classes

    def _cached_lookup(self, pattern: Pattern, mt: Microtheory) -> Optional[Proof]:
        for room in self._chain(mt):
            for fact in room.facts:
                if _unify(pattern, fact) is not None:
                    return Proof(fact, sources=[f"given in mt:{room.name}"])
        return None

    # ------------------------------------------------------------------
    # general backward-chaining fallback
    # ------------------------------------------------------------------
    def _prove(
        self,
        pattern: Pattern,
        mt: Microtheory,
        extra: Set[Fact],
        depth: int,
        seen: Set[Pattern],
    ) -> Optional[Proof]:
        if depth <= 0 or pattern in seen:
            return None
        if pattern in mt._cache and not extra:
            return mt._cache[pattern]
        # fast paths first
        direct = self._cached_lookup(pattern, mt)
        if direct is not None:
            if not extra:
                mt._cache[pattern] = direct
            return direct
        for fact in extra:
            if _unify(pattern, fact) is not None:
                return Proof(fact, sources=["assumed in problem store"])
        # fallback: backward chaining over visible rules
        for room in self._chain(mt):
            for rule in room.rules:
                # unify head against pattern directly
                bindings = _unify(rule.head, pattern)
                if bindings is None:
                    continue
                children: List[Proof] = []
                ok = True
                for b in rule.body:
                    sub = _subst(b, bindings)
                    child = self._prove(sub, mt, extra, depth - 1, seen | {pattern})
                    if child is None:
                        ok = False
                        break
                    children.append(child)
                    # extend bindings from the proven child
                    nb = _unify(b, child.fact, bindings)
                    if nb is not None:
                        bindings = nb
                if ok:
                    fact = _subst(rule.head, bindings)
                    kind = "default" if rule.default else "rule"
                    proof = Proof(
                        fact,
                        sources=[f"{kind}:{rule.name} in mt:{room.name}"],
                        children=children,
                    )
                    if not extra:
                        mt._cache[pattern] = proof
                    return proof
        if not extra:
            mt._cache[pattern] = None
        return None

    def ask(
        self,
        pattern: Pattern,
        mt_name: str,
        extra: Optional[Set[Fact]] = None,
        depth: int = 12,
    ) -> Optional[Proof]:
        mt = self.mts[mt_name]
        return self._prove(tuple(pattern), mt, extra or set(), depth, set())

    def explain(self, pattern: Pattern, mt_name: str) -> List[str]:
        proof = self.ask(pattern, mt_name)
        if proof is None:
            return [f"{tuple(pattern)}: no proof in mt:{mt_name}"]
        return proof.explanation()

    # ------------------------------------------------------------------
    # forward chaining to a fixpoint (bounded)
    # ------------------------------------------------------------------
    def forward(self, mt_name: str, max_rounds: int = 20) -> Set[Fact]:
        mt = self.mts[mt_name]
        derived: Set[Fact] = set()
        chain = self._chain(mt)
        base = set()
        for room in chain:
            base |= room.facts
        for _ in range(max_rounds):
            grown = False
            for room in chain:
                for rule in room.rules:
                    for bindings in self._all_bindings(rule.body, base | derived):
                        fact = _subst(rule.head, bindings)
                        if fact not in base and fact not in derived:
                            derived.add(fact)
                            grown = True
            if not grown:
                break
        return derived

    def _all_bindings(
        self, body: Tuple[Pattern, ...], facts: Set[Fact]
    ) -> Iterator[Dict[str, Any]]:
        if not body:
            yield {}
            return
        first, rest = body[0], body[1:]
        for fact in facts:
            b = _unify(first, fact)
            if b is None:
                continue
            for tail in self._all_bindings(tuple(_subst(p, b) for p in rest), facts):
                merged = dict(b)
                merged.update(tail)
                yield merged

    # ------------------------------------------------------------------
    # abduction — assume-and-check in an ephemeral problem store
    # ------------------------------------------------------------------
    def abduce(
        self,
        goal: Pattern,
        mt_name: str,
        abducibles: List[Pattern],
        max_assumptions: int = 2,
    ) -> List[List[Fact]]:
        """Find minimal assumption sets (from abducible patterns, grounded
        against known constants) under which ``goal`` becomes provable."""
        mt = self.mts[mt_name]
        constants: Set[Any] = set()
        for room in self._chain(mt):
            for fact in room.facts:
                constants.update(f for f in fact if not _is_var(f))
        candidates: List[Fact] = []
        for ab in abducibles:
            if not any(_is_var(p) for p in ab):
                candidates.append(tuple(ab))
                continue
            # ground single-variable abducibles against known constants
            vars_ = [p for p in ab if _is_var(p)]
            if len(vars_) == 1:
                for c in sorted(str(x) for x in constants):
                    candidates.append(_subst(tuple(ab), {vars_[0]: c}))
        found: List[List[Fact]] = []
        from itertools import combinations

        for size in range(0, max_assumptions + 1):
            for combo in combinations(candidates, size):
                extra = set(combo)
                if self._prove(tuple(goal), mt, extra, 12, set()) is not None:
                    found.append(list(combo))
            if found:
                break  # minimal first
        return found
