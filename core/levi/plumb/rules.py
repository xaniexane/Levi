"""LEVI plumbing rules: parsing the keeper's dispatch table.

Rule file format (LEVI's own — not Pike's syntax):

    # comment lines start with '#'
    rule open-urls
      type: text
      match: https?://\\S+
      port: browser
      action: open-url $0

    rule file-addresses
      type: text
      match: (?P<path>/[\\w\\-. /]+):(?P<line>\\d+)
      require: file-exists {path}
      port: editor
      action: open-file {path} line={line}

Directives inside a ``rule`` block:
- ``type: <name>``   — message type must equal <name>. Omit for any type.
- ``match: <regex>``  — one or more, in order. The FIRST pattern winnows:
  the engine picks the match span from the data; every further ``match``
  must also match that same span (Pike's "same portion" rule). Named
  groups feed ``{name}`` substitution; numbered groups feed ``$N``.
- ``require: file-exists <template>`` — the rendered template must name
  an existing file. More predicates may be added; unknown ones are a
  parse error (deny-closed, law 3).
- ``port: <name>``    — destination port (required).
- ``action: <template>`` — rendered with ``$0``..``$9`` (numbered groups
  of the winnowing pattern) and ``{name}`` (named groups of any pattern).
  Required.

Blank lines and ``#`` comments are ignored. Indentation is cosmetic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


class RuleError(ValueError):
    """A plumbing rule file is malformed. Nothing is half-parsed."""


@dataclass(frozen=True)
class Rule:
    """One dispatch rule: name, optional type, ordered patterns,
    predicates, destination port, action template."""

    name: str
    type: str | None
    patterns: tuple[str, ...]
    requires: tuple[str, ...]
    port: str
    action: str
    line_no: int = 0

    def __post_init__(self) -> None:
        # Compile eagerly so a bad regex fails at parse time, never at
        # dispatch time.
        for pat in self.patterns:
            try:
                re.compile(pat)
            except re.error as exc:
                raise RuleError(
                    f"rule {self.name!r}: bad regex {pat!r}: {exc}"
                ) from exc


_DIRECTIVES = ("type", "match", "require", "port", "action")


def parse_rules(text: str) -> list[Rule]:
    """Parse rule file text into a list of :class:`Rule`.

    Raises :class:`RuleError` on anything malformed — unknown directive,
    missing port/action, empty pattern, duplicate rule name. A file that
    fails to parse yields no rules at all.
    """
    rules: list[Rule] = []
    current: dict | None = None
    seen: set[str] = set()

    def finish(block: dict, line_no: int) -> None:
        name = block["name"]
        if name in seen:
            raise RuleError(f"line {line_no}: duplicate rule {name!r}")
        if not block["patterns"]:
            raise RuleError(f"rule {name!r}: at least one 'match' required")
        if not block["port"]:
            raise RuleError(f"rule {name!r}: 'port' is required")
        if not block["action"]:
            raise RuleError(f"rule {name!r}: 'action' is required")
        for req in block["requires"]:
            if not req.startswith("file-exists "):
                raise RuleError(
                    f"rule {name!r}: unknown require predicate {req!r} "
                    "(only 'file-exists <template>' is supported)"
                )
        seen.add(name)
        rules.append(
            Rule(
                name=name,
                type=block["type"],
                patterns=tuple(block["patterns"]),
                requires=tuple(block["requires"]),
                port=block["port"],
                action=block["action"],
                line_no=block["line_no"],
            )
        )

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("rule "):
            if current is not None:
                finish(current, line_no)
            name = line[5:].strip()
            if not name or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
                raise RuleError(f"line {line_no}: bad rule name {name!r}")
            current = {
                "name": name,
                "type": None,
                "patterns": [],
                "requires": [],
                "port": "",
                "action": "",
                "line_no": line_no,
            }
            continue
        if current is None:
            raise RuleError(f"line {line_no}: directive outside any rule")
        if ":" not in line:
            raise RuleError(f"line {line_no}: expected 'directive: value'")
        directive, _, value = line.partition(":")
        directive = directive.strip()
        value = value.strip()
        if directive not in _DIRECTIVES:
            raise RuleError(f"line {line_no}: unknown directive {directive!r}")
        if not value:
            raise RuleError(f"line {line_no}: empty value for {directive!r}")
        if directive == "match":
            current["patterns"].append(value)
        elif directive == "require":
            current["requires"].append(value)
        elif directive in ("port", "action"):
            if current[directive]:
                raise RuleError(
                    f"line {line_no}: duplicate {directive!r} in rule "
                    f"{current['name']!r}"
                )
            current[directive] = value
        elif directive == "type":
            if current["type"] is not None:
                raise RuleError(
                    f"line {line_no}: duplicate 'type' in rule "
                    f"{current['name']!r}"
                )
            current["type"] = value

    if current is not None:
        finish(current, line_no + 1)
    return rules


def default_rules() -> list[Rule]:
    """Opt-in starter rules. NOT enabled by default (law 2) — the keeper
    must choose to load these. They cover the two canonical dispatches:
    URLs and file:line addresses."""
    return parse_rules(
        """\
rule open-urls
  type: text
  match: https?://[^\\s<>"']+
  port: browser
  action: open-url $0

rule file-addresses
  type: text
  match: (?P<path>/[\\w\\-. /]+):(?P<line>\\d+)
  require: file-exists {path}
  port: editor
  action: open-file {path} line={line}
"""
    )
