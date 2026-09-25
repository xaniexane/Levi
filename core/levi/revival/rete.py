"""Rete — an incremental discrimination network for rule matching.

Studied from: ai-si-software-internals-20260916-0005/report.md (sec 1.4)
— both entries MERGED into one module.

The mechanism under study: instead of re-testing every rule against
every fact on every cycle, compile the rules' conditions into a
discrimination network that remembers partial matches:

- **Alpha memories**: one per distinct intra-element test pattern
  (which positions must equal which constants). A fact enters only the
  alpha nodes whose tests it passes.
- **Beta join nodes**: each joins the token stream from the previous
  condition with one alpha memory, keeping a memory of partial matches
  (variable bindings so far). Shared variables must agree across the
  join.
- **Terminal nodes**: a full pass through every condition drops a
  (rule, bindings) entry into the conflict set.

Working-memory changes propagate as **+ / − tokens**, and only the
affected paths recompute — cost scales with the *change*, not the store.

Conflict resolution is a **separate, pluggable policy** object, not
baked into the network: recency, specificity, or arbitrary — swap the
policy, keep the network.

Original, from-scratch implementation for LEVI. Facts are plain tuples
(``("on", "A", "B")``); pattern elements starting with ``"?"`` are
variables, everything else is a constant test. stdlib-only, no network,
deterministic.

Public surface:
- ``Rete()`` — ``add_rule(name, conditions, action=None)``,
  ``assert_fact(*fact)``, ``retract_fact(*fact)``,
  ``conflict_set()``, ``fire(policy=None)``.
- Policies: ``ArbitraryPolicy``, ``RecencyPolicy``,
  ``SpecificityPolicy`` (all share ``ResolutionPolicy.select``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

ORIGIN = "levi-revival/rete"

Fact = Tuple[Any, ...]
Pattern = Tuple[Any, ...]


def _is_var(elem: Any) -> bool:
    return isinstance(elem, str) and elem.startswith("?")


def _signature(pattern: Pattern) -> Tuple[int, Tuple[Tuple[int, Any], ...]]:
    """Alpha key: arity + which positions are pinned to which constants."""
    consts = tuple((i, e) for i, e in enumerate(pattern) if not _is_var(e))
    return (len(pattern), consts)


@dataclass
class _WME:
    fact: Fact
    tag: int  # recency stamp; higher = newer


@dataclass
class _Token:
    bindings: Dict[str, Any]
    wmes: Tuple[_WME, ...]  # the facts justifying this partial match

    def recency(self) -> int:
        return max((w.tag for w in self.wmes), default=-1)


class _AlphaNode:
    def __init__(self, pattern: Pattern) -> None:
        self.pattern = pattern
        self.memory: List[_WME] = []
        self.successors: List["_BetaJoin"] = []  # joins waiting on this alpha

    def matches(self, fact: Fact) -> bool:
        if len(fact) != len(self.pattern):
            return False
        return all(
            _is_var(p) or p == f for p, f in zip(self.pattern, fact, strict=True)
        )

    def add(self, wme: _WME) -> None:
        self.memory.append(wme)
        for join in self.successors:
            join.right_add(wme)

    def remove(self, wme: _WME) -> None:
        self.memory = [w for w in self.memory if w is not wme]
        for join in self.successors:
            join.right_remove(wme)


class _BetaJoin:
    """Joins left tokens (bindings so far) with one alpha memory."""

    def __init__(self, pattern: Pattern, network: "Rete") -> None:
        self.pattern = pattern
        self.network = network
        self.left_memory: List[_Token] = []
        self.successors: List = []  # next _BetaJoin or _Terminal

    def consistent(self, token: _Token, wme: _WME) -> Optional[Dict[str, Any]]:
        bindings = dict(token.bindings)
        for p, f in zip(self.pattern, wme.fact, strict=True):
            if _is_var(p):
                if p in bindings:
                    if bindings[p] != f:
                        return None
                else:
                    bindings[p] = f
            elif p != f:
                return None
        return bindings

    def _emit(self, token: _Token) -> None:
        for succ in self.successors:
            succ.left_add(token)

    def left_add(self, token: _Token) -> None:
        self.left_memory.append(token)
        alpha = self.network.alpha_for(self.pattern)
        assert alpha is not None
        for wme in alpha.memory:
            b = self.consistent(token, wme)
            if b is not None:
                self._emit(_Token(b, token.wmes + (wme,)))

    def left_remove_if(self, pred) -> None:
        doomed = [t for t in self.left_memory if pred(t)]
        self.left_memory = [t for t in self.left_memory if not pred(t)]
        for token in doomed:
            for succ in self.successors:
                succ.left_remove_if(
                    lambda t, tok=token: any(w in tok.wmes for w in t.wmes)
                )

    def right_add(self, wme: _WME) -> None:
        for token in self.left_memory:
            b = self.consistent(token, wme)
            if b is not None:
                self._emit(_Token(b, token.wmes + (wme,)))

    def right_remove(self, wme: _WME) -> None:
        for succ in self.successors:
            succ.left_remove_if(lambda t: any(w is wme for w in t.wmes))


class _Terminal:
    def __init__(self, rule: "Rule", network: "Rete") -> None:
        self.rule = rule
        self.network = network

    def left_add(self, token: _Token) -> None:
        self.network._conflict.append((self.rule, token))

    def left_remove(self, token: _Token) -> None:  # pragma: no cover
        pass

    def left_remove_if(self, pred) -> None:
        self.network._conflict = [
            (r, t)
            for (r, t) in self.network._conflict
            if not (r is self.rule and pred(t))
        ]


@dataclass
class Rule:
    name: str
    conditions: List[Pattern]
    action: Optional[Callable[[Dict[str, Any]], Any]] = None


# ----------------------------------------------------------------------
# conflict resolution — pluggable, separate from the network
# ----------------------------------------------------------------------
class ResolutionPolicy:
    name = "base"

    def select(
        self, conflicts: List[Tuple[Rule, _Token]]
    ) -> Optional[Tuple[Rule, _Token]]:
        raise NotImplementedError


class ArbitraryPolicy(ResolutionPolicy):
    name = "arbitrary"

    def select(self, conflicts):
        return conflicts[0] if conflicts else None


class RecencyPolicy(ResolutionPolicy):
    name = "recency"

    def select(self, conflicts):
        if not conflicts:
            return None
        return max(conflicts, key=lambda rt: (rt[1].recency(), rt[0].name))


class SpecificityPolicy(ResolutionPolicy):
    name = "specificity"

    def select(self, conflicts):
        if not conflicts:
            return None
        return max(conflicts, key=lambda rt: (len(rt[0].conditions), rt[1].recency()))


class Rete:
    """The network. Rules compile to alpha/beta structure; facts stream in."""

    def __init__(self) -> None:
        self._alphas: Dict[Tuple, _AlphaNode] = {}
        self._wmes: List[_WME] = []
        self._conflict: List[Tuple[Rule, _Token]] = []
        self._tag = 0
        self.rules: List[Rule] = []
        self._dummy = _Token({}, ())

    # ------------------------------------------------------------------
    # rule compilation
    # ------------------------------------------------------------------
    def alpha_for(self, pattern: Pattern) -> Optional[_AlphaNode]:
        return self._alphas.get(_signature(pattern))

    def _alpha(self, pattern: Pattern) -> _AlphaNode:
        key = _signature(pattern)
        node = self._alphas.get(key)
        if node is None:
            node = _AlphaNode(pattern)
            self._alphas[key] = node
            # seed with existing memory — late rules see old facts
            for wme in self._wmes:
                if node.matches(wme.fact):
                    node.memory.append(wme)
        return node

    def add_rule(
        self,
        name: str,
        conditions: List[Pattern],
        action: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> Rule:
        rule = Rule(name, [tuple(c) for c in conditions], action)
        self.rules.append(rule)
        first: Any = None
        prev: Any = None
        for cond in rule.conditions:
            alpha = self._alpha(cond)
            join = _BetaJoin(cond, self)
            alpha.successors.append(join)
            if prev is None:
                first = join
            else:
                prev.successors.append(join)
            prev = join
        terminal = _Terminal(rule, self)
        assert prev is not None
        prev.successors.append(terminal)
        # Drive the dummy token through the whole chain exactly once, now
        # that every join and the terminal are attached. Facts already
        # sitting in (seeded) alpha memories join along the way, so a
        # rule added late still sees old facts — as complete matches.
        # (Feeding a join's left_memory to the terminal directly would
        # leak partial matches into the conflict set.)
        assert first is not None
        first.left_add(self._dummy)
        return rule

    # ------------------------------------------------------------------
    # working memory — +/- tokens, incremental by construction
    # ------------------------------------------------------------------
    def assert_fact(self, *fact: Any) -> None:
        wme = _WME(tuple(fact), self._tag)
        self._tag += 1
        self._wmes.append(wme)
        for alpha in self._alphas.values():
            if alpha.matches(wme.fact):
                alpha.add(wme)

    def retract_fact(self, *fact: Any) -> bool:
        target = tuple(fact)
        for wme in list(self._wmes):
            if wme.fact == target:
                self._wmes.remove(wme)
                for alpha in self._alphas.values():
                    if wme in alpha.memory:
                        alpha.remove(wme)
                # drop conflict entries justified by this fact
                self._conflict = [
                    (r, t)
                    for (r, t) in self._conflict
                    if all(w is not wme for w in t.wmes)
                ]
                return True
        return False

    # ------------------------------------------------------------------
    # running
    # ------------------------------------------------------------------
    def conflict_set(self) -> List[Tuple[str, Dict[str, Any]]]:
        return [(r.name, dict(t.bindings)) for (r, t) in self._conflict]

    def fire(self, policy: Optional[ResolutionPolicy] = None) -> Optional[Any]:
        """Select one conflict entry via policy and run its action."""
        policy = policy or ArbitraryPolicy()
        pick = policy.select(self._conflict)
        if pick is None:
            return None
        rule, token = pick
        self._conflict.remove(pick)
        if rule.action is not None:
            return rule.action(dict(token.bindings))
        return (rule.name, dict(token.bindings))

    def stats(self) -> Dict[str, int]:
        return {
            "rules": len(self.rules),
            "alpha_nodes": len(self._alphas),
            "facts": len(self._wmes),
            "conflicts": len(self._conflict),
        }
