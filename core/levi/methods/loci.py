"""Method of Loci: memory-palace builder.

History: the classical Greco-Roman art of memory — the orator mentally walks
a familiar route, depositing one vivid image per "place" (locus), then recites
by re-walking the route in order. (The Simonides-banquet origin story is
founding myth, not documented fact — see Cicero.)

In LEVI: a palace is an ordered list of rooms, each with ordered loci. Facts
are deposited at loci with vivid image-anchors; :meth:`Palace.walk` produces
the recall script ("at your front door you see…"), and
:meth:`Palace.quiz_round` runs a spaced-repetition tour. Palaces persist as
JSON under ``~/.levi/methods/``.

Honesty: LOAD-BEARING — a real mechanism (ordered spatial retrieval) that
works as well on a route list as in a head.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import _persist


@dataclass
class Locus:
    name: str
    fact: str = ""
    image: str = ""  # vivid anchor, e.g. "a flaming bicycle"

    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("locus name must be non-empty")


@dataclass
class Room:
    name: str
    loci: list[Locus] = field(default_factory=list)

    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("room name must be non-empty")


class Palace:
    """One memory palace: ordered rooms, ordered loci, facts with image anchors."""

    def __init__(self, name: str, store: str | None = None):
        if not name or not name.strip():
            raise ValueError("palace name must be non-empty")
        self.name = name.strip()
        self.rooms: list[Room] = []
        self._store = _persist.store_path(store or f"loci-{self.name}")
        self._load()

    # ---- persistence -----------------------------------------------------
    def _load(self) -> None:
        data = _persist.load_json(self._store)
        if not data:
            return
        if not isinstance(data, dict) or data.get("name") != self.name:
            raise _persist.CorruptStoreError(
                f"palace store {self._store} does not match palace {self.name!r}"
            )
        for rd in data.get("rooms", []):
            room = Room(name=rd["name"])
            for ld in rd.get("loci", []):
                room.loci.append(
                    Locus(ld["name"], ld.get("fact", ""), ld.get("image", ""))
                )
            room.validate()
            self.rooms.append(room)

    def save(self) -> None:
        _persist.save_json(
            self._store,
            {"name": self.name, "rooms": [asdict(r) for r in self.rooms]},
        )

    # ---- construction ----------------------------------------------------
    def add_room(self, room_name: str) -> Room:
        room = Room(room_name.strip())
        room.validate()
        if any(r.name == room.name for r in self.rooms):
            raise ValueError(
                f"room {room.name!r} already exists in palace {self.name!r}"
            )
        self.rooms.append(room)
        return room

    def add_locus(self, room_name: str, locus_name: str) -> Locus:
        room = self._room(room_name)
        locus = Locus(locus_name.strip())
        locus.validate()
        if any(l.name == locus.name for l in room.loci):
            raise ValueError(
                f"locus {locus.name!r} already exists in room {room.name!r}"
            )
        room.loci.append(locus)
        return locus

    def deposit(
        self, room_name: str, locus_name: str, fact: str, image: str = ""
    ) -> Locus:
        """Deposit a fact at a locus with a vivid image anchor."""
        if not fact or not fact.strip():
            raise ValueError("fact must be non-empty")
        locus = self._locus(room_name, locus_name)
        locus.fact = fact.strip()
        locus.image = image.strip()
        return locus

    def clear_locus(self, room_name: str, locus_name: str) -> None:
        """Reuse a route for a new speech-set: wipe the image, keep the place."""
        locus = self._locus(room_name, locus_name)
        locus.fact = ""
        locus.image = ""

    # ---- recall ----------------------------------------------------------
    def walk(self) -> list[str]:
        """The recall script: walk the route in order, seeing each image."""
        lines = []
        for room in self.rooms:
            lines.append(f"— {room.name} —")
            for locus in room.loci:
                anchor = locus.image or "(empty)"
                lines.append(f"  at {locus.name}: {anchor} → {locus.fact or '…'}")
        return lines

    def walk_script(self) -> str:
        return "\n".join([f"Memory palace: {self.name}", *self.walk()])

    def quiz_round(self) -> list[tuple[str, str]]:
        """Spaced-repetition tour: (prompt, expected answer) pairs in route order."""
        rounds = []
        for room in self.rooms:
            for locus in room.loci:
                if locus.fact:
                    rounds.append(
                        (
                            f"At {locus.name} ({locus.image or 'no image'}) what did you place?",
                            locus.fact,
                        )
                    )
        return rounds

    def coverage(self) -> tuple[int, int]:
        """(filled_loci, total_loci)."""
        total = sum(len(r.loci) for r in self.rooms)
        filled = sum(1 for r in self.rooms for l in r.loci if l.fact)
        return filled, total

    # ---- internals -------------------------------------------------------
    def _room(self, name: str) -> Room:
        for room in self.rooms:
            if room.name == name:
                return room
        raise KeyError(f"no room {name!r} in palace {self.name!r}")

    def _locus(self, room_name: str, locus_name: str) -> Locus:
        room = self._room(room_name)
        for locus in room.loci:
            if locus.name == locus_name:
                return locus
        raise KeyError(f"no locus {locus_name!r} in room {room.name!r}")
