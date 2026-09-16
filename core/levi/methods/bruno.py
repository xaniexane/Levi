"""Bruno's memory wheels: rotating ring combinatorics bound to image-seeds.

History: Giordano Bruno's 16th-century mnemotechnics — concentric rings of
symbolic images, letters, and archetypal figures rotated (mentally or on
paper wheels) to generate and recall vast *combinations* of concepts: the
method of loci industrialized. Demanded years of training in a Hermetic
cosmology; modern "proto-computer-scientist" framing is romantic projection.

In LEVI: distinct from Llull (``llull``) in two ways — (1) the primitive is
the *ring*, an ordered wheel of symbols with a rotation offset, so
configurations are alignment states, not set combinations; (2) every symbol
binds a vivid image-seed, exploiting visual memory's bandwidth. A
:class:`Wheel` spins deterministic configurations (seeded RNG) so the
assistant can remember wheel positions and reproduce a deck.

Honesty: INSPIRATIONAL — the ring-rotation encoder is real and useful for
prompt-configurations; the Hermetic cosmology it sailed in is not.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field


@dataclass
class Ring:
    name: str
    symbols: list[str]
    images: dict[str, str] = field(default_factory=dict)  # symbol -> image-seed
    offset: int = 0  # current rotation

    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("ring name must be non-empty")
        if len(self.symbols) < 2:
            raise ValueError(f"ring {self.name!r} needs at least 2 symbols")
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError(f"ring {self.name!r} symbols must be distinct")
        for sym, img in self.images.items():
            if sym not in self.symbols:
                raise ValueError(
                    f"image-seed for unknown symbol {sym!r} on ring {self.name!r}"
                )

    def rotate(self, steps: int = 1) -> int:
        self.offset = (self.offset + steps) % len(self.symbols)
        return self.offset

    def current(self) -> str:
        return self.symbols[self.offset]

    def image_for(self, symbol: str | None = None) -> str:
        sym = symbol or self.current()
        return self.images.get(sym, f"a vivid image of {sym}")


class Wheel:
    """A deck of concentric rings; a spin = one alignment configuration."""

    def __init__(self, name: str, seed: int = 0):
        if not name or not name.strip():
            raise ValueError("wheel name must be non-empty")
        self.name = name.strip()
        self.rings: list[Ring] = []
        self._rng = random.Random(seed)
        self.seed = seed

    def add_ring(
        self, name: str, symbols: list[str], images: dict[str, str] | None = None
    ) -> Ring:
        ring = Ring(name.strip(), [str(s) for s in symbols], dict(images or {}))
        ring.validate()
        if any(r.name == ring.name for r in self.rings):
            raise ValueError(f"ring {ring.name!r} already on wheel {self.name!r}")
        self.rings.append(ring)
        return ring

    def configuration(self) -> dict[str, str]:
        """Current alignment: ring name -> symbol."""
        if not self.rings:
            raise ValueError("wheel has no rings")
        return {r.name: r.current() for r in self.rings}

    def configuration_with_images(self) -> dict[str, tuple[str, str]]:
        """Current alignment: ring name -> (symbol, image-seed)."""
        if not self.rings:
            raise ValueError("wheel has no rings")
        return {r.name: (r.current(), r.image_for()) for r in self.rings}

    def spin(self, steps: dict[str, int] | None = None) -> dict[str, str]:
        """Rotate rings (random steps per ring unless given) and read alignment."""
        if not self.rings:
            raise ValueError("wheel has no rings")
        for ring in self.rings:
            if steps is not None and ring.name in steps:
                ring.rotate(int(steps[ring.name]))
            else:
                ring.rotate(self._rng.randrange(len(ring.symbols)))
        return self.configuration()

    def deal(self, count: int) -> list[dict[str, str]]:
        """Deal ``count`` configurations — a prompt deck for drafting."""
        if not isinstance(count, int) or count < 1:
            raise ValueError("count must be a positive integer")
        return [self.spin() for _ in range(count)]

    def total_configurations(self) -> int:
        """Size of the full alignment space (combinatorial budget)."""
        if not self.rings:
            return 0
        total = 1
        for ring in self.rings:
            total *= len(ring.symbols)
        return total

    def render(self, config: dict[str, str] | None = None) -> str:
        cfg = config or self.configuration()
        parts = [
            f"{ring}={cfg.get(ring, '?')}" for ring in [r.name for r in self.rings]
        ]
        return f"{self.name}: " + " · ".join(parts)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "seed": self.seed,
            "rings": [asdict(r) for r in self.rings],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Wheel":
        wheel = cls(data["name"], data.get("seed", 0))
        for rd in data.get("rings", []):
            ring = Ring(
                rd["name"], rd["symbols"], rd.get("images", {}), rd.get("offset", 0)
            )
            ring.validate()
            wheel.rings.append(ring)
        return wheel
