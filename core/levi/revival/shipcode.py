"""LEVI's ship-code vault — send programs to data, never data to programs.

Studied from: systems-internals survey (NeWS, send-programs-to-data
section).

The mechanism, functionally: the vault holds records, and analysis
code is *shipped into* the vault instead of dragging data out to the
code. A shipped program is a plain callable that receives exactly one
thing: a ``Scope`` — a read/filter/aggregate-only view over the
records it was granted. The program never receives the vault itself,
never sees records outside its grant, and gets no write path at all.
What leaves the vault is the program's *return value* — an answer, not
the data.

Honesty: enforcement is by API surface, not by bytecode isolation
(see ``revival.vmcell`` for the bytecode half). The Scope exposes no
reference to the vault or to ungranted records; a program only ever
holds what the vault handed it. The exfiltration test proves a hostile
program cannot reach past its grant through the public API.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

ORIGIN = "levi-revival/shipcode"


class VaultError(Exception):
    """Base failure for vault operations."""


class Scope:
    """The only thing a shipped program may touch.

    Read/filter/aggregate over granted record ids. No vault reference,
    no write path, no way to name an ungranted record.
    """

    def __init__(self, records: Dict[str, Dict[str, Any]], granted: List[str]):
        self._records = records  # shared, read-only by convention
        self._granted = tuple(granted)

    @property
    def granted(self) -> List[str]:
        return list(self._granted)

    def get(self, record_id: str) -> Dict[str, Any]:
        """Read one granted record (a copy — the vault keeps its own)."""
        if record_id not in self._granted:
            raise VaultError(f"record {record_id!r} not in granted scope")
        return dict(self._records[record_id])

    def scan(self) -> Iterable[Dict[str, Any]]:
        """Iterate copies of every granted record."""
        for rid in self._granted:
            yield dict(self._records[rid])

    def count(self) -> int:
        return len(self._granted)

    def filter(self, pred: Callable[[Dict[str, Any]], bool]) -> List[Dict[str, Any]]:
        return [rec for rec in self.scan() if pred(rec)]

    def aggregate(self, fn: Callable[[List[Dict[str, Any]]], Any]) -> Any:
        return fn(list(self.scan()))


class Vault:
    """A dict-of-records that accepts shipped programs."""

    def __init__(self) -> None:
        self._records: Dict[str, Dict[str, Any]] = {}

    def put(self, record_id: str, record: Dict[str, Any]) -> None:
        self._records[record_id] = dict(record)

    def drop(self, record_id: str) -> None:
        self._records.pop(record_id, None)

    def ids(self) -> List[str]:
        return sorted(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def ship(
        self,
        program: Callable[[Scope], Any],
        grant: Optional[List[str]] = None,
        record_ids: Optional[List[str]] = None,
    ) -> Any:
        """Run a program *inside* the vault against a granted scope.

        ``grant`` (alias ``record_ids``) names the records the program
        may see. The program receives a Scope and nothing else; its
        return value — the answer — is what leaves the vault.
        """
        wanted = grant if grant is not None else record_ids
        if wanted is None:
            raise VaultError("ship requires an explicit grant of record ids")
        unknown = [rid for rid in wanted if rid not in self._records]
        if unknown:
            raise VaultError(f"grant names unknown records: {unknown}")
        scope = Scope(self._records, list(wanted))
        return program(scope)


def summarize_by(
    field: str,
) -> Callable[[Scope], Dict[Any, int]]:
    """A ready-made shipped program: count records grouped by a field."""

    def program(scope: Scope) -> Dict[Any, int]:
        totals: Dict[Any, int] = {}
        for rec in scope.scan():
            key = rec.get(field)
            totals[key] = totals.get(key, 0) + 1
        return totals

    return program
