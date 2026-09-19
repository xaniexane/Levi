"""LEVI's shared object memory: live objects over a transactional store.

Studied from: revival-50-more-20260916-0009/report-part2.md (§44).

The studied mechanism splits the world in two: *object execution* (live
objects you talk to) and *transactional storage* (the durable, shared
memory underneath), joined by ACID-ish commit/abort with optimistic
concurrency — write-write conflicts are detected, not silently merged.

LEVI-native remix, and deliberately distinct from mumps.py: mumps.py is
language-variable globals (``^person("mom")`` as persistent variables);
this is *objects plus transactions*. A ``Vault`` holds versioned objects;
you handle live ``VaultObject`` proxies with attribute access; work happens
inside ``Transaction`` blocks that commit atomically or abort cleanly. If
two transactions touch the same object, the second committer gets a
``ConflictError`` instead of a quiet overwrite.

Honesty: ACID-ish, stated plainly. Atomicity and isolation hold within one
process via optimistic version checks; there is no write-ahead log and no
crash durability — persistence is the caller's job (objects are plain
dicts, trivially JSON-serializable). Single-process only; the conflict
window is real but documented. Stdlib only, no network.
"""

import copy

ORIGIN = "levi-revival/objvault"


class ConflictError(Exception):
    """A write-write conflict: the object changed under this transaction."""


class VaultObject:
    """A live object: attribute access over one versioned entry in a Vault."""

    def __init__(self, vault, oid):
        object.__setattr__(self, "_vault", vault)
        object.__setattr__(self, "_oid", oid)

    @property
    def oid(self):
        return self._oid

    @property
    def version(self):
        return self._vault._version(self._oid)

    def read(self):
        """A detached copy of the object's current state."""
        return copy.deepcopy(self._vault._state(self._oid))

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._vault._state(self._oid)[name]
        except KeyError:
            raise AttributeError(f"{self._oid!r} has no attribute {name!r}") from None

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        # Direct writes outside a transaction auto-commit immediately.
        self._vault._apply(self._oid, {name: value})

    def patch(self, mapping):
        self._vault._apply(self._oid, dict(mapping))

    def __repr__(self):
        return f"VaultObject({self._oid!r}, v{self.version})"


class Transaction:
    """Optimistic transaction: validate versions at commit, abort on conflict."""

    def __init__(self, vault):
        self.vault = vault
        self._seen = {}  # oid -> version at first touch
        self._writes = {}  # oid -> pending full state
        self._active = True

    def _touch(self, oid):
        if oid not in self._seen:
            self._seen[oid] = self.vault._version(oid)
            self._writes[oid] = copy.deepcopy(self.vault._state(oid))

    def read(self, oid):
        """Read inside the transaction; records the version seen."""
        self._guard()
        self._touch(oid)
        return copy.deepcopy(self._writes[oid])

    def write(self, oid, patch):
        """Stage a patch; nothing is visible until commit."""
        self._guard()
        self._touch(oid)
        self._writes[oid].update(patch)

    def obj(self, oid):
        """A transaction-scoped live view of one object."""
        return _TxnObject(self, oid)

    def commit(self):
        """Validate then apply atomically; raise ConflictError on write-write."""
        self._guard()
        for oid, seen in self._seen.items():
            if self.vault._version(oid) != seen:
                self._active = False
                raise ConflictError(
                    f"{oid!r} changed during transaction "
                    f"(saw v{seen}, now v{self.vault._version(oid)})"
                )
        for oid, state in self._writes.items():
            self.vault._commit_state(oid, state)
        self._active = False

    def abort(self):
        self._writes.clear()
        self._seen.clear()
        self._active = False

    def _guard(self):
        if not self._active:
            raise RuntimeError("transaction is no longer active")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.abort()
        return False


class _TxnObject:
    """Attribute-style access to one object inside a transaction."""

    def __init__(self, txn, oid):
        object.__setattr__(self, "_txn", txn)
        object.__setattr__(self, "_oid", oid)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._txn.read(self._oid)[name]
        except KeyError:
            raise AttributeError(f"{self._oid!r} has no attribute {name!r}") from None

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        self._txn.write(self._oid, {name: value})


class Vault:
    """The transactional store: versioned objects, live proxies, ACID-ish."""

    def __init__(self):
        self._objects = {}  # oid -> {"state": dict, "version": int}
        self._seq = 0

    def create(self, oid=None, **state):
        """Create an object; returns its live proxy."""
        if oid is None:
            oid = f"obj-{self._seq}"
            self._seq += 1
        if oid in self._objects:
            raise KeyError(f"object {oid!r} already exists")
        self._objects[oid] = {"state": dict(state), "version": 0}
        return VaultObject(self, oid)

    def get(self, oid):
        """The live proxy for an existing object."""
        if oid not in self._objects:
            raise KeyError(f"unknown object {oid!r}")
        return VaultObject(self, oid)

    def begin(self):
        """Open a transaction (also usable as a context manager)."""
        return Transaction(self)

    def _state(self, oid):
        return self._objects[oid]["state"]

    def _version(self, oid):
        try:
            return self._objects[oid]["version"]
        except KeyError:
            raise KeyError(f"unknown object {oid!r}") from None

    def _apply(self, oid, patch):
        """Immediate auto-commit write (outside any transaction)."""
        self._state(oid).update(patch)
        self._objects[oid]["version"] += 1

    def _commit_state(self, oid, state):
        self._objects[oid]["state"] = state
        self._objects[oid]["version"] += 1

    def snapshot(self):
        """Plain-dict snapshot of the whole store (JSON-serializable)."""
        return {
            oid: {"state": copy.deepcopy(e["state"]), "version": e["version"]}
            for oid, e in self._objects.items()
        }

    def restore(self, snapshot):
        self._objects = copy.deepcopy(snapshot)

    def __len__(self):
        return len(self._objects)
