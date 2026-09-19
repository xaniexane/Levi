"""plumber — a system service routing data between applications.

Studied from: revival-50-more-20260916-0009/report-part1.md (Section 2).

The load-bearing idea: one small plumbing service sits between
applications. Anything — selected text, a file path, a message — is
*plumbed*; a rule table decides which named ports receive it. Ports
are just inboxes; rules are editable at runtime; applications never
talk to each other directly.

LEVI's take: ``Plumber`` holds rules (substring or regex pattern ->
port name) and named inboxes in memory. ``plumb(text)`` routes a copy
to every matching port and reports where it went. ``add_rule`` /
``remove_rule`` / ``clear_rules`` work while the system runs — no
restart, no config file dance. Delivery is synchronous and local:
this is plumbing, not a message broker.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Pattern

ORIGIN = "levi-revival/plumber"


@dataclass
class Rule:
    """One routing rule: pattern -> destination port."""

    pattern: str
    port: str
    regex: bool = False
    _compiled: Pattern[str] | None = field(default=None, repr=False)

    def matches(self, text: str) -> bool:
        if self.regex:
            if self._compiled is None:
                object.__setattr__(self, "_compiled", re.compile(self.pattern))
            return self._compiled.search(text) is not None
        return self.pattern.lower() in text.lower()


@dataclass
class Delivery:
    """What happened when something was plumbed."""

    text: str
    ports: List[str]  # ports that received it, in rule order

    @property
    def delivered(self) -> bool:
        return bool(self.ports)


class Plumber:
    """The plumbing service: rules in, inboxes out."""

    def __init__(self) -> None:
        self.rules: List[Rule] = []
        self.ports: Dict[str, List[str]] = {}

    # -- runtime rule editing ------------------------------------------
    def add_rule(self, pattern: str, port: str, regex: bool = False) -> Rule:
        """Add a rule while the system runs. The port inbox is created."""
        rule = Rule(pattern=pattern, port=port, regex=regex)
        self.rules.append(rule)
        self.ports.setdefault(port, [])
        return rule

    def remove_rule(self, pattern: str, port: str) -> bool:
        for rule in self.rules:
            if rule.pattern == pattern and rule.port == port:
                self.rules.remove(rule)
                return True
        return False

    def clear_rules(self) -> None:
        self.rules.clear()

    def list_rules(self) -> List[Dict[str, str]]:
        return [
            {"pattern": r.pattern, "port": r.port, "regex": str(r.regex)}
            for r in self.rules
        ]

    # -- plumbing ------------------------------------------------------
    def plumb(self, text: str) -> Delivery:
        """Route ``text`` to every port whose rule matches.

        Ports receive a copy each; the same text may fan out to many
        ports. Returns a delivery report — LEVI says where it went.
        """
        hit: List[str] = []
        for rule in self.rules:
            if rule.matches(text):
                self.ports.setdefault(rule.port, []).append(text)
                if rule.port not in hit:
                    hit.append(rule.port)
        return Delivery(text=text, ports=hit)

    # -- inboxes -------------------------------------------------------
    def read(self, port: str) -> List[str]:
        """Read everything waiting in a named port inbox."""
        return list(self.ports.get(port, []))

    def drain(self, port: str) -> List[str]:
        """Read and empty a port inbox."""
        messages = self.ports.get(port, [])
        self.ports[port] = []
        return list(messages)

    def port_names(self) -> List[str]:
        return sorted(self.ports)
