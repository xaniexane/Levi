"""Framebench — frames and rules on one inspectable bench.

Studied from: revival-50-more-20260916-0009/report-part1.md (sec 24).

The mechanism under study: an integrated workbench where frames
(classes, slots, inheritance, daemons, message passing) and rules live
together and can see each other. Frames carry the *what* — structured
objects with inherited slots, triggers that fire when a slot is written
(``if_added``) or demanded (``if_needed``), and message passing between
frames. Rules carry the *why* — both forward-chaining (data-driven) and
backward-chaining (goal-driven) over one shared fact base. ``explain()``
shows the derivation of any slot value or fact: own, inherited, daemon,
or rule-fired with premises named.

Original, from-scratch implementation for LEVI. Slots hold plain Python
values; methods are slots holding callables. stdlib-only, no network,
deterministic.

Public surface:
- ``Workbench`` — ``frame(name, parents=...)``, ``set_slot``,
  ``get_slot``, ``add_daemon(frame, slot, kind, fn)``,
  ``def_method(frame, name, fn)``, ``send(frame, message, *args)``,
  ``add_rule(name, body, head, direction)``, ``assert_fact``,
  ``forward()``, ``prove(goal)``, ``explain(...)``, ``inspect()``.
- Directions: ``"forward"``, ``"backward"``, or ``"both"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

ORIGIN = "levi-revival/framebench"

Fact = Tuple[Any, ...]


def _is_var(x: Any) -> bool:
    return isinstance(x, str) and x.startswith("?")


def _unify(
    pattern: Fact, fact: Fact, bindings: Optional[Dict[str, Any]] = None
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


def _subst(pattern: Fact, bindings: Dict[str, Any]) -> Fact:
    return tuple(bindings.get(p, p) if _is_var(p) else p for p in pattern)


@dataclass
class Frame:
    name: str
    parents: Tuple[str, ...] = ()
    slots: Dict[str, Any] = field(default_factory=dict)
    daemons: Dict[str, List[Tuple[str, Callable]]] = field(default_factory=dict)


@dataclass
class BenchRule:
    name: str
    body: Tuple[Fact, ...]
    head: Fact
    direction: str  # "forward" | "backward" | "both"


class Workbench:
    """One bench: frames, daemons, messages, and rules together."""

    def __init__(self) -> None:
        self.frames: Dict[str, Frame] = {}
        self.rules: List[BenchRule] = []
        self.facts: Set[Fact] = set()
        self._provenance: Dict[Any, List[str]] = {}  # (frame,slot) or fact -> lines

    # ------------------------------------------------------------------
    # frames
    # ------------------------------------------------------------------
    def frame(self, name: str, parents: Tuple[str, ...] = ()) -> Frame:
        fr = self.frames.get(name)
        if fr is None:
            fr = Frame(name, parents)
            self.frames[name] = fr
        else:
            fr.parents = parents or fr.parents
        return fr

    def _lineage(self, name: str) -> List[Frame]:
        """Depth-first, left-to-right inheritance walk."""
        out: List[Frame] = []
        seen: Set[str] = set()

        def walk(n: str) -> None:
            if n in seen or n not in self.frames:
                return
            seen.add(n)
            fr = self.frames[n]
            out.append(fr)
            for p in fr.parents:
                walk(p)

        walk(name)
        return out

    def set_slot(
        self, frame_name: str, slot: str, value: Any, source: str = "told"
    ) -> None:
        fr = self.frames[frame_name]
        fr.slots[slot] = value
        self._provenance[(frame_name, slot)] = [f"set directly ({source})"]
        for kind, fn in fr.daemons.get(slot, []):
            if kind == "if_added":
                note = fn(fr, slot, value)
                self._provenance[(frame_name, slot)].append(
                    f"if_added daemon ran{f': {note}' if note else ''}"
                )

    def get_slot(self, frame_name: str, slot: str) -> Any:
        """Own slot → inherited slot → if_needed daemon → KeyError."""
        for fr in self._lineage(frame_name):
            if slot in fr.slots:
                if fr.name != frame_name:
                    self._provenance.setdefault(
                        (frame_name, slot), [f"inherited from {fr.name}"]
                    )
                return fr.slots[slot]
        for fr in self._lineage(frame_name):
            for kind, fn in fr.daemons.get(slot, []):
                if kind == "if_needed":
                    value = fn(fr, slot)
                    fr.slots[slot] = value  # cache the computation
                    self._provenance[(frame_name, slot)] = [
                        f"computed by if_needed daemon on {fr.name}"
                    ]
                    return value
        raise KeyError(f"no slot {slot!r} on {frame_name} or its ancestors")

    def add_daemon(self, frame_name: str, slot: str, kind: str, fn: Callable) -> None:
        assert kind in ("if_added", "if_needed"), "kind must be if_added/if_needed"
        self.frames[frame_name].daemons.setdefault(slot, []).append((kind, fn))

    # ------------------------------------------------------------------
    # message passing
    # ------------------------------------------------------------------
    def def_method(self, frame_name: str, method: str, fn: Callable) -> None:
        self.frames[frame_name].slots[method] = fn

    def send(self, frame_name: str, message: str, *args: Any) -> Any:
        """Find ``message`` as a method slot through inheritance and call it."""
        for fr in self._lineage(frame_name):
            fn = fr.slots.get(message)
            if callable(fn):
                return fn(fr, *args)
        raise KeyError(f"{frame_name} does not answer {message!r}")

    # ------------------------------------------------------------------
    # rules — forward and backward over one fact base
    # ------------------------------------------------------------------
    def add_rule(
        self, name: str, body: Tuple[Fact, ...], head: Fact, direction: str = "both"
    ) -> BenchRule:
        assert direction in ("forward", "backward", "both")
        rule = BenchRule(name, tuple(body), tuple(head), direction)
        self.rules.append(rule)
        return rule

    def assert_fact(self, fact: Fact, source: str = "told") -> None:
        fact = tuple(fact)
        if fact not in self.facts:
            self.facts.add(fact)
            self._provenance[fact] = [f"asserted ({source})"]

    def forward(self, max_rounds: int = 20) -> Set[Fact]:
        """Data-driven: fire forward/both rules to a fixpoint."""
        derived: Set[Fact] = set()
        for _ in range(max_rounds):
            grown = False
            for rule in self.rules:
                if rule.direction not in ("forward", "both"):
                    continue
                # snapshot: matching iterates the fact set lazily while
                # the loop below adds to it — never iterate the live set
                for bindings in self._match_body(rule.body, set(self.facts)):
                    fact = _subst(rule.head, bindings)
                    if fact not in self.facts:
                        self.facts.add(fact)
                        prem = ", ".join(
                            map(str, (_subst(b, bindings) for b in rule.body))
                        )
                        self._provenance[fact] = [
                            f"forward rule {rule.name} from {prem}"
                        ]
                        derived.add(fact)
                        grown = True
            if not grown:
                break
        return derived

    def _match_body(self, body: Tuple[Fact, ...], facts: Set[Fact]):
        if not body:
            yield {}
            return
        first, rest = body[0], body[1:]
        for fact in facts:
            b = _unify(first, fact)
            if b is None:
                continue
            for tail in self._match_body(tuple(_subst(p, b) for p in rest), facts):
                merged = dict(b)
                merged.update(tail)
                yield merged

    def prove(
        self, goal: Fact, depth: int = 12, seen: Optional[Set[Fact]] = None
    ) -> Optional[List[str]]:
        """Goal-driven: backward/both rules, returns derivation lines."""
        seen = seen or set()
        goal = tuple(goal)
        if depth <= 0 or goal in seen:
            return None
        for fact in self.facts:
            if _unify(goal, fact) is not None:
                return [
                    f"{goal} holds: {'; '.join(self._provenance.get(fact, ['given']))}"
                ]
        for rule in self.rules:
            if rule.direction not in ("backward", "both"):
                continue
            bindings = _unify(rule.head, goal)
            if bindings is None:
                continue
            lines: List[str] = []
            ok = True
            for b in rule.body:
                sub = _subst(b, bindings)
                child = self.prove(sub, depth - 1, seen | {goal})
                if child is None:
                    ok = False
                    break
                lines.extend(child)
            if ok:
                self.facts.add(_subst(rule.head, bindings))
                return lines + [f"{goal} via backward rule {rule.name}"]
        return None

    # ------------------------------------------------------------------
    # inspection
    # ------------------------------------------------------------------
    def explain(self, target: Any) -> List[str]:
        """Derivation of a slot ``(frame, slot)`` or a fact tuple."""
        lines = self._provenance.get(target)
        if lines:
            return [f"{target}:"] + [f"  - {ln}" for ln in lines]
        return [f"{target}: no recorded derivation"]

    def explain_slot(self, frame_name: str, slot: str) -> List[str]:
        try:
            value = self.get_slot(frame_name, slot)
        except KeyError as e:
            return [str(e)]
        lines = [f"{frame_name}.{slot} = {value!r}"]
        lines.extend(self.explain((frame_name, slot))[1:])
        return lines

    def inspect(self) -> str:
        fr = ", ".join(sorted(self.frames)) or "none"
        rl = ", ".join(r.name for r in self.rules) or "none"
        return f"workbench: frames[{fr}] rules[{rl}] facts[{len(self.facts)}]"
