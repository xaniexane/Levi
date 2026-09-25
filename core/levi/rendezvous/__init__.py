"""Rendezvous — declared intents, not surveillance (Dodgeball's idea, done right).

Dodgeball (2000-2009) had exactly one load-bearing idea: intent-based
presence. The social act was the *declaration* — "I'm at the Ginger Man" —
sent as an SMS you chose to write; friends of friends got told, and people
showed up. Google bought it in 2005, starved it ("incredibly frustrating,"
per founder Dennis Crowley), killed it in 2009 for Google Latitude, and the
industry kept location-as-surveillance (check-in data, location history)
while dropping location-as-rendezvous.

LEVI has no advertisers, no location history product, and no reason to
track anyone, so the rendezvous can stay honest:

- An intent is a declared message: who / where / when / note. There is no
  GPS, no background anything — the module has no network code at all.
- Joining is opt-in: an RSVP is explicit per person. Being *invited* is not
  attending; nobody is ever added by someone else.
- Intents expire: past the end time, no new RSVPs. Expired and cancelled
  intents stay listed — nothing is thrown away.
- Owner-only local store (dir 0700, file 0600). Handing an intent to
  someone uses the community export path or the telegraph office, like the
  circles module — this module never transmits.

Laws (declared here, proven in tests/test_rendezvous.py):
1. Declaration, not surveillance — the store holds only what a person
   typed; nothing is observed.
2. Opt-in joining — attendance derives ONLY from explicit RSVPs.
3. Expiry is a wall — RSVP/withdraw on an expired intent is refused.
4. Nothing is thrown away — cancelled/withdrawn intents stay in the list.
5. Deny-closed — unknown intent ids raise; there is no default audience.
"""

from __future__ import annotations

__all__ = ["SHELF", "HOME_DIRNAME", "RendezvousError"]

HOME_DIRNAME = "rendezvous"


class RendezvousError(Exception):
    """A rendezvous operation was refused (unknown id, expired, bad time)."""


SHELF = {
    "name": "rendezvous",
    "summary": (
        "Declared-intent rendezvous board: who/where/when intents, opt-in "
        "RSVP only, automatic expiry, owner-only local store. Dodgeball's "
        "intent presence revived without the surveillance."
    ),
    "items": [
        "declare: who/where/when (+note, +invites), deny-closed validation",
        "rsvp/withdraw: explicit opt-in per person; expired intents refuse",
        "cancel: recorded, never deleted",
        "list: active-only or everything; expiry is derived, never stored",
    ],
}
