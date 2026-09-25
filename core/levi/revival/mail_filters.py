"""LEVI's mail filters: a power-user contract for sorting mail.

Studied from: desktop-casualties-20260916 / report.md [3. Eudora]
(Filtering as a first-class feature.)

The studied shape made filtering a contract: conditions you can read,
actions you can trust, order you control. This module rebuilds that as
LEVI's own filter engine. A filter is an ordered list of conditions
(field, operator, value) plus an ordered list of actions (move, label,
flag, mark seen, delete). Filters run in order; each decides whether
later filters still see the message.

What this is NOT: a learning system. Filters do exactly what they say
— no statistics, no adaptation. The Bayesian spam watcher lives in its
own module; this one is the deliberate, legible kind of sorting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List


ORIGIN = "levi-revival/mail-filters"


FIELDS = ("from", "to", "subject", "body", "any")
OPERATORS = ("contains", "is", "starts_with", "ends_with", "regex", "exists")


@dataclass
class Condition:
    """One test against a message: ``field operator value``.

    ``field`` is one of from/to/subject/body/any (any = all of them).
    ``exists`` ignores ``value`` and tests that the field is non-empty.
    Matching is case-insensitive except for ``regex``.
    """

    field: str
    operator: str
    value: str = ""

    def __post_init__(self) -> None:
        if self.field not in FIELDS:
            raise ValueError(f"unknown field: {self.field!r}")
        if self.operator not in OPERATORS:
            raise ValueError(f"unknown operator: {self.operator!r}")
        if self.operator == "regex":
            re.compile(self.value)  # fail fast on a bad pattern

    def _texts(self, message: Dict[str, str]) -> List[str]:
        if self.field == "any":
            return [message.get(f, "") for f in ("from", "to", "subject", "body")]
        return [message.get(self.field, "")]

    def matches(self, message: Dict[str, str]) -> bool:
        for text in self._texts(message):
            if self._hit(text):
                return True
        return False

    def _hit(self, text: str) -> bool:
        op, value = self.operator, self.value
        if op == "exists":
            return bool(text.strip())
        if op == "contains":
            return value.lower() in text.lower()
        if op == "is":
            return value.lower() == text.lower().strip()
        if op == "starts_with":
            return text.lower().startswith(value.lower())
        if op == "ends_with":
            return text.lower().endswith(value.lower())
        if op == "regex":
            return re.search(value, text) is not None
        return False  # unreachable


@dataclass
class Action:
    """One thing to do when a filter fires.

    ``kind`` is one of: move_to, add_label, flag, mark_seen, delete.
    ``argument`` carries the destination folder or label name; it is
    ignored by flag/mark_seen/delete.
    """

    kind: str
    argument: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ("move_to", "add_label", "flag", "mark_seen", "delete"):
            raise ValueError(f"unknown action: {self.kind!r}")
        if self.kind in ("move_to", "add_label") and not self.argument:
            raise ValueError(f"action {self.kind!r} needs an argument")


@dataclass
class MailFilter:
    """A named filter: conditions (all must match) plus actions.

    ``match_all=False`` means any single condition is enough.
    ``stop_after=True`` means later filters never see a message this
    one fired on — the classic "first match wins" contract.
    """

    name: str
    conditions: List[Condition] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    match_all: bool = True
    stop_after: bool = True
    enabled: bool = True

    def fires_on(self, message: Dict[str, str]) -> bool:
        if not self.enabled or not self.conditions:
            return False
        hits = [c.matches(message) for c in self.conditions]
        return all(hits) if self.match_all else any(hits)


class FilterEngine:
    """The ordered set of filters. Runs them, reports what happened."""

    def __init__(self) -> None:
        self.filters: List[MailFilter] = []

    def add(self, mail_filter: MailFilter) -> None:
        self.filters.append(mail_filter)

    def remove(self, name: str) -> None:
        for i, f in enumerate(self.filters):
            if f.name == name:
                del self.filters[i]
                return
        raise KeyError(f"no such filter: {name!r}")

    def move(self, name: str, position: int) -> None:
        """Reorder a filter. Order is the contract — it matters."""
        for i, f in enumerate(self.filters):
            if f.name == name:
                filt = self.filters.pop(i)
                self.filters.insert(max(0, min(position, len(self.filters))), filt)
                return
        raise KeyError(f"no such filter: {name!r}")

    def run(self, message: Dict[str, str]) -> List[Dict[str, str]]:
        """Run every enabled filter in order.

        Returns a report: one dict per fired filter with its name and
        the actions it emitted. Stops at the first filter with
        ``stop_after`` set.
        """
        report = []
        for filt in self.filters:
            if filt.fires_on(message):
                report.append(
                    {
                        "filter": filt.name,
                        "actions": [
                            {"kind": a.kind, "argument": a.argument}
                            for a in filt.actions
                        ],
                    }
                )
                if filt.stop_after:
                    break
        return report

    def apply_to_client(self, client, account: str, uid: str) -> List[Dict[str, str]]:
        """Run filters against a message living on a mail client.

        Translates emitted actions into real client operations (move /
        flag / mark seen / delete). Returns the same report as
        :meth:`run`. The client must look like the built-in mail client
        (``find`` + ``move`` + ``delete``); the message must be filed
        there first.
        """
        msg = client.find(account, uid)
        if msg is None:
            raise KeyError(f"no message {uid!r} in account {account!r}")
        flat = {
            "from": msg.from_addr,
            "to": ", ".join(msg.to_addrs),
            "subject": msg.subject,
            "body": msg.body,
        }
        report = self.run(flat)
        for entry in report:
            for action in entry["actions"]:
                kind, arg = action["kind"], action["argument"]
                if kind == "move_to":
                    client.move(account, uid, arg)
                elif kind == "delete":
                    client.delete(account, uid)
                elif kind == "flag":
                    found = client.find(account, uid)
                    if found is not None:
                        found.flag("flagged")
                elif kind == "mark_seen":
                    found = client.find(account, uid)
                    if found is not None:
                        found.flag("seen")
                # add_label is recorded in the report only: labels are a
                # tagging layer the local client keeps out of folders
        return report
