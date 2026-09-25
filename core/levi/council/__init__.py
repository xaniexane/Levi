"""LEVI Council — LEVI's own minds arguing to get stronger.

"Not artificial. Synthetic." Three LEVI-native minds sit at the table —
no network, no keys, no other companies' agents inside:

* ``native-brain`` — LEVI's own trained brain
  (``levi.agent.brain_provider``). Generates by sampling the brain;
  skips gracefully when torch or the trained weights are unavailable.
  The brain is young; the gates judge it like everyone else.
* ``rules-engine`` — the deterministic symbolic mind. It cannot invent
  algorithms and says so honestly: it generates an API-complete scaffold
  derived from the tests, and its strength is assessment — deterministic
  security/error-handling scans plus heuristic review.
* ``specialists`` — LEVI's specialist personas
  (``levi.agent.specialists``), voiced by the native brain. The
  ``coding`` specialist drafts; a panel (coding, verification,
  security) reviews. Skips gracefully when the brain is unavailable —
  a persona with no voice stays silent.

Pipeline: task brief → each mind generates → static gates → sandboxed
test execution (test results outrank opinions) → property checks →
mutation sample → peer review between the minds → synthesize winner →
receipt naming which mind wrote what, with test evidence.

Honesty rules (binding): every contribution is labeled with the mind
that wrote it; unavailable minds skip with a note, never an error;
nothing leaves the machine.
"""

from .minds import (
    NativeBrainMind,
    RulesEngineMind,
    SpecialistsMind,
    brain_available,
    mind_for,
    synthesize_scaffold,
)
from .orchestrator import run_council
from .seats import ALL_SEATS, Seat, detect_seats
from .techniques import (
    mutation_sample,
    parse_checklist,
    run_properties,
    static_gates,
    test_first_check,
)

__all__ = [
    "ALL_SEATS",
    "NativeBrainMind",
    "RulesEngineMind",
    "Seat",
    "SpecialistsMind",
    "brain_available",
    "detect_seats",
    "mind_for",
    "mutation_sample",
    "parse_checklist",
    "run_council",
    "run_properties",
    "static_gates",
    "synthesize_scaffold",
    "test_first_check",
]
