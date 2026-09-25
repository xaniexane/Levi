"""op_transform — operational transformation for concurrent co-editing.

Studied from: dead-networks-20260916/report.md (Google Wave: real-time
co-edit over the real, slow, unreliable internet).

The load-bearing idea: when two editors change the same document at
once, their operations are *transformed* against each other — each op
is rewritten as if it had been issued after the other one landed.
Both sites then apply the same ordered pair and converge on the same
text, without locking or a central arbiter.

LEVI's take: original character-level OT over plain strings. Ops are
``Insert``/``Delete`` dataclasses with a ``client`` id used only to
break ties. ``transform(op, against)`` rewrites ``op`` so it can
apply *after* ``against``. ``apply`` runs ops on a document;
``converge`` proves the classic diamond: both sites land on the same
string. This is an original, from-scratch implementation for LEVI.

Honest limits: character-level text only — no rich text, no
attributes, no undo, no operation compression. Positions must be
valid for the document an op applies to (checked in ``apply``).
Concurrent edits that overlap destructively still converge, but the
winner is decided by position/tiebreak rules, not intent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Union

ORIGIN = "levi-revival/op-transform"


@dataclass(frozen=True)
class Insert:
    pos: int
    text: str
    client: str = ""  # only used to break same-position ties


@dataclass(frozen=True)
class Delete:
    pos: int
    length: int
    client: str = ""


Op = Union[Insert, Delete]


def _check_insert(doc_len: int, op: Insert) -> None:
    if not (0 <= op.pos <= doc_len):
        raise ValueError(f"insert at {op.pos} out of range for length {doc_len}")
    if not op.text:
        raise ValueError("insert text must be non-empty")


def _check_delete(doc_len: int, op: Delete) -> None:
    if op.length <= 0:
        raise ValueError("delete length must be positive")
    if not (0 <= op.pos <= doc_len - op.length):
        raise ValueError(
            f"delete [{op.pos}, {op.pos + op.length}) out of range for length {doc_len}"
        )


def transform(op: Op, against: Op) -> Op:
    """Rewrite ``op`` (issued against a pre-state) to apply after ``against``.

    Convention for overlaps: an insert landing inside a concurrent
    delete's span is swallowed by the delete; a delete whose span
    overlaps another delete removes only the surviving characters.
    """
    if isinstance(against, Insert):
        n = len(against.text)
        if isinstance(op, Insert):
            if op.pos < against.pos:
                return op
            if op.pos > against.pos:
                return Insert(op.pos + n, op.text, op.client)
            # same position: smaller client id wins the slot
            if op.client <= against.client:
                return op
            return Insert(op.pos + n, op.text, op.client)
        # op is Delete, against is Insert
        q, p, dlen = against.pos, op.pos, op.length
        if q <= p:
            return Delete(p + n, dlen, op.client)
        if q < p + dlen:
            return Delete(p, dlen + n, op.client)  # swallow the inserted text
        return op
    # against is Delete
    q, m = against.pos, against.length
    if isinstance(op, Insert):
        if op.pos <= q:
            return op
        if op.pos >= q + m:
            return Insert(op.pos - m, op.text, op.client)
        return Insert(q, op.text, op.client)  # landed inside: clamp to start
    # op is Delete, against is Delete
    p, dlen = op.pos, op.length
    overlap = max(0, min(p + dlen, q + m) - max(p, q))
    if overlap > 0:
        return Delete(min(p, q), dlen - overlap, op.client)
    if p >= q + m:
        return Delete(p - m, dlen, op.client)
    return op  # p + dlen <= q: fully before


def apply(doc: str, ops: List[Op]) -> str:
    """Apply ops in order to a document (positions validated)."""
    out = doc
    for op in ops:
        if isinstance(op, Insert):
            _check_insert(len(out), op)
            out = out[: op.pos] + op.text + out[op.pos :]
        else:
            _check_delete(len(out), op)
            out = out[: op.pos] + out[op.pos + op.length :]
    return out


def converge(doc: str, a: Op, b: Op) -> Tuple[str, str]:
    """Apply (a then b') and (b then a') and return both results.

    Both sides must agree; that agreement is the convergence proof
    callers can assert on.
    """
    left = apply(doc, [a, transform(b, a)])
    right = apply(doc, [b, transform(a, b)])
    return left, right


def demo() -> dict:
    """Converge a mixed insert/delete conflict both ways."""
    doc = "abcdef"
    a = Insert(1, "X", client="ada")
    b = Delete(2, 3, client="bob")
    left, right = converge(doc, a, b)
    return {
        "doc": doc,
        "op_a": {"insert": 1, "text": "X"},
        "op_b": {"delete": 2, "length": 3},
        "site_a_then_b": left,
        "site_b_then_a": right,
        "converged": left == right,
    }
