"""streetpass — stranger-powered presence, no servers attached.

The 3DS StreetPass (2011-2019) had exactly one load-bearing idea: your
solo games were powered by people you walked past. Miis queued up in
sleep mode — no pairing, no accounts, no cloud round-trip — and Find Mii
turned strangers into a party. Nintendo then routed the amplification
through its own relay stations, so when the servers died, the mechanic
died with them.

This module is the honest inversion: local-first proximity presence for
LEVI daemons on a LAN.

- UDP broadcast beacons on the local network only — nothing ever leaves
  the machine for the internet, and there is no relay server to kill.
- Presence tokens are HMAC-signed with a key from the keeper's own
  keyring. Unsigned or foreign-signed beacons are refused (deny-closed).
- Opt-in tags only: a beacon carries exactly what the keeper typed —
  a display name and a list of interest tags. Nothing is observed.
- Encounters are ephemeral: neighbors expire after their TTL; no
  location history, no journal of where anyone has been.

Laws (declared here, proven in tests/test_streetpass.py):
1. Opt-in only — nothing beacons unless the keeper enables it; the
   payload holds only declared fields.
2. Local only — beacons go to a broadcast target; no internet, no
   relay, no accounts.
3. Signed presence — only HMAC-verified beacons join the neighbor set;
   anything else is dropped silently.
4. Ephemeral — neighbors expire past their TTL; expiry sweeps them out.
5. Declared identity only — unknown token fields are ignored, never
   trusted or stored.
"""

from __future__ import annotations

__all__ = ["HOME_DIRNAME", "StreetPassError", "PresenceToken"]

HOME_DIRNAME = "streetpass"


class StreetPassError(Exception):
    """Deny-closed errors: misconfiguration, bad tokens, expired state."""


class PresenceToken:
    """A signed presence announcement: name + tags + issued + ttl.

    Wire form is JSON + '.' + hex HMAC-SHA256 over the JSON bytes.
    """

    __slots__ = ("name", "tags", "issued", "ttl")

    def __init__(self, name: str, tags: tuple, issued: float, ttl: float):
        self.name = name
        self.tags = tags
        self.issued = issued
        self.ttl = ttl
