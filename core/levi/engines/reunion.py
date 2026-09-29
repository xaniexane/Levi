"""Reunion engine — verdicts over divergent copies of one record.

Two clouds, one file, three different bytes: the reunion engine looks at
every divergent copy and renders one honest verdict. It never picks a
winner on its own — it classifies, and holds real conflicts for the
keeper.

Inputs
------
``versions``: list of 2–8 ``{"id": str, "text": str}`` (ids unique,
non-empty; total text capped at 200,000 chars — refused, never
truncated).
``base``: optional common-ancestor text. When omitted, the reference is
the text of the lexicographically smallest id (deterministic, disclosed
in the trace).

Verdicts
--------
- ``converged`` — every copy byte-identical. Nothing to do.
- ``single-line`` — exactly one distinct text differs from the
  reference. The divergent copy is named; adoption stays the keeper's
  call, never the engine's.
- ``reconcilable`` — every change lands in a disjoint region of the
  reference. A merged text is produced with per-region provenance
  (which copy wrote which span).
- ``conflicted`` — two or more copies claim the same region. No
  auto-merge, ever: the verdict names every competing region and the
  rival texts, held for the keeper.

Laws (declared up front, proved by the test suite)
--------------------------------------------------
1. **Determinism law** — same inputs → byte-identical verdict (every
   ordering is sorted; difflib is deterministic).
2. **No-deletion law** — every version's bytes are accounted for in the
   verdict (sha256 + ids per group; conflict regions carry the rival
   texts). Nothing is ever dropped or silently merged away.
3. **Honest-hold law** — overlapping edits are never auto-merged. A
   ``conflicted`` verdict carries no merged text, only the evidence.
4. **Base-optional law** — a missing base degrades to the smallest-id
   reference, disclosed in the trace, never guessed silently.

Confidence is the engine's own calibration: 1.0 converged, 0.85
single-line, 0.7 reconcilable, 0.4 conflicted (held for the keeper).

Pure computation — no actions, no side effects.
"""

from __future__ import annotations

import hashlib
from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple

from levi.engines.base import Engine, EngineInputError, EngineResult, registry

_MAX_VERSIONS = 8
_MAX_TOTAL_CHARS = 200_000


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _change_spans(reference: str, text: str) -> List[Tuple[int, int, str]]:
    """(ref_start, ref_end, new_text) for every non-equal opcode."""
    spans: List[Tuple[int, int, str]] = []
    matcher = SequenceMatcher(None, reference, text)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            spans.append((i1, i2, text[j1:j2]))
    return spans


def _overlaps(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _reunion(inputs: Dict[str, Any]) -> EngineResult:
    versions = inputs.get("versions")
    base = inputs.get("base")

    if not isinstance(versions, list) or not 2 <= len(versions) <= _MAX_VERSIONS:
        raise EngineInputError(
            f"reunion: 'versions' needs a list of 2–{_MAX_VERSIONS} entries"
        )
    texts: Dict[str, str] = {}
    for entry in versions:
        if not isinstance(entry, dict):
            raise EngineInputError("reunion: each version must be a dict")
        vid = entry.get("id")
        text = entry.get("text")
        if not isinstance(vid, str) or not vid:
            raise EngineInputError("reunion: each version needs a non-empty str 'id'")
        if not isinstance(text, str):
            raise EngineInputError(f"reunion: version '{vid}' needs a str 'text'")
        if vid in texts:
            raise EngineInputError(
                f"reunion: duplicate id '{vid}' — refused, never merged silently"
            )
        texts[vid] = text
    if base is not None and not isinstance(base, str):
        raise EngineInputError("reunion: 'base' must be a str when given")
    total_chars = sum(len(t) for t in texts.values())
    if total_chars > _MAX_TOTAL_CHARS:
        raise EngineInputError(
            f"reunion: {total_chars} chars exceeds the {_MAX_TOTAL_CHARS} cap; "
            "refused rather than truncated"
        )

    ids = sorted(texts)
    reference_id = ids[0]
    reference = base if base is not None else texts[reference_id]
    base_given = base is not None
    if base_given:
        ref_note = "reference: given base"
    else:
        ref_note = "reference: version '" + reference_id + "' (smallest id)"
    trace: List[str] = [
        ref_note,
        f"{len(ids)} versions, {total_chars} chars total",
    ]

    groups: Dict[str, List[str]] = {}
    for vid in ids:
        groups.setdefault(_sha256(texts[vid]), []).append(vid)
    group_list = [
        {"sha256": h, "ids": sorted(vids)} for h, vids in sorted(groups.items())
    ]
    trace.append(f"{len(group_list)} distinct text(s) across {len(ids)} version(s)")
    verdict: Dict[str, Any] = {
        "reference_id": reference_id,
        "base_given": base_given,
        "groups": group_list,
    }

    ref_hash = _sha256(reference)
    divergent_ids = sorted(v for v in ids if _sha256(texts[v]) != ref_hash)
    verdict["divergent_ids"] = divergent_ids

    if len(group_list) == 1:
        verdict.update(
            {
                "status": "converged",
                "merged_text": reference,
                "regions": [],
                "conflicts": [],
            }
        )
        trace.append("all copies byte-identical — converged")
        return EngineResult(
            engine_id="reunion", verdict=verdict, confidence=1.0, trace=trace
        )

    if len(group_list) == 2 and ref_hash in groups:
        verdict.update(
            {
                "status": "single-line",
                "merged_text": None,
                "regions": [],
                "conflicts": [],
            }
        )
        trace.append(
            f"one divergent line ({', '.join(divergent_ids)}) — named, not adopted"
        )
        return EngineResult(
            engine_id="reunion", verdict=verdict, confidence=0.85, trace=trace
        )

    # Two or more distinct non-reference texts: map every change to
    # reference spans, then cluster overlapping spans.
    rep_id = {h: sorted(vids)[0] for h, vids in groups.items()}
    events: List[Tuple[int, int, str, str]] = []  # start, end, new_text, rep id
    for h in sorted(groups):
        if h == ref_hash:
            continue
        for start, end, new_text in _change_spans(reference, texts[rep_id[h]]):
            events.append((start, end, new_text, rep_id[h]))
    trace.append(
        f"{len(events)} change event(s) across {len(group_list) - 1} divergent text(s)"
    )

    parent = list(range(len(events)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(events)):
        for j in range(i + 1, len(events)):
            if _overlaps((events[i][0], events[i][1]), (events[j][0], events[j][1])):
                union(i, j)

    clusters: Dict[int, List[int]] = {}
    for i in range(len(events)):
        clusters.setdefault(find(i), []).append(i)

    conflicts: List[Dict[str, Any]] = []
    for members in clusters.values():
        owners = sorted({events[m][3] for m in members})
        if len(owners) > 1:
            span = (
                min(events[m][0] for m in members),
                max(events[m][1] for m in members),
            )
            conflicts.append(
                {
                    "span": [span[0], span[1]],
                    "competitors": [
                        {
                            "id": events[m][3],
                            "new_text": events[m][2],
                        }
                        for m in sorted(members)
                    ],
                }
            )
    conflicts.sort(key=lambda c: (c["span"][0], c["span"][1]))

    if conflicts:
        verdict.update(
            {
                "status": "conflicted",
                "merged_text": None,
                "regions": [],
                "conflicts": conflicts,
            }
        )
        trace.append(
            f"{len(conflicts)} contested region(s) — held for the keeper, no auto-merge"
        )
        return EngineResult(
            engine_id="reunion", verdict=verdict, confidence=0.4, trace=trace
        )

    # Disjoint changes: splice them into the reference, rightmost first
    # so earlier offsets stay valid.
    regions = [
        {
            "span": [s, e],
            "version_ids": [rid],
            "new_text": new_text,
        }
        for s, e, new_text, rid in sorted(events, key=lambda ev: (ev[0], ev[1]))
    ]
    merged = reference
    for start, end, new_text, _rid in sorted(
        events, key=lambda ev: ev[0], reverse=True
    ):
        merged = merged[:start] + new_text + merged[end:]
    verdict.update(
        {
            "status": "reconcilable",
            "merged_text": merged,
            "regions": regions,
            "conflicts": [],
        }
    )
    trace.append(f"{len(regions)} disjoint region(s) reconciled with provenance")
    return EngineResult(
        engine_id="reunion", verdict=verdict, confidence=0.7, trace=trace
    )


REUNION_ENGINE = Engine(
    id="reunion",
    name="Reunion",
    description=(
        "Verdicts over divergent copies of one record: converged, "
        "single-line, reconcilable (merged with provenance), or conflicted "
        "(held for the keeper — never auto-merged). Nothing is ever dropped."
    ),
    version="1.0.0",
    required=("versions",),
    schema={
        "versions": "list[{id: str, text: str}] (2–8, ids unique)",
        "base": "optional common-ancestor str; else smallest-id version is reference",
    },
    risk="info",
    handler=_reunion,
)

registry.register(REUNION_ENGINE)
