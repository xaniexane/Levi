"""LEVI's contracts — executable promises, checked while the code runs.

Studied from: revival-50-more-20260916-0009/report-part1.md [entry #9]
(Eiffel, Design by Contract).

The studied capability shape: preconditions, postconditions, and class
invariants as *executable language semantics* — promises the runtime
checks, not comments it ignores. This module is an original,
from-scratch expression of that shape for Python: ``@requires`` guards
entry, ``@ensures`` guards exit, and ``@invariant`` wraps every public
method of a class so the object's promise holds before and after each
call (and right after construction). Violations raise
``ContractViolation`` naming the kind, the place, and the message — loud
and early, at the broken promise, not three call frames later.

Honest limits, stated plainly: predicates are plain Python callables,
so contracts are only as smart as what you write — there is no theorem
prover here, just runtime checks. ``@requires`` predicates receive the
call's own arguments (``self`` included for methods); ``@ensures``
predicates receive the result *first*, then the call's arguments.
Invariants wrap plain functions found on the class (dunder, private, and
descriptor-wrapped members are left alone). A global switch,
``contracts_enabled(False)``, silences all checks for measured runs —
contracts are for catching bugs, not for production hot paths. This is a
heuristic discipline tool, and the docstring says so.

Original, from-scratch implementation for LEVI. Local-first, stdlib
only, no network. Not artificial. Synthetic.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, List, Optional, Tuple

ORIGIN = "levi-revival/contracts"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ContractViolation(Exception):
    """A broken promise: precondition, postcondition, or invariant."""

    def __init__(self, kind: str, where: str, message: str = ""):
        text = f"{kind} violated at {where}"
        if message:
            text += f": {message}"
        super().__init__(text)
        self.kind = kind
        self.where = where
        self.message = message


# ---------------------------------------------------------------------------
# Global switch
# ---------------------------------------------------------------------------

_enabled = True


def contracts_enabled(flag: Optional[bool] = None) -> bool:
    """Read or set the global contract switch.

    ``contracts_enabled()`` returns the current state;
    ``contracts_enabled(False)`` silences every check (they cost nothing
    then); ``contracts_enabled(True)`` turns them back on.
    """
    global _enabled
    if flag is not None:
        _enabled = bool(flag)
    return _enabled


# ---------------------------------------------------------------------------
# Specs (introspection)
# ---------------------------------------------------------------------------


def contract_specs(fn: Callable) -> List[Tuple[str, Callable, str]]:
    """The (kind, predicate, message) specs attached to a wrapped callable."""
    return list(getattr(fn, "__contract_specs__", []))


def _attach(fn: Callable, kind: str, predicate: Callable, message: str) -> None:
    specs = list(getattr(fn, "__contract_specs__", []))
    specs.append((kind, predicate, message))
    fn.__contract_specs__ = specs  # noqa: B010 - deliberate attribute


# ---------------------------------------------------------------------------
# requires / ensures
# ---------------------------------------------------------------------------


def requires(predicate: Callable[..., bool], message: str = "") -> Callable:
    """Precondition: checked with the call's own arguments before entry.

    ``predicate(*args, **kwargs)`` must be truthy; for methods the first
    argument is the instance. Violation raises before the body runs.
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if _enabled and not predicate(*args, **kwargs):
                _attach(wrapper, "precondition", predicate, message)
                raise ContractViolation(
                    "precondition", getattr(fn, "__qualname__", repr(fn)), message
                )
            return fn(*args, **kwargs)

        _attach(wrapper, "precondition", predicate, message)
        return wrapper

    return decorator


def ensures(predicate: Callable[..., bool], message: str = "") -> Callable:
    """Postcondition: checked with the result first, then the call's arguments.

    ``predicate(result, *args, **kwargs)`` must be truthy. Violation
    raises after the body ran — the promise was about the outcome.
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = fn(*args, **kwargs)
            if _enabled and not predicate(result, *args, **kwargs):
                raise ContractViolation(
                    "postcondition", getattr(fn, "__qualname__", repr(fn)), message
                )
            return result

        _attach(wrapper, "postcondition", predicate, message)
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# invariant
# ---------------------------------------------------------------------------


def invariant(predicate: Callable[[Any], bool], message: str = "") -> Callable:
    """Class invariant: holds after construction and around every public call.

    Applied as a class decorator. Every public plain-function method is
    wrapped so the predicate is checked against the instance *before*
    and *after* each call, and once right after ``__init__`` finishes.
    Dunder methods, privates, and non-function attributes are untouched.
    """

    def class_decorator(cls: type) -> type:
        where = cls.__qualname__

        def check(instance: Any, when: str) -> None:
            if _enabled and not predicate(instance):
                raise ContractViolation("invariant", f"{where} ({when})", message)

        # After construction: the newborn object must already keep its promise.
        original_init = cls.__init__

        @wraps(original_init)
        def checked_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            check(self, "after __init__")

        cls.__init__ = checked_init

        for name, member in list(vars(cls).items()):
            if name.startswith("_"):
                continue
            if not isinstance(member, type(checked_init)) and not callable(member):
                continue
            # Only wrap plain functions; leave staticmethod/classmethod/
            # property descriptors exactly as the author wrote them.
            import types as _types

            if not isinstance(member, _types.FunctionType):
                continue
            if name == "__init__":
                continue

            @wraps(member)
            def checked_method(
                self: Any, *args: Any, _fn=member, _name=name, **kwargs: Any
            ) -> Any:
                check(self, f"before {where}.{_name}")
                result = _fn(self, *args, **kwargs)
                check(self, f"after {where}.{_name}")
                return result

            setattr(cls, name, checked_method)

        cls.__contract_invariant__ = (predicate, message)
        return cls

    return class_decorator


def invariant_spec(cls: type) -> Optional[Tuple[Callable, str]]:
    """The (predicate, message) invariant of a decorated class, if any."""
    return getattr(cls, "__contract_invariant__", None)


__all__ = [
    "ORIGIN",
    "ContractViolation",
    "contracts_enabled",
    "contract_specs",
    "requires",
    "ensures",
    "invariant",
    "invariant_spec",
]
