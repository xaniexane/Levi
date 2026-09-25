"""Interpenetration adapters — one connection per module, pure functions.

Each adapter wires two (or more) LEVI modules together without editing
either of them. Every adapter:

- imports the connected modules **lazily** (inside the function),
- degrades **honestly** when a module is unavailable (explicit
  "unavailable" results, never invented data),
- performs no side effects beyond what its contract states.
"""

from __future__ import annotations
