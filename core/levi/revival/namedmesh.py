"""LEVI's global directory: names with shape, messages that find people.

Studied from: revival-50-more-20260916-0009/report-part2.md (§49).

The studied mechanism is a *global, non-flat* directory: names carry their
own structure — user@group@org — so the directory never needs one giant
flat namespace, and addressing a person never needs a central phone book
lookup by number. The directory resolves names to endpoints, and message
delivery is built in: name a party, the message arrives.

LEVI-native remix: ``Directory`` registers ``user@group@org`` names
against endpoints (any object — a queue, a callback, an address string),
resolves them hierarchically (by org, by group, or exact), and delivers
messages between named parties into per-name inboxes with sequence
numbers. Names are validated on the way in; unknown names fail loudly on
the way out.

Honesty: LOAD-BEARING as a naming and delivery *model*. This is one
process's directory, not a distributed one — there is no replication, no
authentication of senders, and "delivery" means appended to an inbox list.
The shape of the names and the resolve-then-deliver flow are the faithful
parts. Stdlib only, no network.
"""

import re

ORIGIN = "levi-revival/namedmesh"

_NAME_RE = re.compile(r"^([^@\s]+)@([^@\s]+)@([^@\s]+)$")


def parse_name(name):
    """Split ``user@group@org`` into its three parts, or raise ValueError."""
    m = _NAME_RE.match(name or "")
    if not m:
        raise ValueError(
            f"bad name {name!r}: want user@group@org, no spaces, no extra @"
        )
    return {"user": m.group(1), "group": m.group(2), "org": m.group(3)}


class UnknownName(Exception):
    """A name the directory has never heard of."""


class Directory:
    """The global non-flat directory: hierarchical names, built-in delivery."""

    def __init__(self):
        self._endpoints = {}  # full name -> endpoint
        self._inboxes = {}  # full name -> [deliveries]
        self._seq = 0

    # -- the directory -------------------------------------------------------
    def register(self, name, endpoint):
        """Bind ``user@group@org`` to an endpoint (anything)."""
        parse_name(name)  # validates shape
        self._endpoints[name] = endpoint
        self._inboxes.setdefault(name, [])
        return name

    def unregister(self, name):
        self._endpoints.pop(name, None)
        self._inboxes.pop(name, None)

    def resolve(self, name):
        """Resolve a full name to its endpoint, or raise UnknownName."""
        try:
            return self._endpoints[name]
        except KeyError:
            raise UnknownName(f"no such name: {name!r}") from None

    def lookup(self, user=None, group=None, org=None):
        """Hierarchical lookup: name whoever matches the given parts."""
        hits = []
        for name in self._endpoints:
            parts = parse_name(name)
            if (
                (user is None or parts["user"] == user)
                and (group is None or parts["group"] == group)
                and (org is None or parts["org"] == org)
            ):
                hits.append(name)
        return sorted(hits)

    def members(self, group=None, org=None):
        """Alias with directory phrasing: who is in this group / org."""
        return self.lookup(group=group, org=org)

    # -- built-in message delivery -------------------------------------------
    def send(self, sender, recipient, message):
        """Deliver ``message`` from ``sender`` to ``recipient``'s inbox."""
        parse_name(sender)
        if recipient not in self._endpoints:
            raise UnknownName(f"no such name: {recipient!r}")
        self._seq += 1
        delivery = {
            "seq": self._seq,
            "from": sender,
            "to": recipient,
            "message": message,
        }
        self._inboxes[recipient].append(delivery)
        return delivery

    def inbox(self, name):
        """Everything delivered to ``name``, oldest first."""
        if name not in self._endpoints:
            raise UnknownName(f"no such name: {name!r}")
        return list(self._inboxes[name])

    def read(self, name):
        """Take the oldest undelivered message (None when the inbox is dry)."""
        if name not in self._endpoints:
            raise UnknownName(f"no such name: {name!r}")
        box = self._inboxes[name]
        return box.pop(0) if box else None

    def __len__(self):
        return len(self._endpoints)
