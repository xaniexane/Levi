"""LEVI's token-budget accountant: the scarcity lesson, operationalized.

Studied from: ai-si-software-internals-20260916-0005/report.md (section 2.3)

contextpack.py answers "fit this pile into a budget, once." This answers
the live question: an agent loop spends tokens step after step — per
session, per component (planner, retriever, reflector, tool runner) — and
someone has to keep the books. The ``TokenLedger`` is that bookkeeper:

- tracks spend per (session, component) against per-component caps and a
  per-session ceiling;
- enforces caps with graceful degradation: when content won't fit, it
  summarizes instead of truncating — a shape-preserving fallback, never a
  silent chop;
- emits a spend receipt: where the tokens went, what degraded, what was
  refused, and how much headroom remains.

This is LEVI's own twist on "context tokens are the scarce resource":
not a better compressor, but the discipline of a wallet. Estimates use
the same honest word-count heuristic as contextpack (not a tokenizer).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .contextpack import estimate_tokens, extractive_summary

ORIGIN = "levi-revival/tokbudget"


@dataclass
class Cap:
    """A spending limit and how to behave when it's hit."""

    limit: int
    # 'summarize': shrink content to fit; 'refuse': block the spend.
    on_exceed: str = "summarize"

    def __post_init__(self) -> None:
        if self.on_exceed not in ("summarize", "refuse"):
            raise ValueError("on_exceed must be 'summarize' or 'refuse'")


@dataclass
class SpendEvent:
    session: str
    component: str
    tokens: int
    note: str = ""
    degraded: bool = False


@dataclass
class _SessionBooks:
    component_caps: Dict[str, Cap]
    session_cap: Optional[Cap]
    spent: Dict[str, int] = field(default_factory=dict)
    events: List[SpendEvent] = field(default_factory=list)
    degradations: int = 0
    refusals: int = 0


class TokenLedger:
    """Per-session token accounting with graceful-degradation enforcement."""

    def __init__(self) -> None:
        self._books: Dict[str, _SessionBooks] = {}

    def open_session(
        self,
        session: str,
        component_caps: Optional[Dict[str, Cap]] = None,
        session_cap: Optional[Cap] = None,
    ) -> None:
        """Register a session and its limits. Re-opening resets the books."""
        self._books[session] = _SessionBooks(
            component_caps=dict(component_caps or {}),
            session_cap=session_cap,
        )

    def _require(self, session: str) -> _SessionBooks:
        try:
            return self._books[session]
        except KeyError:
            raise KeyError(
                f"unknown session: {session!r} (open_session first)"
            ) from None

    def spent(self, session: str, component: str) -> int:
        return self._require(session).spent.get(component, 0)

    def session_spent(self, session: str) -> int:
        return sum(self._require(session).spent.values())

    def headroom(self, session: str, component: str) -> Optional[int]:
        """Tokens left for a component before its cap bites; None = uncapped."""
        books = self._require(session)
        cap = books.component_caps.get(component)
        if cap is None:
            return None
        return max(0, cap.limit - books.spent.get(component, 0))

    def check(self, session: str, component: str, needed: int) -> Tuple[bool, str]:
        """Would ``needed`` tokens fit under the component and session caps?"""
        books = self._require(session)
        comp_cap = books.component_caps.get(component)
        if (
            comp_cap is not None
            and books.spent.get(component, 0) + needed > comp_cap.limit
        ):
            return False, (
                f"component cap: {books.spent.get(component, 0)}+{needed} "
                f"> {comp_cap.limit}"
            )
        if (
            books.session_cap is not None
            and self.session_spent(session) + needed > books.session_cap.limit
        ):
            return False, (
                f"session cap: {self.session_spent(session)}+{needed} "
                f"> {books.session_cap.limit}"
            )
        return True, "fits"

    def spend(
        self,
        session: str,
        component: str,
        tokens: int,
        note: str = "",
        degraded: bool = False,
    ) -> bool:
        """Record a spend. Returns False (and records a refusal) if capped."""
        books = self._require(session)
        ok, _ = self.check(session, component, tokens)
        if not ok:
            books.refusals += 1
            books.events.append(SpendEvent(session, component, 0, f"REFUSED: {note}"))
            return False
        books.spent[component] = books.spent.get(component, 0) + tokens
        if degraded:
            books.degradations += 1
        books.events.append(SpendEvent(session, component, tokens, note, degraded))
        return True

    def fit(
        self,
        session: str,
        component: str,
        text: str,
        note: str = "",
    ) -> Tuple[bool, str, bool]:
        """Spend text against the budget, degrading gracefully.

        Returns (accepted, content_to_use, was_degraded). If the text fits,
        it is recorded as-is. If it doesn't and the component cap allows
        summarizing, an extractive summary sized to the remaining headroom
        is recorded instead. If the cap says refuse, the spend is refused
        and the original text is returned untouched (caller decides).
        """
        books = self._require(session)
        cost = estimate_tokens(text)
        if self.spend(session, component, cost, note):
            return True, text, False
        cap = books.component_caps.get(component)
        if cap is not None and cap.on_exceed == "summarize":
            room = self.headroom(session, component) or 0
            summary = extractive_summary(text, room) if room > 0 else ""
            if summary:
                scost = estimate_tokens(summary)
                accepted = self.spend(
                    session, component, scost, note + " [summarized]", degraded=True
                )
                if accepted:
                    return True, summary, True
        # Refused: don't touch the caller's text, don't pretend we spent.
        return False, text, False

    def receipt(self, session: str) -> str:
        """The spend receipt: where the tokens went, what bent, what broke."""
        books = self._require(session)
        total = self.session_spent(session)
        lines = [f"token receipt — session {session!r}: {total} tok total"]
        for comp in sorted(books.spent):
            spent = books.spent[comp]
            cap = books.component_caps.get(comp)
            cap_s = f"/{cap.limit}" if cap else "/uncapped"
            lines.append(f"  {comp}: {spent}{cap_s} tok")
        if books.session_cap is not None:
            lines.append(f"  session ceiling: {total}/{books.session_cap.limit} tok")
        lines.append(
            f"  degradations: {books.degradations}, refusals: {books.refusals}, "
            f"events: {len(books.events)}"
        )
        return "\n".join(lines)

    def events(self, session: str) -> List[SpendEvent]:
        return list(self._require(session).events)


def demo() -> str:
    ledger = TokenLedger()
    ledger.open_session(
        "morning-brief",
        component_caps={
            "retriever": Cap(limit=120),
            "planner": Cap(limit=200),
            "reflector": Cap(limit=60, on_exceed="refuse"),
        },
        session_cap=Cap(limit=400),
    )
    long_doc = (
        "The garden needs watering every morning before the sun climbs high. "
        "Roses drink deeply but hate wet leaves at dusk. Tomatoes want steady "
        "moisture and mulch to keep their feet cool. Herbs prefer to dry out "
        "between drinks, especially the rosemary. Compost feeds everything "
        "slowly, which is the whole point of compost."
    )
    ok1, used1, deg1 = ledger.fit(
        "morning-brief", "retriever", long_doc, "garden notes"
    )
    ledger.spend("morning-brief", "planner", 80, "plan the day")
    ok2 = ledger.spend("morning-brief", "reflector", 100, "long reflection")
    lines = [
        f"retriever fit: accepted={ok1} degraded={deg1} "
        f"({estimate_tokens(used1)} tok used)",
        f"reflector 100-tok spend: accepted={ok2} (cap refuses)",
        ledger.receipt("morning-brief"),
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(demo())
