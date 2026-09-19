"""LEVI's alloyed knowledge shell: rules, frames, and procedural attachments
in one reasoning engine — knowledge-representation pluralism.

Studied from: revival-50-more-20260916-0009/report-part2.md (§26)
(functional description only; no historical claims).

The lesson, reborn as LEVI's own: don't pick one representation. Facts
live as *frames* (named objects with slots). *Rules* reason over those
slots. *Procedural attachments* hang off the slots themselves —
``if_needed`` computes a slot's value on read, ``if_added`` reacts when a
slot is written. A forward-chaining driver runs all three together until
the knowledge base reaches a fixed point.

Honesty: LOAD-BEARING. The chainer is naive but sound — it re-scans the
rule set until a full pass fires nothing, and a rule re-fires only after
a genuine state change (writes that change nothing don't count, so
self-sustaining rules can't loop forever). Procedural attachments are
plain Python callables; there is no truth-maintenance or retraction.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

ORIGIN = "levi-revival/alloy"


# ---------------------------------------------------------------------------
# Frames — facts as named objects with slots
# ---------------------------------------------------------------------------


class Frame:
    """A named fact-bundle. Slots hold data; a slot may carry an
    ``if_needed`` thunk (compute-on-read) and/or an ``if_added`` hook
    (react-on-write)."""

    def __init__(
        self,
        name: str,
        slots: Optional[Dict[str, Any]] = None,
        parent: Optional["Frame"] = None,
    ) -> None:
        self.name = name
        self.slots: Dict[str, Any] = dict(slots or {})
        self.parent = parent
        self._if_needed: Dict[str, Callable[["AlloyKB", "Frame"], Any]] = {}
        self._if_added: Dict[str, Callable[["AlloyKB", "Frame", Any], None]] = {}

    # -- procedural attachments -------------------------------------------
    def attach_needed(
        self, slot: str, thunk: Callable[["AlloyKB", "Frame"], Any]
    ) -> "Frame":
        """if_needed: compute this slot's value lazily when it is read."""
        self._if_needed[slot] = thunk
        return self

    def attach_added(
        self, slot: str, hook: Callable[["AlloyKB", "Frame", Any], None]
    ) -> "Frame":
        """if_added: react whenever this slot is written."""
        self._if_added[slot] = hook
        return self

    # -- slot access -------------------------------------------------------
    def read(self, slot: str, kb: Optional["AlloyKB"] = None) -> Any:
        """Read a slot, walking the parent chain; fires if_needed on miss."""
        frame: Optional[Frame] = self
        while frame is not None:
            if slot in frame.slots:
                return frame.slots[slot]
            if slot in frame._if_needed and kb is not None:
                value = frame._if_needed[slot](kb, self)
                frame.slots[slot] = value  # cache the computed value
                return value
            frame = frame.parent
        return None

    def write(self, slot: str, value: Any, kb: Optional["AlloyKB"] = None) -> bool:
        """Write a slot; fires if_added. Returns True iff the value changed."""
        old = self.slots.get(slot, _MISSING)
        if old is not _MISSING and old == value:
            return False
        self.slots[slot] = value
        if slot in self._if_added and kb is not None:
            self._if_added[slot](kb, self, value)
        return True


_MISSING = object()


# ---------------------------------------------------------------------------
# Rules — condition/action pairs over frame slots
# ---------------------------------------------------------------------------


class Rule:
    """A forward-chaining rule: ``when(kb)`` tests the world, ``then(kb)``
    acts on it and reports whether anything changed."""

    def __init__(
        self,
        name: str,
        when: Callable[["AlloyKB"], bool],
        then: Callable[["AlloyKB"], bool],
    ) -> None:
        self.name = name
        self.when = when
        self.then = then

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Rule({self.name!r})"


# ---------------------------------------------------------------------------
# The alloy shell — one driver for all three representations
# ---------------------------------------------------------------------------


class AlloyKB:
    """One shell holding frames, rules, and procedural attachments."""

    def __init__(self) -> None:
        self.frames: Dict[str, Frame] = {}
        self.rules: List[Rule] = []
        self.fired: List[str] = []  # rule names, in firing order

    def frame(self, frame_name: str, **slots: Any) -> Frame:
        f = Frame(frame_name, slots)
        self.frames[frame_name] = f
        return f

    def rule(self, name: str, when, then) -> Rule:
        r = Rule(name, when, then)
        self.rules.append(r)
        return r

    def run(self, max_passes: int = 1000) -> List[str]:
        """Forward-chain to a fixed point. Only firings that change the
        world are recorded; a rule whose action is a no-op settles until
        some other rule changes the world. A rule fires at most once per
        pass, so self-rearming rules converge pass by pass."""
        settled: set = set()  # fired with no effect: skipped until change
        for _ in range(max_passes):
            fired_this_pass: set = set()
            progress = False
            for rule in self.rules:
                if rule.name in fired_this_pass or rule.name in settled:
                    continue
                if rule.when(self):
                    if rule.then(self):
                        self.fired.append(rule.name)
                        fired_this_pass.add(rule.name)
                        settled = set()  # new facts may re-arm settled rules
                        progress = True
                    else:
                        settled.add(rule.name)
            if not progress:
                break
        else:  # pragma: no cover - safety valve
            raise RuntimeError("alloy: forward chaining did not converge")
        return list(self.fired)


# ---------------------------------------------------------------------------
# Helpers for building readable rules
# ---------------------------------------------------------------------------


def slot_is(frame: str, slot: str, value: Any):
    """Condition factory: frame's slot equals value."""

    def _when(kb: AlloyKB) -> bool:
        f = kb.frames.get(frame)
        return f is not None and f.read(slot, kb) == value

    return _when


def set_slot(frame: str, slot: str, value: Any):
    """Action factory: write value into frame's slot (reports change)."""

    def _then(kb: AlloyKB) -> bool:
        f = kb.frames.get(frame)
        if f is None:  # pragma: no cover - defensive
            return False
        return f.write(slot, value, kb)

    return _then


# ---------------------------------------------------------------------------
# Demo — a small server-health reasoner using all three representations
# ---------------------------------------------------------------------------


def demo() -> AlloyKB:
    kb = AlloyKB()

    srv = kb.frame("server", name="levi-node-1")
    kb.frame("cpu", load=0.93)
    mem = kb.frame("mem", used_gb=14.8, total_gb=16.0)

    # if_needed: derived slots computed lazily on read
    mem.attach_needed(
        "pressure",
        lambda kb, f: f.read("used_gb", kb) / f.read("total_gb", kb),
    )
    srv.attach_needed(
        "summary",
        lambda kb, f: (
            f"load={kb.frames['cpu'].read('load', kb):.2f} "
            f"mem_pressure={kb.frames['mem'].read('pressure', kb):.2f} "
            f"alert={f.read('alert', kb)}"
        ),
    )

    # if_added: procedural reaction to a write
    notes: List[str] = []
    srv.attach_added("alert", lambda kb, f, v: notes.append(f"ALERT: {v}"))
    kb.notes = notes  # type: ignore[attr-defined]

    # rules over slots
    kb.rule(
        "thrashing",
        lambda kb: (
            (kb.frames["cpu"].read("load", kb) or 0) > 0.9
            and (kb.frames["mem"].read("pressure", kb) or 0) > 0.9
        ),
        set_slot("server", "alert", "thrashing"),
    )
    kb.rule(
        "page-ops",
        slot_is("server", "alert", "thrashing"),
        set_slot("server", "escalate", "page-ops"),
    )

    kb.run()
    return kb


if __name__ == "__main__":  # pragma: no cover - demo
    kb = demo()
    print(kb.frames["server"].read("summary", kb))
    print("fired:", kb.fired)
    print("notes:", kb.notes)
