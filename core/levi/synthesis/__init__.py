"""Synthesis — the organism's mind and vital signs behind one front door.

PROPOSED NAME — Chauncey renames. ("unified" was already taken by the
Daemon Core unified cycle.)

Not another organ: the thing that answers (``mind.ask``) and the thing that
reports health (``status``), wired to the organs that already exist —
Alpha's deliberating Reasoner, the native-brain weights, the skill registry,
the L.W.P. press console, the growth loop, the paper-only finance broker,
the daemon kernel. Synthesis adds no duplicate organs.

Offline-first is structural here, not a flag: ``offline.py`` proves zero
network with ``OfflineGuard``, and the import closure of this package is
scanned by tests for network libraries.

Stdlib only at import time. Heavy modules (torch, the organs) load lazily
inside the functions that need them.
"""

ORIGIN = "levi-synthesis"

__all__ = ["ORIGIN"]
