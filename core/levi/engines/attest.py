"""Attest engine — hash-chain receipt attestation.

Inputs
------
``receipts``: list of ``{"id": str, "body": str, "prev": str}``, in chain
order. ``prev`` is the link the receipt *claims* points at its
predecessor.
``genesis``: the anchor value the first receipt's ``prev`` must equal
(required — an unattested chain starts nowhere).

The link rule is fixed and disclosed: the link a receipt *should* carry
is ``sha256_hex(id + "\\n" + body)`` of its predecessor. The engine
recomputes every link from scratch — it trusts nothing it was told.

The verdict is one of:

- ``"intact"`` — every link recomputed and matched, anchor included.
- ``"broken"`` — the first index whose link failed, with the exact
  expected and actual values (nothing fabricated).
- ``"empty"`` — the chain has zero receipts; nothing to attest.

Laws (declared up front, proved by the test suite)
--------------------------------------------------
1. **Determinism law** — same inputs → byte-identical verdict.
2. **Anchor law** — receipts[0].prev must equal ``genesis``; a forged
   anchor breaks at index 0.
3. **Link law** — every receipt's ``prev`` must equal the recomputed
   hash of its predecessor. Trust is never assumed; every link is
   recomputed.
4. **Honest-report law** — a break names the exact index, the exact
   expected value, and the exact actual value. Expected values are only
   ever recomputed hashes, never invented.
5. **First-break law** — verification runs in order from index 0 and
   reports the *first* break; a later link is never blamed for an
   earlier one's failure.

Confidence is 1.0 on ``intact`` and ``empty`` (the math is exact), and
1.0 on ``broken`` too — a located break is a fact, not a guess.

Pure computation — no actions, no side effects.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Dict, List

from levi.engines.base import Engine, EngineInputError, EngineResult, registry


def _link_hash(receipt_id: str, body: str) -> str:
    """The one disclosed link rule: sha256 over id + newline + body."""
    return sha256(f"{receipt_id}\n{body}".encode("utf-8")).hexdigest()


def _attest(inputs: Dict[str, Any]) -> EngineResult:
    receipts = inputs.get("receipts")
    genesis = inputs.get("genesis")

    if not isinstance(receipts, list):
        raise EngineInputError("attest: 'receipts' needs a list")
    if not isinstance(genesis, str) or not genesis:
        raise EngineInputError("attest: 'genesis' needs a non-empty str anchor")
    for index, receipt in enumerate(receipts):
        if not isinstance(receipt, dict):
            raise EngineInputError(f"attest: receipt at index {index} must be a dict")
        for key in ("id", "body", "prev"):
            if not isinstance(receipt.get(key), str) or not receipt.get(key):
                raise EngineInputError(
                    f"attest: receipt at index {index} needs a non-empty str '{key}'"
                )

    trace: List[str] = [f"attesting {len(receipts)} receipts against anchor"]
    if not receipts:
        trace.append("empty chain: nothing to attest")
        return EngineResult(
            engine_id="attest",
            verdict={"status": "empty", "receipt_count": 0},
            confidence=1.0,
            trace=trace,
        )

    # Index 0: the anchor law. The chain starts where the keeper said it
    # starts, or it does not start at all.
    first = receipts[0]
    if first["prev"] != genesis:
        trace.append(
            f"break at index 0: anchor mismatch — expected {genesis!r}, "
            f"got {first['prev']!r}"
        )
        return EngineResult(
            engine_id="attest",
            verdict={
                "status": "broken",
                "break_index": 0,
                "reason": "anchor-mismatch",
                "expected": genesis,
                "actual": first["prev"],
                "receipt_count": len(receipts),
            },
            confidence=1.0,
            trace=trace,
        )
    trace.append("index 0: anchor holds")

    # Indices 1..n: the link law, in order, first break wins.
    for index in range(1, len(receipts)):
        predecessor = receipts[index - 1]
        expected = _link_hash(predecessor["id"], predecessor["body"])
        actual = receipts[index]["prev"]
        if actual != expected:
            trace.append(
                f"break at index {index}: link mismatch — expected "
                f"{expected!r} (recomputed from '{predecessor['id']}'), "
                f"got {actual!r}"
            )
            return EngineResult(
                engine_id="attest",
                verdict={
                    "status": "broken",
                    "break_index": index,
                    "reason": "link-mismatch",
                    "expected": expected,
                    "actual": actual,
                    "receipt_count": len(receipts),
                },
                confidence=1.0,
                trace=trace,
            )
        trace.append(f"index {index}: link holds (recomputed)")

    trace.append(f"{len(receipts)} receipts: every link recomputed and matched")
    return EngineResult(
        engine_id="attest",
        verdict={"status": "intact", "receipt_count": len(receipts)},
        confidence=1.0,
        trace=trace,
    )


ATTEST_ENGINE = Engine(
    id="attest",
    name="Attest",
    description=(
        "Hash-chain receipt attestation: recomputes every link from "
        "scratch against a genesis anchor and reports intact, broken "
        "(exact index and values), or empty. Trusts nothing it was told."
    ),
    version="1.0.0",
    required=("receipts", "genesis"),
    schema={
        "receipts": "list[{id: str, body: str, prev: str}] in chain order",
        "genesis": "non-empty str anchor the first receipt's prev must equal",
    },
    risk="info",
    handler=_attest,
)

registry.register(ATTEST_ENGINE)
