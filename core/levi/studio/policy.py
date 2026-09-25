"""Omega Studio consent kit — Rego-style policy-as-code, LEVI-native.

The original Omega Studio (``omega-studio/``) was a "free & local AI agent
consent framework": human-in-the-loop consent for side-effect actions with
**Rego policy-as-code** and **HMAC-SHA256 signed audit trails**. This module
rebuilds those two missing organs as clean-room LEVI code, stdlib-only,
local-first, no network.

The policy language is a small, safe, *deterministic* subset of Rego:

.. code-block:: rego

    package consent

    default allow = false

    allow {
        input.action == "read"
        input.risk == "low"
    }

    deny {
        input.side_effects == true
        input.actor_trust == "untrusted"
    }

Rules supported
---------------
- ``package <ident>`` header (informational only).
- ``default allow = true|false`` and ``default deny = true|false``.
- ``allow { ... }`` / ``deny { ... }`` rules. Each rule body is a
  conjunction of comparisons: ``<path> <op> <literal>``.
- Paths: ``input`` or ``input.<ident>[.<ident>...]``.
- Operators: ``==`` ``!=`` ``>`` ``>=`` ``<`` ``<=`` ``in``.
- Literals: strings (double-quoted), numbers, ``true``/``false``,
  arrays of literals (for ``in``).

LAWS (fail-closed, always)
--------------------------
1. **Deny by default.** An unparseable policy is refused at load
   (``PolicyError``); a valid policy whose rules match nothing falls back
   to the declared default (default: deny).
2. **Deny overrides allow.** If any ``deny`` rule matches, the decision is
   ``deny`` even when an ``allow`` rule also matches.
3. **No guessing.** Unknown operators, malformed literals, and missing
   input fields make the condition false — never an exception at
   decision time, never a silent permit.
4. **Deterministic.** Same policy + same input = same decision, always.
   No randomness, no clock, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "PolicyError",
    "Condition",
    "Rule",
    "Policy",
    "DECISION_ALLOW",
    "DECISION_DENY",
]

DECISION_ALLOW = "allow"
DECISION_DENY = "deny"

# -- lexer --------------------------------------------------------------

_TOKEN = re.compile(
    r"""
    (?P<ws>\s+)
    |(?P<string>"(?:[^"\\]|\\.)*")
    |(?P<number>-?\d+(?:\.\d+)?)
    |(?P<op>==|!=|>=|<=|>|<)
    |(?P<punct>[{}.,\[\]])
    |(?P<word>[A-Za-z_][A-Za-z0-9_]*)
    """,
    re.VERBOSE,
)


class PolicyError(Exception):
    """A policy failed to parse or is malformed. Fail closed: never permit."""


def _tokenize(text: str) -> List[Tuple[str, str]]:
    tokens: List[Tuple[str, str]] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise PolicyError(f"cannot tokenize at offset {pos}: {text[pos:pos+20]!r}")
        kind = m.lastgroup or ""
        value = m.group(0)
        pos = m.end()
        if kind == "ws":
            continue
        tokens.append((kind, value))
    return tokens


def _unquote(s: str) -> str:
    inner = s[1:-1]
    out: List[str] = []
    i = 0
    while i < len(inner):
        c = inner[i]
        if c == "\\" and i + 1 < len(inner):
            nxt = inner[i + 1]
            out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, nxt))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


# -- AST ----------------------------------------------------------------

VALID_OPS = ("==", "!=", ">", ">=", "<", "<=", "in")


@dataclass(frozen=True)
class Condition:
    """One ``path op literal`` comparison. Missing paths are false."""

    path: Tuple[str, ...]
    op: str
    literal: Any

    def evaluate(self, data: Dict[str, Any]) -> bool:
        try:
            value = self._resolve(data)
        except (KeyError, TypeError):
            return False  # unknown input field: condition is false, never permit
        try:
            return self._compare(value)
        except TypeError:
            return False  # incomparable types: false, never permit

    def _resolve(self, data: Dict[str, Any]) -> Any:
        # In Rego, `input` is the root of the decision document, so
        # `input.action` addresses data["action"], not data["input"]["action"].
        parts = self.path[1:] if self.path[:1] == ("input",) else self.path
        current: Any = data
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                raise KeyError(part)
            current = current[part]
        return current

    def _compare(self, value: Any) -> bool:
        op, lit = self.op, self.literal
        if op == "==":
            return self._eq_strict(value, lit)
        if op == "!=":
            return not self._eq_strict(value, lit)
        if op == "in":
            if not isinstance(lit, list):
                return False
            return any(self._eq_strict(value, item) for item in lit)
        if not isinstance(value, (int, float)) or not isinstance(lit, (int, float)):
            return False
        if isinstance(value, bool) or isinstance(lit, bool):
            return False
        if op == ">":
            return value > lit
        if op == ">=":
            return value >= lit
        if op == "<":
            return value < lit
        if op == "<=":
            return value <= lit
        return False  # unreachable: parser rejects unknown ops

    @staticmethod
    def _eq_strict(a: Any, b: Any) -> bool:
        # Strict equality: no bool/int cross-talk (True == 1 in Python).
        if isinstance(a, bool) or isinstance(b, bool):
            return isinstance(a, bool) and isinstance(b, bool) and a == b
        return type(a) is type(b) and a == b


@dataclass(frozen=True)
class Rule:
    """An ``allow``/``deny`` rule: a conjunction of conditions."""

    effect: str
    conditions: Tuple[Condition, ...] = ()

    def matches(self, data: Dict[str, Any]) -> bool:
        return all(c.evaluate(data) for c in self.conditions)


@dataclass
class Policy:
    """A parsed consent policy. ``decide`` is total and deterministic."""

    package: str = "consent"
    default_allow: bool = False
    default_deny: bool = False
    rules: List[Rule] = field(default_factory=list)

    @classmethod
    def from_rego(cls, text: str) -> "Policy":
        """Parse Rego-subset text. Raises ``PolicyError`` — never guess."""
        parser = _Parser(_tokenize(_normalize_defaults(text)))
        return parser.parse()

    def decide(self, data: Dict[str, Any]) -> str:
        """Return ``allow`` or ``deny``. Never raises on bad input data."""
        if not isinstance(data, dict):
            return DECISION_DENY
        for rule in self.rules:
            if rule.effect == DECISION_DENY and rule.matches(data):
                return DECISION_DENY  # deny overrides allow, always
        for rule in self.rules:
            if rule.effect == DECISION_ALLOW and rule.matches(data):
                return DECISION_ALLOW
        if self.default_deny:
            return DECISION_DENY
        return DECISION_ALLOW if self.default_allow else DECISION_DENY


# -- parser -------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: List[Tuple[str, str]]) -> None:
        self.tokens = tokens
        self.pos = 0

    def parse(self) -> Policy:
        policy = Policy()
        while self.pos < len(self.tokens):
            kind, value = self.tokens[self.pos]
            if kind == "word" and value == "package":
                policy.package = self._package()
            elif kind == "word" and value == "default":
                self._default(policy)
            elif kind == "word" and value in (DECISION_ALLOW, DECISION_DENY):
                policy.rules.append(self._rule(value))
            else:
                raise PolicyError(f"unexpected {value!r} at token {self.pos}")
        return policy

    def _expect(self, kind: str, value: Optional[str] = None) -> str:
        if self.pos >= len(self.tokens):
            raise PolicyError("unexpected end of policy")
        k, v = self.tokens[self.pos]
        if k != kind or (value is not None and v != value):
            raise PolicyError(
                f"expected {kind} {value!r}, got {k} {v!r} at token {self.pos}"
            )
        self.pos += 1
        return v

    def _package(self) -> str:
        self._expect("word", "package")
        name = self._expect("word")
        return name

    def _default(self, policy: Policy) -> None:
        self._expect("word", "default")
        effect = self._expect("word")
        if effect not in (DECISION_ALLOW, DECISION_DENY):
            raise PolicyError(f"default must be allow|deny, got {effect!r}")
        # Pre-normalized: "default allow = false" -> "default allow __assign__ false"
        self._expect("word", "__assign__")
        val = self._expect("word")
        if val not in ("true", "false"):
            raise PolicyError(f"default {effect} must be true|false, got {val!r}")
        if effect == DECISION_ALLOW:
            policy.default_allow = val == "true"
        else:
            policy.default_deny = val == "true"

    def _rule(self, effect: str) -> Rule:
        self._expect("word", effect)
        self._expect("punct", "{")
        conditions: List[Condition] = []
        while True:
            kind, value = self.tokens[self.pos]
            if kind == "punct" and value == "}":
                self.pos += 1
                break
            conditions.append(self._condition())
        return Rule(effect=effect, conditions=tuple(conditions))

    def _condition(self) -> Condition:
        path = self._path()
        kind, value = self.tokens[self.pos]
        if kind == "op":
            self.pos += 1
            op = value
        elif kind == "word" and value == "in":
            self.pos += 1
            op = "in"
        else:
            raise PolicyError(f"expected operator, got {value!r}")
        if op not in VALID_OPS:
            raise PolicyError(f"unsupported operator {op!r}")
        literal = self._literal()
        return Condition(path=tuple(path), op=op, literal=literal)

    def _path(self) -> List[str]:
        parts = [self._expect("word")]
        while self.pos < len(self.tokens):
            kind, value = self.tokens[self.pos]
            if kind == "punct" and value == ".":
                self.pos += 1
                parts.append(self._expect("word"))
            else:
                break
        return parts

    def _literal(self) -> Any:
        kind, value = self.tokens[self.pos]
        if kind == "string":
            self.pos += 1
            return _unquote(value)
        if kind == "number":
            self.pos += 1
            return float(value) if "." in value else int(value)
        if kind == "word" and value in ("true", "false"):
            self.pos += 1
            return value == "true"
        if kind == "punct" and value == "[":
            self.pos += 1
            items: List[Any] = []
            while True:
                k, v = self.tokens[self.pos]
                if k == "punct" and v == "]":
                    self.pos += 1
                    break
                items.append(self._literal())
                k2, v2 = self.tokens[self.pos]
                if k2 == "punct" and v2 == ",":
                    self.pos += 1
            return items
        raise PolicyError(f"expected literal, got {value!r}")


# NOTE: the tokenizer does not match a bare '=' (assignment in `default`),
# so we pre-normalize `default allow = false` before tokenizing.
_DEFAULT_RE = re.compile(
    r"\bdefault\s+(allow|deny)\s*=\s*(true|false)\b", re.IGNORECASE
)


def _normalize_defaults(text: str) -> str:
    def repl(m: "re.Match[str]") -> str:
        return f"default {m.group(1).lower()} __assign__ {m.group(2).lower()}"

    return _DEFAULT_RE.sub(repl, text)
