"""Thin adapters to the middle team: rule and fact protocols plus stubs.

``RuleSource`` / ``FactSource`` are the protocols the middle team's
rule-reflex layer and memory must honor (see
``~/workspace/levi-unified-build/end-to-middle-contract.md``):

- ``iter_rules()`` returns rules in fixed id order;
- ``facts()`` returns facts in insertion (receipt-sequence) order.

Until the middle team exists, ``DictRuleSource`` / ``DictFactSource``
supply fixed local test data.
"""

from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from .rules import Fact, Rule
from .terms import Term, term_from_dict


@runtime_checkable
class RuleSource(Protocol):
    """Source of rules-as-data for the prover."""

    def iter_rules(self) -> list[Rule]:
        """Rules in fixed id order."""
        ...


@runtime_checkable
class FactSource(Protocol):
    """Source of witnessed facts for the prover."""

    def facts(self) -> list[Fact]:
        """Facts in insertion (receipt-sequence) order."""
        ...


def _coerce_rule(item: Rule | dict) -> Rule:
    if isinstance(item, Rule):
        return item
    return Rule(
        id=item["id"],
        head=item["head"]
        if isinstance(item["head"], Term)
        else term_from_dict(item["head"]),
        body=tuple(
            b if isinstance(b, Term) else term_from_dict(b)
            for b in item.get("body", ())
        ),
        provenance=item.get("provenance", ""),
    )


def _coerce_fact(item: Fact | dict) -> Fact:
    if isinstance(item, Fact):
        return item
    return Fact(
        id=item["id"],
        term=item["term"]
        if isinstance(item["term"], Term)
        else term_from_dict(item["term"]),
        witness=item["witness"],
    )


class DictRuleSource:
    """Local stub: fixed rules from plain data. Rules are data, not code."""

    def __init__(self, rules: Iterable[Rule | dict]) -> None:
        self._rules = [_coerce_rule(r) for r in rules]

    def iter_rules(self) -> list[Rule]:
        return sorted(self._rules, key=lambda r: r.id)


class DictFactSource:
    """Local stub: fixed witnessed facts, kept in insertion order."""

    def __init__(self, facts: Iterable[Fact | dict]) -> None:
        self._facts = [_coerce_fact(f) for f in facts]

    def facts(self) -> list[Fact]:
        return list(self._facts)
