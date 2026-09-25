"""LEVI's protos: objects from examples, not from classes.

Studied from: catalog (§28) — prototype cloning (functional description
only; no historical claims).

The lesson, reborn as LEVI's own: there are no classes here. You make an
object by *copying an example* and changing what's different — change by
copying, not by instantiating. Every object is a bundle of *slots*, and a
slot doesn't care whether it holds data or behavior: a number, a string,
or a little function that takes the object itself as its first argument
— state and behavior unified in one lookup. Lookup walks the
parent-prototype chain, so a whole family shares what it doesn't
override.

Honesty: LOAD-BEARING, with one stated limit. Method slots are plain
Python callables invoked with the receiver — there is no message-passing
machinery underneath, just the discipline that every behavior is a slot
and every slot is looked up the same way.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

ORIGIN = "levi-revival/protos"

_MISSING = object()  # sentinel: "no default given" for Proto.get


class Proto:
    """A prototype object: named slots, one parent link, no classes."""

    def __init__(
        self, name: str, parent: Optional["Proto"] = None, **slots: Any
    ) -> None:
        self.name = name
        self.parent = parent
        self.slots: Dict[str, Any] = dict(slots)

    # -- change by copying an example -----------------------------------------
    def clone(self, name: str, **overrides: Any) -> "Proto":
        """Copy this object; the copy shares the parent chain and starts
        with a copy of my own slots, plus any overrides."""
        child = Proto(name, parent=self, **self.slots)
        child.slots.update(overrides)
        return child

    # -- unified slots: data and behavior in one lookup -------------------------
    def get(self, slot: str, default: Any = _MISSING) -> Any:
        """Find a slot's raw value, walking the parent chain. With a
        default, missing slots return it instead of raising."""
        obj: Optional[Proto] = self
        while obj is not None:
            if slot in obj.slots:
                return obj.slots[slot]
            obj = obj.parent
        if default is not _MISSING:
            return default
        raise AttributeError(f"protos: {self.name!r} has no slot {slot!r}")

    def set(self, slot: str, value: Any) -> "Proto":
        self.slots[slot] = value
        return self

    def call(self, slot: str, *args: Any) -> Any:
        """Invoke a behavior slot: the callable receives this object first."""
        fn = self.get(slot)
        if not callable(fn):
            raise TypeError(
                f"protos: slot {slot!r} of {self.name!r} is data, not behavior"
            )
        return fn(self, *args)

    def chain(self) -> Iterator["Proto"]:
        """The parent-prototype chain, self first."""
        obj: Optional[Proto] = self
        while obj is not None:
            yield obj
            obj = obj.parent

    def lineage(self) -> List[str]:
        return [o.name for o in self.chain()]

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Proto({self.name!r})"


# ---------------------------------------------------------------------------
# Demo — a small live world: creatures cloned from examples
# ---------------------------------------------------------------------------


def demo_world() -> Dict[str, Proto]:
    # the primal example: a generic critter
    critter = Proto(
        "critter",
        kind="critter",
        legs=4,
        energy=10,
        describe=lambda self: f"a {self.get('kind')} with {self.get('legs')} legs",
        # behavior slots: callables taking the object
        eat=lambda self, food: self.set(
            "energy", self.get("energy") + food.get("nutrition", 1)
        ),
        tired=lambda self: self.get("energy") <= 0,
    )

    berry = Proto("berry", kind="food", nutrition=3)

    # change by copying: a fox is a critter that hunts
    fox = critter.clone(
        "fox",
        kind="fox",
        hunt=lambda self, prey: (
            self.set("energy", self.get("energy") + 5),
            f"{self.get('kind')} caught the {prey.get('kind')}",
        )[1],
    )

    # and a cub is a fox that's small and clumsy — cloned from the fox
    cub = fox.clone("cub", kind="fox cub", legs=4, energy=4)

    return {"critter": critter, "berry": berry, "fox": fox, "cub": cub}


def demo() -> List[str]:
    w = demo_world()
    out = [
        w["cub"].call("describe"),  # inherited behavior
        f"cub lineage: {' -> '.join(w['cub'].lineage())}",
        w["fox"].call("hunt", w["critter"]),  # fox's own slot
        f"fox energy: {w['fox'].get('energy')}",
    ]
    w["cub"].call("eat", w["berry"])  # inherited, mutates cub
    out.append(f"cub energy after berry: {w['cub'].get('energy')}")
    out.append(f"critter energy untouched: {w['critter'].get('energy')}")
    return out


if __name__ == "__main__":  # pragma: no cover - demo
    print("\n".join(demo()))
