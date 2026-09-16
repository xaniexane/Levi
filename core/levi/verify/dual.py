"""Dual-path agreement: never trust one computation path.

Run two independent implementations of the same computation and compare.
If either path raises, that is recorded in the receipt — an exception is
evidence, never swallowed. Equality of outputs is checked with ==; paths
that must agree loosely should normalize before returning.

This is the modern form of the desk-machine ritual: the proof clerk re-ran
the tape on a *different* machine, because two clerks making the same
mistake independently is the thing you are actually guarding against.
"""

from __future__ import annotations

from typing import Any, Callable

from .receipts import VerificationReceipt


def dual_path(
    fn_a: Callable[..., Any], fn_b: Callable[..., Any], *args: Any, **kwargs: Any
) -> VerificationReceipt:
    """Run both callables with the same arguments; receipt their agreement."""
    if not callable(fn_a) or not callable(fn_b):
        raise TypeError("dual_path needs two callables")
    try:
        out_a = fn_a(*args, **kwargs)
    except Exception as exc:  # recorded, never swallowed
        return VerificationReceipt(
            ok=False,
            method="dual-path",
            detail="path A raised %s: %s" % (type(exc).__name__, exc),
            expected="path A result",
            got="raised",
        )
    try:
        out_b = fn_b(*args, **kwargs)
    except Exception as exc:  # recorded, never swallowed
        return VerificationReceipt(
            ok=False,
            method="dual-path",
            detail="path B raised %s: %s" % (type(exc).__name__, exc),
            expected="path B result",
            got="raised",
        )
    ok = out_a == out_b
    return VerificationReceipt(
        ok=ok,
        method="dual-path",
        detail=("both paths agree: %r" % (out_a,) if ok else "paths disagree"),
        expected=repr(out_a),
        got=repr(out_b),
    )
