"""Array-as-primitive executable mathematical notation.

Studied from: languages-hunt-20260915, report.md [S4, USEFUL PATTERN].

Inspired by the *shape* of APL: arrays are the primitive unit, so one
operation replaces a loop — elementwise arithmetic over whole vectors,
reduction (``+/`` folds a vector to a scalar), outer product (every pair),
and reshape/transpose as first-class verbs. This is an original,
from-scratch implementation for LEVI — no APL code is used. Operator
names are plain-English methods (``reduce``, ``outer``) rather than APL
glyphs, keeping the notation executable without a special keyboard.

An :class:`Array` is a flat row-major list plus a shape tuple; scalars
broadcast. Everything is pure and immutable: operations return new
arrays, never mutate.

Honest limits: elementwise ops need matching shapes (or a scalar) —
no implicit broadcasting of mismatched ranks; reduction is over the
whole array (no axis argument); transpose is 2-D only; division by zero
follows Python semantics (raises) instead of APL's ``0÷0 is 1``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce as _reduce
from math import prod
from typing import Callable, Iterable, List, Tuple, Union

ORIGIN = "levi-revival/apl"

Number = Union[int, float]


def _is_number(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


@dataclass(frozen=True)
class Array:
    """An immutable row-major array; shape ``()`` means scalar."""

    data: Tuple[Number, ...]
    shape: Tuple[int, ...]

    def __post_init__(self) -> None:
        if prod(self.shape, start=1) != len(self.data):
            raise ValueError(
                f"shape {self.shape} needs {prod(self.shape, start=1)} items, "
                f"got {len(self.data)}"
            )
        for x in self.data:
            if not _is_number(x):
                raise TypeError(f"array elements must be numbers, got {x!r}")

    # -- construction ------------------------------------------------------
    @classmethod
    def scalar(cls, value: Number) -> "Array":
        return cls((value,), ())

    @classmethod
    def vector(cls, items: Iterable[Number]) -> "Array":
        items = tuple(items)
        return cls(items, (len(items),))

    @classmethod
    def iota(cls, n: int) -> "Array":
        """``iota n`` — the vector 1..n (1-origin, as in the tradition)."""
        if n < 0:
            raise ValueError("iota needs a non-negative count")
        return cls(tuple(range(1, n + 1)), (n,))

    @classmethod
    def matrix(cls, rows: Iterable[Iterable[Number]]) -> "Array":
        rows = [tuple(r) for r in rows]
        if not rows:
            raise ValueError("matrix needs at least one row")
        width = len(rows[0])
        if any(len(r) != width for r in rows):
            raise ValueError("matrix rows must all have the same length")
        return cls(tuple(x for r in rows for x in r), (len(rows), width))

    # -- views --------------------------------------------------------------
    @property
    def rank(self) -> int:
        return len(self.shape)

    @property
    def size(self) -> int:
        return len(self.data)

    def is_scalar(self) -> bool:
        return self.shape == ()

    def to_list(self) -> Union[Number, List]:
        """Nested Python lists mirroring the shape (scalar -> bare number)."""
        if self.is_scalar():
            return self.data[0]
        if self.rank == 1:
            return list(self.data)
        rows, cols = self.shape
        return [list(self.data[r * cols : (r + 1) * cols]) for r in range(rows)]

    # -- elementwise --------------------------------------------------------
    def _elementwise(
        self, other: Union["Array", Number], fn: Callable[[Number, Number], Number]
    ) -> "Array":
        other = other if isinstance(other, Array) else Array.scalar(other)
        if other.is_scalar():
            return Array(tuple(fn(x, other.data[0]) for x in self.data), self.shape)
        if self.is_scalar():
            return Array(tuple(fn(self.data[0], x) for x in other.data), other.shape)
        if self.shape != other.shape:
            raise ValueError(f"shape mismatch: {self.shape} vs {other.shape}")
        return Array(
            tuple(fn(x, y) for x, y in zip(self.data, other.data, strict=True)),
            self.shape,
        )

    def __add__(self, other: Union["Array", Number]) -> "Array":
        return self._elementwise(other, lambda a, b: a + b)

    def __radd__(self, other: Number) -> "Array":
        return self._elementwise(other, lambda a, b: a + b)

    def __sub__(self, other: Union["Array", Number]) -> "Array":
        return self._elementwise(other, lambda a, b: a - b)

    def __mul__(self, other: Union["Array", Number]) -> "Array":
        return self._elementwise(other, lambda a, b: a * b)

    def __truediv__(self, other: Union["Array", Number]) -> "Array":
        def div(a: Number, b: Number) -> Number:
            if b == 0:
                raise ZeroDivisionError("division by zero")
            return a / b

        return self._elementwise(other, div)

    def __neg__(self) -> "Array":
        return Array(tuple(-x for x in self.data), self.shape)

    # -- the big three: reduce, scan, reshape --------------------------------
    def reduce(self, fn: Callable[[Number, Number], Number]) -> "Array":
        """Fold the whole array to a scalar (``+/v`` in spirit)."""
        if not self.data:
            raise ValueError("cannot reduce an empty array")
        return Array.scalar(_reduce(fn, self.data))

    def sum(self) -> Number:
        return self.reduce(lambda a, b: a + b).to_list()  # type: ignore[return-value]

    def product(self) -> Number:
        return self.reduce(lambda a, b: a * b).to_list()  # type: ignore[return-value]

    def maximum(self) -> Number:
        return self.reduce(max).to_list()  # type: ignore[return-value]

    def minimum(self) -> Number:
        return self.reduce(min).to_list()  # type: ignore[return-value]

    def scan(self, fn: Callable[[Number, Number], Number]) -> "Array":
        """Running fold: each prefix reduced (``+\\v`` in spirit)."""
        if not self.data:
            return Array((), (0,))
        acc = self.data[0]
        out = [acc]
        for x in self.data[1:]:
            acc = fn(acc, x)
            out.append(acc)
        return Array(tuple(out), self.shape)

    def reshape(self, shape: Tuple[int, ...]) -> "Array":
        """Give the same data a new shape (``rho`` in spirit)."""
        return Array(self.data, shape)

    def ravel(self) -> "Array":
        """Flatten to a vector."""
        return Array(self.data, (len(self.data),))

    # -- outer / inner product ----------------------------------------------
    def outer(
        self,
        other: "Array",
        fn: Callable[[Number, Number], Number] = lambda a, b: a * b,
    ) -> "Array":
        """Outer product: every pair ``fn(a, b)``; result rank is the sum."""
        data = tuple(fn(a, b) for a in self.data for b in other.data)
        return Array(data, self.shape + other.shape)

    def inner(
        self,
        other: "Array",
        combine: Callable[[Number, Number], Number] = lambda a, b: a + b,
        pair: Callable[[Number, Number], Number] = lambda a, b: a * b,
    ) -> "Array":
        """Inner product over the last axis of self / first of other.

        With default ``combine=+`` and ``pair=*`` this is matrix
        multiplication for 2-D arrays.
        """
        if self.rank == 0 or other.rank == 0:
            raise ValueError("inner product needs non-scalar arrays")
        if self.shape[-1] != other.shape[0]:
            raise ValueError(f"inner dimension mismatch: {self.shape} vs {other.shape}")
        k = self.shape[-1]
        out_shape = self.shape[:-1] + other.shape[1:]
        left = self.data
        right = other.data
        right_cols = prod(other.shape[1:], start=1)
        result = []
        for i in range(prod(self.shape[:-1], start=1)):
            for j in range(right_cols):
                total = pair(left[i * k], right[j])
                for t in range(1, k):
                    total = combine(
                        total, pair(left[i * k + t], right[t * right_cols + j])
                    )
                result.append(total)
        return Array(tuple(result), out_shape)

    # -- selection / ordering -------------------------------------------------
    def compress(self, mask: Iterable[int]) -> "Array":
        """Keep items where the boolean mask is true (``/`` in spirit)."""
        mask = tuple(mask)
        if len(mask) != len(self.data):
            raise ValueError("mask length must match array size")
        return Array(
            tuple(x for x, m in zip(self.data, mask, strict=True) if m),
            (sum(1 for m in mask if m),),
        )

    def catenate(self, other: "Array") -> "Array":
        """Join two vectors end to end."""
        if self.rank > 1 or other.rank > 1:
            raise ValueError("catenate works on vectors (and scalars)")
        return Array(self.data + other.data, (len(self.data) + len(other.data),))

    def grade_up(self) -> "Array":
        """Indices that would sort the vector ascending."""
        return Array(
            tuple(i + 1 for i, _ in sorted(enumerate(self.data), key=lambda p: p[1])),
            (len(self.data),),
        )

    def transpose(self) -> "Array":
        """2-D transpose (rows become columns)."""
        if self.rank != 2:
            raise ValueError("transpose is 2-D only in this implementation")
        rows, cols = self.shape
        data = tuple(self.data[r * cols + c] for c in range(cols) for r in range(rows))
        return Array(data, (cols, rows))

    def rotate(self, n: int) -> "Array":
        """Rotate a vector left by ``n`` places."""
        if self.rank > 1:
            raise ValueError("rotate works on vectors")
        n = n % len(self.data) if self.data else 0
        return Array(self.data[n:] + self.data[:n], self.shape)
