"""LEVI's sacrificial model: a full-fidelity scratchpad built to be burned.

Studied from: lost-crafts-20260916/report.md [Batch 3] (functional description
only; no historical claims).

The lesson, reborn as LEVI's own: sometimes the work needs a *full-fidelity
model* — every intermediate, every draft value — that must not survive the
task. A ``SacrificialModel`` is a non-persisted scratch tier: you build it,
write and transform freely inside it, ``derive()`` the one result worth
keeping, then ``burnout()`` destroys the scratch state completely. What
remains is a ``BurnReceipt`` — a hash-linked record of the model's name, the
operation count, the derived result's digest, and the burn timestamp —
provenance *without* the model. Reading a burned model raises
``BurnedOutError``; nothing is ever written to disk by this module.

Honesty: the "burn" is in-memory destruction (state dict replaced, references
dropped). It is honest about its limits: it cannot scrub copies the caller
made elsewhere, and the receipt proves *that* a model was burned and what it
derived, not what was inside it.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

ORIGIN = "levi-revival/sacrificial-model"


class BurnedOutError(RuntimeError):
    """Raised when touching a model that has already been burned out."""


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(value: Any) -> str:
    """Stable string form for digesting derived results."""
    if isinstance(value, dict):
        items = ",".join(
            f"{_canonical(k)}:{_canonical(v)}"
            for k, v in sorted(value.items(), key=repr)
        )
        return "{" + items + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonical(v) for v in value) + "]"
    return repr(value)


@dataclass(frozen=True)
class DerivedResult:
    """The one thing allowed to survive the burn: a named, digested result."""

    model_name: str
    payload: Any
    digest: str


@dataclass(frozen=True)
class BurnReceipt:
    """Proof of destruction: what was burned, what it derived, when."""

    model_name: str
    operations: int
    result_digest: Optional[str]
    burned_at: float
    receipt_digest: str

    def verify(self) -> bool:
        """Recompute the receipt digest from its own fields."""
        body = (
            f"{self.model_name}|{self.operations}|{self.result_digest}|{self.burned_at}"
        )
        return _digest(body) == self.receipt_digest


class SacrificialModel:
    """A scratch model with a built-in self-destruct.

    Lifecycle: ``build`` -> ``write`` / ``transform`` -> ``derive`` (optional)
    -> ``burnout``. After ``burnout`` every accessor raises ``BurnedOutError``
    and only the receipt remains.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._state: Dict[str, Any] = {}
        self._operations = 0
        self._result: Optional[DerivedResult] = None
        self._receipt: Optional[BurnReceipt] = None

    @classmethod
    def build(cls, name: str) -> "SacrificialModel":
        return cls(name)

    @property
    def name(self) -> str:
        return self._name

    @property
    def operations(self) -> int:
        return self._operations

    def _guard(self) -> None:
        if self._receipt is not None:
            raise BurnedOutError(f"model {self._name!r} has been burned out")

    # -- scratch work ----------------------------------------------------------
    def write(self, key: str, value: Any) -> None:
        self._guard()
        self._state[key] = value
        self._operations += 1

    def read(self, key: str) -> Any:
        self._guard()
        return self._state[key]

    def erase(self, key: str) -> None:
        self._guard()
        del self._state[key]
        self._operations += 1

    def transform(
        self, key: str, func: Callable[[Any], Any], label: str = "transform"
    ) -> Any:
        """Apply ``func`` to the value at ``key`` and store the result back."""
        self._guard()
        if not callable(func):
            raise TypeError("func must be callable")
        self._state[key] = func(self._state[key])
        self._operations += 1
        return self._state[key]

    def keys(self) -> tuple:
        self._guard()
        return tuple(self._state.keys())

    # -- derive & burn -----------------------------------------------------------
    def derive(self, payload: Any) -> DerivedResult:
        """Distill the scratch work into the one result worth keeping."""
        self._guard()
        digest = _digest(f"{self._name}|{_canonical(payload)}")
        self._result = DerivedResult(
            model_name=self._name, payload=payload, digest=digest
        )
        return self._result

    def burnout(self) -> BurnReceipt:
        """Destroy the scratch state; return the receipt. Idempotent."""
        if self._receipt is not None:
            return self._receipt
        result_digest = self._result.digest if self._result else None
        burned_at = time.time()
        receipt_digest = _digest(
            f"{self._name}|{self._operations}|{result_digest}|{burned_at}"
        )
        # The burn: drop every reference to the scratch state and the result.
        self._state = {}
        self._result = None
        self._receipt = BurnReceipt(
            model_name=self._name,
            operations=self._operations,
            result_digest=result_digest,
            burned_at=burned_at,
            receipt_digest=receipt_digest,
        )
        return self._receipt

    @property
    def receipt(self) -> Optional[BurnReceipt]:
        return self._receipt
