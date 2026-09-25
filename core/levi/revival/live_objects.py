"""LEVI's live object shelf — persistent objects with replaceable classes.

Studied from: revival-50-more-20260916-0009/report-part1.md [entry #3]
(OS/2 Workplace Shell + SOM).

The studied capability shape: the desktop as a *live object database* —
files, printers, programs as persistent objects whose *class
implementations are replaceable* while the objects live on. This module
is an original, from-scratch expression of that shape: an ``ObjectStore``
of persistent ``LiveObject``s, a ``ClassRegistry`` where each class's
implementation (its method table) can be *replaced at runtime* with an
optional migration that reshapes existing objects' attributes, and
explicit snapshot/restore so the object database survives as plain data.

Honest limits, stated plainly: persistence is explicit — ``snapshot()``
/ ``restore()`` move the database through plain JSON-compatible dicts
(``save``/``load`` do the file I/O you ask for, nothing hidden).
Restoring requires the classes to be re-registered first; a snapshot
records class versions so mismatches raise instead of silently
misbehaving. Method dispatch is a plain dict lookup, not a binary
component model. Local-first, stdlib-only, no network.

Original, from-scratch implementation for LEVI. Not artificial. Synthetic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

ORIGIN = "levi-revival/live-objects"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ObjectError(Exception):
    """Base class for live-object failures."""


class UnknownClass(ObjectError):
    """An operation named a class that isn't registered."""

    def __init__(self, class_name: str):
        super().__init__(f"no class registered as {class_name!r}")
        self.class_name = class_name


class DuplicateClass(ObjectError):
    """A class name was registered twice (use replace to evolve it)."""

    def __init__(self, class_name: str):
        super().__init__(f"class {class_name!r} already registered; use replace()")
        self.class_name = class_name


class UnknownObject(ObjectError):
    """An object id that isn't in the store."""

    def __init__(self, object_id: str):
        super().__init__(f"no object {object_id!r} in this store")
        self.object_id = object_id


class UnknownMethod(ObjectError):
    """Dispatch named a method the class doesn't implement."""

    def __init__(self, class_name: str, method: str):
        super().__init__(f"class {class_name!r} implements no method {method!r}")
        self.class_name = class_name
        self.method = method


class VersionMismatch(ObjectError):
    """A snapshot was restored against different class versions."""

    def __init__(self, message: str):
        super().__init__(message)


# A method implementation: (live_object, store, *args) -> anything.
Method = Callable[..., Any]
# A migration: old attrs dict -> new attrs dict, applied on class replace.
Migrate = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass
class ClassSpec:
    """A replaceable class implementation: version + method table."""

    name: str
    version: int = 1
    methods: Dict[str, Method] = field(default_factory=dict)
    doc: str = ""

    def history_note(self) -> str:
        """One line describing this implementation."""
        return f"{self.name} v{self.version}: {sorted(self.methods)}"


class ClassRegistry:
    """Where class implementations live — and get replaced, live.

    Objects keep their identity and attributes across a replace; only
    the *implementation* behind their class name changes. An optional
    migration reshapes each existing object's attributes at replace
    time; without one, attributes carry over untouched.
    """

    def __init__(self) -> None:
        self._classes: Dict[str, ClassSpec] = {}
        self._history: Dict[str, List[str]] = {}

    def register(self, spec: ClassSpec) -> ClassSpec:
        """Register a brand-new class implementation."""
        if spec.name in self._classes:
            raise DuplicateClass(spec.name)
        self._classes[spec.name] = spec
        self._history[spec.name] = [spec.history_note()]
        return spec

    def replace(
        self,
        name: str,
        spec: ClassSpec,
        migrate: Optional[Migrate] = None,
        store: Optional["ObjectStore"] = None,
    ) -> ClassSpec:
        """Replace a class's implementation while objects live on.

        The new spec's version should exceed the old one's; the old
        implementation's note stays in history. If a store is given,
        ``migrate`` (when provided) reshapes every existing object of
        that class right now — eagerly and visibly, not lazily.
        """
        old = self._classes.get(name)
        if old is None:
            raise UnknownClass(name)
        if spec.version <= old.version:
            raise ObjectError(
                f"replacement v{spec.version} must exceed current v{old.version}"
            )
        self._classes[name] = spec
        self._history[name].append(spec.history_note())
        if store is not None:
            for obj in store.query(class_name=name):
                if migrate is not None:
                    obj.attrs = migrate(dict(obj.attrs))
        return spec

    def get(self, name: str) -> ClassSpec:
        """The current implementation of a class."""
        spec = self._classes.get(name)
        if spec is None:
            raise UnknownClass(name)
        return spec

    def classes(self) -> List[str]:
        """Every registered class name."""
        return list(self._classes.keys())

    def history(self, name: str) -> List[str]:
        """Every implementation note a class has ever had."""
        if name not in self._history:
            raise UnknownClass(name)
        return list(self._history[name])


@dataclass
class LiveObject:
    """A persistent object: identity + class name + attributes.

    Behavior lives in the class registry, not in the object — so the
    class can be replaced under it and the object keeps living.
    """

    object_id: str
    class_name: str
    attrs: Dict[str, Any] = field(default_factory=dict)

    def get(self, attr: str, default: Any = None) -> Any:
        """Read an attribute."""
        return self.attrs.get(attr, default)

    def set(self, attr: str, value: Any) -> None:
        """Write an attribute."""
        self.attrs[attr] = value


class ObjectStore:
    """The live object database: create, dispatch, query, persist."""

    def __init__(self, registry: Optional[ClassRegistry] = None) -> None:
        self.registry = registry or ClassRegistry()
        self._objects: Dict[str, LiveObject] = {}
        self._next_id = 1

    # -- lifecycle -------------------------------------------------------

    def create(self, class_name: str, **attrs: Any) -> str:
        """Create a persistent object of a registered class; returns its id."""
        self.registry.get(class_name)  # raises UnknownClass early
        object_id = f"obj-{self._next_id}"
        self._next_id += 1
        self._objects[object_id] = LiveObject(object_id, class_name, dict(attrs))
        return object_id

    def get(self, object_id: str) -> LiveObject:
        """Fetch a live object by id."""
        obj = self._objects.get(object_id)
        if obj is None:
            raise UnknownObject(object_id)
        return obj

    def delete(self, object_id: str) -> None:
        """Remove an object from the database."""
        if object_id not in self._objects:
            raise UnknownObject(object_id)
        del self._objects[object_id]

    # -- behavior ----------------------------------------------------------

    def call(self, object_id: str, method: str, *args: Any) -> Any:
        """Dispatch a method through the object's *current* class.

        Because dispatch consults the registry every time, a class
        replaced after the object was created changes what this does —
        that is the whole mechanism.
        """
        obj = self.get(object_id)
        spec = self.registry.get(obj.class_name)
        impl = spec.methods.get(method)
        if impl is None:
            raise UnknownMethod(obj.class_name, method)
        return impl(obj, self, *args)

    # -- query -------------------------------------------------------------

    def query(self, class_name: Optional[str] = None, **where: Any) -> List[LiveObject]:
        """Find objects by class and/or attribute equality."""
        result = []
        for obj in self._objects.values():
            if class_name is not None and obj.class_name != class_name:
                continue
            if all(obj.attrs.get(k) == v for k, v in where.items()):
                result.append(obj)
        return result

    def count(self) -> int:
        """How many objects live in the database."""
        return len(self._objects)

    # -- persistence (explicit, never hidden) ------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """The whole database as plain data: class versions + objects."""
        return {
            "classes": {
                name: self.registry.get(name).version
                for name in self.registry.classes()
            },
            "objects": [
                {
                    "object_id": obj.object_id,
                    "class_name": obj.class_name,
                    "attrs": obj.attrs,
                }
                for obj in self._objects.values()
            ],
        }

    def restore(self, data: Dict[str, Any]) -> int:
        """Rebuild the database from a snapshot; returns object count.

        Every class in the snapshot must be registered at the recorded
        version first — mismatches raise ``VersionMismatch`` rather than
        silently misbehaving.
        """
        recorded = data.get("classes", {})
        for name, version in recorded.items():
            current = self.registry.get(name).version
            if current != version:
                raise VersionMismatch(
                    f"class {name!r}: snapshot v{version}, registry v{current}"
                )
        self._objects = {}
        for entry in data.get("objects", []):
            obj = LiveObject(entry["object_id"], entry["class_name"], entry["attrs"])
            self._objects[obj.object_id] = obj
        # Keep future ids from colliding with restored ones.
        taken = [
            int(o.object_id.split("-", 1)[1])
            for o in self._objects.values()
            if o.object_id.startswith("obj-") and o.object_id.split("-", 1)[1].isdigit()
        ]
        self._next_id = max(taken, default=0) + 1
        return len(self._objects)

    def export_json(self) -> str:
        """Snapshot serialized to a JSON string."""
        return json.dumps(self.snapshot(), sort_keys=True)

    def import_json(self, text: str) -> int:
        """Restore from a JSON string; returns object count."""
        return self.restore(json.loads(text))

    def save(self, path: str) -> None:
        """Write the snapshot to a file you name — explicit I/O."""
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.export_json())

    def load(self, path: str) -> int:
        """Restore the snapshot from a file you name — explicit I/O."""
        with open(path, encoding="utf-8") as fh:
            return self.import_json(fh.read())


# ---------------------------------------------------------------------------
# A small built-in cast, so the mechanism is demonstrable out of the box
# ---------------------------------------------------------------------------


def _printer_print_page(obj: LiveObject, store: ObjectStore, text: str) -> str:
    name = obj.get("name", "printer")
    count = obj.get("pages", 0) + 1
    obj.set("pages", count)
    return f"[{name}] page {count}: {text}"


def _note_word_count(obj: LiveObject, store: ObjectStore) -> int:
    return len(str(obj.get("text", "")).split())


def _note_preview(obj: LiveObject, store: ObjectStore, width: int = 40) -> str:
    text = str(obj.get("text", ""))
    return text if len(text) <= width else text[: width - 1] + "…"


def standard_registry() -> ClassRegistry:
    """A registry with two honest example classes: Printer and Note."""
    registry = ClassRegistry()
    registry.register(
        ClassSpec("Printer", 1, {"print_page": _printer_print_page}, "a shared printer")
    )
    registry.register(
        ClassSpec(
            "Note",
            1,
            {"word_count": _note_word_count, "preview": _note_preview},
            "a persistent note",
        )
    )
    return registry


__all__ = [
    "ORIGIN",
    "ObjectError",
    "UnknownClass",
    "DuplicateClass",
    "UnknownObject",
    "UnknownMethod",
    "VersionMismatch",
    "ClassSpec",
    "ClassRegistry",
    "LiveObject",
    "ObjectStore",
    "standard_registry",
]
