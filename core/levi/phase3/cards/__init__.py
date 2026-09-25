"""Memory cards (A6 salvage: HyperCard's stack metaphor, modernized).
WORKING TITLE — naming is Chauncey's, never canon.

Cards are auto-maintained, human-facing *views* over memory — never a
second store. The SI pays HyperCard's authoring labor at machine speed:
cards are derived, linked, and re-linked mechanically as the corpus
changes.

- :mod:`.types`   — Card / Fact / Decision / the read-only
  ``MemoryView`` protocol + the local ``DictMemoryView`` stub.
- :mod:`.derive`  — pure ``derive()``: same memory state -> same card.
  Card bodies are deterministic template renders; generative polish may
  layer on top later, but the template render is the card's truth.
- :mod:`.sync`    — ``CardStore.sync_cycle()``: re-derive and re-resolve
  links (housekeeping step only, never mid-task).
- :mod:`.index`   — term index + hop-bounded reachability.
- :mod:`.render`  — cards as readable plain-speech text.

Laws: stdlib-only at import; zero network at runtime; deterministic;
no sentience or subjective-experience claims (a card is an index entry,
not a memory of being).
"""

from .derive import derive, derive_decision, summarize
from .index import CardIndex
from .render import render
from .sync import CardStore
from .types import RELATIONS, Card, Decision, DictMemoryView, Fact, Link, MemoryView

__all__ = [
    "RELATIONS",
    "Card",
    "CardIndex",
    "CardStore",
    "Decision",
    "DictMemoryView",
    "Fact",
    "Link",
    "MemoryView",
    "derive",
    "derive_decision",
    "render",
    "summarize",
]
