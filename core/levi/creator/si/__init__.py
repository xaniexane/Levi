"""SI track — adult dating + creator platform, gated and sealed.

Every public function in this package calls
:func:`levi.plaiground.gate.require_adult` first: adult-only, default OFF,
minors hard-locked out. User-supplied text passes the Plaiground bounds
check. Records are sealed (Veil lineage) at rest.

No explicit content ships in this code — the unfiltered stance is in
voice (no moralizing, no sanitizing adult topics), not in law. Content is
user-driven at runtime, inside the bounds.
"""

from __future__ import annotations

__all__: list = []
