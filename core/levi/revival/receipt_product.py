"""The receipt is the product: every consequential computation carries its proof.

Studied from: pre-digital-computation-20260916, report.md [Cross-entry pattern 4].

Inspired by the *shape* of the old receipt discipline — the printed
adding-machine tape, the bell-and-transcribe check: the computation is
not finished until its evidence exists alongside it. A
:class:`ReceiptingCalculator` wraps ordinary arithmetic so each operation
emits a :class:`Receipt` carrying the inputs, the output, a digest of the
whole thing, and the method that produced it. The tape of receipts *is*
the deliverable; the numbers alone are not.

Receipts are tamper-evident: :func:`verify` recomputes the digest from
the receipt's own fields, so an altered receipt fails. :meth:`Tape.seal`
closes a tape with a final checksum, and :meth:`Tape.verify` replays the
whole tape, catching edits, deletions, and reorderings.

Honest limits: a receipt proves *what was recorded*, not that the method
was correct — garbage in, receipted garbage out. Digests use SHA-256
from the standard library; this is evidence, not cryptography-grade
non-repudiation (no keys, no signatures).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

ORIGIN = "levi-revival/receipt-product"


class ReceiptError(Exception):
    """Base class for receipt failures."""


class TamperedReceipt(ReceiptError):
    """A receipt's digest does not match its contents."""


@dataclass(frozen=True)
class Receipt:
    """Proof that a computation happened: inputs, output, method, digest."""

    seq: int
    operation: str
    inputs: tuple
    output: Any
    method: str
    digest: str

    @staticmethod
    def _digest(
        seq: int, operation: str, inputs: tuple, output: Any, method: str
    ) -> str:
        canonical = json.dumps(
            {
                "seq": seq,
                "op": operation,
                "in": inputs,
                "out": output,
                "method": method,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def issue(
        cls, seq: int, operation: str, inputs: tuple, output: Any, method: str
    ) -> "Receipt":
        return cls(
            seq,
            operation,
            inputs,
            output,
            method,
            cls._digest(seq, operation, inputs, output, method),
        )

    def verify(self) -> bool:
        """True when the digest matches the receipt's own fields."""
        return self.digest == self._digest(
            self.seq, self.operation, self.inputs, self.output, self.method
        )

    def tape_line(self) -> str:
        """One printed-tape line, in the spirit of the adding-machine roll."""
        return (
            f"{self.seq:04d}  {self.operation:<6} "
            f"{' '.join(map(str, self.inputs))} = {self.output}  "
            f"[{self.method}] #{self.digest[:8]}"
        )


class Tape:
    """The product: an ordered, sealable roll of receipts."""

    def __init__(self) -> None:
        self.receipts: List[Receipt] = []
        self._seal: Optional[str] = None

    def append(self, receipt: Receipt) -> None:
        if self._seal is not None:
            raise ReceiptError("tape is sealed; open a new tape")
        if receipt.seq != len(self.receipts):
            raise ReceiptError(
                f"receipt seq {receipt.seq} out of order; expected {len(self.receipts)}"
            )
        self.receipts.append(receipt)

    def seal(self) -> str:
        """Close the tape; returns the seal digest over all receipts."""
        joined = "".join(r.digest for r in self.receipts)
        self._seal = hashlib.sha256(joined.encode("utf-8")).hexdigest()
        return self._seal

    @property
    def sealed(self) -> bool:
        return self._seal is not None

    def verify(self) -> List[str]:
        """Replay the tape; returns a list of problems (empty = clean).

        Catches tampered receipts, out-of-order sequences, and a broken
        seal — but not entries that were wrong from birth.
        """
        problems: List[str] = []
        for i, r in enumerate(self.receipts):
            if r.seq != i:
                problems.append(f"receipt {i}: sequence broken (seq={r.seq})")
            if not r.verify():
                problems.append(
                    f"receipt {i} ({r.operation}): digest mismatch — tampered"
                )
        if self._seal is not None:
            joined = "".join(r.digest for r in self.receipts)
            if hashlib.sha256(joined.encode("utf-8")).hexdigest() != self._seal:
                problems.append("seal broken: tape changed after sealing")
        return problems

    def print_tape(self) -> str:
        """Render the whole tape as printed lines, seal included."""
        lines = [r.tape_line() for r in self.receipts]
        if self._seal is not None:
            lines.append(
                f"----  SEAL #{self._seal[:16]}  ({len(self.receipts)} entries)"
            )
        return "\n".join(lines)


class ReceiptingCalculator:
    """Arithmetic that cannot run without producing its evidence.

    Every operation appends a receipt to the tape and returns the plain
    result — the caller gets the number, the tape keeps the proof.
    """

    def __init__(self, method: str = "levi-arithmetic") -> None:
        self.method = method
        self.tape = Tape()

    def _record(self, operation: str, inputs: tuple, output: Any) -> Any:
        receipt = Receipt.issue(
            len(self.tape.receipts), operation, inputs, output, self.method
        )
        self.tape.append(receipt)
        return output

    def add(self, a: float, b: float) -> float:
        return self._record("add", (a, b), a + b)

    def sub(self, a: float, b: float) -> float:
        return self._record("sub", (a, b), a - b)

    def mul(self, a: float, b: float) -> float:
        return self._record("mul", (a, b), a * b)

    def div(self, a: float, b: float) -> float:
        if b == 0:
            raise ReceiptError("division by zero is not receipted")
        return self._record("div", (a, b), a / b)

    def apply(self, name: str, fn: Callable[..., Any], *args: Any) -> Any:
        """Run any named callable and receipt its inputs and output."""
        return self._record(name, args, fn(*args))

    def audit(self) -> Dict[str, Any]:
        """Independent re-verification of the tape: digest + seal check."""
        problems = self.tape.verify()
        return {
            "entries": len(self.tape.receipts),
            "sealed": self.tape.sealed,
            "clean": not problems,
            "problems": problems,
        }
