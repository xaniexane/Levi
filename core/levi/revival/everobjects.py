"""LEVI's ever-objects — identities that outlive reboots.

Studied from: systems-internals survey (OS/2 Workplace Shell + SOM,
persistent-objects section).

The mechanism, functionally: objects carry a persistent identity
independent of any live process. The registry saves every object's
identity, class name, and data to a JSON store — a "reboot" (fresh
registry, load from store) brings the same identities back. Class
implementations are replaceable at runtime: swap the code behind a
class name and every object of that class re-instantiates under the new
implementation with identity and data intact. Classes can be derived
from other registered classes, so subclassing crosses the whole
registry.

Honesty: persistence is a JSON file, not an object database; "reboot"
is a new Registry loading the store. Identity survival and hot class
swaps are real within the model.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional, Type

ORIGIN = "levi-revival/everobjects"


class EverError(Exception):
    """Base failure for ever-object operations."""


class EverObject:
    """Base for persistent objects. Subclasses define the behavior."""

    def __init__(self, obj_id: str, data: Optional[Dict[str, Any]] = None):
        self.obj_id = obj_id
        self.data: Dict[str, Any] = dict(data or {})

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def describe(self) -> Dict[str, Any]:
        return {
            "id": self.obj_id,
            "class": type(self).__name__,
            "data": dict(self.data),
        }


class ClassRegistry:
    """Maps class names to implementations; swappable at runtime."""

    def __init__(self) -> None:
        self._classes: Dict[str, Type[EverObject]] = {}

    def register(self, name: str, cls: Type[EverObject]) -> None:
        if not issubclass(cls, EverObject):
            raise EverError(f"{cls.__name__} is not an EverObject")
        self._classes[name] = cls

    def swap(self, name: str, new_cls: Type[EverObject]) -> Type[EverObject]:
        """Replace the implementation behind a class name at runtime."""
        if name not in self._classes:
            raise EverError(f"unknown class {name!r}")
        if not issubclass(new_cls, EverObject):
            raise EverError(f"{new_cls.__name__} is not an EverObject")
        old = self._classes[name]
        self._classes[name] = new_cls
        return old

    def derive(
        self, new_name: str, parent_name: str, **defaults: Any
    ) -> Type[EverObject]:
        """Subclass an already-registered class across the registry."""
        if parent_name not in self._classes:
            raise EverError(f"unknown parent class {parent_name!r}")
        parent = self._classes[parent_name]

        def __init__(self, obj_id: str, data: Optional[Dict[str, Any]] = None):
            merged = dict(defaults)
            merged.update(data or {})
            parent.__init__(self, obj_id, merged)

        child = type(new_name, (parent,), {"__init__": __init__})
        self._classes[new_name] = child
        return child

    def instantiate(self, name: str, obj_id: str, data: Dict[str, Any]) -> EverObject:
        if name not in self._classes:
            raise EverError(f"unknown class {name!r}")
        return self._classes[name](obj_id, data)

    def known(self) -> List[str]:
        return sorted(self._classes)


class Registry:
    """The living registry of ever-objects; save/load gives reboot survival."""

    def __init__(self, classes: Optional[ClassRegistry] = None):
        self.classes = classes or ClassRegistry()
        self._objects: Dict[str, EverObject] = {}
        self._class_of: Dict[str, str] = {}

    def create(self, class_name: str, **data: Any) -> EverObject:
        obj_id = uuid.uuid4().hex
        obj = self.classes.instantiate(class_name, obj_id, dict(data))
        self._objects[obj_id] = obj
        self._class_of[obj_id] = class_name
        return obj

    def get(self, obj_id: str) -> EverObject:
        try:
            return self._objects[obj_id]
        except KeyError:
            raise EverError(f"no ever-object {obj_id!r}") from None

    def class_of(self, obj_id: str) -> str:
        return self._class_of[obj_id]

    def reinstantiate(self) -> None:
        """Rebuild every object under its class's CURRENT implementation."""
        for obj_id, class_name in list(self._class_of.items()):
            old = self._objects[obj_id]
            self._objects[obj_id] = self.classes.instantiate(
                class_name, obj_id, dict(old.data)
            )

    def save(self, path: str) -> None:
        payload = {
            obj_id: {"class": self._class_of[obj_id], "data": obj.data}
            for obj_id, obj in self._objects.items()
        }
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
        os.replace(tmp, path)

    def load(self, path: str) -> int:
        """Load a store into this registry — the 'reboot'. Returns count."""
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        count = 0
        for obj_id, entry in payload.items():
            obj = self.classes.instantiate(
                entry["class"], obj_id, dict(entry.get("data", {}))
            )
            self._objects[obj_id] = obj
            self._class_of[obj_id] = entry["class"]
            count += 1
        return count

    def __len__(self) -> int:
        return len(self._objects)
