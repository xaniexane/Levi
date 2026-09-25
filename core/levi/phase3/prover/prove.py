"""Bounded backward-chaining search.

``prove(goal, rule_source, fact_source, budget)`` runs a deterministic
depth-first search:

- rules are tried in fixed id order, facts in insertion (receipt) order;
- the proof tree is the *first complete derivation* found;
- depth, branch attempts, and wall-clock are all capped — exceeding a
  cap produces a receipted :class:`ProofFault`, never a hang and never
  a silent partial proof.

Same goal + same rules + same facts -> byte-identical proof tree.
"""

from __future__ import annotations

import time
from typing import Callable

from .rules import Budget, Fact, ProofFault, ProofNode, ProofOutcome, Rule
from .sources import FactSource, RuleSource
from .terms import Atom, Compound, Term, Var
from .unify import Subst, apply, unify


class _BudgetExceeded(Exception):
    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


class _Searcher:
    def __init__(
        self,
        rules: list[Rule],
        facts: list[Fact],
        budget: Budget,
        clock: Callable[[], float],
    ) -> None:
        self.rules = rules
        self.facts = facts
        self.budget = budget
        self.clock = clock
        self.started = clock()
        self.branches = 0
        self.var_counter = 0
        self.fault_seq = 0
        self.audit: list[str] = []

    # -- budget ---------------------------------------------------------
    def _check(self, depth: int) -> None:
        if depth > self.budget.max_depth:
            raise _BudgetExceeded(
                "depth",
                "proof incomplete: budget exhausted at depth %d "
                "(max_depth=%d)" % (depth, self.budget.max_depth),
            )
        if self.branches > self.budget.max_branches:
            raise _BudgetExceeded(
                "branches",
                "proof incomplete: budget exhausted after %d branch attempts "
                "(max_branches=%d)" % (self.branches, self.budget.max_branches),
            )
        elapsed_ms = (self.clock() - self.started) * 1000.0
        if elapsed_ms > self.budget.max_ms:
            raise _BudgetExceeded(
                "time",
                "proof incomplete: budget exhausted after %.1f ms "
                "(max_ms=%.1f)" % (elapsed_ms, self.budget.max_ms),
            )

    def _fault(self, exc: _BudgetExceeded) -> ProofFault:
        self.fault_seq += 1
        return ProofFault(
            reason="budget-exhausted",
            detail=exc.detail,
            receipt_id="prf-fault-%d" % self.fault_seq,
        )

    # -- variable freshening --------------------------------------------
    def _freshen_rule(self, rule: Rule) -> tuple[Term, list[Term]]:
        """Rename a rule's variables to fresh names (standardize apart).

        The head and the body share ONE renaming so variable links
        between them survive. Counter-based, so renaming is
        deterministic across runs and processes for identical inputs.
        """
        mapping: dict[str, str] = {}

        def fresh(name: str) -> str:
            if name not in mapping:
                self.var_counter += 1
                mapping[name] = "%s@%d" % (name, self.var_counter)
            return mapping[name]

        def go(t: Term) -> Term:
            if isinstance(t, Var):
                return Var(fresh(t.name))
            if isinstance(t, Atom):
                return t
            assert isinstance(t, Compound)
            return Compound(t.functor, tuple(go(a) for a in t.args))

        return go(rule.head), [go(b) for b in rule.body]

    # -- search -----------------------------------------------------------
    def _prove_goals(
        self, goals: list[Term], subst: Subst, depth: int
    ) -> tuple[bool, Subst, list[ProofNode]]:
        """Prove a conjunction.

        Returns ``(ok, subst, nodes)`` where ``nodes[i]`` is the proof of
        ``goals[i]`` — a rule node's children are exactly the proofs of
        its own body, never the sibling goals that follow it.
        """
        if not goals:
            return True, subst, []
        goal = apply(goals[0], subst)
        rest = goals[1:]

        # Facts first (insertion order), then rules (fixed id order).
        for fact in self.facts:
            self.branches += 1
            self._check(depth)
            s2 = unify(goal, fact.term, subst)
            if s2 is None:
                continue
            ok, s3, rest_nodes = self._prove_goals(rest, s2, depth)
            if ok:
                self.audit.append("fact:" + fact.id)
                leaf = ProofNode(
                    claim=goal,
                    rule_used="fact:" + fact.id,
                    subst=dict(s3),
                    witness=fact.witness,
                )
                return True, s3, [leaf] + rest_nodes

        for rule in self.rules:
            self.branches += 1
            self._check(depth)
            head, body = self._freshen_rule(rule)
            s2 = unify(goal, head, subst)
            if s2 is None:
                continue
            ok_body, s_body, body_nodes = self._prove_goals(body, s2, depth + 1)
            if not ok_body:
                continue
            ok_rest, s_rest, rest_nodes = self._prove_goals(rest, s_body, depth)
            if not ok_rest:
                continue
            self.audit.append(rule.id)
            node = ProofNode(
                claim=goal,
                rule_used=rule.id,
                subst=dict(s_rest),
                children=body_nodes,
            )
            return True, s_rest, [node] + rest_nodes

        return False, subst, []

    def run(self, goal: Term) -> ProofOutcome:
        self._check(0)
        try:
            ok, subst, kids = self._prove_goals([goal], {}, 0)
        except _BudgetExceeded as exc:
            return ProofOutcome(fault=self._fault(exc), audit=list(self.audit))
        except RecursionError:
            # The search outgrew the interpreter stack before any budget
            # counter tripped: that is still budget exhaustion, receipted
            # as a fault — never a crash, never a hang.
            self.fault_seq += 1
            return ProofOutcome(
                fault=ProofFault(
                    reason="budget-exhausted",
                    detail="proof incomplete: budget exhausted: search "
                    "exceeded the interpreter's recursion limit "
                    "(depth beyond any honest budget)",
                    receipt_id="prf-fault-%d" % self.fault_seq,
                ),
                audit=list(self.audit),
            )
        if not ok:
            self.fault_seq += 1
            return ProofOutcome(
                fault=ProofFault(
                    reason="unprovable",
                    detail="no derivation: goal has no complete proof "
                    "from the given rules and facts",
                    receipt_id="prf-fault-%d" % self.fault_seq,
                ),
                audit=list(self.audit),
            )
        # kids holds exactly one root node for the single goal.
        root = ProofNode(
            claim=apply(goal, subst),
            rule_used=kids[0].rule_used,
            subst=dict(subst),
            children=kids[0].children,
            witness=kids[0].witness,
        )
        return ProofOutcome(tree=root, audit=list(self.audit))


def prove(
    goal: Term,
    rule_source: RuleSource,
    fact_source: FactSource,
    budget: Budget | None = None,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> ProofOutcome:
    """Backward-chain ``goal`` to a proof tree inside ``budget``.

    Deterministic: rules in fixed id order, facts in insertion order,
    first complete derivation wins. Returns a :class:`ProofOutcome`
    with either a proof tree or a receipted fault.
    """
    rules = sorted(rule_source.iter_rules(), key=lambda r: r.id)
    facts = list(fact_source.facts())
    searcher = _Searcher(rules, facts, budget or Budget(), clock)
    return searcher.run(goal)
