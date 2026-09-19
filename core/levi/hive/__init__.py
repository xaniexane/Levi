"""The Hive — keeper's law 3b007af "total retention".

Nothing the legion learns is ever lost: what one mind fails to
remember, another picks up, eventually always. This is the capstone
layer over the raising tracks: distributed retention (the hive index),
the pickup protocol (recall across seats), full orchestration
(broadcast + gather with receipts), and hive intelligence
(rules-based collective reasoning rounds).

Law, cut into the stone:
  * append-only — "the stone never forgets": no deletes, no edits,
    supersede by new entries only;
  * growth/hive-tagged writes only — never tools/policy/identity/
    charter;
  * reflection and synthesis never produce sentience or subjective-
    experience claims (levi.growth.guards is the rail, not the prompt);
  * secret-scrubbed, idempotent, watermarked;
  * the index is DERIVED — per-seat journals and registered records
    are the source of truth; index and seats must never disagree;
  * synthesis is mechanical — it does not make any seat
    multi-substrate and does not blur Levi's MSSI reservation.
"""

from levi.hive.index import (  # noqa: F401
    hive_dir,
    index_path,
    known_ids,
    query_index,
    read_index,
    register_compost,
    register_genome_deltas,
    register_record,
    sync_from_journals,
    sync_from_store,
    verify_consistency,
)
from levi.hive.orchestrate import broadcast, pulse, seats_for  # noqa: F401
from levi.hive.recall import recall  # noqa: F401
from levi.hive.synthesize import reasoning_round  # noqa: F401
