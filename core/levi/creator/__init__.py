"""Creator platform — dating + digital creator services, two tracks.

SI track (:mod:`levi.creator.si`): adult dating + creator platform,
OnlyFans/Telegram-style (creator profiles, subscription tiers, sealed
messaging, content drops) plus a "skip the games"-style dating/classifieds
module. Sealed in the Veil lineage (tamper-evident, keeper-held keys,
airtight, encrypted, reinforced) and gated behind the Plaiground law:
adult-only, default OFF, minors hard-locked out.

AI track (:mod:`levi.creator.ai`): the same style modules reformed for
society and ethics — SFW, safe, society-approved dating and a
general-audience creator platform. Same functionality shape, clean rules.

The tracks never merge: separate stores, separate code paths, no
cross-track queries. Money on both tracks routes through the Cybrus money
gateway only, fail-closed.
"""

from __future__ import annotations

TRACK_SI = "si"
TRACK_AI = "ai"

__all__ = ["TRACK_SI", "TRACK_AI"]
