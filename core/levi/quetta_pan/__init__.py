"""Quetta-Pan rebuilt — possibility-space traversal with the REIM/RIEM loop wired in.

Canon (Chauncey's words):
- REIM = Recursion Echo Inverse Mapping — failure-compost intelligence.
  A failed mutation is inverse-mapped back through Echo into compost:
  a structured failure lesson (what was tried, why it failed).
- RIEM = Recursion Inverse Echo Mapping — dream-compression intelligence.
  Composted lessons are mapped forward into the genome: persistent
  learned patterns that steer future projections.
- Quetta-Pan = possibility-space traversal. The signature formula
  (LEXICON.md:709-710): Quetta runs "through Echo, REIM, RIEM, Mandella,
  variating combos without end." REIM/RIEM are canon peers in the
  unattempted-intelligence pool (LEXICON.md:783-785).

The v10.0 original (drive-sweep, read-only, untouched) contained ZERO
REIM/RIEM references. This module closes that honest gap: the loop is
now code, not just canon intent.

LOOP INVARIANTS (law -> guard -> prove; each has a test):
1. No write without backup. Every mutation writes a timestamped ``.bak``
   of the pre-image before touching the file.
2. No projection applied without evaluation. Every applied mutation is
   evaluated (parse check, heuristic delta, optional test command).
   A parse failure triggers automatic rollback to the backup.
3. Failures always composted, never dropped silently. Every failed
   evaluation appends a REIM compost entry (tried-what, failed-why,
   inverse lesson).
4. Genome consulted before generation. Suggestions check the RIEM genome
   first; rules with a recorded failure pattern in this context are
   suppressed with a stated reason, successes are boosted.
5. Dry-run default. Nothing is written unless ``--apply`` plus explicit
   per-file approval.
6. Fail-closed. Any guard error aborts the mutation, restores the
   pre-image from backup, and composts the attempt.
7. agent-pi fan-out/fan-in. One job fans out into parallel variant
   proposals (one agent x pi); failures compost to REIM, wins compress
   into the RIEM genome without collapse, every proposal is receipted,
   and the pass itself never writes the target file.

stdlib-only, like the original.
"""

from .agent_pi import (
    AGENT_PI,
    PI_FANOUT_CAP,
    PiDisposition,
    PiProposal,
    PiReceipt,
    agent_pi_pass,
    fan_in,
    fan_out,
    run_pi,
)
from .brain import QuettaPanDaVinci
from .engine import QuettaPanEngine
from .evaluate import MutationResult, evaluate_mutation
from .reim import ReimCompost, derive_inverse_lesson
from .riem import RiemGenome, context_key_for

__all__ = [
    "AGENT_PI",
    "PI_FANOUT_CAP",
    "PiDisposition",
    "PiProposal",
    "PiReceipt",
    "QuettaPanDaVinci",
    "QuettaPanEngine",
    "MutationResult",
    "agent_pi_pass",
    "evaluate_mutation",
    "fan_in",
    "fan_out",
    "run_pi",
    "ReimCompost",
    "derive_inverse_lesson",
    "RiemGenome",
    "context_key_for",
]
