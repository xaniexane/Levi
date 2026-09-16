"""Lotus Agenda revival: inspectable rule-based auto-categorization.

Lotus Agenda's killer feature was automatic categorization driven by
user-visible rules. This module is the same idea for LEVI's memory/journal
ingestion: a small rule engine that files entries into categories, where
every filing decision is *explainable* — the "glass cockpit" rule.

The glass cockpit contract
---------------------------
``file_entry(entry)`` returns ``(category, explanation)`` where the
explanation names the winning rule and lists which of its conditions
matched. Nothing is ever filed silently: if no rule matches, the entry
lands in ``"uncategorized"`` with an explanation that says exactly that
(fail-open), and every decision is appended to an audit log.

Entries are plain dicts (typically memory/journal entry dicts) with
optional keys: ``content``, ``tags``, ``source``, ``importance``,
``memory_type``, ... Anything else is ignored.

stdlib-only. No network. Defensive: invalid rules and malformed entries
raise ``ValueError``/``TypeError`` at construction time, never at file
time — ``file_entry`` itself never raises for a bad entry.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# --------------------------------------------------------------------------
# Conditions
# --------------------------------------------------------------------------

_CONDITION_KINDS = (
    "keywords",
    "regex",
    "tags",
    "source",
    "min_importance",
    "max_importance",
)


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _norm_tags(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    try:
        return [str(t) for t in value]
    except TypeError:
        return []


def _check_condition(kind: str, spec: Any, entry: Dict[str, Any]) -> Optional[str]:
    """Return a human-readable description if the condition matches, else None."""
    if kind == "keywords":
        words = spec if isinstance(spec, list) else [spec]
        words = [str(w) for w in words]
        content = _norm_text(entry.get("content")).lower()
        hit = [w for w in words if w.lower() in content]
        if hit:
            return "keywords matched: %s" % ", ".join(sorted(set(hit)))
        return None
    if kind == "regex":
        patterns = spec if isinstance(spec, list) else [spec]
        content = _norm_text(entry.get("content"))
        hit = [str(p) for p in patterns if re.search(str(p), content, re.IGNORECASE)]
        if hit:
            return "regex matched: %s" % ", ".join(hit)
        return None
    if kind == "tags":
        want = spec if isinstance(spec, list) else [spec]
        want_l = {str(t).lower() for t in want}
        have = {t.lower() for t in _norm_tags(entry.get("tags"))}
        hit = sorted(want_l & have)
        if hit:
            return "tags matched: %s" % ", ".join(hit)
        return None
    if kind == "source":
        sources = spec if isinstance(spec, list) else [spec]
        got = _norm_text(entry.get("source"))
        if got in [str(s) for s in sources]:
            return "source matched: %s" % got
        return None
    if kind == "min_importance":
        try:
            imp = float(entry.get("importance", 0.0))
        except (TypeError, ValueError):
            imp = 0.0
        if imp >= float(spec):
            return "importance %.2f >= %.2f" % (imp, float(spec))
        return None
    if kind == "max_importance":
        try:
            imp = float(entry.get("importance", 1.0))
        except (TypeError, ValueError):
            imp = 1.0
        if imp <= float(spec):
            return "importance %.2f <= %.2f" % (imp, float(spec))
        return None
    return None


# --------------------------------------------------------------------------
# Rule
# --------------------------------------------------------------------------


@dataclass
class Rule:
    """A single filing rule: when its conditions match, file into ``category``.

    Higher ``priority`` wins. ``conditions`` maps condition-kind to spec::

        Rule("incidents", {"keywords": ["error", "crash"]}, "incidents", priority=10)
    """

    name: str
    conditions: Dict[str, Any] = field(default_factory=dict)
    category: str = "uncategorized"
    priority: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("agenda: rule name must be a non-empty string")
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("agenda: rule category must be a non-empty string")
        if not isinstance(self.conditions, dict) or not self.conditions:
            raise ValueError(
                "agenda: rule %r must have at least one condition" % self.name
            )
        unknown = [k for k in self.conditions if k not in _CONDITION_KINDS]
        if unknown:
            raise ValueError(
                "agenda: rule %r has unknown condition kind(s): %s (known: %s)"
                % (self.name, ", ".join(unknown), ", ".join(_CONDITION_KINDS))
            )
        # Validate regexes eagerly so bad rules fail at construction.
        if "regex" in self.conditions:
            patterns = self.conditions["regex"]
            patterns = patterns if isinstance(patterns, list) else [patterns]
            for p in patterns:
                try:
                    re.compile(str(p))
                except re.error as exc:
                    raise ValueError(
                        "agenda: rule %r has invalid regex %r: %s" % (self.name, p, exc)
                    ) from exc
        for key in ("min_importance", "max_importance"):
            if key in self.conditions:
                try:
                    float(self.conditions[key])
                except (TypeError, ValueError):
                    raise ValueError(
                        "agenda: rule %r condition %r must be a number"
                        % (self.name, key)
                    ) from None

    def matches(self, entry: Dict[str, Any]) -> List[str]:
        """Evaluate against an entry; return matched condition descriptions.

        Empty list means "no match". Never raises for malformed entries.
        """
        if not isinstance(entry, dict):
            return []
        matched: List[str] = []
        for kind, spec in self.conditions.items():
            try:
                desc = _check_condition(kind, spec, entry)
            except Exception:
                desc = None
            if desc:
                matched.append(desc)
        return matched

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "conditions": self.conditions,
            "category": self.category,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Rule":
        if not isinstance(data, dict):
            raise ValueError("agenda: rule record must be a dict")
        return cls(
            name=data.get("name", ""),
            conditions=data.get("conditions", {}),
            category=data.get("category", "uncategorized"),
            priority=int(data.get("priority", 0)),
        )


# --------------------------------------------------------------------------
# Explanation
# --------------------------------------------------------------------------


@dataclass
class Explanation:
    """Why an entry was filed where it was. Always human-readable."""

    category: str
    rule_name: Optional[str]  # None when fail-open fallback fired
    matched: List[str] = field(default_factory=list)
    candidates: List[str] = field(
        default_factory=list
    )  # other matching rules, by priority
    detail: str = ""

    def summary(self) -> str:
        if self.rule_name is None:
            return "filed as %r: %s" % (
                self.category,
                self.detail or "no rule matched (fail-open)",
            )
        base = "filed as %r by rule %r" % (self.category, self.rule_name)
        if self.matched:
            base += " (%s)" % "; ".join(self.matched)
        if self.candidates:
            base += "; also matched: %s" % ", ".join(self.candidates)
        return base

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "rule_name": self.rule_name,
            "matched": self.matched,
            "candidates": self.candidates,
            "detail": self.detail,
        }


# --------------------------------------------------------------------------
# RuleEngine
# --------------------------------------------------------------------------

_FALLBACK_CATEGORY = "uncategorized"


def default_rules() -> List[Rule]:
    """Sensible default rules for journal/memory ingestion.

    Ordered by priority (highest first): incidents beat everything because
    an error log that also says "thanks" is still an incident.
    """
    return [
        Rule(
            name="incidents",
            conditions={
                "keywords": [
                    "error",
                    "failure",
                    "crash",
                    "exception",
                    "traceback",
                    "bug",
                    "broken",
                    "panic",
                ]
            },
            category="incidents",
            priority=100,
        ),
        Rule(
            name="decisions",
            conditions={
                "keywords": [
                    "decided",
                    "decision",
                    "chose",
                    "will do",
                    "going with",
                    "settled on",
                ]
            },
            category="decisions",
            priority=80,
        ),
        Rule(
            name="learnings",
            conditions={
                "keywords": [
                    "learned",
                    "discovered",
                    "realized",
                    "til ",
                    "today i learned",
                    "insight",
                ]
            },
            category="learnings",
            priority=70,
        ),
        Rule(
            name="ideas",
            conditions={
                "keywords": [
                    "idea",
                    "someday",
                    "maybe we should",
                    "what if",
                    "brainstorm",
                ]
            },
            category="ideas",
            priority=60,
        ),
        Rule(
            name="gratitude",
            conditions={"keywords": ["thank", "grateful", "appreciate"]},
            category="gratitude",
            priority=50,
        ),
        Rule(
            name="tasks",
            conditions={"regex": [r"\btodo\b", r"action item", r"\bnext step\b"]},
            category="tasks",
            priority=40,
        ),
        Rule(
            name="important-memory",
            conditions={"min_importance": 0.8},
            category="highlights",
            priority=20,
        ),
        Rule(
            name="journal-entries",
            conditions={"tags": ["journal"]},
            category="journal",
            priority=10,
        ),
    ]


class RuleEngine:
    """In-memory rule engine with JSON persistence and an audit log.

    ``file_entry`` never raises for a malformed entry: worst case it
    returns ("uncategorized", explanation) and logs the fallback.
    """

    def __init__(
        self, rules: Optional[List[Rule]] = None, audit_path: Optional[Path] = None
    ):
        self._rules: Dict[str, Rule] = {}
        self._audit: List[Dict[str, Any]] = []
        self.audit_path = Path(audit_path) if audit_path else None
        for rule in rules if rules is not None else default_rules():
            self.add_rule(rule)

    # -- rule CRUD ---------------------------------------------------------
    def add_rule(self, rule: Rule) -> Rule:
        if not isinstance(rule, Rule):
            raise TypeError(
                "agenda: add_rule expects a Rule, got %r" % type(rule).__name__
            )
        if rule.name in self._rules:
            raise ValueError(
                "agenda: rule %r already exists (remove it first)" % rule.name
            )
        self._rules[rule.name] = rule
        return rule

    def remove_rule(self, name: str) -> Rule:
        try:
            return self._rules.pop(name)
        except KeyError:
            raise ValueError("agenda: no rule named %r" % name) from None

    def get_rule(self, name: str) -> Optional[Rule]:
        return self._rules.get(name)

    def list_rules(self) -> List[Rule]:
        return sorted(self._rules.values(), key=lambda r: (-r.priority, r.name))

    def update_rule(self, name: str, **changes: Any) -> Rule:
        old = self.get_rule(name)
        if old is None:
            raise ValueError("agenda: no rule named %r" % name)
        data = old.to_dict()
        data.update(changes)
        new = Rule.from_dict(data)
        self._rules[name] = new
        return new

    # -- filing ------------------------------------------------------------
    def file_entry(self, entry: Any) -> Tuple[str, Explanation]:
        """File an entry; returns (category, explanation). Never raises."""
        try:
            if not isinstance(entry, dict):
                category, expl = (
                    _FALLBACK_CATEGORY,
                    Explanation(
                        category=_FALLBACK_CATEGORY,
                        rule_name=None,
                        detail="entry is not a dict (%s); fail-open"
                        % type(entry).__name__,
                    ),
                )
            else:
                ranked: List[Tuple[Rule, List[str]]] = []
                for rule in self.list_rules():
                    try:
                        matched = rule.matches(entry)
                    except Exception:
                        matched = []
                    if matched:
                        ranked.append((rule, matched))
                if ranked:
                    winner, matched = ranked[0]
                    category = winner.category
                    expl = Explanation(
                        category=category,
                        rule_name=winner.name,
                        matched=matched,
                        candidates=[r.name for r, _ in ranked[1:]],
                        detail="priority %d" % winner.priority,
                    )
                else:
                    category, expl = (
                        _FALLBACK_CATEGORY,
                        Explanation(
                            category=_FALLBACK_CATEGORY,
                            rule_name=None,
                            detail="no rule matched; fail-open",
                        ),
                    )
        except Exception as exc:  # absolute last resort: still fail open
            category, expl = (
                _FALLBACK_CATEGORY,
                Explanation(
                    category=_FALLBACK_CATEGORY,
                    rule_name=None,
                    detail="engine error (%s); fail-open" % exc,
                ),
            )
        self._log_audit(entry, category, expl)
        return category, expl

    def explain(self, entry: Any) -> Explanation:
        """Return just the explanation for an entry (same machinery, no audit)."""
        category, expl = self._file_no_audit(entry)
        return expl

    def _file_no_audit(self, entry: Any) -> Tuple[str, Explanation]:
        # Shared core without the audit write, used by explain().
        ranked: List[Tuple[Rule, List[str]]] = []
        if isinstance(entry, dict):
            for rule in self.list_rules():
                matched = rule.matches(entry)
                if matched:
                    ranked.append((rule, matched))
        if ranked:
            winner, matched = ranked[0]
            return winner.category, Explanation(
                category=winner.category,
                rule_name=winner.name,
                matched=matched,
                candidates=[r.name for r, _ in ranked[1:]],
                detail="priority %d" % winner.priority,
            )
        return _FALLBACK_CATEGORY, Explanation(
            category=_FALLBACK_CATEGORY,
            rule_name=None,
            detail="no rule matched; fail-open",
        )

    # -- audit log ----------------------------------------------------------
    def _entry_preview(self, entry: Any) -> str:
        if isinstance(entry, dict):
            return _norm_text(entry.get("content"))[:120]
        return repr(entry)[:120]

    def _log_audit(self, entry: Any, category: str, expl: Explanation) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "category": category,
            "rule_name": expl.rule_name,
            "matched": expl.matched,
            "entry_preview": self._entry_preview(entry),
        }
        self._audit.append(record)
        if self.audit_path is not None:
            try:
                self.audit_path.parent.mkdir(parents=True, exist_ok=True)
                with self.audit_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError:
                pass  # audit write must never break filing

    def audit_log(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return the in-memory audit trail, newest last."""
        if limit is None:
            return list(self._audit)
        return list(self._audit[-limit:])

    # -- persistence ---------------------------------------------------------
    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {"rules": [r.to_dict() for r in self.list_rules()]},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, path: Path, audit_path: Optional[Path] = None) -> "RuleEngine":
        path = Path(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        rules = [Rule.from_dict(r) for r in raw.get("rules", [])]
        return cls(rules=rules, audit_path=audit_path)


__all__ = [
    "Rule",
    "Explanation",
    "RuleEngine",
    "default_rules",
]
