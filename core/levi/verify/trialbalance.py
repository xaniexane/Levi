"""The trial balance: two orthogonal representations, one global invariant.

Pacioli (1494) codified the Venetian merchant's integrity protocol: every
transaction lives in two books — the giornale (chronological journal) and
the quaderno (ledger organized by account). Periodically all debit balances
are summed against all credit balances; Pacioli's rule was "do not go to
sleep until the debits equal the credits." An imbalance cannot locate the
error, but it *proves* one exists — a 1494 Merkle-tree ancestor.

LEVI-native version: every learning is stored twice — once chronologically
(the journal) and once by topic (the index). The trial balance verifies the
two representations agree: every journal entry reachable from the index,
every index entry traceable to a journal entry, counts reconciled.
Orphaned entries are reported and quarantined — you cannot silently lose
a fact.

Caveat Pacioli would endorse: double-entry catches *recording* errors, not
fraud or valuation errors. This is a recording-integrity check, not a
truth machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping


@dataclass(frozen=True)
class TrialBalance:
    ok: bool
    journal_count: int
    index_count: int
    journal_orphans: List[str]  # journal ids with no index entry
    index_orphans: List[str]  # index entries pointing at missing journal ids
    detail: str = ""

    def __str__(self) -> str:
        if self.ok:
            return (
                "trial balance: OK — %d journal entries, %d index entries, "
                "both representations reconcile"
                % (self.journal_count, self.index_count)
            )
        bits = ["trial balance: IMBALANCE (%s)" % self.detail]
        if self.journal_orphans:
            bits.append("journal orphans: %s" % ", ".join(self.journal_orphans[:10]))
        if self.index_orphans:
            bits.append("index orphans: %s" % ", ".join(self.index_orphans[:10]))
        return "; ".join(bits)


def trial_balance(
    journal: Mapping[str, object], index: Mapping[str, Iterable[str]]
) -> TrialBalance:
    """Reconcile a chronological journal against a by-topic index.

    journal: id -> entry (entry content is not inspected).
    index: topic -> iterable of journal ids.
    """
    if not isinstance(journal, Mapping) or not isinstance(index, Mapping):
        raise TypeError("trial_balance needs two mappings")
    indexed: Dict[str, int] = {}
    for topic, ids in index.items():
        if isinstance(ids, str):
            raise TypeError("index[%r] must be an iterable of ids" % (topic,))
        for jid in ids:
            indexed[str(jid)] = indexed.get(str(jid), 0) + 1
    journal_ids = {str(k) for k in journal}
    journal_orphans = sorted(j for j in journal_ids if j not in indexed)
    index_orphans = sorted(j for j in indexed if j not in journal_ids)
    ok = not journal_orphans and not index_orphans
    detail = ""
    if not ok:
        parts = []
        if journal_orphans:
            parts.append("%d journal entries unindexed" % len(journal_orphans))
        if index_orphans:
            parts.append("%d index entries point nowhere" % len(index_orphans))
        detail = ", ".join(parts)
    return TrialBalance(
        ok=ok,
        journal_count=len(journal_ids),
        index_count=len(indexed),
        journal_orphans=journal_orphans,
        index_orphans=index_orphans,
        detail=detail,
    )
