"""LEVI's navigational store: records linked by named sets.

Studied from: revival-50-more-20260916-0009/report-part2.md (§43).

CAUTION — carried over from the report, and it stands: this mechanism is
easy to get lost in. Navigation is positional, not declarative: you walk
first/next/prior through set occurrences holding *currency* (where you
are), and a wrong turn leaves you somewhere meaningless with no query to
explain how you got there. The schema is rigid — record types and set
types are declared up front, and the world must fit them. LEVI keeps this
module because the *mechanism* is instructive (named relationships with
ordered membership and a real cursor vocabulary), not because it is the
recommended way to model anything new. Prefer the declarative modules
(catgrid, manyfields) unless you specifically need ordered navigational
traversal.

LEVI-native remix: ``Schema`` declares record types and named set types
(owner type, member type); ``Subschema`` names a restricted vocabulary over
it; ``Database`` links records into ordered set occurrences and walks them
with first/next/prior/last, tracking currency per set and for the run unit.

Honesty: LOAD-BEARING as a navigational mechanism with the caution above.
Single-process, in-memory; sets are ordered lists, not B-trees; the
subschema is vocabulary, not an enforced view. Stdlib only, no network.
"""

ORIGIN = "levi-revival/navsets"


class Schema:
    """The declared world: record types and the named sets between them."""

    def __init__(self, name):
        self.name = name
        self.record_types = {}  # name -> [field names]
        self.set_types = {}  # name -> {"owner": rtype, "member": rtype}

    def define_record(self, name, fields=()):
        self.record_types[name] = list(fields)
        return name

    def define_set(self, name, owner, member):
        """A named set: each owner links an ordered run of members."""
        if owner not in self.record_types:
            raise KeyError(f"unknown owner record type {owner!r}")
        if member not in self.record_types:
            raise KeyError(f"unknown member record type {member!r}")
        self.set_types[name] = {"owner": owner, "member": member}
        return name


class Subschema:
    """A named, restricted vocabulary over a schema.

    Honest scope: this is vocabulary — which types and sets a given
    program is *supposed* to see — not an enforced security view.
    """

    def __init__(self, name, schema, record_types=(), set_types=()):
        for rt in record_types:
            if rt not in schema.record_types:
                raise KeyError(f"{rt!r} not in schema {schema.name!r}")
        for st in set_types:
            if st not in schema.set_types:
                raise KeyError(f"{st!r} not in schema {schema.name!r}")
        self.name = name
        self.schema = schema
        self.record_types = tuple(record_types)
        self.set_types = tuple(set_types)

    def allows_record(self, rtype):
        return rtype in self.record_types

    def allows_set(self, set_name):
        return set_name in self.set_types


class _Record:
    def __init__(self, rid, rtype, fields):
        self.rid = rid
        self.rtype = rtype
        self.fields = dict(fields)

    def __repr__(self):
        return f"<{self.rtype} {self.rid} {self.fields!r}>"


class Database:
    """Records linked by named sets; you walk, holding currency."""

    def __init__(self, schema):
        self.schema = schema
        self._records = {}  # rid -> _Record
        self._sets = {}  # set_name -> {owner_rid: [member_rids]}
        self._seq = 0
        # currency: where the run unit is, and where it is within each set
        self.currency = {"run_unit": None}

    # -- records -------------------------------------------------------------
    def add_record(self, rtype, **fields):
        if rtype not in self.schema.record_types:
            raise KeyError(f"unknown record type {rtype!r}")
        self._seq += 1
        rid = f"{rtype}#{self._seq}"
        self._records[rid] = _Record(rid, rtype, fields)
        self.currency["run_unit"] = rid
        return rid

    def get(self, rid):
        return self._records[rid]

    # -- sets: linking --------------------------------------------------------
    def link(self, set_name, owner_rid, member_rid):
        spec = self.schema.set_types[set_name]
        owner, member = self._records[owner_rid], self._records[member_rid]
        if owner.rtype != spec["owner"]:
            raise TypeError(
                f"{owner_rid} is {owner.rtype}, set {set_name!r} "
                f"needs owner {spec['owner']!r}"
            )
        if member.rtype != spec["member"]:
            raise TypeError(
                f"{member_rid} is {member.rtype}, set {set_name!r} "
                f"needs member {spec['member']!r}"
            )
        occ = self._sets.setdefault(set_name, {}).setdefault(owner_rid, [])
        if member_rid not in occ:
            occ.append(member_rid)

    def unlink(self, set_name, owner_rid, member_rid):
        occ = self._sets.get(set_name, {}).get(owner_rid, [])
        if member_rid in occ:
            occ.remove(member_rid)

    def members(self, set_name, owner_rid):
        """The ordered member rids of one set occurrence (the honest list)."""
        return list(self._sets.get(set_name, {}).get(owner_rid, []))

    # -- navigation: first / next / prior / last -----------------------------
    def _occurrence(self, set_name, owner_rid):
        if set_name not in self.schema.set_types:
            raise KeyError(f"unknown set {set_name!r}")
        return self._sets.get(set_name, {}).get(owner_rid, [])

    def first(self, set_name, owner_rid):
        occ = self._occurrence(set_name, owner_rid)
        rid = occ[0] if occ else None
        self._set_currency(set_name, rid)
        return self._records[rid] if rid else None

    def last(self, set_name, owner_rid):
        occ = self._occurrence(set_name, owner_rid)
        rid = occ[-1] if occ else None
        self._set_currency(set_name, rid)
        return self._records[rid] if rid else None

    def next(self, set_name, owner_rid):
        occ = self._occurrence(set_name, owner_rid)
        cur = self.currency.get(set_name)
        nxt = (
            occ[occ.index(cur) + 1]
            if cur in occ and occ.index(cur) + 1 < len(occ)
            else None
        )
        self._set_currency(set_name, nxt)
        return self._records[nxt] if nxt else None

    def prior(self, set_name, owner_rid):
        occ = self._occurrence(set_name, owner_rid)
        cur = self.currency.get(set_name)
        prv = occ[occ.index(cur) - 1] if cur in occ and occ.index(cur) > 0 else None
        self._set_currency(set_name, prv)
        return self._records[prv] if prv else None

    def current(self, set_name):
        rid = self.currency.get(set_name)
        return self._records[rid] if rid else None

    def find_owner(self, set_name, member_rid):
        """Walk backward: which owner claims this member in the set?"""
        for owner_rid, members in self._sets.get(set_name, {}).items():
            if member_rid in members:
                self.currency["run_unit"] = owner_rid
                return self._records[owner_rid]
        return None

    def _set_currency(self, set_name, rid):
        self.currency[set_name] = rid
        if rid is not None:
            self.currency["run_unit"] = rid
