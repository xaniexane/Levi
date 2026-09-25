"""Tag-team teacher loop: the closed training circuit for LEVI's native brain.

Protocol (Chauncey's word, 2026-09-21):

1. Teachers (KAI-9000, Qwen, DeepSeek, Mistral, Kimi, Grok, Claude, Gemini,
   Rex) generate training batches — Q&A pairs, reasoning traces,
   corrections. Teacher material arrives as local file drops (JSONL);
   the loop makes NO network calls, ever.
2. ONLY LEVI's trainer updates LEVI's weights. This is structural, not
   a promise: the train stage invokes LEVI's own ``continue.py`` and the
   drop validator rejects any weight file (``.pt``/``.bin``/``.safetensors``/
   ``.ckpt``) outright. Teachers supply text, never weights.
3. Fixed-prompt eval scores each round (``prompts.py`` — kept OUT of
   training by an explicit guard); weaknesses become targeted generation
   requests back to the teachers (``requests.py``).
4. Repeat. Teachers rotate round-robin; no permanent authority;
   disagreements are preserved (each gap goes to 2+ teachers);
   intake stays filtered and honesty-checked.

New code lives here; existing pieces are reused read-only:
- ``levi.brain.train.teacher_intake`` — curator seat (normalization,
  identity-law spot checks, stable IDs, provenance, dedupe).
- ``levi.brain.train.teacher_pipeline`` — cross-round dedupe, teacher
  balancing, held-out split.
- ``levi.brain.train.eval`` — held-out loss + sample generation (torch).

Offline-first, stdlib only, CPU-runnable. All stages are injectable so
tests run hermetic without torch.

CLI: ``python -m levi.brain.tagteam run --round 1 --drops drops/ ...``
"""

from __future__ import annotations

from levi.brain.tagteam import ledger, loop, personas, prompts, requests, roster
from levi.brain.tagteam.personas import operator_seats

__all__ = [
    "ledger",
    "loop",
    "personas",
    "prompts",
    "requests",
    "roster",
    "operator_seats",
]
